import boto3
import cv2
import json
import os
import requests
import time
import uuid

from urllib.parse import parse_qs


AWS_REGION = os.environ.get("AWSREGION", "ap-northeast-1")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "")
SLACK_API_TOKEN = os.environ.get("SLACK_API_TOKEN", "")
STORAGE_NAME = os.environ.get("STORAGE_NAME", "deeplens-doorman-demo")
TABLE_NAME = os.environ.get("TABLE_NAME", "deeplens-doorman-demo")

LINE_COLOR = (255, 165, 20)

MAX_FACES = 3


# from doorman import guess
# from doorman import train
# from doorman import unknown


# s3 = boto3.client("s3")
s3 = boto3.resource("s3")

rek = boto3.client("rekognition", region_name=AWS_REGION)

ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
tbl = ddb.Table(TABLE_NAME)


def new_path(key, path1, path2="0"):
    keys = key.split("/")
    if path2 == "0":
        return "{}/{}".format(path1, keys[len(keys) - 1])
    return "{}/{}/{}".format(path1, path2, keys[len(keys) - 1])


def gen_name(key):
    keys = key.split(".")
    if len(keys) == 0:
        ext = "jpg"
    else:
        ext = keys[len(keys) - 1]
    return "{}.{}".format(uuid.uuid4(), ext)


def move_trash(key):
    print("move_trash", key)
    new_key = new_path(gen_name(key), "trash")
    copy_img(key, new_key)
    return new_key


def move_trained(key):
    print("move_trained", key)
    new_key = new_path(gen_name(key), "trained")
    copy_img(key, new_key)
    return new_key


def move_unknown(key, box, user_id="0"):
    print("move_unknown", key)
    new_key = new_path(gen_name(key), "unknown", user_id)
    # copy_img(key, new_key)
    make_crop(key, new_key, box)
    return new_key


def mave_detected(key, box, user_id="0"):
    print("mave_detected", key)
    new_key = new_path(gen_name(key), "detected", user_id)
    # copy_img(key, new_key)
    make_rectangle(key, new_key, box)
    return new_key


def copy_img(key, new_key, delete=True):
    print("copy img", key, new_key)

    # copy
    s3.Object(STORAGE_NAME, new_key).copy_from(
        CopySource="{}/{}".format(STORAGE_NAME, key)
    )
    s3.ObjectAcl(STORAGE_NAME, new_key).put(ACL="public-read")
    # s3.copy_object(Bucket=STORAGE_NAME, CopySource=key, Key=new_key, ACL="public-read")

    if delete == True:
        delete_img(key)


def delete_img(key):
    print("delete img", key)

    # delete
    s3.Object(STORAGE_NAME, key).delete()
    # s3.delete_object(Bucket=STORAGE_NAME, Key=key)


def make_rectangle(src_key, dst_key, box):
    client = boto3.client("s3")

    if os.path.isdir("/tmp") == False:
        os.mkdir("/tmp")

    tmp_img = "/tmp/image.jpg"

    client.download_file(STORAGE_NAME, src_key, tmp_img)

    src = cv2.imread(tmp_img, cv2.IMREAD_COLOR)

    width = src.shape[1]
    height = src.shape[0]

    left, top, right, bottom = get_bounding_box(width, height, box)

    line_width = max(int(width * 0.003), 1)

    cv2.rectangle(src, (left, top), (right, bottom), LINE_COLOR, line_width)

    # cv2.imwrite(dst_img, src)
    _, jpg_data = cv2.imencode(".jpg", src)

    res = client.put_object(
        Bucket=STORAGE_NAME, Key=dst_key, Body=jpg_data.tostring(), ACL="public-read"
    )

    return res


def make_crop(src_key, dst_key, box):
    client = boto3.client("s3")

    if os.path.isdir("/tmp") == False:
        os.mkdir("/tmp")

    tmp_img = "/tmp/image.jpg"

    client.download_file(STORAGE_NAME, src_key, tmp_img)

    src = cv2.imread(tmp_img, cv2.IMREAD_COLOR)

    width = src.shape[1]
    height = src.shape[0]

    left, top, right, bottom = get_bounding_box(width, height, box)

    dst = src.copy()
    dst = src[top:bottom, left:right]

    # cv2.imwrite(dst_img, dst)
    _, jpg_data = cv2.imencode(".jpg", dst)

    res = client.put_object(
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
        # rek = boto3.client("rekognition", region_name=AWS_REGION)
        res = rek.search_faces_by_image(
            CollectionId=STORAGE_NAME,
            Image={"S3Object": {"Bucket": STORAGE_NAME, "Name": key}},
            MaxFaces=MAX_FACES,
            FaceMatchThreshold=80,
        )
    except Exception as ex:
        print("Error:", ex, key)
        res = []

    print("search_faces", res)

    return res


def index_faces(key):
    try:
        # rek = boto3.client("rekognition", region_name=AWS_REGION)
        res = rek.index_faces(
            CollectionId=STORAGE_NAME,
            Image={"S3Object": {"Bucket": STORAGE_NAME, "Name": key}},
            MaxFaces=MAX_FACES,
            DetectionAttributes=["DEFAULT"],
            # ExternalImageId=image_id,
        )
    except Exception as ex:
        print("Error:", ex, key)
        res = []

    print("index_faces", res)

    return res


def get_faces(user_id):
    # ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
    # tbl = ddb.Table(TABLE_NAME)

    try:
        res = tbl.get_item(Key={"user_id": user_id})
    except Exception as ex:
        print("Error:", ex, user_id)
        res = []

    print("get_faces", res)

    return res


def create_faces(
    user_id,
    image_key,
    image_url,
    image_type="unknown",
    user_name="unknown",
    real_name="Unknown",
):
    # ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
    # tbl = ddb.Table(TABLE_NAME)

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

    return res


def put_faces(
    user_id,
    image_key,
    image_url,
    image_type="unknown",
    user_name="unknown",
    real_name="Unknown",
):
    # ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
    # tbl = ddb.Table(TABLE_NAME)

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
    # ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
    # tbl = ddb.Table(TABLE_NAME)

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


def send_message(text, key):
    image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
        STORAGE_NAME, AWS_REGION, key
    )

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


