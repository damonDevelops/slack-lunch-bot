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

_JUDGE_SYSTEM = """You are evaluating emoji selection quality for a Slack status bot. Given a food or drink description and the emoji that was chosen, decide if it was the best available pick from the allowed list JSON array.

CRITICAL GRADING RUBRIC (You MUST grade based on these rules):
1. Multi-item meals: The bot is instructed to pick the main dish (e.g., `:hamburger:` for burger & fries). If the main dish has no valid western emoji (like battered fish), it is instructed to pick the side (`:fries:`). Score this as "good". Do NOT suggest `:fish_cake:` (kamaboko) for fried fish.
2. Drinks: For smoothies and shakes, `:cup_with_straw:` or `:milk_glass:` are correct. Do NOT suggest solid food (like `:green_salad:`) for liquids.
3. Ambiguous/Mixed Items: For items like "Charcuterie" or "Dirty Chai Latte", accept the closest primary ingredient (`:cheese:`, `:meat_on_bone:`, `:coffee:`, or `:tea:`) as "good" since both are technically correct.
4. Soups/Broths: `:bowl_with_spoon:` is the standard correct vessel for miso, congee, and broths. Do not dock points requesting stew unless it is actually a chunky stew.

Rate it as one of:
- "good" — best or near-best choice available, or followed the rules above perfectly
- "could_be_better" — acceptable but a strictly more fitting emoji exists in the list
- "poor" — clearly wrong or confusing

Give a one-sentence reason. If the rating is not "good", name the better emoji.
Return only JSON: {"rating": "...", "reason": "..."}"""


def load_cases(path: str) -> list[str]:
    with open(path) as f:
        return yaml.safe_load(f)


def rating_to_score(rating: str) -> float:
    return _SCORES.get(rating, 0.0)


def judge_emoji(client: anthropic.Anthropic, food_input: str, chosen_emoji: str, allowed_emojis: list[str]) -> dict:
    # Dumping to a JSON string forces the LLM to treat it as a structured data array
    allowed_json = json.dumps(allowed_emojis)
    user_content = f"Food/drink: {food_input!r}\nChosen emoji: {chosen_emoji}\nAllowed emojis: {allowed_json}"
    
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        temperature=0,
        system=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = message.content[0].text.strip()
    # Strip markdown fences if present (e.g. ```json ... ```)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _make_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=load_secrets()["ANTHROPIC_API_KEY"])


def run_eval(cases: list[str], client: anthropic.Anthropic | None = None) -> float:
    if client is None:
        client = _make_client()
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
