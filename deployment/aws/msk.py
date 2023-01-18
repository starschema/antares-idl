import json
import glob
import shutil
import os
import tempfile
import pulumi
import pulumi_aws as aws
import pulumi_random as random
import urllib.request as request
from antares_common.resources import resources
from antares_common.config import config
from antares_common import str2bool, read_text_file


def deploy_msk():
    """Deploy the MSK cluster."""
    snowflake_stack_ref = pulumi.StackReference(
        f"{config.org}/antares-idl-snowflake/{config.stack}"
    )

    vpc_id = config.get("/msk/vpc/id")
    kafka_version = config.get("/msk/kafka-version")
    subnets = config.get("/msk/subnets")
    instance_type = config.get("/msk/kafka-instance-type")
    use_tls_auth = config.get("/msk/use-tls-auth")

    private_ca_arn = config.get("/msk/private-ca-arn")
    kafka_username = config.get("/msk/kafka-username")
    kafka_password = random.RandomPassword("password", length=16, special=True)

    aws_security_group = deploy_security_group(vpc_id)

    client_authentication = create_client_auth_obj(use_tls_auth, private_ca_arn)

    antares_bucket = aws.s3.BucketV2(
        "antares-bucket",
        force_destroy=config.get("/msk/s3/force-destroy-bucket", False),
    )

    # aws.s3.BucketLifecycleConfigurationV2(
    #     "antares-bucket-storage-transitions",
    #     bucket=antares_bucket.id,
    #     rules=[
    #         aws.s3.BucketLifecycleConfigurationV2RuleArgs(
    #             id="rule-1",
    #             filter=aws.s3.BucketLifecycleConfigurationV2RuleFilterArgs(
    #                 prefix="logs/"
    #             ),
    #             status="Enabled",
    #             transitions=[
    #                 aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
    #                     days=1, storage_class="STANDARD_IA"
    #                 ),
    #                 aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
    #                     days=15, storage_class="GLACIER_IR"
    #                 ),
    #                 aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
    #                     days=60, storage_class="DEEP_ARCHIVE"
    #                 ),
    #             ],
    #         )
    #     ],
    # )

    antares_kafka_cluster = deploy_msk_cluster(
        kafka_version,
        subnets,
        instance_type,
        aws_security_group,
        client_authentication,
        antares_bucket,
    )

    antares_secret, antares_key = deploy_username_password_auth(
        kafka_username, kafka_password, antares_kafka_cluster
    )

    admin_lambda = deploy_admin_lambda(
        antares_kafka_cluster, aws_security_group, antares_secret, antares_key
    )

    create_topics_invocation = create_topics(
        admin_lambda, antares_kafka_cluster, antares_secret
    )
    # print(create_topics_invocation)

    deploy_kafka_connector(
        snowflake_stack_ref,
        antares_kafka_cluster,
        aws_security_group,
        antares_bucket,
        create_topics_invocation,
    )

    exports(use_tls_auth, antares_kafka_cluster, kafka_username, kafka_password)


def create_topics(admin_lambda, antares_kafka_cluster, antares_secret):
    def create_invocation(args):
        payload = {
            "operation": "create_topic",
            "bootstrap_servers": args[0],
            "authentication-secret-name": args[1],
            "topics": config["/msk/topics"][:],
            "send_test_message": True,
        }

        return json.dumps(payload)

    payload = pulumi.Output.all(
        antares_kafka_cluster.bootstrap_brokers_sasl_scram, antares_secret.name
    ).apply(create_invocation)

    return aws.lambda_.Invocation(
        "antares-create-topics",
        function_name=admin_lambda.name,
        input=payload,
        opts=pulumi.ResourceOptions(depends_on=[admin_lambda, antares_kafka_cluster]),
    )


def create_service_execution_role(
    role_resorce_id,
    permission_resource_id,
    assume_role_policy_file,
    permission_policy_file,
    replacements: pulumi.Output[dict],
):
    assume_role_policy = read_text_file(assume_role_policy_file)
    permissions_policy = read_text_file(permission_policy_file)

    def replace_keys(replacements):
        new_permissions_policy = permissions_policy
        for key, value in replacements.items():
            new_permissions_policy = new_permissions_policy.replace(key, value)
        return new_permissions_policy

    return aws.iam.Role(
        role_resorce_id,
        assume_role_policy=assume_role_policy,
        inline_policies=[
            aws.iam.RoleInlinePolicyArgs(
                name=permission_resource_id,
                policy=replacements.apply(replace_keys),
            )
        ],
    )


