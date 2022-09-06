import argparse
import logging
import time
import os

import yaml
from homeassistant import config_entries  # to fix circular imports
from const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME

from custom_components.xiaomi_cloud_map_extractor.camera import PLATFORM_SCHEMA, VacuumCamera
from custom_components.xiaomi_cloud_map_extractor.const import *
from custom_components.xiaomi_cloud_map_extractor.dreame.vacuum import DreameVacuum
from custom_components.xiaomi_cloud_map_extractor.roidmi.vacuum import RoidmiVacuum
from custom_components.xiaomi_cloud_map_extractor.viomi.vacuum import ViomiVacuum
from custom_components.xiaomi_cloud_map_extractor.xiaomi.vacuum import XiaomiVacuum

logging.basicConfig()
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)

secrets = yaml.load(open("secrets.yaml", "r"), Loader=yaml.FullLoader)
NODERED_HOST = secrets.get("NODERED_HOST")
NODERED_PORT = secrets.get("NODERED_PORT")

def open_and_validate_config(filename) -> dict:
    stream = open(filename, 'r')
    camera_config = yaml.load(stream, Loader=yaml.FullLoader)
    if not isinstance(camera_config, list) and "camera" in camera_config.keys():
        camera_config = camera_config["camera"]
    if isinstance(camera_config, list):
        camera_config = list(filter(lambda x: x["platform"] == "xiaomi_cloud_map_extractor", camera_config))[0]
    return PLATFORM_SCHEMA(camera_config)


def create_camera(config: dict, output_dir: str) -> VacuumCamera:
    host = config[CONF_HOST]
    token = config[CONF_TOKEN]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    country = config[CONF_COUNTRY]
    image_config = config[CONF_MAP_TRANSFORM]
    colors = config[CONF_COLORS]
    room_colors = config[CONF_ROOM_COLORS]
    for room, color in room_colors.items():
        colors[f"{COLOR_ROOM_PREFIX}{room}"] = color
    drawables = config[CONF_DRAW]
    sizes = config[CONF_SIZES]
    texts = config[CONF_TEXTS]
    if DRAWABLE_ALL in drawables:
        drawables = CONF_AVAILABLE_DRAWABLES[1:]
    attributes = CONF_AVAILABLE_ATTRIBUTES
    force_api = config[CONF_FORCE_API]
    return VacuumCamera("", host, token, username, password, country, "", False, image_config, colors, drawables, sizes,
                        texts, attributes, True, True, output_dir, force_api)


def attributes_to_dict(attributes):
    if isinstance(attributes, list):
        return list(map(lambda x: attributes_to_dict(x), attributes))
    if isinstance(attributes, dict):
        output = dict(attributes)
        for k, v in output.items():
            output[k] = attributes_to_dict(v)
        return output
    if hasattr(attributes, "as_dict"):
        output = attributes.as_dict()
        for k, v in output.items():
            output[k] = attributes_to_dict(v)
        return output
    return attributes


def parse_map_file(map_config, map_filename, api, suffix=""):
    print(f"Parsing map file \"{map_filename}\" with api \"{api}\"")
    map_file = open(map_filename, "rb").read()
    colors = map_config[CONF_COLORS]
    room_colors = map_config[CONF_ROOM_COLORS]
    texts = map_config[CONF_TEXTS]
    sizes = map_config[CONF_SIZES]
    transform = map_config[CONF_MAP_TRANSFORM]
    for room, color in room_colors.items():
        colors[f"{COLOR_ROOM_PREFIX}{room}"] = color
    drawables = map_config[CONF_DRAW]
    if DRAWABLE_ALL in drawables:
        drawables = CONF_AVAILABLE_DRAWABLES[1:]

    map_data = None
    try:
        if api == CONF_AVAILABLE_API_XIAOMI:
            map_data = XiaomiVacuum.decode_map(None, map_file, colors, drawables, texts, sizes, transform)
        elif api == CONF_AVAILABLE_API_VIOMI:
            map_data = ViomiVacuum.decode_map(None, map_file, colors, drawables, texts, sizes, transform)
        elif api == CONF_AVAILABLE_API_ROIDMI:
            map_data = RoidmiVacuum.decode_map(None, map_file, colors, drawables, texts, sizes, transform)
        elif api == CONF_AVAILABLE_API_DREAME:
            map_data = DreameVacuum.decode_map(None, map_file, colors, drawables, texts, sizes, transform)
    except Exception as e:
        print(f"Failed to parse map data! {e}")
    if map_data is not None:
        map_data.image.data.save(f"{map_filename}{suffix}.png")
        print(f"Map image saved to \"{map_filename}{suffix}.png\"")
        attributes_output_file = open(f"{map_filename}{suffix}.yaml", "w")
        attributes = VacuumCamera.extract_attributes(map_data, CONF_AVAILABLE_ATTRIBUTES, "")
        yaml.dump(attributes_to_dict(attributes), attributes_output_file)
        attributes_output_file.close()
        print(f"Map attributes saved to \"{map_filename}{suffix}.yaml\"")
    else:
        print("Failed to parse map data!")


