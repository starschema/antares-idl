import pulumi
import pulumi_aws as aws
import json
from antares_common.resources import resources
from antares_common.config import config
from antares_common import str2bool
import glob



def deploy_msk():
    config = pulumi.Config()
    config = config.require_object("msk")

    vpc_id = config.get("vpc-id")
    kafka_version = config.get("kafka-version")
    subnets = config.get("subnets")
    instance_type = config.get("kafka-instance-type")
    use_tls_auth = str2bool(config.get("use-tls-auth"))

    private_ca_arn = config.get("private-ca-arn")
    kafka_username = config.get("kafka-username")
    kafka_password = pulumi.Output.secret(config.get("kafka-password"))

    aws_security_group = deploy_security_group(vpc_id)

    client_authentication = create_client_auth_obj(use_tls_auth, private_ca_arn)

    antares_kafka_cluster = deploy_msk_cluster(kafka_version, subnets, instance_type, aws_security_group, client_authentication)

    deploy_username_password_auth(kafka_username, kafka_password, antares_kafka_cluster)

    kafka_snowflake_connector_plugin = deploy_kafka_connector()

    exports(use_tls_auth, antares_kafka_cluster)


def exports(use_tls_auth, antares_kafka_cluster):
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

def deploy_msk_cluster(kafka_version, subnets, instance_type, aws_security_group, client_authentication):
    antares_kafka_cluster = aws.msk.Cluster(
        "antares-kafka",
        kafka_version=kafka_version,
        number_of_broker_nodes=3,
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
        client_authentication=client_authentication,
        tags={
            "Name": "antares-kafka",
        },
    )
    
    return antares_kafka_cluster

def create_client_auth_obj(use_tls_auth, private_ca_arn):
    if use_tls_auth:
        tls=aws.msk.ClusterClientAuthenticationTlsArgs(
                certificate_authority_arns=[private_ca_arn]
            )
    else:
        tls=None

    client_authentication = aws.msk.ClusterClientAuthenticationArgs(
        tls=tls,
        sasl=aws.msk.ClusterClientAuthenticationSaslArgs(
            scram=True,
            iam=True
    ))

    return client_authentication

def deploy_security_group(vpc_id):
    aws_vpc = aws.ec2.get_vpc_output(id=vpc_id)

    aws_security_group = aws.ec2.SecurityGroup(
        "antares-kafka-sg",
        description="Allow Kafka inbound traffic from the VPC",
        vpc_id=aws_vpc.id,
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                description="Zookeeper connection from VPC",
                from_port=2181,
                to_port=2182,
                protocol="tcp",
                cidr_blocks=[aws_vpc.cidr_block],
                # ipv6_cidr_blocks=[aws_vpc.ipv6_cidr_block],
            ),
            aws.ec2.SecurityGroupIngressArgs(
                description="Kafka connection from VPC",
                from_port=9092,
                to_port=9098,
                protocol="tcp",
                cidr_blocks=[aws_vpc.cidr_block],
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

def deploy_username_password_auth(kafka_username, kafka_password, antares_kafka_cluster):
    antarest_key = aws.kms.Key(
            "AmazonMSK_antares-key",
            description="Key MSK Cluster Scram Secret Association",
        )
    antares_secret = aws.secretsmanager.Secret(
            "AmazonMSK_antares-secret", kms_key_id=antarest_key.key_id
        )
    antares_secret_version = kafka_password.apply(
            lambda decoded_kafka_password: aws.secretsmanager.SecretVersion(
                "AmazonMSK_antares_secret_1",
                secret_id=antares_secret.id,
                secret_string=json.dumps(
                    {"username": kafka_username, "password": decoded_kafka_password}
                ),
            )
        )

    antares_scram_secret_association = aws.msk.ScramSecretAssociation(
            "AmazonMSK_antares-secret-association",
            cluster_arn=antares_kafka_cluster.arn,
            secret_arn_lists=[antares_secret.arn],
            opts=pulumi.ResourceOptions(depends_on=[antares_secret_version]),
        )

    antares_secret_policy = aws.secretsmanager.SecretPolicy(
            "AmazonMSK_antares-secret-policy",
            secret_arn=antares_secret.arn,
            policy=antares_secret.arn.apply(
                lambda arn: f"""{{
            "Version" : "2012-10-17",
            "Statement" : [ {{
                "Sid": "AWSKafkaResourcePolicy",
                "Effect" : "Allow",
                "Principal" : {{
                "Service" : "kafka.amazonaws.com"
                }},
                "Action" : "secretsmanager:getSecretValue",
                "Resource" : "{arn}"
            }} ]
        }}
        """
            ),
        )

def deploy_kafka_connector():
    drivers = sorted(glob.glob('*kafka-connector*.zip'))
    driver = drivers[-1]

    antares_bucket = aws.s3.BucketV2(
        "antares-kafka-connector-bucket"
    )
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


    # example = aws.mskconnect.Connector("example",
    #     kafkaconnect_version="2.8.1",
    #     capacity=aws.mskconnect.ConnectorCapacityArgs(
    #         autoscaling=aws.mskconnect.ConnectorCapacityAutoscalingArgs(
    #             mcu_count=1,
    #             min_worker_count=1,
    #             max_worker_count=8,
    #             scale_in_policy=aws.mskconnect.ConnectorCapacityAutoscalingScaleInPolicyArgs(
    #                 cpu_utilization_percentage=20,
    #             ),
    #             scale_out_policy=aws.mskconnect.ConnectorCapacityAutoscalingScaleOutPolicyArgs(
    #                 cpu_utilization_percentage=80,
    #             ),
    #         ),
    #     ),
    #     connector_configuration={
    #         "connector.class": "com.github.jcustenborder.kafka.connect.simulator.SimulatorSinkConnector",
    #         "tasks.max": "1",
    #         "topics": "",
    #     },
    #     kafka_cluster=aws.mskconnect.ConnectorKafkaClusterArgs(
    #         apache_kafka_cluster=aws.mskconnect.ConnectorKafkaClusterApacheKafkaClusterArgs(
    #             bootstrap_servers=aws_msk_cluster["example"]["bootstrap_brokers_tls"],
    #             vpc=aws.mskconnect.ConnectorKafkaClusterApacheKafkaClusterVpcArgs(
    #                 security_groups=[aws_security_group["example"]["id"]],
    #                 subnets=[
    #                     aws_subnet["example1"]["id"],
    #                     aws_subnet["example2"]["id"],
    #                     aws_subnet["example3"]["id"],
    #                 ],
    #             ),
    #         ),
    #     ),
    #     kafka_cluster_client_authentication=aws.mskconnect.ConnectorKafkaClusterClientAuthenticationArgs(
    #         authentication_type="NONE",
    #     ),
    #     kafka_cluster_encryption_in_transit=aws.mskconnect.ConnectorKafkaClusterEncryptionInTransitArgs(
    #         encryption_type="TLS",
    #     ),
    #     plugins=[aws.mskconnect.ConnectorPluginArgs(
    #         custom_plugin=aws.mskconnect.ConnectorPluginCustomPluginArgs(
    #             arn=aws_mskconnect_custom_plugin["example"]["arn"],
    #             revision=aws_mskconnect_custom_plugin["example"]["latest_revision"],
    #         ),
    #     )],
    #     service_execution_role_arn=aws_iam_role["example"]["arn"])


    # return kafka_snowflake_connector_plugin
