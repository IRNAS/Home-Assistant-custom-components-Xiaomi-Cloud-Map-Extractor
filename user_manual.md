## User Manual

Inside this repository are two scripts, which, in combination, plot a heatmap of bluetooth RF coverage of selected devices.

## Processor map
In the original repository the `map_processor.py` extracts the map data from the cloud and plots it.

We have made a slight modification in regards to the original repo, in the form of the `run` command. This will start the vacuum, and periodically upload position data to the cloud. We do this to get a point in space, which we can match with a `rssi` reading from some BLE device.

To run the robot vacuum use 
```
python3 map_processor.py run --config camera.yaml --duration <duration_seconds> [--update-interval <interval_seconds>] [--local-control] 
```
See the `camera_example.yaml` file for an example of the config file and fill out the missing secrets.


## Plot RSSI Heatmap
We plot the heatmap using the `plot_heatmap.py` script. This script takes the `rssi` data from the BLE device, and the `position` data from the vacuum, and plots a heatmap.
You can run it with default settings using
```
python3 plot_heatmap.py
```

Or specify the `--down-scale`, `--time` and `--config` parameters. The `--down-scale` parameter is used to downscale the resulting image. The `--time` parameter is used to specify from how far back in time up until now the data should be fetched. The `--config` parameter is used to specify the config file to use.

See the `secrets_empty.yaml` file for an example of the config file and fill it out.