def run_download(map_config, data_output_dir):
    print("Downloading map data...")
    camera = create_camera(map_config, data_output_dir)
    camera.update()
    attributes = camera.extra_state_attributes
    # print(f"Attributes: {attributes}")
    model = attributes[ATTR_MODEL]
    # print(f"Model: {model}")
    attributes_output_file = open(f"{data_output_dir}/attributes_{model}.yaml", "w")
    yaml.dump(attributes_to_dict(attributes), attributes_output_file)
    attributes_output_file.close()
    print(f"Map data successfully saved to \"{data_output_dir}\" directory!")
    print(f"Time: {time.time()}")


def run_test(map_config, test_dir):
    print("Running tests")
    for api in list(filter(lambda d: d in CONF_AVAILABLE_APIS, os.listdir(test_dir))):
        print(api)
        for file in filter(lambda ff: os.path.isfile(ff),
                           map(lambda f: f"{test_dir}/{api}/{f}", os.listdir(f"{test_dir}/{api}"))):
            print("  " + file)
            output = file + "_output"
            if not os.path.exists(output):
                os.mkdir(output)
            parse_map_file(map_config, file, api, "_output/data")

# Vacuum api: https://github.com/rytilahti/python-miio/blob/master/miio/integrations/vacuum/roborock/vacuum.py
def run_periodically(map_config, data_output_dir, update_interval, vacuum_duration, local_control=False):
    camera = create_camera(map_config, data_output_dir)

    if local_control:  # This will start the robot from this script
        camera._vacuum.persist_map(2)
        # camera._vacuum.enable_lab_mode(1)
        camera._vacuum.set_sound_volume(10)

        print(f"Updating camera 1")
        camera._vacuum.resume_or_start()

    # Wait for fresh map to be created
    camera.update()
    time.sleep(10)

    attributes = camera.extra_state_attributes
    current_pos = attributes[ATTRIBUTE_VACUUM_POSITION]

    import json
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)

    start_time = time.time()
    while time.time() - start_time < vacuum_duration:
        camera.update()
        print(f"Updating camera")

        attributes = camera.extra_state_attributes

        current_pos = attributes[ATTRIBUTE_VACUUM_POSITION]

        # print(current_pos)
        if current_pos is not None:
            pos_dict = current_pos.as_dict()
            # print(pos_dict)
            pos_dict["devId"] = "roborock_s6"

            charger_pos = attributes[ATTRIBUTE_CHARGER]
            # print(charger_pos)

            if charger_pos is not None:
                charger_pos_dict = charger_pos.as_dict()
                pos_dict["charger_x"] = charger_pos_dict["x"]
                pos_dict["charger_y"] = charger_pos_dict["y"]

                pos_dict["time"] = int(time.time() * 1000)

                print(f"Current pos: {pos_dict}")

                s.sendto(json.dumps(pos_dict).encode(), (NODERED_HOST, NODERED_PORT))

        model = attributes[ATTR_MODEL]
        # print(f"Model: {model}")
        attributes_output_file = open(f"{data_output_dir}/attributes_{model}.yaml", "w")
        yaml.dump(attributes_to_dict(attributes), attributes_output_file)
        attributes_output_file.close()

        time.sleep(update_interval)

    if local_control:
        camera._vacuum.home()
    # clean_details = camera._vacuum.last_clean_details()
    # print(f"Last clean details: {clean_details}")

if __name__ == '__main__':
    args_parser = argparse.ArgumentParser(description='Map processor')
    args_subparsers = args_parser.add_subparsers(help="Available run modes", dest="mode")
    args_parser_download = args_subparsers.add_parser("download", help="Download and parse map")
    args_parser_download.add_argument("--config", type=str, required=True, help="camera yaml config file")
    args_parser_test = args_subparsers.add_parser("test", help="Test multiple raw map files")
    args_parser_test.add_argument("--config", type=str, required=True, help="camera yaml config file")
    args_parser_test.add_argument("--test-data", type=str, required=True, help="test data directory")
    args_parser_parse = args_subparsers.add_parser("parse", help="Parse already downloaded map file")
    args_parser_parse.add_argument("--config", type=str, required=True, help="camera yaml config file")
    args_parser_parse.add_argument("--map-file", type=str, required=True, help="raw map file")
    args_parser_parse.add_argument("--api", type=str, choices=["xiaomi", "viomi", "roidmi", "dreame"], required=True,
                                   help="used api")
    args_parser_run = args_subparsers.add_parser("run", help="Run periodically")
    args_parser_run.add_argument("--config", type=str, required=True, help="camera yaml config file")
    args_parser_run.add_argument("--local-control", action="store_true", help="enable control from the python script")
    args_parser_run.add_argument("--duration", type=int, required=True, help="vacuum duration in seconds")
    args_parser_run.add_argument("--update-interval", type=int, default=1, help="map update interval in seconds")
    args = args_parser.parse_args()

    config_filename = args.config
    print(f"Validating configuration file: {config_filename}")
    config = open_and_validate_config(config_filename)
    print("Configuration validation successful")
    output_dir = config_filename.replace(".yaml", "")
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    if args.mode == "download":
        run_download(config, output_dir)
    elif args.mode == "run":
        run_periodically(config, output_dir, args.update_interval, args.duration, args.local_control)  
    elif args.mode == "parse":
        parse_map_file(config, args.map_file, args.api)
    elif args.mode == "test":
        run_test(config, args.test_data)
