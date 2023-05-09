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
from msk import create_service_execution_role


def deploy_msk_snowflake_connector(
    cluster, security_group, antares_bucket, snowflake_stack_ref
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
        "antares-msk-snowflake-connector-jar-file",
        bucket=antares_bucket.id,
        key=driver,
        source=pulumi.FileAsset(driver),
    )

    kafka_snowflake_connector_plugin = aws.mskconnect.CustomPlugin(
        "antares-msk-snowflake-connector-plugin",
        content_type="ZIP",
        location=aws.mskconnect.CustomPluginLocationArgs(
            s3=aws.mskconnect.CustomPluginLocationS3Args(
                bucket_arn=antares_bucket.arn,
                file_key=antares_jar_file.key,
            ),
        ),
    )

    connector_config = dict(config.get("/msk/snowflake-connector/connector-config"))
    connector_config["snowflake.url.name"] = snowflake_stack_ref.get_output(
        "snowflake-url"
    )
    connector_config["snowflake.user.name"] = snowflake_stack_ref.get_output(
        "username-kafka"
    )
    connector_config["snowflake.schema.name"] = snowflake_stack_ref.get_output(
        "antares-schema-kafka"
    )
    connector_config["snowflake.database.name"] = snowflake_stack_ref.get_output(
        "antares-database"
    )
    connector_config["snowflake.private.key"] = snowflake_stack_ref.get_output(
        "private-key-no-headers-kafka"
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
        "antares-msk-snowflake-connect-role",
        "antares-msk-snowflake-client-policy",
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
        "antares-msk-snowflake-connector",
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
        ),
    )
    return connector
