import yaml
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

class InfluxV2Client():
    def __init__(self, token, url, org, bucket):
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
        self.bucket = bucket

    def write_point(self, data):
        self.write_api.write(bucket=self.bucket, record=data)

    def query_data(self, query):
        return self.query_api.query(query)