import json
import boto3
import requests
import hashlib
import os
from urllib.parse import parse_qs

aws_region = os.environ["AWSREGION"]
storage_name = os.environ["STORAGE_NAME"]
slack_token = os.environ["SLACK_API_TOKEN"]
slack_channel_id = os.environ["SLACK_CHANNEL_ID"]

from doorman import guess
from doorman import train
from doorman import unknown
