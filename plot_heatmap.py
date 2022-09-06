import yaml
import argparse
import numpy as np
from matplotlib import cm
from datetime import datetime, timedelta
from influxdb import InfluxDBClient as InfluxClientV1
from influxdb_client import InfluxDBClient as InfluxClientV2

from matplotlib.colors import ListedColormap

def get_influx_entry(client, measurement, range_minutes: int = 10) -> list:
    """Returns data point from influxDB at specified start_time.
    Data points are searched for in the range_seconds time from start time.
    Args:
        start_time_obj (datetime): datetime object of desired data point.
        range_seconds (int, optional): Time in seconds from start time. Defaults to 10.
    Returns:
        dict: _description_
    """
    res = client.query(
        f'SELECT * FROM {measurement} WHERE ("devId" =~ /^(CA:2A:55:83:6E:EF)$/) AND time >= now() - {range_minutes}m',
    )

    datapoints = list(res.get_points())
    return datapoints



def run(secrets_file, query_duration, display_resolution_downscale):
    secrets = yaml.load(open(secrets_file, "r"), Loader=yaml.FullLoader)
    INFLUXDB_HOST_v2 = secrets.get("INFLUXDB_HOST_v2")
    INFLUXDB_PORT_v2 = secrets.get("INFLUXDB_PORT_v2")
    INFLUXDB_TOKEN_v2 = secrets.get("INFLUXDB_TOKEN_v2")
    INFLUXDB_HOST_v1 = secrets.get("INFLUXDB_HOST_v1")
    INFLUXDB_PORT_v1 = secrets.get("INFLUXDB_PORT_v1")
    ORG = secrets.get("ORG")
    DATABASE_v1 = secrets.get("DATABASE_v1")
    USERNAME_v1 = secrets.get("USERNAME_v1")
    PASSWORD_v1 = secrets.get("PASSWORD_v1")
    MEASUREMENT_v1 = secrets.get("MEASUREMENT_v1")


    client_roborock = InfluxClientV2(
        url=f"http://{INFLUXDB_HOST_v2}:8086",
        token=INFLUXDB_TOKEN_v2,
        org=ORG,
    )

    query = f' from(bucket: "roborock_position") \
    |> range(start: -{query_duration}m) \
    |> filter(fn: (r) => r["_measurement"] == "data") \
    |> filter(fn: (r) => r["_field"] == "x" or r["_field"] == "y") \
    |> filter(fn: (r) => r["devId"] == "roborock_s6") \
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value") \
    '

    result = client_roborock.query_api().query(org=ORG, query=query)

    dpts_roborock = []
    for table in result:
        # print(table)
        for record in table.records:
            datapoint = {
                "ts": int(record.get_time().timestamp() * 10**3),
                "x": record.values.get("x"),
                "y": record.values.get("y"),
            }
            # print(datapoint)
            dpts_roborock.append(datapoint)
    #         results.append((record.get_value(), record.get_field()))

    client_v1 = InfluxClientV1(
        host=INFLUXDB_HOST_v1,
        port=INFLUXDB_PORT_v1,
        database=DATABASE_v1,
        username=USERNAME_v1,
        password=PASSWORD_v1
    )

    temp_pts = get_influx_entry(client_v1, MEASUREMENT_v1, range_minutes=query_duration)

    dpts_rssi = []
    for dpt in temp_pts:
        val = dpt.get("time")
        val = val[:-4]
        try:
            date_obj = datetime.strptime(val, "%Y-%m-%dT%H:%M:%S.%f")
            date_obj += timedelta(hours=2)
        except Exception as e:
            date_obj = datetime.strptime(dpt.get("time")[:-4], "%Y-%m-%dT%H:%M:%S")
            date_obj += timedelta(hours=2)
            print(f"EXCEPTION")
        ts = int(date_obj.timestamp() * 10**3)
        dpts_rssi.append({"ts": ts, "rssi": dpt.get("rssi")})

    output_pts = []
    for dpt_rssi in dpts_rssi:
        for dpt_robo in dpts_roborock:
            ts_rssi = dpt_rssi.get("ts")
            ts_robo = dpt_robo.get("ts")
            combined_pt = {}
            if abs(ts_rssi - ts_robo) < 3000:  # less than 3000 ms diff
                combined_pt["x"] = int(dpt_robo.get("x"))
                combined_pt["y"] = int(dpt_robo.get("y"))
                combined_pt["rssi"] = dpt_rssi.get("rssi")
                output_pts.append(combined_pt)

    ## Printing
    import matplotlib.pyplot as plt
    import numpy as np

    x = []
    y = []
    z = []

    min_x = 500000
    min_y = 500000

    for dpt in output_pts:
        x_val = dpt.get("x")
        y_val = dpt.get("y")

        x.append(x_val)
        y.append(y_val)

        if x_val < min_x:
            min_x = x_val

        if y_val < min_y:
            min_y = y_val

    x = np.array(x)
    y = np.array(y)

    x = x - min_x
    y = y - min_y

    X, Y = np.meshgrid(np.linspace(0, max(x), num=max(x) // display_resolution_downscale + 1), np.linspace(0, max(y), num=max(y) // display_resolution_downscale + 1))
    Z = np.zeros((max(x) // display_resolution_downscale + 1, max(y) // display_resolution_downscale + 1, 1), dtype=object)
    # Z_ = np.ndarray(shape=(max(x) + 1, max(y) + 1, 1), dtype=object)

    # Create empty lists for each bin
    for i in range(0, Z.shape[0]):
        for j in range(0, Z.shape[1]):
            Z[i][j][0] = []

    # print(Z.shape)

    for dpt in output_pts:
        x_val = dpt.get("x") - min_x
        y_val = dpt.get("y") - min_y
        z_val = dpt.get("rssi")

        # print(f"{x_val}, {y_val}, {z_val}")

        # Z[x_val // display_resolution_downscale, y_val // display_resolution_downscale] = z_val
        Z[x_val // display_resolution_downscale, y_val // display_resolution_downscale, 0].append(z_val)

    # Average the value in each bin
    Z_out = np.zeros((max(x) // display_resolution_downscale + 1, max(y) // display_resolution_downscale + 1))
    for i in range(0, Z.shape[0]):
        for j in range(0, Z.shape[1]):
            Z_out[i][j] = np.median(Z[i][j][0])


    print(Z_out)
    Z_out = Z_out.T  # Transpose the matrix, this is the correct orientation

    # Create custom colormap and plot
    rainbow = cm.get_cmap('rainbow', 256)
    newcolors = rainbow(np.linspace(0, 1, 256))
    white = np.array([256/256, 256/256, 256/256, 1])
    newcolors = newcolors[::-1]
    newcolors[-1:, :] = white
    newcmp = ListedColormap(newcolors)

    im = plt.imshow(Z_out, cmap=newcmp, vmax=-50, vmin=-100, origin="lower")

    cbar = plt.colorbar(im)
    cbar.ax.set_title("RSSI")

    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title("Signal Level vs. Position")
    plt.show()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plot rssi signal level vs position')
    parser.add_argument("-d", "--down-scale", help="Down Scale Resolution", type=int, default=50)
    parser.add_argument("-t", "--time", help="Period in minutes, how long back from now to fetch the data", type=int, default=120)
    parser.add_argument("-c", "--config", help="Config file", type=str, default="secrets.yaml")
    args = parser.parse_args()

    run(args.config, args.time, args.down_scale)