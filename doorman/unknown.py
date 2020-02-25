import boto3
import hashlib
import json
import os
import requests
from urllib.parse import parse_qs

aws_region = os.environ["AWSREGION"]
bucket_name = os.environ["BUCKET_NAME"]
slack_token = os.environ["SLACK_API_TOKEN"]
slack_channel_id = os.environ["SLACK_CHANNEL_ID"]
rekognition_collection_id = os.environ["REKOGNITION_COLLECTION_ID"]
dynamodb_table = os.environ["DYNAMODB_TABLE"]


def unknown(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    # event_bucket_name = event["Records"][0]["s3"]["bucket"]["name"]

    print("Unknown", key)

    auth = "Bearer {}".format(slack_token)

    image_url = "https://{}.s3-{}.amazonaws.com/{}".format(bucket_name, aws_region, key)

    message = {
        "channel": slack_channel_id,
        "text": "I don't know who this is, can you tell me?",
        "attachments": [
            {
                "image_url": image_url,
                "fallback": "Nope?",
                "callback_id": key,
                "attachment_type": "default",
                "actions": [
                    {
                        "name": "username",
                        "text": "Select a username...",
                        "type": "select",
                        "data_source": "users",
                    },
                    {
                        "name": "discard",
                        "text": "Ignore",
                        "style": "danger",
                        "type": "button",
                        "value": "ignore",
                        # "confirm": {
                        #     "title": "Are you sure?",
                        #     "text": "Are you sure you want to ignore and delete this image?",
                        #     "ok_text": "Yes",
                        #     "dismiss_text": "No",
                        # },
                    },
                ],
            },
        ],
    }
    # print(message)
    res = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Authorization": auth,
        },
        json=message,
    )
    print(res.json())
