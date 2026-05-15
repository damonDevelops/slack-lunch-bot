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
