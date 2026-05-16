import json
import re
import anthropic
from bot_secrets import load_secrets

FALLBACK_EMOJI = ":fork_and_knife_with_plate:"
_EMOJI_RE = re.compile(r'^:[a-z0-9_+-]+:$')

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=load_secrets()["ANTHROPIC_API_KEY"])
    return _client

_SYSTEM_PROMPT = """You are a Slack status assistant. Given a description of what someone is eating for lunch, return ONLY a valid JSON object with exactly these three fields:

- "emoji": a standard Slack emoji code that fits the food (e.g. ":burrito:", ":salad:", ":pizza:", ":sushi:"). Use only emoji codes that exist in every Slack workspace — no custom emoji.
- "status_text": a clean, concise description of the food, max 30 characters, no "Eating:" prefix.
- "duration_minutes": an integer parsed from any duration in the input (e.g. "1h" → 60, "45m" → 45, "1.5h" → 90), or null if no duration is mentioned.

Return ONLY the JSON object. No explanation, no markdown, no code fences."""


def parse_lunch(user_text: str) -> dict:
    message = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system=_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": "```json"},
        ],
        stop_sequences=["```"],
    )
    result = json.loads(message.content[0].text.strip())
    if not isinstance(result.get("status_text"), str) or not isinstance(result.get("emoji"), str):
        raise ValueError(f"LLM returned invalid output: {result}")
    # Normalize emoji to :name: format; fall back if it doesn't match
    emoji = result["emoji"].strip()
    if not emoji.startswith(":"):
        emoji = f":{emoji}"
    if not emoji.endswith(":"):
        emoji = f"{emoji}:"
    result["emoji"] = emoji if _EMOJI_RE.match(emoji) else FALLBACK_EMOJI
    return result
