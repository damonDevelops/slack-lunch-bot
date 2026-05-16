import os
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")

import boto3
import pytest
from datetime import datetime, timezone
from moto import mock_aws
from slack_sdk.oauth.installation_store import Installation

from store import DynamoDBInstallationStore


def make_table():
    dynamodb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    dynamodb.create_table(
        TableName="slack-lunch-bot",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def make_installation(user_id="U456", user_token="xoxp-test-user"):
    return Installation(
        app_id="A123",
        enterprise_id=None,
        team_id="T123",
        team_name="Test Workspace",
        bot_token="xoxb-test-bot",
        bot_id="B123",
        bot_user_id="U000",
        bot_scopes=["commands"],
        user_id=user_id,
        user_token=user_token,
        user_scopes=["users.profile:write"],
        installed_at=datetime.now(tz=timezone.utc),
    )


@mock_aws
def test_save_and_find_user_token():
    make_table()
    store = DynamoDBInstallationStore()
    store.save(make_installation())

    found = store.find_installation(enterprise_id=None, team_id="T123", user_id="U456")
    assert found is not None
    assert found.user_token == "xoxp-test-user"


@mock_aws
def test_find_returns_none_for_unknown_user():
    make_table()
    store = DynamoDBInstallationStore()
    store.save(make_installation())

    found = store.find_installation(enterprise_id=None, team_id="T123", user_id="U999")
    assert found is None


@mock_aws
def test_find_bot_returns_bot_token():
    make_table()
    store = DynamoDBInstallationStore()
    store.save(make_installation())

    bot = store.find_bot(enterprise_id=None, team_id="T123")
    assert bot is not None
    assert bot.bot_token == "xoxb-test-bot"


@mock_aws
def test_save_overwrites_existing_user_token():
    make_table()
    store = DynamoDBInstallationStore()
    store.save(make_installation(user_token="xoxp-old"))
    store.save(make_installation(user_token="xoxp-new"))

    found = store.find_installation(enterprise_id=None, team_id="T123", user_id="U456")
    assert found.user_token == "xoxp-new"


@mock_aws
def test_save_and_get_workspace_config():
    make_table()
    store = DynamoDBInstallationStore()
    store.save_workspace_config("T123", 45)

    config = store.get_workspace_config("T123")
    assert config is not None
    assert config["default_duration_minutes"] == 45


@mock_aws
def test_get_workspace_config_returns_none_when_absent():
    make_table()
    store = DynamoDBInstallationStore()

    config = store.get_workspace_config("T123")
    assert config is None


@mock_aws
def test_delete_workspace_config():
    make_table()
    store = DynamoDBInstallationStore()
    store.save_workspace_config("T123", 45)
    store.delete_workspace_config("T123")

    config = store.get_workspace_config("T123")
    assert config is None
