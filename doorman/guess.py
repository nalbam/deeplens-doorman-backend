import boto3
import hashlib
import json
import os
import requests

aws_region = os.environ["AWSREGION"]
storage_name = os.environ["STORAGE_NAME"]
slack_token = os.environ["SLACK_API_TOKEN"]
slack_channel_id = os.environ["SLACK_CHANNEL_ID"]


def move_to(s3, key, to):
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


def guess(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    # event_bucket_name = event["Records"][0]["s3"]["bucket"]["name"]

    # dynamodb = boto3.resource("dynamodb", region_name=aws_region)
    # table = dynamodb.Table(storage_name)

    try:
        client = boto3.client("rekognition", region_name=aws_region)
        res = client.search_faces_by_image(
            CollectionId=storage_name,
            Image={"S3Object": {"Bucket": storage_name, "Name": key}},
            MaxFaces=1,
            FaceMatchThreshold=80,
        )
    except Exception as ex:
        print("Error", ex, key)
        res = []

    print(res)

    s3 = boto3.resource("s3")

    if len(res) == 0:
        # error detected, move to trash

        print("Error", key)

        move_to(s3, key, "trash")

    elif len(res["FaceMatches"]) == 0:
        # no known faces detected, let the users decide in slack

        print("No matches found", key)

        new_key = move_to(s3, key, "unknown")

    else:
        # known faces detected, send welcome message

        user_ids = []
        user_names = []

        user_id = res["FaceMatches"][0]["Face"]["ExternalImageId"]

        # search username from slack
        params = {"token": slack_token, "user": user_id}
        res = requests.post("https://slack.com/api/users.info", data=params)
        print(res.json())

        username = res.json()["user"]["name"]

        print("Face found", key)

        new_key = move_to(s3, key, "detected/{}-{}".format(user_id, username))

        # for slack
        text = "Welcome @{}".format(username)
        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            storage_name, aws_region, new_key
        )
        auth = "Bearer {}".format(slack_token)

        message = {
            "channel": slack_channel_id,
            "text": text,
            "link_names": True,
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
            "https://slack.com/api/chat.postMessage",
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Authorization": auth,
            },
            json=message,
        )
        print(res.json())

    return {}
