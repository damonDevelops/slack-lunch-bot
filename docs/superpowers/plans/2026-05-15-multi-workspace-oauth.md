# Multi-Workspace OAuth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded `SLACK_USER_TOKEN` with a DynamoDB-backed OAuth flow so any user in any workspace can install and use the bot.

**Architecture:** Bolt's built-in `OAuthSettings` + a custom `DynamoDBInstallationStore` handle the install flow and token storage. The `/lunch` handler looks up each user's token from DynamoDB at call time. All OAuth endpoints (`/slack/install`, `/slack/oauth_redirect`) are served by the same Lambda function via an updated API Gateway catch-all route.

**Tech Stack:** Python 3.12, slack-bolt, boto3, moto[dynamodb] (tests), pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Modify | Add boto3, moto[dynamodb], pytest |
| `store.py` | Create | DynamoDB InstallationStore — save/find tokens |
| `test_store.py` | Create | Unit tests for store.py using moto |
| `main.py` | Modify | Wire up OAuthSettings + InstallationStore, look up user token per call |
| `.env.example` | Modify | Document new env vars |

---

### Task 1: Update dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update `requirements.txt`**

```
slack-bolt>=1.18
anthropic>=0.25
python-dotenv>=1.0
boto3>=1.34
moto[dynamodb]>=5.0
pytest>=8.0
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: installs without errors.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add boto3, moto, pytest for OAuth + DynamoDB"
```

---

### Task 2: Create DynamoDB table in AWS

**Files:** none — manual AWS console step

- [ ] **Step 1: Create the table**

Go to **AWS Console → DynamoDB → Create table**:
- Table name: `slack-lunch-bot`
- Partition key: `pk` (String)
- Sort key: `sk` (String)
- Table settings: **Customize** → Capacity mode: **On-demand**
- Click **Create table**

- [ ] **Step 2: Note the table ARN**

Once created, click the table → **Overview → General information** → copy the **ARN** (looks like `arn:aws:dynamodb:ap-southeast-2:123456789:table/slack-lunch-bot`). You'll need this for Lambda permissions.

- [ ] **Step 3: Grant Lambda permission to access DynamoDB**

Go to **Lambda → slack-lunch-bot → Configuration → Permissions → click the execution role link** (opens IAM).

In IAM: **Add permissions → Attach policies → search "DynamoDB" → select `AmazonDynamoDBFullAccess`** → Add permissions.

