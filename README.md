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

## Prompt Evaluator

`eval_prompt.py` runs a set of lunch descriptions through the LLM and grades each emoji choice using a second Claude call as a judge. Use it to measure prompt quality and compare versions objectively.

### Setup

Copy `.env.example` to `.env` and add your Anthropic API key:

```bash
cp .env.example .env
# then edit .env and fill in your key
```

### Running

```bash
python eval_prompt.py
```

Each case prints the chosen emoji, a rating (`good` / `could_be_better` / `poor`), and the judge's reasoning. A final average score (0.00–1.00) is printed at the end.

To save results for comparison across prompt versions:

```bash
python eval_prompt.py > results/v1.txt
grep "Score:" results/v1.txt results/v2.txt
```

Test cases live in `eval_cases.yaml`. Add new cases any time you spot a real-world input that produced a questionable emoji.

## License

AGPL v3
