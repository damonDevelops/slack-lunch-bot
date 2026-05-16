import json
import os
import boto3


def load_secrets() -> dict:
    arn = os.environ["BOT_SECRET_ARN"]
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=arn)
    return json.loads(response["SecretString"])