def deploy_admin_lambda(cluster, aws_security_group, secret, key):
    def create_role(args):
        region = aws.get_region()
        caller_identity = aws.get_caller_identity()
        replacements = {
            "$$region$$": region.name,
            "$$account-id$$": caller_identity.account_id,
            "$$cluster-arn$$": args[0],
            "$$cluster-name$$": args[1],
            "$$cluster-uuid$$": args[0].split("/")[-1],
            "$$secret-arn$$": args[2],
            "$$kms-key-arn$$": args[3],
        }

        return replacements

    replacements = pulumi.Output.all(
        cluster.arn, cluster.cluster_name, secret.arn, key.arn
    ).apply(create_role)

    iam_role = create_service_execution_role(
        "antares-lambda-kafka-admin-role",
        "antares-lambda-kafka-admin-policy",
        "msk_resources/msk_admin_lambda_trusted_entities.json",
        "msk_resources/msk_admin_lambda_permission_policy.json",
        replacements,
    )

    shutil.rmtree("kafka_admin_lambda", ignore_errors=True)
    os.mkdir("kafka_admin_lambda")
    shutil.unpack_archive(
        "msk_resources/kafka_admin_deps.zip", "kafka_admin_lambda", "zip"
    )
    shutil.copy("kafka_admin.py", "kafka_admin_lambda")
    shutil.make_archive("kafka_admin_lambda", "zip", "kafka_admin_lambda")

    admin_lambda_log_group = aws.cloudwatch.LogGroup(
        "antares-kafka-admin-lambda-log-group", retention_in_days=14
    )
    admin_lambda = aws.lambda_.Function(
        "antares-kafka-admin-lambda",
        role=iam_role.arn,
        handler="kafka_admin.lambda_handler",
        runtime="python3.8",
        code=pulumi.FileArchive("kafka_admin_lambda.zip"),
        timeout=60,
        memory_size=128,
        vpc_config=aws.lambda_.FunctionVpcConfigArgs(
            subnet_ids=config["/msk/subnets"][:],
            # vpc_id=config["/msk/vpc/id"][:],
            security_group_ids=[aws_security_group.id],
        ),
        opts=pulumi.ResourceOptions(
            depends_on=[
                admin_lambda_log_group,
                iam_role,
            ]
        ),
    )
    return admin_lambda


def exports(use_tls_auth, antares_kafka_cluster, kafka_username, kafka_password):
    """Export the Kafka cluster connection strings."""
    pulumi.export(
        "zookeeperConnectString", antares_kafka_cluster.zookeeper_connect_string
    )
    pulumi.export("bootstrapBrokersTls", antares_kafka_cluster.bootstrap_brokers_tls)
    pulumi.export(
        "bootstrapBrokersSaslScram", antares_kafka_cluster.bootstrap_brokers_sasl_scram
    )
    pulumi.export(
        "bootstrapBrokersSaslIam", antares_kafka_cluster.bootstrap_brokers_sasl_iam
    )
    pulumi.export(
        "bootstrapBrokers",
        antares_kafka_cluster.bootstrap_brokers_tls
        if use_tls_auth
        else antares_kafka_cluster.bootstrap_brokers_sasl_scram,
    )
    pulumi.export("kafkaUsername", kafka_username)
    pulumi.export("kafkaPassword", kafka_password.result)


def deploy_msk_cluster(
    kafka_version,
    subnets,
    instance_type,
    aws_security_group,
    client_authentication,
    antares_bucket,
):
    server_props = read_text_file("msk_resources/server.properties")

    antares_kafka_cluster_conf = aws.msk.Configuration(
        "antares-kafka-configuration",
        kafka_versions=[kafka_version],
        server_properties=server_props,
    )

    """Deploy the MSK cluster."""
    antares_kafka_cluster = aws.msk.Cluster(
        "antares-kafka",
        kafka_version=kafka_version,
        number_of_broker_nodes=3,
        configuration_info=aws.msk.ClusterConfigurationInfoArgs(
            arn=antares_kafka_cluster_conf.arn,
            revision=antares_kafka_cluster_conf.latest_revision,
        ),
        broker_node_group_info=aws.msk.ClusterBrokerNodeGroupInfoArgs(
            instance_type=instance_type,
            client_subnets=subnets,
            security_groups=[aws_security_group.id],
            storage_info=aws.msk.ClusterBrokerNodeGroupInfoStorageInfoArgs(
                ebs_storage_info=aws.msk.ClusterBrokerNodeGroupInfoStorageInfoEbsStorageInfoArgs(
                    volume_size=50,
                ),
            ),
        ),
        logging_info=aws.msk.ClusterLoggingInfoArgs(
            broker_logs=aws.msk.ClusterLoggingInfoBrokerLogsArgs(
                s3=aws.msk.ClusterLoggingInfoBrokerLogsS3Args(
                    enabled=True,
                    bucket=antares_bucket.id,
                    prefix="logs/msk-broker/",
                )
            )
        ),
        client_authentication=client_authentication,
        tags={
            "Name": "antares-kafka",
        },
        opts=pulumi.ResourceOptions(
            custom_timeouts=pulumi.CustomTimeouts(create="60m")
        ),
    )

    return antares_kafka_cluster


