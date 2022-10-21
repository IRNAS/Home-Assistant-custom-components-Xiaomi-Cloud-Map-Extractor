from turtle import backward
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from rf_mapping.influx_client import InfluxV2Client
import datetime
import yaml

def map_ts_to_distance(distance):
    if distance == 30:
        start_time = datetime.datetime(2022, 10, 21, 13, 52, 30)
        label = "30m"
    if distance == 60:
        start_time = datetime.datetime(2022, 10, 21, 13, 53, 10)
        label = "60m"
    if distance == 100:
        start_time = datetime.datetime(2022, 10, 21, 13, 54, 0)
        label = "100m"
    if distance == 200:
        start_time = datetime.datetime(2022, 10, 21, 13, 55, 0)
        label = "200m"
    if distance == 350:
        start_time = datetime.datetime(2022, 10, 21, 13, 56, 5)
        label = "350m"
    if distance == "backwards":
        start_time = datetime.datetime(2022, 10, 21, 13, 57, 0)
        label = "30m"

    return int(datetime.datetime.timestamp(start_time)*1000), int(datetime.datetime.timestamp(start_time + datetime.timedelta(seconds=30))*1000), label

secrets_file = "secrets.yaml"
secrets = yaml.load(open(secrets_file, "r"), Loader=yaml.FullLoader)
INFLUX_TOKEN_ROBOROCK = secrets.get("INFLUX_TOKEN_ROBOROCK")
INFLUX_TOKEN_RF_MAP = secrets.get("INFLUX_TOKEN_RF_MAP")
BUCKET_RF_MAP = secrets.get("BUCKET_RF_MAP")
BUCKET_ROBOROCK = secrets.get("BUCKET_ROBOROCK")
INFLUX_URL = secrets.get("INFLUX_URL")
INFLUX_ORG = secrets.get("INFLUX_ORG")

query_duration = 100

# Used to extrack robot vs. time position
client_roborock = InfluxV2Client(
    token=INFLUX_TOKEN_ROBOROCK,
    url=INFLUX_URL,
    org=INFLUX_ORG,
    bucket=BUCKET_ROBOROCK,
)


client_mapper = InfluxV2Client(token=INFLUX_TOKEN_RF_MAP,
    url=INFLUX_URL,
    org=INFLUX_ORG,
    bucket=BUCKET_RF_MAP
)

# END_TIME = datetime.datetime(2022, 10, 21, 14, 0, 0)

query = f' from(bucket: "{BUCKET_RF_MAP}") \
|> range(start: -{query_duration}m, stop: -20m) \
|> filter(fn: (r) => r["_measurement"] == "data") \
|> filter(fn: (r) => r["_field"] == "RSSI") \
|> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value") \
'

rf_map_result = client_mapper.query_data(query)
dpts = {}    
for table in rf_map_result:
    # print(table.get_group_key())
    dpts_rssi = []
    configId = ""
    
    for record in table.records:
        ts = int(record.get_time().timestamp() * 10**3)
        # print(record.values.get("RSSI"))
        dpts_rssi.append({"ts": ts, "rssi": record.values.get("RSSI")})
        configId = record.values.get("configId")

    dpts[configId] = dpts_rssi
    # print(configId)
    # print(len(dpts[configId]))

# print(dpts)
fig, ax = plt.subplots()
for record_id in dpts.keys():
    x = [dpt["ts"] for dpt in dpts[record_id]]
    y = [dpt["rssi"] for dpt in dpts[record_id]]
    # plt.clf()
    # plt.legend
    ax.plot(x, y, label=record_id)

    # print(dpts[record_id])

# Add rectangles for all distances
for d in [30, 60, 100, 200, 350]:
    start_ts, end_ts, label = map_ts_to_distance(d)
    ax.add_patch(Rectangle((start_ts, -110), end_ts-start_ts, 75, color="blue", alpha=0.2))
    ax.text(start_ts + 10000, -45, label, style='italic')
plt.legend()
plt.show()