# deeplens-doorman-backend

## clone

```bash
git clone https://github.com/nalbam/deeplens-doorman-backend
```

## env

```bash
export AWSREGION="ap-northeast-1"
export SLACK_API_TOKEN="xoxb-xxx-xxx-xxx"
export SLACK_CHANNEL_ID="CU6UJ4XXX"
export STORAGE_NAME="deeplens-doorman-demo"
export TABLE_USERS="doorman-users-demo"
export TABLE_HISTORY="doorman-history-demo"
```

## resource

```bash
# aws s3 mb s3://${STORAGE_NAME} --region ${AWSREGION}

# aws rekognition delete-collection --collection-id ${STORAGE_NAME} --region ${AWSREGION} | jq .
aws rekognition create-collection --collection-id ${STORAGE_NAME} --region ${AWSREGION} | jq .
```

## deploy

```bash
git pull

# pip install pyenv
# pyenv install 3.7.6
pyenv shell 3.7.6

# npm install -g serverless
# sls plugin install -n serverless-python-requirements
sls deploy
```

## rekognition

```bash
aws rekognition detect-faces \
    --image "{\"S3Object\":{\"Bucket\":\"${STORAGE_NAME}\",\"Name\":\"photos/twice.jpg\"}}" \
    --region ${AWSREGION} | jq .

aws rekognition index-faces \
    --image "{\"S3Object\":{\"Bucket\":\"${STORAGE_NAME}\",\"Name\":\"photos/twice.jpg\"}}" \
    --collection-id ${STORAGE_NAME} \
    --max-faces 2 \
    --quality-filter "AUTO" \
    --detection-attributes "DEFAULT" \
    --external-image-id "twice.jpg" \
    --region ${AWSREGION} | jq .
```
