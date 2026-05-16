# Lunchbot

Set your Slack status to what you're eating, with the right emoji. Just type `/lunch` and let AI do the rest.

```text
/lunch a spicy burrito 45m
```

Lunchbot picks a fitting emoji, sets your status text, and clears it automatically when time's up.

## Commands

| Command | What it does |
| --- | --- |
| `/lunch [what you're eating]` | Sets your status with a matching emoji |
| `/lunch [what you're eating] 45m` | Sets status for a specific duration |
| `/lunch clear` or `/lunch done` | Clears your status early |
| `/lunch config` | Shows the workspace default duration |
| `/lunch config 45` | Sets workspace default duration — admins only |
| `/lunch config reset` | Resets to system default — admins only |

Duration defaults to the workspace setting if not specified (system default: 30 minutes).

## How it's built

- **[Slack Bolt](https://github.com/slackapi/bolt-python)** — handles slash commands and OAuth
- **[Claude](https://anthropic.com) (Haiku)** — parses the lunch description into an emoji and status text
- **AWS Lambda** — runs the bot serverlessly, with EventBridge pings to prevent cold starts
- **DynamoDB** — stores OAuth installations and per-workspace config
- **AWS CDK** — infrastructure as code

## License

AGPL v3
