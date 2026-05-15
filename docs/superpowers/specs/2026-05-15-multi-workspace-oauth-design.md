# Multi-Workspace OAuth — Design Spec

**Date:** 2026-05-15

## Overview

Add full multi-workspace distribution to the Slack Lunch Bot. Any workspace admin can install the app via an "Add to Slack" link. Each individual user authorises once to grant `users.profile:write`, and their token is stored in DynamoDB. The `/lunch` command looks up the calling user's token at runtime.

## Architecture

| Component | Change |
|---|---|
| `store.py` | New — DynamoDB `InstallationStore` implementation |
| `main.py` | Modified — initialise App with InstallationStore, look up user token per `/lunch` call |
| `lambda_handler.py` | No change |
| `llm.py` | No change |
| DynamoDB | New table: `slack-lunch-bot` |
| API Gateway | Route changed from `ANY /slack-lunch-bot` to `ANY /{proxy+}` |

## DynamoDB Table

**Table name:** `slack-lunch-bot`  
**Billing:** On-demand (pay-per-request, free tier covers this workload)

| Record type | PK | SK | Attributes |
|---|---|---|---|
| Workspace install | `T#{team_id}` | `bot` | `bot_token`, `app_id`, `installed_at` |
| User token | `T#{team_id}` | `U#{user_id}` | `user_token`, `authed_at` |

## OAuth Flows

### Workspace Install (one-time per workspace)
1. Admin clicks "Add to Slack" → `/slack/install` → Slack OAuth page
2. Admin approves bot scopes (`commands`) + user scopes (`users.profile:write`) in one flow
3. Slack redirects to `/slack/oauth_redirect` with auth code
4. Bolt exchanges code for tokens, calls `InstallationStore.save()`
5. `store.py` writes bot token (`T#{team_id}/bot`) and admin's user token (`T#{team_id}/U#{user_id}`) to DynamoDB

### First-Time User (per user)
1. User runs `/lunch` → app calls `InstallationStore.find_installation()` for their `user_id`
2. No user token found → ephemeral: "Before I can set your status, you need to connect your account. [Authorise →](install_url)"
3. User clicks link → `/slack/install` with `user_scope=users.profile:write` → approves
4. Token stored → user runs `/lunch` again, works from now on

### Subsequent `/lunch` Calls
1. Look up user token from DynamoDB by `team_id` + `user_id`
2. Call `users.profile.set` with that token
3. Respond with confirmation

## Error Handling

| Scenario | Response |
|---|---|
| User not yet authorised | Ephemeral with authorise link — not an error |
| DynamoDB read fails | Ephemeral: "Something went wrong — try again in a moment" |
| Token revoked / profile set fails | Ephemeral: "Couldn't set your status — try re-authorising [link]" |
| Workspace uninstalls app | Bolt + InstallationStore handle token cleanup automatically |

## New Environment Variables (Lambda)

```
SLACK_CLIENT_ID=...         # Basic Information → App Credentials
SLACK_CLIENT_SECRET=...     # Basic Information → App Credentials
```

Remove: `SLACK_USER_TOKEN` (replaced by DynamoDB lookup)
Keep: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `ANTHROPIC_API_KEY`, `DEFAULT_LUNCH_DURATION_MINUTES`

Note: `SLACK_BOT_TOKEN` is still needed for local dev. In production, Bolt uses the InstallationStore to resolve the bot token per workspace.

## Slack App Config Changes

1. **Manage Distribution** → Enable public distribution
2. **OAuth & Permissions → Redirect URLs** → add: `https://rs21458dog.execute-api.ap-southeast-2.amazonaws.com/slack/oauth_redirect`
3. **User Token Scopes** → confirm `users.profile:write` is present (already done)
4. **Bot Token Scopes** → confirm `commands` is present (already done)

## API Gateway Change

Change the existing `ANY /slack-lunch-bot` route to `ANY /{proxy+}` so Bolt can serve:
- `POST /slack/events` — slash command
- `GET /slack/install` — OAuth start
- `GET /slack/oauth_redirect` — OAuth callback

## Out of Scope

- Token refresh (Slack user tokens don't expire)
- Workspace uninstall webhook handling beyond Bolt defaults
- Admin dashboard or token management UI
