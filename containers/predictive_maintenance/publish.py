import time
import paho.mqtt.client as mqtt
import config


def publish_msg(message, topic):
    client = mqtt.Client()
    client.connect(config.broker_address, config.broker_port)
    client.publish(topic, message)
    time.sleep(config.wait_time_on_publish)
    client.disconnect()
