#!/bin/sh

echo
echo "$ git pull"
git pull

echo
echo "$ aws rekognition delete-collection --collection-id ${STORAGE_NAME} --region ${AWSREGION}"
aws rekognition delete-collection --collection-id ${STORAGE_NAME} --region ${AWSREGION} | jq .

echo
echo "$ sls remove"
sls remove
