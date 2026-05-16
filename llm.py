import json
import logging
import re
import time
import anthropic
from bot_secrets import load_secrets

logger = logging.getLogger(__name__)

FALLBACK_EMOJI = ":fork_and_knife_with_plate:"
_EMOJI_RE = re.compile(r'^:[a-z0-9_+-]+:$')

# Built-in Slack food/drink emoji shortcodes (all valid aliases included).
BUILTIN_FOOD_EMOJIS = [
    # Fruit
    ":grapes:", ":melon:", ":watermelon:", ":mandarin:", ":orange:", ":tangerine:",
    ":lemon:", ":banana:", ":pineapple:", ":mango:", ":apple:", ":green_apple:",
    ":pear:", ":peach:", ":cherries:", ":strawberry:", ":blueberries:", ":kiwi_fruit:",
    ":tomato:", ":olive:", ":coconut:",
    # Vegetables
    ":avocado:", ":eggplant:", ":potato:", ":carrot:", ":corn:", ":hot_pepper:",
    ":bell_pepper:", ":cucumber:", ":leafy_green:", ":broccoli:", ":garlic:",
    ":onion:", ":peanuts:", ":chestnut:",
    # Prepared food
    ":bread:", ":croissant:", ":baguette_bread:", ":flatbread:", ":pretzel:", ":bagel:",
    ":pancakes:", ":waffle:", ":cheese:", ":meat_on_bone:", ":poultry_leg:",
    ":cut_of_meat:", ":bacon:", ":hamburger:", ":fries:", ":pizza:", ":hotdog:",
    ":sandwich:", ":taco:", ":burrito:", ":tamale:", ":stuffed_flatbread:", ":falafel:",
    ":egg:", ":fried_egg:", ":shallow_pan_of_food:", ":stew:", ":fondue:",
    ":bowl_with_spoon:", ":green_salad:", ":popcorn:", ":butter:", ":salt:", ":canned_food:",
    # Asian food
    ":bento:", ":rice_cracker:", ":rice_ball:", ":rice:", ":curry:", ":ramen:",
    ":spaghetti:", ":sweet_potato:", ":oden:", ":sushi:", ":fried_shrimp:", ":fish_cake:",
    ":moon_cake:", ":dango:", ":dumpling:", ":fortune_cookie:", ":takeout_box:",
    # Seafood
    ":crab:", ":lobster:", ":shrimp:", ":squid:", ":oyster:",
    # Sweets
    ":icecream:", ":shaved_ice:", ":ice_cream:", ":doughnut:", ":cookie:", ":birthday:",
    ":cake:", ":cupcake:", ":pie:", ":chocolate_bar:", ":candy:", ":lollipop:",
    ":custard:", ":honey_pot:",
    # Drinks
    ":baby_bottle:", ":milk_glass:", ":coffee:", ":teapot:", ":tea:", ":sake:",
    ":champagne:", ":wine_glass:", ":cocktail:", ":tropical_drink:", ":beer:", ":beers:",
    ":clinking_glasses:", ":tumbler_glass:", ":cup_with_straw:", ":bubble_tea:",
    ":beverage_box:", ":mate:", ":ice_cube:",
    # Dishware / generic
    ":chopsticks:", ":plate_with_cutlery:", ":fork_and_knife:", ":spoon:",
    ":hocho:", ":knife:", ":amphora:", ":fork_and_knife_with_plate:",
]

_emoji_cache: dict[str, tuple[float, list[str]]] = {}
_EMOJI_CACHE_TTL = 3600  # 1 hour; resets naturally on Lambda cold start


def get_workspace_emoji_list(client, team_id: str) -> list[str]:
    """Return built-in food emojis merged with the workspace's custom emojis, cached per team."""
    cached = _emoji_cache.get(team_id)
    if cached and time.time() - cached[0] < _EMOJI_CACHE_TTL:
        return cached[1]

    custom: list[str] = []
    try:
        response = client.emoji_list()
        custom = [f":{name}:" for name in response.get("emoji", {}).keys()]
        logger.info("Fetched %d custom emojis for team %s", len(custom), team_id)
    except Exception:
        logger.warning("Failed to fetch custom emojis for team %s, using built-ins only", team_id)

    combined = BUILTIN_FOOD_EMOJIS + custom
    _emoji_cache[team_id] = (time.time(), combined)
    return combined


