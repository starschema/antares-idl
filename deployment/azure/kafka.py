"""
MIT License

Copyright (c) 2022 HCLTech

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import json
import re
import pulumi
import pulumi_azure_native as azure_native
import pulumi_azure_native.hdinsight as hdinsight
from antares_common.config import config
import pulumi_random as random
import pulumi_tls as tls
import pulumi_azuread as azuread
import pulumi_command as command

from antares_common.resources import resources


def deploy():
    stack_no_special = re.sub("[^a-zA-Z0-9]", "", config["stack"][:])
    stack_underscore = re.sub("[^a-zA-Z0-9]", "_", config["stack"][:])
    rest_username = config.get("/kafka/rest-auth/username", "KafkaUser")
    rest_password = random.RandomPassword(
        "antares-kafka-rest-password", length=16, special=True
    )
    ssh_password = random.RandomPassword(
        "antares-kafka-ssh-password", length=16, special=True
    )
    dummy_user_password = random.RandomPassword(
        "antares-kafka-dummy-password", length=16, special=True
    )
    kafka_version = config.get("/kafka/kafka-version")

    current_user = azure_native.authorization.get_client_config()

    # Workaround solution for https://github.com/hashicorp/terraform-provider-azuread/issues/624 and https://github.com/pulumi/pulumi-azuread/issues/289
    # Implementing workaround based on https://github.com/hashicorp/terraform-provider-azuread/issues/624#issuecomment-940984433 using a dummy user owner

    # dummy_user = azuread.User(
    #     "antares-kafka-dummy-user",
    #     display_name=f"antares-kafka-dummy-user-{config['stack'][:]}",
    #     user_principal_name=f"antares_kafka_dummy_user_{stack_no_special}@antares.com",
    #     password=dummy_user_password.result,
    # )

    # ad_group = azuread.Group(
    #     "antares-kafka-ad-group",
    #     security_enabled=True,
    #     owners=[
    #         current_user.object_id,
    #         dummy_user.object_id.apply(lambda id: id),
    #     ],
    #     display_name=f"antares-kafka-ad-group-{config['stack']}",
    # )

    # Workaround solution for https://github.com/hashicorp/terraform-provider-azuread/issues/624 and https://github.com/pulumi/pulumi-azuread/issues/289
    # Implementing workaround based on https://github.com/pulumi/pulumi-azuread/issues/289#issuecomment-1179211292

    # ad_group_display_name = "antares-kafka-ad-group-" + config["stack"][:]
    # ad_group_cmd = command.local.Command(
    #     resource_name="antares-kafka-ad-group",
    #     create=f"az ad group create --display-name {ad_group_display_name} --mail-nickname {ad_group_display_name}",
    #     delete=f"az ad group delete --group {ad_group_display_name}",
    # )

    # # ad_group = ad_group_cmd.stdout.apply(lambda stdout: json.loads(stdout))

    storage_account = azure_native.storage.StorageAccount(
        "atares-kafka-storage-account",
        account_name=f"antares{stack_no_special}",
        allow_blob_public_access=False,
        allow_shared_key_access=True,
        encryption=azure_native.storage.EncryptionArgs(
            key_source="Microsoft.Storage",
            require_infrastructure_encryption=False,
            services={
                "blob": azure_native.storage.EncryptionServiceArgs(
                    enabled=True,
                    key_type="Account",
                ),
            },
        ),
        key_policy=azure_native.storage.KeyPolicyArgs(
            key_expiration_period_in_days=30,
        ),
        kind="Storage",
        location=config["/storage/location"][:],
        minimum_tls_version="TLS1_2",
        resource_group_name=resources["resource-group"].name,
        # routing_preference=azure_native.storage.RoutingPreferenceArgs(
        #     publish_internet_endpoints=False,
        #     publish_microsoft_endpoints=True,
        #     routing_choice="MicrosoftRouting",
        # ),
        sas_policy=azure_native.storage.SasPolicyArgs(
            expiration_action="Log",
            sas_expiration_period="1.15:59:59",
        ),
        sku=azure_native.storage.SkuArgs(
            name="Standard_GRS",
        ),
    )

    cluster = azure_native.hdinsight.Cluster(
        "antares-kafka-cluster",
        cluster_name="antares-kafka-cluster",
        properties=hdinsight.ClusterCreatePropertiesArgs(
            cluster_definition=azure_native.hdinsight.ClusterDefinitionArgs(
                component_version={
                    "Kafka": kafka_version,  # static version, this is the only version that works with HDInsights ver 5.0
                },
                configurations={
                    "gateway": {
                        "restAuthCredential.isEnabled": True,
                        "restAuthCredential.password": rest_password.result,
                        "restAuthCredential.username": rest_username,
                    },
                },
                kind="kafka",
            ),
            cluster_version="5.0",  # static version
            compute_profile={
                "roles": [
                    {
                        "hardwareProfile": azure_native.hdinsight.HardwareProfileArgs(
                            vm_size=config["/kafka/headnode/size"][:],
                        ),
                        "name": "headnode",
                        "osProfile": {
                            "linuxOperatingSystemProfile": azure_native.hdinsight.LinuxOperatingSystemProfileArgs(
                                password=ssh_password.result,
                                username="sshuser",
                            ),
                        },
                        "targetInstanceCount": config["/kafka/headnode/instances"][:],
                    },
                    {
                        "dataDisksGroups": [
                            azure_native.hdinsight.DataDisksGroupsArgs(
                                disks_per_node=1,
                            )
                        ],
                        "hardwareProfile": azure_native.hdinsight.HardwareProfileArgs(
                            vm_size=config["/kafka/workernode/size"][:],
                        ),
                        "name": "workernode",
                        "osProfile": {
                            "linuxOperatingSystemProfile": azure_native.hdinsight.LinuxOperatingSystemProfileArgs(
                                password=ssh_password.result,
                                username="sshuser",
                            ),
                        },
                        "targetInstanceCount": config["/kafka/workernode/instances"][:],
                    },
                    {
                        "hardwareProfile": azure_native.hdinsight.HardwareProfileArgs(
                            vm_size=config["/kafka/zookeepernode/size"][:],
                        ),
                        "name": "zookeepernode",
                        "osProfile": {
                            "linuxOperatingSystemProfile": azure_native.hdinsight.LinuxOperatingSystemProfileArgs(
                                password=ssh_password.result,
                                username="sshuser",
                            ),
                        },
                        "targetInstanceCount": config["/kafka/zookeepernode/instances"][
                            :
                        ],
                    },
                    {
                        "hardwareProfile": azure_native.hdinsight.HardwareProfileArgs(
                            vm_size=config["/kafka/managementnode/size"][:],
                        ),
                        "name": "kafkamanagementnode",
                        "osProfile": {
                            "linuxOperatingSystemProfile": azure_native.hdinsight.LinuxOperatingSystemProfileArgs(
                                password=ssh_password.result,
                                username="kafkauser",
                            ),
                        },
                        "targetInstanceCount": config[
                            "/kafka/managementnode/instances"
                        ][:],
                    },
                ],
            },
            # kafka_rest_properties={
            #     "clientGroupInfo": azure_native.hdinsight.ClientGroupInfoArgs(
            #         group_id=ad_group.id,
            #         group_name="Kafka security group name",
            #     ),
            # },
            os_type=azure_native.hdinsight.OSType.LINUX,
            storage_profile={
                "storageaccounts": [
                    azure_native.hdinsight.StorageAccountArgs(
                        container="antares-kafka-container",
                        is_default=True,
                        key="antares-kafka-storagekey",
                        name=storage_account.name,
                    )
                ],
            },
            tier=azure_native.hdinsight.Tier.STANDARD,
        ),
        resource_group_name=resources["resource-group"].name,
    )

    export(rest_username, rest_password)


def export(rest_username, rest_password):
    pulumi.export("kafkaRestUsername", rest_username)
    pulumi.export("kafkaRestPassword", rest_password.result)
