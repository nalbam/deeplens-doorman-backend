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

    client = boto3.client("rekognition")
    res = client.search_faces_by_image(
        CollectionId=rekognition_collection_id,
        Image={"S3Object": {"Bucket": bucket_name, "Name": key}},
        MaxFaces=1,
        FaceMatchThreshold=70,
    )
    print(res)

    s3 = boto3.resource("s3")

    if len(res["FaceMatches"]) == 0:
        # no known faces detected, let the users decide in slack
        print("No matches found, sending to unknown")

        hashkey = hashlib.md5(key.encode("utf-8")).hexdigest()
        new_key = "unknown/{}.jpg".format(hashkey)

        # move to 'unknown'
        s3.Object(bucket_name, new_key).copy_from(
            CopySource="{}/{}".format(bucket_name, key)
        )
        s3.ObjectAcl(bucket_name, new_key).put(ACL="public-read")

        # delete
        s3.Object(bucket_name, key).delete()
    else:
        print("Face found")

        user_id = res["FaceMatches"][0]["Face"]["ExternalImageId"]
        hashkey = hashlib.md5(key.encode("utf-8")).hexdigest()
        new_key = "detected/{}/{}.jpg".format(user_id, hashkey)

        # move to 'detected'
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
