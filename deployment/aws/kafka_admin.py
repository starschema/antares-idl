import json
import kafka
import datetime
from aws_lambda_powertools.utilities import parameters


def create_topic(event, context):
    """Create a topic in Kafka"""
    secret = parameters.get_secret(
        event["authentication-secret-name"], transform="json"
    )

    admin_client = kafka.KafkaAdminClient(
        bootstrap_servers=event["bootstrap_servers"],
        client_id="kafka_admin_lambda",
        security_protocol="SASL_SSL",
        ssl_check_hostname=False,
        sasl_mechanism="SCRAM-SHA-512",
        sasl_plain_username=secret["username"],
        sasl_plain_password=secret["password"],
    )
    ret = {}
    for topic in event["topics"]:
        new_topic = kafka.admin.NewTopic(
            name=topic["name"],
            num_partitions=topic["partitions"],
            replication_factor=topic["replication_factor"],
        )

        try:
            admin_client.create_topics(new_topics=[new_topic], validate_only=False)
            print(f"Topic created: {str(topic)}")
            ret[topic["name"]] = True
        except Exception as exception:
            print(f"Unable to create topic: {str(topic['name'])}")
            print(exception)
            ret[topic["name"]] = False

    if event.get("send_test_message"):
        producer = kafka.KafkaProducer(
            bootstrap_servers=event["bootstrap_servers"],
            client_id="kafka_admin_lambda",
            security_protocol="SASL_SSL",
            ssl_check_hostname=False,
            sasl_mechanism="SCRAM-SHA-512",
            sasl_plain_username=secret["username"],
            sasl_plain_password=secret["password"],
            value_serializer=lambda x: json.dumps(x).encode("utf-8"),
        )
        now = str(datetime.datetime.now())
        for topic in event["topics"]:
            data = {
                "source": "kafka_admin_lambda",
                "message": "Hello Antares",
                "time": now,
            }
            print("Sending test message to " + topic["name"])
            print(f"Message:\n{str(data)}\n")
            producer.send(topic["name"], value=data)

    return ret


def lambda_handler(event, context):
    """Lambda handler for Kafka Admin Lambda"""
    operation = event["operation"]

    if operation == "create_topic":
        return json.dumps(create_topic(event, context))

    raise ValueError("Unrecognized operation: " + str(operation)[:100])
