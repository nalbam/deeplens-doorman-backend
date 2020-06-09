#!/bin/sh

echo
echo "$ git pull"
git pull

echo
echo "$ sls deploy"
sls deploy
