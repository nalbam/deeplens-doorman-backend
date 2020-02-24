import boto3
import hashlib
import json
import os
import requests

aws_region = os.environ["AWSREGION"]
bucket_name = os.environ["BUCKET_NAME"]
slack_token = os.environ["SLACK_API_TOKEN"]
slack_channel_id = os.environ["SLACK_CHANNEL_ID"]
rekognition_collection_id = os.environ["REKOGNITION_COLLECTION_ID"]


def guess(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    # event_bucket_name = event["Records"][0]["s3"]["bucket"]["name"]

    try:
        client = boto3.client("rekognition")
        res = client.search_faces_by_image(
            CollectionId=rekognition_collection_id,
            Image={"S3Object": {"Bucket": bucket_name, "Name": key}},
            MaxFaces=1,
            FaceMatchThreshold=70,
        )
    except Exception as ex:
        print("Error", ex, key)
        res = []

    print(res)

    s3 = boto3.resource("s3")

    if len(res) == 0:
        # error detected, move to trash

        hashkey = hashlib.md5(key.encode("utf-8")).hexdigest()
        new_key = "trash/{}.jpg".format(hashkey)

        print("Trash", new_key)

        # move to 'trash'
        s3.Object(bucket_name, new_key).copy_from(
            CopySource="{}/{}".format(bucket_name, key)
        )
        s3.ObjectAcl(bucket_name, new_key).put(ACL="public-read")

        # delete
        s3.Object(bucket_name, key).delete()

    elif len(res["FaceMatches"]) == 0:
        # no known faces detected, let the users decide in slack

        hashkey = hashlib.md5(key.encode("utf-8")).hexdigest()
        new_key = "unknown/{}.jpg".format(hashkey)

        print("No matches found", new_key)

        # move to 'unknown'
        s3.Object(bucket_name, new_key).copy_from(
            CopySource="{}/{}".format(bucket_name, key)
        )
        s3.ObjectAcl(bucket_name, new_key).put(ACL="public-read")

        # delete
        s3.Object(bucket_name, key).delete()

    else:
        # known faces detected, send welcome message

        user_id = res["FaceMatches"][0]["Face"]["ExternalImageId"]

        # search username from slack
        params = {"token": slack_token, "user": user_id}
        res = requests.post("https://slack.com/api/users.info", data=params)
        print(res.json())

        username = res.json()["user"]["name"]

        hashkey = hashlib.md5(key.encode("utf-8")).hexdigest()
        new_key = "detected/{}-{}/{}.jpg".format(user_id, username, hashkey)

        print("Face found", new_key)

        # move to 'detected'
        s3.Object(bucket_name, new_key).copy_from(
            CopySource="{}/{}".format(bucket_name, key)
        )
        s3.ObjectAcl(bucket_name, new_key).put(ACL="public-read")

        # delete
        s3.Object(bucket_name, key).delete()

        text = "Welcome @{}".format(username)
        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            bucket_name, aws_region, new_key
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
