# Slack Lunch Status Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a `/lunch` Slack slash command that uses Claude to pick a fitting emoji and parse duration, then sets the user's Slack status accordingly.

**Architecture:** A Slack Bolt app in `main.py` handles the `/lunch` command. `llm.py` encapsulates the Claude API call and returns structured JSON. `main.py` converts the result into a Slack `users.profile.set` call with a computed expiration timestamp.

**Tech Stack:** Python 3.11+, `slack-bolt`, `anthropic`, `python-dotenv`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Create | Pin all dependencies |
| `.env.example` | Create | Document required env vars |
| `llm.py` | Create | Claude API call, prompt, JSON parsing |
| `test_llm.py` | Create | Standalone smoke-test script for llm.py |
| `main.py` | Modify (full rewrite) | Slack Bolt app, command handlers |

---

### Task 1: Project setup

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: Create `requirements.txt`**

```
slack-bolt>=1.18
anthropic>=0.25
python-dotenv>=1.0
```

- [ ] **Step 2: Create `.env.example`**

```
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
DEFAULT_LUNCH_DURATION_MINUTES=30
```

- [ ] **Step 3: Copy `.env.example` to `.env` and fill in your real values**

```bash
cp .env.example .env
# Edit .env with your actual tokens
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: packages install without errors.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example
git commit -m "chore: add dependencies and env template"
```

---

### Task 2: Write `test_llm.py` (before implementing `llm.py`)

**Files:**
- Create: `test_llm.py`

Write the test script first so we can verify `llm.py` works end-to-end once it exists.

- [ ] **Step 1: Create `test_llm.py`**

```python
from dotenv import load_dotenv
load_dotenv()

import json
from llm import parse_lunch

cases = [
    "a spicy burrito 45m",
    "pulled pork tacos 1h",
    "a caesar salad",
    "fish and chips 30m",
    "leftover pasta",
    "a green smoothie 20m",
]

for case in cases:
    print(f"\nInput:  {case!r}")
    try:
        result = parse_lunch(case)
        print(f"Output: {json.dumps(result)}")
        assert "emoji" in result, "missing 'emoji'"
        assert "status_text" in result, "missing 'status_text'"
        assert "duration_minutes" in result, "missing 'duration_minutes'"
        print("       OK")
    except Exception as e:
        print(f"ERROR: {e}")
```

- [ ] **Step 2: Run it to confirm it fails with ImportError**

```bash
python test_llm.py
```

Expected output:
```
ModuleNotFoundError: No module named 'llm'
```

(This confirms the test is wired up before the implementation exists.)

- [ ] **Step 3: Commit**

```bash
git add test_llm.py
git commit -m "test: add standalone smoke test for llm.parse_lunch"
```

---

### Task 3: Implement `llm.py`

**Files:**
- Create: `llm.py`

- [ ] **Step 1: Create `llm.py`**

```python
import os
import json
import anthropic

_client = anthropic.Anthropic()

_SYSTEM_PROMPT = """You are a Slack status assistant. Given a description of what someone is eating for lunch, return ONLY a valid JSON object with exactly these three fields:

- "emoji": a standard Slack emoji code that fits the food (e.g. ":burrito:", ":salad:", ":pizza:", ":sushi:"). Use only emoji codes that exist in every Slack workspace — no custom emoji.
- "status_text": a clean, concise description of the food, max 30 characters, no "Eating:" prefix.
- "duration_minutes": an integer parsed from any duration in the input (e.g. "1h" → 60, "45m" → 45, "1.5h" → 90), or null if no duration is mentioned.

Return ONLY the JSON object. No explanation, no markdown, no code fences."""


def parse_lunch(user_text: str) -> dict:
    message = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_text}],
    )
    raw = message.content[0].text.strip()
    return json.loads(raw)
```

- [ ] **Step 2: Run `test_llm.py` to verify all cases pass**

```bash
python test_llm.py
```

Expected: six inputs each print an `Output:` line with valid JSON and `OK`. No `ERROR:` lines. Example:

```
Input:  'a spicy burrito 45m'
Output: {"emoji": ":burrito:", "status_text": "Spicy burrito", "duration_minutes": 45}
       OK

Input:  'a caesar salad'
Output: {"emoji": ":salad:", "status_text": "Caesar salad", "duration_minutes": null}
       OK
```

- [ ] **Step 3: Commit**

```bash
git add llm.py
git commit -m "feat: add llm.parse_lunch using Claude"
```

---

### Task 4: Implement `main.py`

**Files:**
- Modify: `main.py` (full rewrite of the existing scaffold)

- [ ] **Step 1: Replace the contents of `main.py` with the full implementation**

```python
import os
import time
from dotenv import load_dotenv

load_dotenv()

from slack_bolt import App
from llm import parse_lunch

app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)

DEFAULT_DURATION = int(os.environ.get("DEFAULT_LUNCH_DURATION_MINUTES", "30"))


@app.command("/lunch")
def handle_lunch_command(ack, body, client, respond):
    ack()

    user_text = body.get("text", "").strip()
    user_id = body["user_id"]

    if not user_text:
        respond("Tell me what you're eating! e.g. `/lunch a spicy burrito 45m`")
        return

    if user_text.lower() in ("clear", "done"):
        try:
            client.users_profile_set(
                user=user_id,
                profile={"status_text": "", "status_emoji": "", "status_expiration": 0},
            )
            respond("Status cleared.")
        except Exception:
            respond("Couldn't clear your status — check the app has the right permissions.")
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
        )
    except Exception:
        respond("Couldn't set your status — check the app has the right permissions.")
        return

    respond(f"{result['emoji']} Status set to *Eating: {result['status_text']}* for {duration} minutes.")


if __name__ == "__main__":
    app.start(port=3000)
```

- [ ] **Step 2: Start the app locally to verify it boots without errors**

```bash
python main.py
```

Expected output:
```
⚡️ Bolt app is running! (development server)
```

Press Ctrl+C to stop.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: implement /lunch command with Claude emoji picking and status expiry"
```

---

### Task 5: End-to-end test with ngrok

**Files:** none — manual testing step

- [ ] **Step 1: Install ngrok if you don't have it**

```bash
brew install ngrok
```

- [ ] **Step 2: Start the app**

```bash
python main.py
```

- [ ] **Step 3: In a separate terminal, start ngrok**

```bash
ngrok http 3000
```

Copy the `Forwarding` HTTPS URL, e.g. `https://abc123.ngrok.io`.

- [ ] **Step 4: Update your Slack app's slash command request URL**

Go to [api.slack.com/apps](https://api.slack.com/apps) → your app → **Slash Commands** → `/lunch` → edit → set **Request URL** to:

```
https://abc123.ngrok.io/slack/events
```

Save.

- [ ] **Step 5: Test each command in Slack**

In any channel or DM in your workspace:

| Command | Expected behaviour |
|---|---|
| `/lunch` | Ephemeral usage hint |
| `/lunch a spicy burrito 45m` | Status set to 🌯 Eating: Spicy burrito for 45 minutes |
| `/lunch leftover pasta` | Status set with emoji, uses DEFAULT_LUNCH_DURATION_MINUTES |
| `/lunch clear` | Status cleared |
| `/lunch done` | Status cleared |

- [ ] **Step 6: Commit any fixes found during testing, then final commit**

```bash
git add -p
git commit -m "fix: <describe anything you fixed>"
```