def guess(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    # event_bucket_name = event["Records"][0]["s3"]["bucket"]["name"]

    res = search_faces(key)

    if len(res) == 0:
        # error detected, move to trash
        print("No faces", key)
        move_trash(key)
        return {}

    bounding_box = res["SearchedFaceBoundingBox"]

    if len(res["FaceMatches"]) == 0:
        # no known faces detected, let the users decide in slack
        print("No matches found", key)
        move_unknown(key, bounding_box)
        delete_img(key)
        return {}

    # known faces detected, send welcome message

    user_id = res["FaceMatches"][0]["Face"]["FaceId"]

    # for face in res["FaceMatches"]:
    #     user_id = face["Face"]["FaceId"]
    #     bounding_box = face["Face"]["BoundingBox"]

    print("face matches", user_id, bounding_box)

    res = get_faces(user_id)

    image_type = res["Item"]["image_type"]
    user_name = res["Item"]["user_name"]
    real_name = res["Item"]["real_name"]

    if image_type == "unknown":
        print("unknown", user_id, user_name, real_name, key)
        new_key = move_unknown(key, bounding_box, user_id)
    else:
        print("detected", user_id, user_name, real_name, key)
        new_key = mave_detected(key, bounding_box, user_id)

        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            STORAGE_NAME, AWS_REGION, new_key
        )

        put_faces_image(user_id, new_key, image_url)

        text = "Detected {}".format(real_name)
        send_message(text, new_key)

    delete_img(key)

    return {}


def unknown(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    # event_bucket_name = event["Records"][0]["s3"]["bucket"]["name"]

    print("Unknown", key)

    keys = key.split("/")

    image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
        STORAGE_NAME, AWS_REGION, key
    )

    if len(keys) > 2:
        user_id = keys[1]

        put_faces(user_id, key, image_url)

    else:
        res = index_faces(key)

        if len(res) == 0:
            # error detected, move to trash
            print("No faces", key)
            move_trash(key)
            return {}

        if len(res["FaceRecords"]) == 0:
            # no known faces detected, let the users decide in slack
            print("No index faces", key)
            move_trash(key)
            return {}

        user_id = res["FaceRecords"][0]["Face"]["FaceId"]
        bounding_box = res["FaceRecords"][0]["Face"]["BoundingBox"]

        print("Indexed faces", user_id, bounding_box)

        # new_key = move_unknown(key, bounding_box, user_id)

        put_faces(user_id, key, image_url)

    text = "I don't know who this is, can you tell me?"
    send_message(text, key)

    # message = {
    #     "channel": SLACK_CHANNEL_ID,
    #     "text": text,
    #     "attachments": [
    #         {
    #             "image_url": image_url,
    #             "fallback": "Nope?",
    #             "attachment_type": "default",
    #             # "callback_id": user_id,
    #             # "actions": [
    #             #     {
    #             #         "name": "username",
    #             #         "text": "Select a username...",
    #             #         "type": "select",
    #             #         "data_source": "users",
    #             #     },
    #             #     # {
    #             #     #     "name": "discard",
    #             #     #     "text": "Ignore",
    #             #     #     "style": "danger",
    #             #     #     "type": "button",
    #             #     #     "value": "ignore",
    #             #     #     # "confirm": {
    #             #     #     #     "title": "Are you sure?",
    #             #     #     #     "text": "Are you sure you want to ignore and delete this image?",
    #             #     #     #     "ok_text": "Yes",
    #             #     #     #     "dismiss_text": "No",
    #             #     #     # },
    #             #     # },
    #             # ],
    #         },
    #     ],
    # }
    # # print(message)
    # res = requests.post(
    #     "https://slack.com/api/chat.postMessage",
    #     headers={
    #         "Content-Type": "application/json;charset=UTF-8",
    #         "Authorization": auth,
    #     },
    #     json=message,
    # )
    # print(res.json())

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

    # if we got a discard action, send an update first, and then remove the referenced image
    if data["actions"][0]["name"] == "discard":
        print("Ignored", key)

        new_key = move_trash(key)

        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            STORAGE_NAME, AWS_REGION, new_key
        )

        put_faces(user_id, new_key, image_url, "ignored")

        text = "Ok, I ignored this image"
        send_message(text, new_key)

    elif data["actions"][0]["name"] == "username":
        selected_id = data["actions"][0]["selected_options"][0]["value"]

        # search username from slack
        params = {"token": SLACK_API_TOKEN, "user": selected_id}
        res = requests.post("https://slack.com/api/users.info", data=params)
        print(res.json())

        user_name = res.json()["user"]["name"]
        real_name = res.json()["user"]["real_name"]

        print("Trained", key)

        new_key = move_trained(key)

        image_url = "https://{}.s3-{}.amazonaws.com/{}".format(
            STORAGE_NAME, AWS_REGION, new_key
        )

        put_faces(user_id, new_key, image_url, "trained", user_name, real_name)

        text = "Trained as {}".format(real_name)
        send_message(text, new_key)

    return {"statusCode": 200}
