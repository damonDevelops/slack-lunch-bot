# Slack Lunch Status Bot — Design Spec

**Date:** 2026-05-15

## Overview

A Slack slash command bot that lets users set their Slack status to what they're eating for lunch, with an AI-picked emoji and optional duration. The user types natural language; Claude handles parsing, emoji selection, and status text cleanup.

## User-Facing Commands

| Command | Behaviour |
|---|---|
| `/lunch a spicy burrito 45m` | Sets status to 🌯 Eating: Spicy burrito for 45 minutes |
| `/lunch pulled pork tacos 1h` | Sets status to 🌮 Eating: Pulled pork tacos for 1 hour |
| `/lunch a salad` | Sets status with no expiry (uses `DEFAULT_LUNCH_DURATION_MINUTES` from env) |
| `/lunch clear` or `/lunch done` | Clears status immediately |
| `/lunch` (no text) | Ephemeral usage hint |

## Architecture

Three files:

- **`main.py`** — Slack Bolt app entry point; registers command handlers, wires up the flow
- **`llm.py`** — Claude API call, system prompt, JSON response parsing
- **`.env`** — secrets and configuration (never committed)

### Request Flow

```
User: /lunch a spicy burrito 45m
  → Bolt: ack() immediately
  → llm.parse_lunch("a spicy burrito 45m")
      → Claude returns { "emoji": ":burrito:", "status_text": "Spicy burrito", "duration_minutes": 45 }
  → Compute status_expiration unix timestamp (now + 45 min), or 0 if null
  → client.users_profile_set(...)
  → Ephemeral reply: "🌯 Status set to *Spicy burrito* for 45 minutes"
```

## LLM Design (`llm.py`)

**System prompt instructs Claude to:**
- Return only valid JSON, no prose
- Pick a standard Slack emoji code (e.g. `:burrito:`, `:salad:`) — no custom workspace emojis
- Produce a clean short status text (≤30 chars), no "Eating:" prefix (app prepends it)
- Parse duration from the input (`1h` → 60, `45m` → 45, `1.5h` → 90) and return as `duration_minutes` integer, or `null` if absent

**Response schema:**
```json
{
  "emoji": ":burrito:",
  "status_text": "Spicy burrito",
  "duration_minutes": 45
}
```

**Fallback:** If `duration_minutes` is `null`, the app uses `DEFAULT_LUNCH_DURATION_MINUTES` from env (e.g. `30`).

## Configuration (`.env`)

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LUNCH_DURATION_MINUTES=30
```

`DEFAULT_LUNCH_DURATION_MINUTES` is org-configurable — change it without touching code.

## Error Handling

| Scenario | Behaviour |
|---|---|
| `/lunch` with no text | Ephemeral: "Tell me what you're eating! e.g. `/lunch a spicy burrito 45m`" |
| Claude returns malformed JSON | Ephemeral: "Couldn't figure out that lunch — try describing it differently" |
| Slack API call fails (e.g. missing scope) | Ephemeral: "Couldn't set your status — check the app has the right permissions" |
| `/lunch clear` or `/lunch done` | Clears status, ephemeral: "Status cleared" |

## Slack App Requirements

The Slack app (created at api.slack.com) needs:

- **Slash command:** `/lunch` pointing at `POST /slack/events`
- **OAuth scopes:** `commands`, `users.profile:write`, `chat:write` (for ephemeral messages)
- **Socket Mode or HTTP:** HTTP via ngrok for local dev; proper URL for production

## Testing

- **`test_llm.py`** — standalone script, no Slack needed. Fires a handful of food descriptions at Claude and prints parsed results. Run with `python test_llm.py`.
- **Manual e2e** — `ngrok http 3000` to tunnel localhost, update Slack app's request URL, test in a real workspace.

## Out of Scope

- Slack modals / multi-step UI
- Status history or logging
- Multi-workspace / OAuth installation flow
- Pytest / full test suite
