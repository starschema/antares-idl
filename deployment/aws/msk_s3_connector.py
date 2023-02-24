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


def deploy_msk_s3_connector(cluster, security_group, antares_bucket):
    antares_landing_bucket = aws.s3.BucketV2(
        "antares-msk-s3-landing-bucket",
        force_destroy=config.get("/msk/s3/force-destroy-bucket", False),
    )

    """Deploy the Kafka S3 plugin and connector."""
    drivers = sorted(
        glob.glob("*kafka-connect-s3*.zip") + glob.glob("*kafka-connect-s3*.jar")
    )
    if len(drivers) == 0:
        url = config["/msk/default-s3-kafka-connector"][:]
        driver = config["/msk/default-s3-kafka-connector"][:].split("/")[-1]
        print(f"No driver found, downloading from {url}")
        request.urlretrieve(url, driver)

    else:
        driver = drivers[-1]

    antares_jar_file = aws.s3.BucketObjectv2(
        "antares-msk-s3-connector-jar-file",
        bucket=antares_bucket.id,
        key=driver,
        source=pulumi.FileAsset(driver),
    )

    kafka_s3_connector_plugin = aws.mskconnect.CustomPlugin(
        "antares-msk-s3-connector-plugin",
        content_type="ZIP",
        location=aws.mskconnect.CustomPluginLocationArgs(
            s3=aws.mskconnect.CustomPluginLocationS3Args(
                bucket_arn=antares_bucket.arn,
                file_key=antares_jar_file.key,
            ),
        ),
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
            "$$landing-bucket-arn$$": args[3],
        }
        return replacements

    replacements = pulumi.Output.all(
        cluster.arn,
        cluster.cluster_name,
        antares_bucket.arn,
        antares_landing_bucket.arn,
    ).apply(create_role)

    iam_role = create_service_execution_role(
        "antares-msk-s3-connect-role",
        "antares-msk-s3-client-policy",
        "msk_resources/msk_connect_trusted_entities.json",
        "msk_resources/msk_connect_s3_permission_policy.json",
        replacements,
    )

    topics = config["/msk/topics"][:]
    connector_config = dict(config.get("/msk/s3-connector/connector-config"))
    connector_config["topics"] = ",".join(map(lambda t: t["name"], topics))
    connector_config["s3.bucket.name"] = antares_landing_bucket.bucket

    connector = aws.mskconnect.Connector(
        "antares-msk-s3-connector",
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
                    arn=kafka_s3_connector_plugin.arn,
                    revision=kafka_s3_connector_plugin.latest_revision,
                ),
            )
        ],
        service_execution_role_arn=iam_role.arn,
        log_delivery=aws.mskconnect.ConnectorLogDeliveryArgs(
            worker_log_delivery=aws.mskconnect.ConnectorLogDeliveryWorkerLogDeliveryArgs(
                s3=aws.mskconnect.ConnectorLogDeliveryWorkerLogDeliveryS3Args(
                    bucket=antares_bucket.bucket,
                    prefix="logs/msk-s3-connector/",
                    enabled=True,
                )
            )
        ),
        opts=pulumi.ResourceOptions(
            custom_timeouts=pulumi.CustomTimeouts(create="60m"),
        ),
    )
    return connector
