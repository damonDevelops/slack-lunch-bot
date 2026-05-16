from dotenv import load_dotenv
load_dotenv()

import json
import sys
import anthropic
import yaml
from llm import parse_lunch, BUILTIN_FOOD_EMOJIS
from bot_secrets import load_secrets

_SCORES = {"good": 1.0, "could_be_better": 0.5, "poor": 0.0}
_SYMBOLS = {"good": "✓", "could_be_better": "~", "poor": "✗", "error": "!"}

_JUDGE_SYSTEM = """You are evaluating emoji selection quality for a Slack status bot. Given a food or drink description and the emoji that was chosen, decide if it was the best available pick from the allowed list.

Rate it as one of:
- "good" — best or near-best choice available
- "could_be_better" — acceptable but a more fitting emoji exists in the list
- "poor" — clearly wrong, confusing, or a generic fallback was used when a better option existed

Give a one-sentence reason. If the rating is not "good", name the better emoji.
Return only JSON: {"rating": "...", "reason": "..."}"""


def load_cases(path: str) -> list[str]:
    with open(path) as f:
        return yaml.safe_load(f)


def rating_to_score(rating: str) -> float:
    return _SCORES.get(rating, 0.0)


def judge_emoji(client: anthropic.Anthropic, food_input: str, chosen_emoji: str, allowed_emojis: list[str]) -> dict:
    emoji_list = " ".join(allowed_emojis)
    user_content = f"Food/drink: {food_input!r}\nChosen emoji: {chosen_emoji}\nAllowed emojis: {emoji_list}"
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        temperature=0,
        system=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    return json.loads(message.content[0].text.strip())


def run_eval(cases: list[str], client: anthropic.Anthropic | None = None) -> float:
    if client is None:
        client = anthropic.Anthropic(api_key=load_secrets()["ANTHROPIC_API_KEY"])
    total = len(cases)
    scores: list[float] = []
    counts: dict[str, int] = {"good": 0, "could_be_better": 0, "poor": 0, "error": 0}

    for i, food_input in enumerate(cases, 1):
        print(f"[{i}/{total}] {food_input!r}")

        try:
            result = parse_lunch(food_input, BUILTIN_FOOD_EMOJIS)
            chosen_emoji = result["emoji"]
        except Exception as e:
            print(f"       ! error (0.0) — parse_lunch failed: {e}")
            scores.append(0.0)
            counts["error"] += 1
            continue

        try:
            judgment = judge_emoji(client, food_input, chosen_emoji, BUILTIN_FOOD_EMOJIS)
            rating = judgment.get("rating", "error")
            if rating not in _SCORES:
                raise ValueError(f"unexpected rating: {rating!r}")
            reason = judgment.get("reason", "")
        except Exception as e:
            print(f"       ! error (0.0) — judge failed: {e}")
            scores.append(0.0)
            counts["error"] += 1
            continue

        score = rating_to_score(rating)
        scores.append(score)
        counts[rating] = counts.get(rating, 0) + 1
        symbol = _SYMBOLS[rating]
        print(f"       Emoji: {chosen_emoji}  {symbol} {rating} ({score:.1f}) — {reason}")

    avg = sum(scores) / len(scores) if scores else 0.0
    print(
        f"\nScore: {avg:.2f} / 1.00"
        f"  (good: {counts['good']}, could_be_better: {counts['could_be_better']},"
        f" poor: {counts['poor']}, error: {counts['error']})"
    )
    return avg


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "eval_cases.yaml"
    cases = load_cases(path)
    run_eval(cases)
