import os
from datetime import datetime, timezone
from typing import Optional

import boto3
from slack_sdk.oauth.installation_store import InstallationStore, Installation
from slack_sdk.oauth.installation_store.models.bot import Bot


def get_system_default_duration() -> int:
    try:
        ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "ap-southeast-2"))
        resp = ssm.get_parameter(Name="/slack-lunch-bot/default_duration_minutes")
        return int(resp["Parameter"]["Value"])
    except Exception:
        return 30


class DynamoDBInstallationStore(InstallationStore):
    def __init__(self, table_name: str = "slack-lunch-bot"):
        self.table = boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "ap-southeast-2"),
        ).Table(table_name)

    def save(self, installation: Installation) -> None:
        self.table.put_item(Item={
            "pk": f"T#{installation.team_id}",
            "sk": "bot",
            "bot_token": installation.bot_token or "",
            "bot_id": installation.bot_id or "",
            "bot_user_id": installation.bot_user_id or "",
            "app_id": installation.app_id or "",
            "enterprise_id": installation.enterprise_id or "",
            "team_name": installation.team_name or "",
        })
        if installation.user_token:
            self.table.put_item(Item={
                "pk": f"T#{installation.team_id}",
                "sk": f"U#{installation.user_id}",
                "user_token": installation.user_token,
                "user_id": installation.user_id,
                "enterprise_id": installation.enterprise_id or "",
            })

    def find_installation(
        self,
        enterprise_id: Optional[str],
        team_id: Optional[str],
        user_id: Optional[str] = None,
        is_enterprise_install: Optional[bool] = False,
    ) -> Optional[Installation]:
        if not user_id:
            return None
        resp = self.table.get_item(Key={"pk": f"T#{team_id}", "sk": f"U#{user_id}"})
        item = resp.get("Item")
        if not item:
            return None
        bot_resp = self.table.get_item(Key={"pk": f"T#{team_id}", "sk": "bot"})
        bot = bot_resp.get("Item", {})
        return Installation(
            app_id=bot.get("app_id", ""),
            enterprise_id=item.get("enterprise_id") or None,
            team_id=team_id,
            user_id=user_id,
            user_token=item.get("user_token"),
            user_scopes=["users.profile:write"],
            bot_token=bot.get("bot_token"),
            bot_id=bot.get("bot_id", ""),
            bot_user_id=bot.get("bot_user_id", ""),
            bot_scopes=["commands"],
            installed_at=datetime.now(tz=timezone.utc),
        )

    def get_workspace_config(self, team_id: str) -> Optional[dict]:
        resp = self.table.get_item(Key={"pk": f"T#{team_id}", "sk": "config"})
        item = resp.get("Item")
        if not item:
            return None
        return {"default_duration_minutes": int(item["default_duration_minutes"])}

    def save_workspace_config(self, team_id: str, default_duration_minutes: int) -> None:
        self.table.put_item(Item={
            "pk": f"T#{team_id}",
            "sk": "config",
            "default_duration_minutes": default_duration_minutes,
        })

    def delete_workspace_config(self, team_id: str) -> None:
        self.table.delete_item(Key={"pk": f"T#{team_id}", "sk": "config"})

    def find_bot(
        self,
        enterprise_id: Optional[str],
        team_id: Optional[str],
        is_enterprise_install: Optional[bool] = False,
    ) -> Optional[Bot]:
        resp = self.table.get_item(Key={"pk": f"T#{team_id}", "sk": "bot"})
        item = resp.get("Item")
        if not item:
            return None
        return Bot(
            app_id=item.get("app_id", ""),
            enterprise_id=item.get("enterprise_id") or None,
            team_id=team_id,
            bot_token=item.get("bot_token"),
            bot_id=item.get("bot_id", ""),
            bot_user_id=item.get("bot_user_id", ""),
            bot_scopes=["commands"],
            installed_at=datetime.now(tz=timezone.utc),
        )
