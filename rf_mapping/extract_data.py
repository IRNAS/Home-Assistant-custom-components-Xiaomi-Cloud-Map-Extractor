import yaml
import json
from serial import Serial
from influxdb_client import Point
from influx_client import InfluxV2Client

secrets_file = "../secrets.yaml"
secrets = yaml.load(open(secrets_file, "r"), Loader=yaml.FullLoader)
INFLUX_TOKEN_IRNAS = secrets.get("INFLUX_TOKEN_ROBOROCK")
INFLUX_TOKEN_RF_MAP = secrets.get("INFLUX_TOKEN_RF_MAP")
BUCKET_RF_MAP = secrets.get("BUCKET_RF_MAP")
BUCKET_ROBOROCK = secrets.get("BUCKET_ROBOROCK")
BUCKET_RF_MAP = secrets.get("BUCKET_RF_MAP")
INFLUX_URL = secrets.get("INFLUX_URL")
INFLUX_ORG = secrets.get("INFLUX_ORG")

client = InfluxV2Client(INFLUX_TOKEN_IRNAS, INFLUX_URL, INFLUX_ORG, BUCKET_RF_MAP)

def write_point(data, client):
    configId = data.get("type", "None") + "_" + data.get("config_id", "None")
    p = (
        Point("data")
        .tag("configId", configId)
        .field("freq", data.get("freq", None))
        .field("P", data.get("P", None))
        .field("SF", data.get("SF", None))
        .field("BW", data.get("BW", None))
        .field("CR", data.get("CR", None))
        .field("RSSI", data.get("RSSI", None))
        .field("S_RSSI", data.get("S_RSSI", None))
        .field("SNR", data.get("SNR", None))
        .field("count", data.get("count", None))
    )
    # print(p)
    client.write_point(p)

ser = Serial('/dev/ttyACM0', 115200)
while True:
    line = ser.readline().decode("utf-8")
    # print(line)
    reading_obj = json.loads(line)
    write_point(reading_obj, client)
    print(reading_obj)
