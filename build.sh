#!/bin/bash
set -e

rm -rf package deployment.zip
pip install -r requirements-prod.txt \
  --platform manylinux2014_x86_64 \
  --target package/ \
  --only-binary=:all: \
  --python-version 3.12 \
  -q
cp main.py llm.py lambda_handler.py store.py package/
cd package && zip -r ../deployment.zip . -q
cd ..
echo "deployment.zip ready ($(du -sh deployment.zip | cut -f1))"
