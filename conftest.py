import os
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")

import bot_secrets

# Pre-populate secrets cache so main.py's module-level load_secrets() call
# doesn't hit AWS during tests.
bot_secrets._cache = {
    "SLACK_SIGNING_SECRET": "test-signing",
    "SLACK_CLIENT_ID": "test-id",
    "SLACK_CLIENT_SECRET": "test-secret",
    "ANTHROPIC_API_KEY": "test-key",
}
