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


def train(event, context):
    # print(event['body'])
    data = parse_qs(event["body"])
    data = json.loads(data["payload"][0])
    print(data)

    key = data["callback_id"]

    auth = "Bearer {}".format(slack_token)

    s3 = boto3.resource("s3")

    # if we got a discard action, send an update first, and then remove the referenced image
    if data["actions"][0]["name"] == "discard":
        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            bucket_name, aws_region, key
        )

        message = {
            "text": "Ok, I ignored this image",
            "attachments": [
                {
                    "image_url": image_url,
                    "fallback": "Nope?",
                    "attachment_type": "default",
                }
            ],
        }
        # print(message)
        res = requests.post(
            data["response_url"],
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Authorization": auth,
            },
            json=message,
        )
        print(res.json())

        # delete
        s3.Object(bucket_name, key).delete()

    if data["actions"][0]["name"] == "username":
        user_id = data["actions"][0]["selected_options"][0]["value"]
        hashkey = hashlib.md5(key.encode("utf-8")).hexdigest()
        new_key = "trained/{}/{}.jpg".format(user_id, hashkey)

        # save user_id
        client = boto3.client("rekognition")
        res = client.index_faces(
            CollectionId=rekognition_collection_id,
            Image={"S3Object": {"Bucket": bucket_name, "Name": key,}},
            ExternalImageId=user_id,
            DetectionAttributes=["DEFAULT"],
        )

        # move to 'trained'
        s3.Object(bucket_name, new_key).copy_from(
            CopySource="{}/{}".format(bucket_name, key)
        )
        s3.ObjectAcl(bucket_name, new_key).put(ACL="public-read")

        # delete
        s3.Object(bucket_name, key).delete()

        # search username from slack
        params = {"token": slack_token, "user": user_id}
        res = requests.post("https://slack.com/api/users.info", data=params)
        print(res.json())

        username = res.json()["user"]["name"]

        text = "Trained as @{} ({})".format(username, user_id)
        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            bucket_name, aws_region, new_key
        )

        message = {
            "text": text,
            "attachments": [
                {
                    "image_url": image_url,
                    "fallback": "Nope?",
                    "attachment_type": "default",
                }
            ],
        }
        # print(message)
        res = requests.post(
            data["response_url"],
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Authorization": auth,
            },
            json=message,
        )
        print(res.json())

    return {"statusCode": 200}