(For production you'd scope this tighter, but this works for now.)

---

### Task 3: Implement `store.py` — write the test first

**Files:**
- Create: `test_store.py`
- Create: `store.py`

- [ ] **Step 1: Create `test_store.py`**

```python
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
```

- [ ] **Step 2: Run tests — confirm they fail with ImportError**

```bash
pytest test_store.py -v
```

Expected:
```
ERROR collecting test_store.py - ModuleNotFoundError: No module named 'store'
```

- [ ] **Step 3: Create `store.py`**

```python
import os
from datetime import datetime, timezone
from typing import Optional

import boto3
from slack_sdk.oauth.installation_store import InstallationStore, Installation
from slack_sdk.oauth.installation_store.models.bot import Bot


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
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
pytest test_store.py -v
```

Expected:
```
test_store.py::test_save_and_find_user_token PASSED
test_store.py::test_find_returns_none_for_unknown_user PASSED
test_store.py::test_find_bot_returns_bot_token PASSED
test_store.py::test_save_overwrites_existing_user_token PASSED

4 passed in X.XXs
```

- [ ] **Step 5: Commit**

```bash
git add store.py test_store.py
git commit -m "feat: add DynamoDB InstallationStore with tests"
```

---

### Task 4: Update `main.py` for OAuth

**Files:**
- Modify: `main.py` (full rewrite)
- Modify: `.env.example`

- [ ] **Step 1: Rewrite `main.py`**

```python
import os
import time
from dotenv import load_dotenv

load_dotenv()

from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from store import DynamoDBInstallationStore
from llm import parse_lunch

installation_store = DynamoDBInstallationStore()

app = App(
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    oauth_settings=OAuthSettings(
        client_id=os.environ["SLACK_CLIENT_ID"],
        client_secret=os.environ["SLACK_CLIENT_SECRET"],
        scopes=["commands"],
        user_scopes=["users.profile:write"],
        installation_store=installation_store,
        redirect_uri=os.environ.get("SLACK_REDIRECT_URI"),
    ),
    process_before_response=True,
)

DEFAULT_DURATION = int(os.environ.get("DEFAULT_LUNCH_DURATION_MINUTES", "30"))
APP_BASE_URL = os.environ.get("APP_BASE_URL", "")


@app.command("/lunch")
def handle_lunch_command(ack, body, client, respond, context):
    ack()

    user_text = body.get("text", "").strip()
    user_id = body["user_id"]
    team_id = body["team_id"]

    if not user_text:
        respond("Tell me what you're eating! e.g. `/lunch a spicy burrito 45m`")
        return

    installation = installation_store.find_installation(
        enterprise_id=context.get("enterprise_id"),
        team_id=team_id,
        user_id=user_id,
    )

    if not installation or not installation.user_token:
        install_url = f"{APP_BASE_URL}/slack/install"
        respond(f"Before I can set your status, connect your account first. <{install_url}|Authorise here →>")
        return

    if user_text.lower() in ("clear", "done"):
        try:
            client.users_profile_set(
                user=user_id,
                profile={"status_text": "", "status_emoji": "", "status_expiration": 0},
                token=installation.user_token,
            )
            respond("Status cleared.")
        except Exception:
            install_url = f"{APP_BASE_URL}/slack/install"
            respond(f"Couldn't clear your status — try re-authorising. <{install_url}|Authorise here →>")
        return

    try:
        result = parse_lunch(user_text)
    except Exception:
        respond("Couldn't figure out that lunch — try describing it differently.")
        return

    duration = result.get("duration_minutes") or DEFAULT_DURATION
    expiration = int(time.time()) + duration * 60

    try:
        client.users_profile_set(
            user=user_id,
            profile={
                "status_text": f"Eating: {result['status_text']}",
                "status_emoji": result["emoji"],
                "status_expiration": expiration,
            },
            token=installation.user_token,
        )
    except Exception:
        install_url = f"{APP_BASE_URL}/slack/install"
        respond(f"Couldn't set your status — try re-authorising. <{install_url}|Authorise here →>")
        return

    respond(f"{result['emoji']} Status set to *Eating: {result['status_text']}* for {duration} minutes.")


if __name__ == "__main__":
    app.start(port=3000)
```

- [ ] **Step 2: Update `.env.example`**

```
SLACK_SIGNING_SECRET=your-signing-secret-here
SLACK_CLIENT_ID=your-client-id-here
SLACK_CLIENT_SECRET=your-client-secret-here
SLACK_REDIRECT_URI=https://YOUR-API-GW-URL/slack/oauth_redirect
APP_BASE_URL=https://YOUR-API-GW-URL
ANTHROPIC_API_KEY=sk-ant-your-key-here
DEFAULT_LUNCH_DURATION_MINUTES=30
```

- [ ] **Step 3: Add new vars to your local `.env`**

Open `.env` and add:
```
SLACK_CLIENT_ID=         # Basic Information → App Credentials → Client ID
SLACK_CLIENT_SECRET=     # Basic Information → App Credentials → Client Secret
SLACK_REDIRECT_URI=https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com/slack/oauth_redirect
APP_BASE_URL=https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com
```

- [ ] **Step 4: Commit**

```bash
git add main.py .env.example
git commit -m "feat: wire up Bolt OAuth with DynamoDB installation store"
```

---

### Task 5: Update Slack app settings

**Files:** none — manual Slack console steps

- [ ] **Step 1: Add OAuth redirect URL**

Go to [api.slack.com/apps](https://api.slack.com/apps) → your app → **OAuth & Permissions → Redirect URLs → Add New Redirect URL**:
```
https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com/slack/oauth_redirect
```
Click **Save URLs**.

- [ ] **Step 2: Enable distribution**

Go to **Manage Distribution → Share Your App with Other Workspaces** → click **Activate Public Distribution** → confirm.

- [ ] **Step 3: Verify scopes**

Under **OAuth & Permissions**:
- Bot Token Scopes: `commands` ✓
- User Token Scopes: `users.profile:write` ✓

---

### Task 6: Update Lambda environment variables

**Files:** none — AWS console step

Go to **Lambda → slack-lunch-bot → Configuration → Environment variables → Edit**, add:

| Key | Value |
|---|---|
| `SLACK_CLIENT_ID` | From Basic Information → App Credentials |
| `SLACK_CLIENT_SECRET` | From Basic Information → App Credentials |
| `SLACK_REDIRECT_URI` | `https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com/slack/oauth_redirect` |
| `APP_BASE_URL` | `https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com` |

Remove: `SLACK_USER_TOKEN` (no longer needed).

Click **Save**.

---

### Task 7: Update API Gateway route

**Files:** none — AWS console step

The current route `ANY /slack-lunch-bot` only matches that one path. Bolt needs to serve `/slack/install` and `/slack/oauth_redirect` too.

Go to **API Gateway → your API → Routes**:
1. Delete the existing `ANY /slack-lunch-bot` route
2. Create new route: **ANY** with path `/{proxy+}`
3. Attach the same Lambda integration as before

The Slack app's slash command Request URL stays the same (`https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com/slack/events`) — Bolt handles that path automatically when using OAuth settings.

Update the slash command Request URL in your Slack app to:
```
https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com/slack/events
```

---

### Task 8: Rebuild and deploy

**Files:** none — build and upload step

- [ ] **Step 1: Rebuild the zip**

```bash
bash build.sh
```

Expected: `deployment.zip ready (X.XM)`

- [ ] **Step 2: Upload to Lambda**

**Lambda → Code tab → Upload from → .zip file** → select `deployment.zip` → Save.

- [ ] **Step 3: Verify handler is still set correctly**

**Code tab → Runtime settings → Edit** → confirm Handler is `lambda_handler.handler`.

---

### Task 9: End-to-end test

**Files:** none — manual testing

- [ ] **Step 1: Test the install URL**

Open in your browser:
```
https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com/slack/install
```

Expected: redirects to Slack OAuth page showing your app requesting permissions.

- [ ] **Step 2: Complete install in your test workspace**

Approve the OAuth prompt. Expected: redirected to a success page (Bolt shows a default "You can close this" page).

Check DynamoDB — **AWS Console → DynamoDB → Tables → slack-lunch-bot → Explore items**. You should see two records: a `bot` record and a `U#{your_user_id}` record.

- [ ] **Step 3: Test `/lunch` in Slack**

In your test workspace:

| Command | Expected |
|---|---|
| `/lunch a burger 30m` | 🍔 Status set to *Eating: Burger* for 30 minutes |
| `/lunch clear` | Status cleared |
| `/lunch` (no text) | Usage hint |

- [ ] **Step 4: Test unauthorised user flow**

If you have a second account in the test workspace, have them run `/lunch a salad`. Expected: ephemeral message with an authorise link. After they click and approve, `/lunch` should work for them too.
