import boto3
import hashlib
import json
import os
import requests
import time

from urllib.parse import parse_qs

aws_region = os.environ["AWSREGION"]
storage_name = os.environ["STORAGE_NAME"]
slack_token = os.environ["SLACK_API_TOKEN"]
slack_channel_id = os.environ["SLACK_CHANNEL_ID"]
table_name = os.environ["TABLE_NAME"]


def move_to(key, to):
    s3 = boto3.resource("s3")

    hashkey = hashlib.md5(key.encode("utf-8")).hexdigest()
    new_key = "{}/{}.jpg".format(to, hashkey)

    print("Move to", to, new_key)

    # copy
    s3.Object(storage_name, new_key).copy_from(
        CopySource="{}/{}".format(storage_name, key)
    )
    s3.ObjectAcl(storage_name, new_key).put(ACL="public-read")

    # delete
    s3.Object(storage_name, key).delete()

    return new_key


def index_faces(key, image_id):
    try:
        client = boto3.client("rekognition", region_name=aws_region)
        res = client.index_faces(
            CollectionId=storage_name,
            Image={"S3Object": {"Bucket": storage_name, "Name": key,}},
            ExternalImageId=image_id,
            DetectionAttributes=["DEFAULT"],
        )
    except Exception as ex:
        print("Error:", ex, key)
        res = []

    print("index_faces", res)

    return res


def get_faces(user_id):
    dynamodb = boto3.resource("dynamodb", region_name=aws_region)
    table = dynamodb.Table(table_name)

    try:
        res = table.get_item(Key={"user_id": user_id})
    except Exception as ex:
        print("Error:", ex, user_id)
        res = []

    print("get_faces", res)

    return res


def put_faces(user_id, user_name, real_name, image_key, image_url):
    dynamodb = boto3.resource("dynamodb", region_name=aws_region)
    table = dynamodb.Table(table_name)

    latest = int(round(time.time() * 1000))

    try:
        res = table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="set user_name = :user_name, real_name=:real_name, image_key=:image_key, image_url=:image_url, image_type=:image_type, latest=:latest",
            ExpressionAttributeValues={
                ":user_name": user_name,
                ":real_name": real_name,
                ":image_key": image_key,
                ":image_url": image_url,
                ":image_type": "trained",
                ":latest": latest,
            },
            ReturnValues="UPDATED_NEW",
        )
    except Exception as ex:
        print("Error:", ex, user_id)
        res = []

    print("put_faces", res)

    return res


def train(event, context):
    # print(event['body'])
    data = parse_qs(event["body"])
    data = json.loads(data["payload"][0])
    print(data)

    user_id = data["callback_id"]

    print("Train", user_id)

    res = get_faces(user_id)

    if len(res) == 0:
        return {"statusCode": 500}

    key = res["Item"]["image_key"]

    auth = "Bearer {}".format(slack_token)

    # if we got a discard action, send an update first, and then remove the referenced image
    if data["actions"][0]["name"] == "discard":

        print("Ignored", key)

        new_key = move_to(key, "trash")

        put_faces(user_id, "ignored", "Ignored", new_key)

        text = "Ok, I ignored this image"
        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            storage_name, aws_region, new_key
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

    elif data["actions"][0]["name"] == "username":
        selected_id = data["actions"][0]["selected_options"][0]["value"]

        # search username from slack
        params = {"token": slack_token, "user": selected_id}
        res = requests.post("https://slack.com/api/users.info", data=params)
        print(res.json())

        user_name = res.json()["user"]["name"]
        real_name = res.json()["user"]["real_name"]

        print("Trained", key)

        new_key = move_to(key, "trained/{}".format(user_id))

        text = "Trained as {}".format(real_name)
        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            storage_name, aws_region, new_key
        )

        put_faces(user_id, user_name, real_name, new_key, image_url)

        # index_faces(new_key, user_id)

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
