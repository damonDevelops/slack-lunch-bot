#!/bin/bash
set -e

rm -rf package deployment.zip
pip install -r requirements.txt -t package/ -q
cp main.py llm.py lambda_handler.py package/
cd package && zip -r ../deployment.zip . -q
cd ..
echo "deployment.zip ready ($(du -sh deployment.zip | cut -f1))"
