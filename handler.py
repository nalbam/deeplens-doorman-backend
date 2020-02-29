import boto3
import cv2
import hashlib
import json
import os
import requests
import time

from urllib.parse import parse_qs


AWS_REGION = os.environ.get("AWSREGION", "ap-northeast-1")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "")
SLACK_API_TOKEN = os.environ.get("SLACK_API_TOKEN", "")
STORAGE_NAME = os.environ.get("STORAGE_NAME", "deeplens-doorman-demo")
TABLE_NAME = os.environ.get("TABLE_NAME", "deeplens-doorman-demo")

LINE_COLOR = (255, 165, 20)
LINE_WIDTH = 2


# from doorman import guess
# from doorman import train
# from doorman import unknown


s3 = boto3.client("s3")


def new_path(key, path1, path2="0"):
    keys = key.split("/")
    return "{}/{}/{}".format(path1, path2, keys[len(keys) - 1])


def copy_img(key, new_key, delete=True):
    print("copy img", key, new_key)

    # copy
    s3.copy_object(Bucket=STORAGE_NAME, CopySource=key, Key=new_key, ACL="public-read")

    if delete == True:
        delete_img(key)


def delete_img(key):
    print("delete img", key)

    # delete
    s3.delete_object(Bucket=STORAGE_NAME, Key=key)


def make_rectangle(src_key, dst_key, box):
    if os.path.isdir("/tmp") == False:
        os.mkdir("/tmp")

    tmp_img = "/tmp/image.jpg"

    s3.download_file(STORAGE_NAME, src_key, tmp_img)

    src = cv2.imread(tmp_img, cv2.IMREAD_COLOR)

    left, top, right, bottom = get_bounding_box(src.shape[1], src.shape[0], box)

    cv2.rectangle(src, (left, top), (right, bottom), LINE_COLOR, LINE_WIDTH)

    # cv2.imwrite(dst_img, src)
    _, jpg_data = cv2.imencode(".jpg", src)

    res = s3.put_object(
        Bucket=STORAGE_NAME, Key=dst_key, Body=jpg_data.tostring(), ACL="public-read"
    )

    return res


def make_crop(src_key, dst_key, box):
    if os.path.isdir("/tmp") == False:
        os.mkdir("/tmp")

    tmp_img = "/tmp/image.jpg"

    s3.download_file(STORAGE_NAME, src_key, tmp_img)

    src = cv2.imread(tmp_img, cv2.IMREAD_COLOR)

    left, top, right, bottom = get_bounding_box(src.shape[1], src.shape[0], box)

    dst = src.copy()
    dst = src[top:bottom, left:right]

    # cv2.imwrite(dst_img, dst)
    _, jpg_data = cv2.imencode(".jpg", dst)

    res = s3.put_object(
        ACL="public-read", Body=jpg_data.tostring(), Bucket=STORAGE_NAME, Key=dst_key,
    )

    return res


def get_bounding_box(width, height, box, rate=0.1):
    rw = box["Width"] * rate
    rh = box["Height"] * rate

    left = int(width * max(box["Left"] - rw, 0))
    top = int(height * max(box["Top"] - rh, 0))

    right = int(width * min(box["Left"] + box["Width"] + rw, 100))
    bottom = int(height * min(box["Top"] + box["Height"] + rh, 100))

    return left, top, right, bottom


def search_faces(key):
    try:
        rek = boto3.client("rekognition", region_name=AWS_REGION)
        res = rek.search_faces_by_image(
            CollectionId=STORAGE_NAME,
            Image={"S3Object": {"Bucket": STORAGE_NAME, "Name": key}},
            MaxFaces=1,
            FaceMatchThreshold=80,
        )
    except Exception as ex:
        print("Error:", ex, key)
        res = []

    print("search_faces", res)

    return res


def index_faces(key, image_id):
    try:
        rek = boto3.client("rekognition", region_name=AWS_REGION)
        res = rek.index_faces(
            CollectionId=STORAGE_NAME,
            Image={"S3Object": {"Bucket": STORAGE_NAME, "Name": key,}},
            ExternalImageId=image_id,
            DetectionAttributes=["DEFAULT"],
        )
    except Exception as ex:
        print("Error:", ex, key)
        res = []

    print("index_faces", res)

    return res


def get_faces(user_id):
    ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
    tbl = ddb.Table(TABLE_NAME)

    try:
        res = tbl.get_item(Key={"user_id": user_id})
    except Exception as ex:
        print("Error:", ex, user_id)
        res = []

    print("get_faces", res)

    return res


def create_faces(
    image_key, image_url, image_type="unknown", user_name="unknown", real_name="Unknown"
):
    ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
    tbl = ddb.Table(TABLE_NAME)

    user_id = hashlib.md5(image_key.encode("utf-8")).hexdigest()
    latest = int(round(time.time() * 1000))

    try:
        res = tbl.put_item(
            Item={
                "user_id": user_id,
                "user_name": user_name,
                "real_name": real_name,
                "image_key": image_key,
                "image_url": image_url,
                "image_type": image_type,
                "latest": latest,
            }
        )
    except Exception as ex:
        print("Error:", ex, user_id)
        res = []

    print("create_faces", res)

    return user_id, res


