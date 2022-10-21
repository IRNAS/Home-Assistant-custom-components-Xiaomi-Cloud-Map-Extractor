import yaml
import argparse
import alphashape
import numpy as np
import matplotlib.pyplot as plt

from matplotlib import cm
from matplotlib.colors import ListedColormap
from rf_mapping.influx_client import InfluxV2Client


def run(secrets_file, query_duration, display_resolution_downscale):
    secrets = yaml.load(open(secrets_file, "r"), Loader=yaml.FullLoader)

    INFLUX_TOKEN_ROBOROCK = secrets.get("INFLUX_TOKEN_ROBOROCK")
    INFLUX_TOKEN_RF_MAP = secrets.get("INFLUX_TOKEN_RF_MAP")
    BUCKET_RF_MAP = secrets.get("BUCKET_RF_MAP")
    BUCKET_ROBOROCK = secrets.get("BUCKET_ROBOROCK")
    INFLUX_URL = secrets.get("INFLUX_URL")
    INFLUX_ORG = secrets.get("INFLUX_ORG")

    # Used to extrack robot vs. time position
    client_roborock = InfluxV2Client(
        token=INFLUX_TOKEN_ROBOROCK,
        url=INFLUX_URL,
        org=INFLUX_ORG,
        bucket=BUCKET_ROBOROCK,
    )

    query = f' from(bucket: "{BUCKET_ROBOROCK}") \
    |> range(start: -{query_duration}m) \
    |> filter(fn: (r) => r["_measurement"] == "data") \
    |> filter(fn: (r) => r["_field"] == "x" or r["_field"] == "y") \
    |> filter(fn: (r) => r["devId"] == "roborock_s6") \
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value") \
    '

    result = client_roborock.query_data(query)

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

    print(len(dpts_roborock))

    client_mapper = InfluxV2Client(token=INFLUX_TOKEN_RF_MAP,
        url=INFLUX_URL,
        org=INFLUX_ORG,
        bucket=BUCKET_RF_MAP
    )

    query = f' from(bucket: "{BUCKET_RF_MAP}") \
    |> range(start: -{query_duration}m) \
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
            dpts_rssi.append({"ts": ts, "rssi": record.values.get("RSSI")})
            configId = record.values.get("configId")
        dpts[configId] = dpts_rssi
        print(configId)
        # print(len(dpts[configId]))

    for record_id in dpts.keys():
        plt.clf()

        output_pts = []
        dpts_rssi = dpts[record_id]
        # print(len(dpts_rssi))
        for dpt_rssi in dpts_rssi:
            for dpt_robo in dpts_roborock:
                ts_rssi = dpt_rssi.get("ts")
                ts_robo = dpt_robo.get("ts")
                combined_pt = {}
                if abs(ts_rssi - ts_robo) < 3000:  # less than 3000 ms diff
                    try:
                        combined_pt["x"] = int(dpt_robo.get("x"))
                        combined_pt["y"] = int(dpt_robo.get("y"))
                        combined_pt["rssi"] = dpt_rssi.get("rssi")
                        output_pts.append(combined_pt)
                    except Exception as e:
                        print(e)

        x = []
        y = []

        min_x = 500000
        min_y = 500000

        print(len(output_pts))

        if len(output_pts) == 0:
            continue

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

        # X, Y = np.meshgrid(np.linspace(0, max(x), num=max(x) // display_resolution_downscale + 1), np.linspace(0, max(y), num=max(y) // display_resolution_downscale + 1))
        Z = np.zeros((max(x) // display_resolution_downscale + 1, max(y) // display_resolution_downscale + 1, 1), dtype=object)
        # Z_ = np.ndarray(shape=(max(x) + 1, max(y) + 1, 1), dtype=object)

        pt_coords = []
        # Create empty lists for each bin
        for i in range(0, Z.shape[0]):
            for j in range(0, Z.shape[1]):
                Z[i][j][0] = []

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
                rssi_val = np.median(Z[i][j][0])
                if rssi_val < 0:
                    Z_out[i][j] = rssi_val
                    pt_coords.append((i, j))


        print(Z_out)
        Z_out = np.nan_to_num(Z_out)
        print(Z_out)

        Z_out = Z_out.T  # Transpose the matrix, this is the correct orientation


        # Create custom colormap and plot
        rainbow = cm.get_cmap('rainbow', 256)
        newcolors = rainbow(np.linspace(0, 1, 256))
        white = np.array([256/256, 256/256, 256/256, 1])
        newcolors = newcolors[::-1]
        newcolors[-1:, :] = white
        newcmp = ListedColormap(newcolors)

        im = plt.imshow(Z_out, cmap=newcmp, vmax=-25, vmin=-100, origin="lower")

        cbar = plt.colorbar(im)
        cbar.ax.set_title("RSSI")

        plt.xlabel("X")
        plt.ylabel("Y")
        plt.title("Signal Level vs. Position")

        # Calculate alpha shape of points, which will be used to plot the outline of the room
        pt_coords = np.array(pt_coords)

        def generate_hull(pt_coords):
            import time
            from descartes import PolygonPatch
            start_time = time.time()
            alpha = 0.95 * alphashape.optimizealpha(pt_coords)
            # print(f"Alpha: {alpha}")
            print(f"Duration for alpha: {time.time() - start_time}")
            # const = 192
            num_pts = pt_coords.shape[0]
            # alpha = const / num_pts
            with open("pts_alpha_map.txt", "a+") as f:
                f.write(f"{num_pts} - {alpha}\n")
            print(num_pts)
            print(f"Alpha: {alpha}")
            start_time = time.time()
            hull = alphashape.alphashape(pt_coords, alpha)

            print(f"Duration for hull: {time.time() - start_time}")
            hull_pts = hull.exterior.coords.xy

            fig, ax = plt.subplots()
            ax.scatter(hull_pts[0], hull_pts[1], color='red')
            ax.add_patch(PolygonPatch(hull, fill=False, color='green'))

        # Interpolate RSSI values
        def interpolate(Z_out, pt_coords):
            from scipy.interpolate import griddata

            # print(np.linspace(0, Z_out.shape[0], len(vals)))
            # print(y)
            # print(pt_coords)
            x = pt_coords[:, 0]
            y = pt_coords[:, 1]
            print(f"Num x coords: {len(x)}")
            print(f"Num y coords: {len(y)}")
            print(f"Max x: {max(x)}")
            print(f"Max y: {max(y)}")
            # print(y)
            # x = np.linspace(0, Z_out.shape[0], len(vals))
            # y = np.linspace(0, Z_out.shape[1], len(vals))

            X, Y = np.meshgrid(
                np.linspace(0, max(x), max(x)),
                np.linspace(0, max(y), max(y)),
            )

            # non_zero = Z_out.nonzero()
            Z_out = Z_out.flatten()
            vals = []
            for val in Z_out:
                if val < 0:
                    vals.append(val)
            # vals = Z_out[Z_out < 0]
            print(f"Num vals: {len(vals)}")

            interpolated_vals = griddata((x, y), vals, (X, Y), method='cubic')
            print(f"Interpolated vals shape: {interpolated_vals.shape}")

            # im = plt.imshow(Z_out, cmap=newcmp, vmax=-25, vmin=-100, origin="lower")
            plt.contourf(X, Y, interpolated_vals, cmap=newcmp, vmax=-25, vmin=-100, origin="lower", alpha=0.3)

            cbar = plt.colorbar(im)
            cbar.ax.set_title("RSSI")

            plt.xlabel("X")
            plt.ylabel("Y")
            plt.title("Signal Level vs. Position")

        # interpolate(Z_out, pt_coords)
        
        plt.show()
        plt.savefig("rf_map_" + record_id + ".png")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plot rssi signal level vs position')
    parser.add_argument("-d", "--down-scale", help="Down Scale Resolution", type=int, default=50)
    parser.add_argument("-t", "--time", help="Period in minutes, how long back from now to fetch the data", type=int, default=120)
    parser.add_argument("-s", "--secrets", help="Secrets file", type=str, default="secrets.yaml")
    args = parser.parse_args()

    run(args.secrets, args.time, args.down_scale)