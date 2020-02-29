# deeplens-doorman-backend

## env

```bash
export AWSREGION="ap-northeast-1"
export SLACK_API_TOKEN="xoxb-xxx-xxx-xxx"
export SLACK_CHANNEL_ID="CU6UJ4XXX"
export STORAGE_NAME="deeplens-doorman-demo"
export TABLE_NAME="doorman-users-demo"
```

## resource

```bash
# aws s3 mb s3://${STORAGE_NAME} --region ${AWSREGION}

# aws rekognition delete-collection --collection-id $STORAGE_NAME --region $AWSREGION | jq .
aws rekognition create-collection --collection-id $STORAGE_NAME --region $AWSREGION | jq .
```

## deploy

```bash
# pip install pyenv
# pyenv install 3.7.6
pyenv shell 3.7.6

# npm install -g serverless
# sls plugin install -n serverless-python-requirements
sls deploy
```
