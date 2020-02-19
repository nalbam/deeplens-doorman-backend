# deeplens-doorman-backend

```bash
export AWSREGION="ap-northeast-1"
export BUCKET_NAME="deeplens-doorman-dev"
export SLACK_API_TOKEN="xoxb-xxx-xxx-xxx"
export SLACK_CHANNEL_ID="CU6UJ4XXX"
export REKOGNITION_COLLECTION_ID="doorman"
```

```bash
# aws s3 mb s3://${BUCKET_NAME} --region ${AWSREGION}

aws rekognition create-collection --collection-id "doorman" --region $AWSREGION
```

```bash
# pip install pyenv
# pyenv install 3.7.6
pyenv shell 3.7.6
sls plugin install -n serverless-python-requirements
sls deploy
```
