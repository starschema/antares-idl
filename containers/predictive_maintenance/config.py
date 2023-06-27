import os

# influx
token = os.environ.get("INFLUX_TOKEN")
org = os.environ.get("INFLUX_ORG") or "Starschema"
url_base = os.environ.get("INFLUX_URL") or "http://influxdb2"
url_port = int(os.environ.get("INFLUX_PORT") or 80)
url = url_base + ":" + str(url_port)

bucket = os.environ.get("INFLUX_BUCKET") or "default"

# mqtt
broker_address = os.environ.get("MQTT_HOST")
broker_port = int(os.environ.get("MQTT_PORT") or 1883)
wait_time_on_publish = 6

raw_data_topic = "/engines/raw"
predictions_topic = "/engines/predictions"
