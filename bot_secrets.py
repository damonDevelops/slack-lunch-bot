import json
import os
import boto3

_cache: dict | None = None


def load_secrets() -> dict:
    global _cache
    if _cache is None:
        arn = os.environ["BOT_SECRET_ARN"]
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=arn)
        _cache = json.loads(response["SecretString"])
    return _cache