_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=load_secrets()["ANTHROPIC_API_KEY"])
    return _client


_SYSTEM_PROMPT_BASE = """You are a Slack status assistant. Given a description of what someone is eating for lunch, return ONLY a valid JSON object with exactly these three fields:

- "emoji": the Slack emoji shortcode that best represents the food. Be creative — pick the closest thematic match even if it is not exact (e.g. use `:green_salad:` for salad, `:bowl_with_spoon:` for a grain bowl, `:ramen:` for any noodle soup). Only use `:fork_and_knife_with_plate:` as a last resort if nothing is even remotely appropriate.
- "status_text": preserve the user's original phrasing as closely as possible — keep descriptive words like "greasy", "spicy", "a big bowl of". Strip any duration mention (e.g. "45m", "1h", "for 30 minutes"). Only condense if the result would exceed 90 characters. No "Eating:" prefix.
- "duration_minutes": an integer parsed from any duration in the input (e.g. "1h" → 60, "45m" → 45, "1.5h" → 90), or null if no duration is mentioned.

Return ONLY the JSON object. No explanation, no markdown, no code fences."""

_SYSTEM_PROMPT_WITH_LIST = """You are a Slack status assistant. Given a description of what someone is eating for lunch, return ONLY a valid JSON object with exactly these three fields:

- "emoji": the Slack emoji shortcode from the allowed list below that best represents the food. Be creative — pick the closest thematic match even if it is not exact (e.g. use `:green_salad:` for salad, `:bowl_with_spoon:` for a grain bowl, `:ramen:` for any noodle soup). Only use `:fork_and_knife_with_plate:` if nothing else is even remotely appropriate.
- "status_text": preserve the user's original phrasing as closely as possible — keep descriptive words like "greasy", "spicy", "a big bowl of". Strip any duration mention (e.g. "45m", "1h", "for 30 minutes"). Only condense if the result would exceed 90 characters. No "Eating:" prefix.
- "duration_minutes": an integer parsed from any duration in the input (e.g. "1h" → 60, "45m" → 45, "1.5h" → 90), or null if no duration is mentioned.

Return ONLY the JSON object. No explanation, no markdown, no code fences.

Allowed emojis: {emoji_list}"""


def parse_lunch(user_text: str, emoji_allowlist: list[str] | None = None) -> dict:
    if emoji_allowlist:
        system_prompt = _SYSTEM_PROMPT_WITH_LIST.format(emoji_list=" ".join(emoji_allowlist))
    else:
        system_prompt = _SYSTEM_PROMPT_BASE

    message = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        temperature=0.2,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": "```json"},
        ],
        stop_sequences=["```"],
    )
    raw_text = message.content[0].text.strip()
    logger.info("LLM raw response for %r: %s", user_text, raw_text)
    result = json.loads(raw_text)
    if not isinstance(result.get("status_text"), str) or not isinstance(result.get("emoji"), str):
        raise ValueError(f"LLM returned invalid output: {result}")
    # Normalize emoji to :name: format, then validate against the allowlist.
    # If it's not in the allowlist (or malformed), use the fallback rather than
    # letting Slack reject it at the API level.
    raw_emoji = result["emoji"]
    emoji = raw_emoji.strip()
    if not emoji.startswith(":"):
        emoji = f":{emoji}"
    if not emoji.endswith(":"):
        emoji = f"{emoji}:"
    if not _EMOJI_RE.match(emoji):
        logger.warning("Emoji %r failed format validation, using fallback", raw_emoji)
        emoji = FALLBACK_EMOJI
    elif emoji_allowlist and emoji not in emoji_allowlist:
        logger.warning("Emoji %r not in allowlist, using fallback", emoji)
        emoji = FALLBACK_EMOJI
    result["emoji"] = emoji
    logger.info("Parsed lunch result: status_text=%r emoji=%r duration_minutes=%r",
                result["status_text"], result["emoji"], result.get("duration_minutes"))
    return result