def put_faces(
    user_id,
    image_key,
    image_url,
    image_type="unknown",
    user_name="unknown",
    real_name="Unknown",
):
    ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
    tbl = ddb.Table(TABLE_NAME)

    latest = int(round(time.time() * 1000))

    try:
        res = tbl.update_item(
            Key={"user_id": user_id},
            UpdateExpression="set user_name = :user_name, real_name=:real_name, image_key=:image_key, image_url=:image_url, image_type=:image_type, latest=:latest",
            ExpressionAttributeValues={
                ":user_name": user_name,
                ":real_name": real_name,
                ":image_key": image_key,
                ":image_url": image_url,
                ":image_type": image_type,
                ":latest": latest,
            },
            ReturnValues="UPDATED_NEW",
        )
    except Exception as ex:
        print("Error:", ex, user_id)
        res = []

    print("put_faces", res)

    return res


def put_faces_image(user_id, image_key, image_url, image_type="detected"):
    ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
    tbl = ddb.Table(TABLE_NAME)

    latest = int(round(time.time() * 1000))

    try:
        res = tbl.update_item(
            Key={"user_id": user_id},
            UpdateExpression="set image_key=:image_key, image_url=:image_url, image_type=:image_type, latest=:latest",
            ExpressionAttributeValues={
                ":image_key": image_key,
                ":image_url": image_url,
                ":image_type": image_type,
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
        new_key = new_path(key, "trash")
        copy_img(key, new_key)
        return {}

    if len(res["FaceMatches"]) == 0:
        # no known faces detected, let the users decide in slack
        print("No matches found", key)
        new_key = new_path(key, "unknown")
        copy_img(key, new_key)
        return {}

    # known faces detected, send welcome message

    user_id = res["FaceMatches"][0]["Face"]["ExternalImageId"]
    bounding_box = res["SearchedFaceBoundingBox"]

    res = get_faces(user_id)

    user_name = res["Item"]["user_name"]
    real_name = res["Item"]["real_name"]

    if user_name == "unknown" or user_name == "ignored":
        print(user_name, key)
        new_key = new_path(key, user_name, user_id)
        copy_img(key, new_key)
        return {}

    print("Face found", user_name, real_name)

    new_key = new_path(key, "detected", user_id)

    # new_key = copy_img(key, new_key)

    make_rectangle(key, new_key, bounding_box)

    delete_img(key)

    text = "Detected {}".format(real_name)
    image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
        STORAGE_NAME, AWS_REGION, new_key
    )

    put_faces(user_id, new_key, image_url)

    auth = "Bearer {}".format(SLACK_API_TOKEN)

    message = {
        "channel": SLACK_CHANNEL_ID,
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


def unknown(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    # event_bucket_name = event["Records"][0]["s3"]["bucket"]["name"]

    print("Unknown", key)

    keys = key.split("/")

    text = "I don't know who this is, can you tell me?"
    image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
        STORAGE_NAME, AWS_REGION, key
    )

    if len(keys) > 2:
        user_id = keys[1]

        put_faces(user_id, key, image_url)

    else:
        user_id, res = create_faces("unknown", "Unknown", key, image_url)

        index_faces(key, user_id)

    auth = "Bearer {}".format(SLACK_API_TOKEN)

    message = {
        "channel": SLACK_CHANNEL_ID,
        "text": text,
        "attachments": [
            {
                "image_url": image_url,
                "fallback": "Nope?",
                "attachment_type": "default",
                "callback_id": user_id,
                "actions": [
                    {
                        "name": "username",
                        "text": "Select a username...",
                        "type": "select",
                        "data_source": "users",
                    },
                    # {
                    #     "name": "discard",
                    #     "text": "Ignore",
                    #     "style": "danger",
                    #     "type": "button",
                    #     "value": "ignore",
                    #     # "confirm": {
                    #     #     "title": "Are you sure?",
                    #     #     "text": "Are you sure you want to ignore and delete this image?",
                    #     #     "ok_text": "Yes",
                    #     #     "dismiss_text": "No",
                    #     # },
                    # },
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

    return {}


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

    auth = "Bearer {}".format(SLACK_API_TOKEN)

    # if we got a discard action, send an update first, and then remove the referenced image
    if data["actions"][0]["name"] == "discard":
        print("Ignored", key)

        new_key = new_path(key, "trash")
        copy_img(key, new_key)

        text = "Ok, I ignored this image"
        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            STORAGE_NAME, AWS_REGION, new_key
        )

        put_faces(user_id, "ignored", "Ignored", new_key, image_url)

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
        params = {"token": SLACK_API_TOKEN, "user": selected_id}
        res = requests.post("https://slack.com/api/users.info", data=params)
        print(res.json())

        user_name = res.json()["user"]["name"]
        real_name = res.json()["user"]["real_name"]

        print("Trained", key)

        new_key = new_path(key, "trained")
        copy_img(key, new_key)

        text = "Trained as {}".format(real_name)
        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            STORAGE_NAME, AWS_REGION, new_key
        )

        put_faces(user_id, user_name, real_name, new_key, image_url)

        # index_faces(new_key, user_id)

        message = {
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
            data["response_url"],
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Authorization": auth,
            },
            json=message,
        )
        print(res.json())

    return {"statusCode": 200}
