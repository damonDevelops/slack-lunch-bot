import json
import os
import boto3

_cache: dict | None = None


_LOCAL_SECRET_KEYS = ("ANTHROPIC_API_KEY", "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "BOT_SECRET_ARN")


def load_secrets() -> dict:
    global _cache
    if _cache is None:
        if "BOT_SECRET_ARN" in os.environ:
            arn = os.environ["BOT_SECRET_ARN"]
            client = boto3.client("secretsmanager")
            response = client.get_secret_value(SecretId=arn)
            _cache = json.loads(response["SecretString"])
        else:
            # Local dev fallback: read known keys directly from environment
            _cache = {k: os.environ[k] for k in _LOCAL_SECRET_KEYS if k in os.environ}
    return _cache
