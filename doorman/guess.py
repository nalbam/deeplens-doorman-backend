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
    client = boto3.client("rekognition")
    key = event["Records"][0]["s3"]["object"]["key"]
    event_bucket_name = event["Records"][0]["s3"]["bucket"]["name"]
    image = {"S3Object": {"Bucket": event_bucket_name, "Name": key}}
    # print(image)

    resp = client.search_faces_by_image(
        CollectionId=rekognition_collection_id,
        Image=image,
        MaxFaces=1,
        FaceMatchThreshold=70,
    )

    s3 = boto3.resource("s3")

    if len(resp["FaceMatches"]) == 0:
        # no known faces detected, let the users decide in slack
        print("No matches found, sending to unknown")
        new_key = "unknown/%s.jpg" % hashlib.md5(key.encode("utf-8")).hexdigest()
        s3.Object(bucket_name, new_key).copy_from(
            CopySource="%s/%s" % (bucket_name, key)
        )
        s3.ObjectAcl(bucket_name, new_key).put(ACL="public-read")
        s3.Object(bucket_name, key).delete()
    else:
        print("Face found")
        print(resp)
        # move image
        user_id = resp["FaceMatches"][0]["Face"]["ExternalImageId"]
        new_key = "detected/%s/%s.jpg" % (
            user_id,
            hashlib.md5(key.encode("utf-8")).hexdigest(),
        )
        s3.Object(bucket_name, new_key).copy_from(
            CopySource="%s/%s" % (event_bucket_name, key)
        )
        s3.ObjectAcl(bucket_name, new_key).put(ACL="public-read")
        s3.Object(bucket_name, key).delete()

        # fetch the username for this user_id
        data = {"token": slack_token, "user": user_id}
        print(data)
        resp = requests.post("https://slack.com/api/users.info", data=data)
        print(resp.content)
        print(resp.json())
        username = resp.json()["user"]["name"]

        message = {
            "channel": slack_channel_id,
            "text": "Welcome @%s" % username,
            "link_names": True,
            "attachments": [
                {
                    "image_url": "https://%s.s3-%s.amazonaws.com/%s"
                    % (bucket_name, aws_region, new_key),
                    "fallback": "Nope?",
                    "attachment_type": "default",
                }
            ],
        }
        res = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Authorization": "Bearer %s" % slack_token,
            },
            json=message,
        )
        print(res.json())

    return {}