def create_client_auth_obj(use_tls_auth, private_ca_arn):
    """Create the client authentication object."""
    if use_tls_auth:
        tls = aws.msk.ClusterClientAuthenticationTlsArgs(
            certificate_authority_arns=[private_ca_arn]
        )
    else:
        tls = None

    client_authentication = aws.msk.ClusterClientAuthenticationArgs(
        tls=tls, sasl=aws.msk.ClusterClientAuthenticationSaslArgs(scram=True, iam=True)
    )

    return client_authentication


def deploy_security_group(vpc_id):
    """Deploy the security group for the MSK cluster."""
    if config.get("/msk/vpc/cidr-block"):
        cidr_block = config.get("/msk/vpc/cidr-block")
    else:
        cidr_block = aws.ec2.get_vpc_output(id=vpc_id).apply(lambda vpc: vpc.cidr_block)

    aws_security_group = aws.ec2.SecurityGroup(
        "antares-kafka-sg",
        description="Allow Kafka inbound traffic from the VPC",
        vpc_id=vpc_id,
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                description="Zookeeper connection from VPC",
                from_port=2181,
                to_port=2182,
                protocol="tcp",
                cidr_blocks=[cidr_block],
                # ipv6_cidr_blocks=[aws_vpc.ipv6_cidr_block],
            ),
            aws.ec2.SecurityGroupIngressArgs(
                description="Kafka connection from VPC",
                from_port=9092,
                to_port=9098,
                protocol="tcp",
                cidr_blocks=[cidr_block],
                # ipv6_cidr_blocks=[aws_vpc.ipv6_cidr_block],
            ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                from_port=0,
                to_port=0,
                protocol="-1",
                cidr_blocks=["0.0.0.0/0"],
                ipv6_cidr_blocks=["::/0"],
            )
        ],
        tags={
            "Name": "antares-kafka-sg",
        },
    )

    return aws_security_group


def deploy_username_password_auth(
    kafka_username, kafka_password, antares_kafka_cluster
):
    """Deploy the username and password authentication."""

    antarest_key = aws.kms.Key(
        "AmazonMSK_antares-key",
        description="Key MSK Cluster Scram Secret Association",
    )
    antares_secret = aws.secretsmanager.Secret(
        "AmazonMSK_antares-secret", kms_key_id=antarest_key.key_id
    )
    aws.secretsmanager.SecretVersion(
        "AmazonMSK_antares_secret_1",
        secret_id=antares_secret.id,
        secret_string=kafka_password.result.apply(
            lambda pw: json.dumps({"username": kafka_username, "password": pw})
        ),
    )

    aws.msk.ScramSecretAssociation(
        "AmazonMSK_antares-secret-association",
        cluster_arn=antares_kafka_cluster.arn,
        secret_arn_lists=[antares_secret.arn],
        # opts=pulumi.ResourceOptions(depends_on=[antares_secret_version]),
    )

    aws.secretsmanager.SecretPolicy(
        "AmazonMSK_antares-secret-policy",
        secret_arn=antares_secret.arn,
        policy=antares_secret.arn.apply(
            lambda arn: f"""{{
            "Version" : "2012-10-17",
            "Statement" : [ {{
                "Sid": "AWSKafkaResourcePolicy",
                "Effect" : "Allow",
                "Principal" : {{
                    "Service" : ["kafka.amazonaws.com", "lambda.amazonaws.com"]
                }},
                "Action" : "secretsmanager:getSecretValue",
                "Resource" : "{arn}"
            }} ]
        }}
        """
        ),
    )
    return antares_secret, antarest_key


