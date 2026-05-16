import os
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")

import json
import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch


SECRET_VALUES = {
    "SLACK_SIGNING_SECRET": "test-signing-secret",
    "SLACK_CLIENT_ID": "test-client-id",
    "SLACK_CLIENT_SECRET": "test-client-secret",
    "ANTHROPIC_API_KEY": "test-api-key",
}


def _create_secret(name="slack-lunch-bot-secrets"):
    client = boto3.client("secretsmanager", region_name="ap-southeast-2")
    resp = client.create_secret(Name=name, SecretString=json.dumps(SECRET_VALUES))
    return resp["ARN"]


@mock_aws
def test_load_secrets_returns_all_keys():
    arn = _create_secret()
    import importlib
    import bot_secrets
    importlib.reload(bot_secrets)
    with patch.dict(os.environ, {"BOT_SECRET_ARN": arn}):
        result = bot_secrets.load_secrets()
    assert result["SLACK_SIGNING_SECRET"] == "test-signing-secret"
    assert result["SLACK_CLIENT_ID"] == "test-client-id"
    assert result["SLACK_CLIENT_SECRET"] == "test-client-secret"
    assert result["ANTHROPIC_API_KEY"] == "test-api-key"


@mock_aws
def test_load_secrets_raises_when_arn_missing():
    env = {k: v for k, v in os.environ.items() if k != "BOT_SECRET_ARN"}
    import importlib
    import bot_secrets
    importlib.reload(bot_secrets)
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(KeyError):
            bot_secrets.load_secrets()
