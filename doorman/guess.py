import boto3
import hashlib
import json
import os
import requests
import time

aws_region = os.environ["AWSREGION"]
storage_name = os.environ["STORAGE_NAME"]
slack_token = os.environ["SLACK_API_TOKEN"]
slack_channel_id = os.environ["SLACK_CHANNEL_ID"]
table_name = os.environ["TABLE_NAME"]


def move_to(key, to):
    s3 = boto3.resource("s3")

    hashkey = hashlib.md5(key.encode("utf-8")).hexdigest()
    new_key = "{}/{}.jpg".format(to, hashkey)

    print("Move to", key, new_key)

    # copy
    s3.Object(storage_name, new_key).copy_from(
        CopySource="{}/{}".format(storage_name, key)
    )
    s3.ObjectAcl(storage_name, new_key).put(ACL="public-read")

    # delete
    s3.Object(storage_name, key).delete()

    return new_key


def search_faces(key):
    try:
        client = boto3.client("rekognition", region_name=aws_region)
        res = client.search_faces_by_image(
            CollectionId=storage_name,
            Image={"S3Object": {"Bucket": storage_name, "Name": key}},
            MaxFaces=1,
            FaceMatchThreshold=80,
        )
    except Exception as ex:
        print("Error:", ex, key)
        res = []

    print("search_faces", res)

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


def put_faces(user_id, image_key, image_url):
    dynamodb = boto3.resource("dynamodb", region_name=aws_region)
    table = dynamodb.Table(table_name)

    latest = int(round(time.time() * 1000))

    try:
        res = table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="set image_key=:image_key, image_url=:image_url, image_type=:image_type, latest=:latest",
            ExpressionAttributeValues={
                ":image_key": image_key,
                ":image_url": image_url,
                ":image_type": "detected",
                ":latest": latest,
            },
            ReturnValues="UPDATED_NEW",
        )
    except Exception as ex:
        print("Error:", ex, user_id)
        res = []

    print("put_faces", res)

    return res


def guess(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    # event_bucket_name = event["Records"][0]["s3"]["bucket"]["name"]

    res = search_faces(key)

    if len(res) == 0:
        # error detected, move to trash
        print("Error", key)
        move_to(key, "trash")
        return {}

    if len(res["FaceMatches"]) == 0:
        # no known faces detected, let the users decide in slack
        print("No matches found", key)
        move_to(key, "unknown")
        return {}

    # known faces detected, send welcome message

    user_id = res["FaceMatches"][0]["Face"]["ExternalImageId"]

    res = get_faces(user_id)

    user_name = res["Item"]["user_name"]
    real_name = res["Item"]["real_name"]

    if user_name == "unknown" or user_name == "ignored":
        print("Unknown", key)
        move_to(key, "unknown/{}".format(user_id))
        return {}

    print("Face found", user_name, real_name)

    new_key = move_to(key, "detected/{}".format(user_id))

    auth = "Bearer {}".format(slack_token)

    text = "Detected {}".format(real_name)
    image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
        storage_name, aws_region, new_key
    )

    put_faces(user_id, new_key, image_url)

    message = {
        "channel": slack_channel_id,
        "text": text,
        "link_names": True,
        "attachments": [
            {"image_url": image_url, "fallback": "Nope?", "attachment_type": "default",}
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

    return {}