def deploy_kafka_connector(
    snowflake_stack_ref, cluster, security_group, antares_bucket, lambda_invocation
):
    """Deploy the Kafka Snowflake plugin and connector."""
    drivers = sorted(
        glob.glob("*kafka-connector*.zip") + glob.glob("*kafka-connector*.jar")
    )
    if len(drivers) == 0:
        url = config["/msk/default-snowflake-kafka-connector"][:]
        driver = config["/msk/default-snowflake-kafka-connector"][:].split("/")[-1]
        print(f"No driver found, downloading from {url}")
        request.urlretrieve(url, driver)

    else:
        driver = drivers[-1]

    antares_jar_file = aws.s3.BucketObjectv2(
        "antares-kafka-connector-jar-file",
        bucket=antares_bucket.id,
        key=driver,
        source=pulumi.FileAsset(driver),
    )

    kafka_snowflake_connector_plugin = aws.mskconnect.CustomPlugin(
        "antares-snowflake-connector-plugin",
        content_type="ZIP",
        location=aws.mskconnect.CustomPluginLocationArgs(
            s3=aws.mskconnect.CustomPluginLocationS3Args(
                bucket_arn=antares_bucket.arn,
                file_key=antares_jar_file.key,
            ),
        ),
    )

    connector_config = dict(config.get("/msk/connector-config"))
    connector_config["snowflake.url.name"] = snowflake_stack_ref.get_output(
        "snowflake-url"
    )
    connector_config["snowflake.user.name"] = snowflake_stack_ref.get_output("username")
    connector_config["snowflake.schema.name"] = snowflake_stack_ref.get_output(
        "antares-schema"
    )
    connector_config["snowflake.database.name"] = snowflake_stack_ref.get_output(
        "antares-database"
    )
    connector_config["snowflake.private.key"] = snowflake_stack_ref.get_output(
        "private-key-no-headers"
    )

    def create_role(args):
        region = aws.get_region()
        caller_identity = aws.get_caller_identity()
        replacements = {
            "$$region$$": region.name,
            "$$account-id$$": caller_identity.account_id,
            "$$cluster-arn$$": args[0],
            "$$cluster-name$$": args[1],
            "$$bucket-arn$$": args[2],
            "$$cluster-uuid$$": args[0].split("/")[-1],
        }
        return replacements

    replacements = pulumi.Output.all(
        cluster.arn, cluster.cluster_name, antares_bucket.arn
    ).apply(create_role)

    iam_role = create_service_execution_role(
        "antares-kafka-connect-role",
        "antares-kafka-client-policy",
        "msk_resources/msk_connect_trusted_entities.json",
        "msk_resources/msk_connect_permission_policy.json",
        replacements,
    )

    topics = config["/msk/topics"][:]
    connector_config["topics"] = ",".join(map(lambda t: t["name"], topics))
    connector_config["snowflake.topic2table.map"] = ",".join(
        map(lambda topic: f"{topic['name']}:{topic['name']}", topics)
    )
    # print("topics", connector_config["topics"])
    # print("snowflake.topic2table.map", connector_config["snowflake.topic2table.map"])

    connector = aws.mskconnect.Connector(
        "antares-connector",
        kafkaconnect_version="2.7.1",
        capacity=aws.mskconnect.ConnectorCapacityArgs(
            autoscaling=aws.mskconnect.ConnectorCapacityAutoscalingArgs(
                mcu_count=1,
                min_worker_count=1,
                max_worker_count=8,
                scale_in_policy=aws.mskconnect.ConnectorCapacityAutoscalingScaleInPolicyArgs(
                    cpu_utilization_percentage=20,
                ),
                scale_out_policy=aws.mskconnect.ConnectorCapacityAutoscalingScaleOutPolicyArgs(
                    cpu_utilization_percentage=80,
                ),
            ),
        ),
        connector_configuration=connector_config,
        kafka_cluster=aws.mskconnect.ConnectorKafkaClusterArgs(
            apache_kafka_cluster=aws.mskconnect.ConnectorKafkaClusterApacheKafkaClusterArgs(
                bootstrap_servers=cluster.bootstrap_brokers_sasl_iam,
                vpc=aws.mskconnect.ConnectorKafkaClusterApacheKafkaClusterVpcArgs(
                    security_groups=[security_group.id],
                    subnets=config["/msk/subnets"][:],
                ),
            ),
        ),
        kafka_cluster_client_authentication=aws.mskconnect.ConnectorKafkaClusterClientAuthenticationArgs(
            authentication_type="IAM",
        ),
        kafka_cluster_encryption_in_transit=aws.mskconnect.ConnectorKafkaClusterEncryptionInTransitArgs(
            encryption_type="TLS",
        ),
        plugins=[
            aws.mskconnect.ConnectorPluginArgs(
                custom_plugin=aws.mskconnect.ConnectorPluginCustomPluginArgs(
                    arn=kafka_snowflake_connector_plugin.arn,
                    revision=kafka_snowflake_connector_plugin.latest_revision,
                ),
            )
        ],
        service_execution_role_arn=iam_role.arn,
        log_delivery=aws.mskconnect.ConnectorLogDeliveryArgs(
            worker_log_delivery=aws.mskconnect.ConnectorLogDeliveryWorkerLogDeliveryArgs(
                s3=aws.mskconnect.ConnectorLogDeliveryWorkerLogDeliveryS3Args(
                    bucket=antares_bucket.bucket,
                    prefix="logs/msk-snowflake-connector/",
                    enabled=True,
                )
            )
        ),
        opts=pulumi.ResourceOptions(
            custom_timeouts=pulumi.CustomTimeouts(create="60m"),
            depends_on=[
                lambda_invocation,
            ],
        ),
    )
    return connector
