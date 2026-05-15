import os
import time
from dotenv import load_dotenv

load_dotenv()

from slack_bolt import App
from llm import parse_lunch

app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)

DEFAULT_DURATION = int(os.environ.get("DEFAULT_LUNCH_DURATION_MINUTES", "30"))


@app.command("/lunch")
def handle_lunch_command(ack, body, client, respond):
    ack()

    user_text = body.get("text", "").strip()
    user_id = body["user_id"]

    if not user_text:
        respond("Tell me what you're eating! e.g. `/lunch a spicy burrito 45m`")
        return

    if user_text.lower() in ("clear", "done"):
        try:
            client.users_profile_set(
                user=user_id,
                profile={"status_text": "", "status_emoji": "", "status_expiration": 0},
                token=os.environ["SLACK_USER_TOKEN"],
            )
            respond("Status cleared.")
        except Exception:
            respond("Couldn't clear your status — check the app has the right permissions.")
        return

    try:
        result = parse_lunch(user_text)
    except Exception:
        respond("Couldn't figure out that lunch — try describing it differently.")
        return

    duration = result.get("duration_minutes") or DEFAULT_DURATION
    expiration = int(time.time()) + duration * 60

    try:
        client.users_profile_set(
            user=user_id,
            profile={
                "status_text": f"Eating: {result['status_text']}",
                "status_emoji": result["emoji"],
                "status_expiration": expiration,
            },
            token=os.environ["SLACK_USER_TOKEN"],
        )
    except Exception:
        respond("Couldn't set your status — check the app has the right permissions.")
        return

    respond(f"{result['emoji']} Status set to *Eating: {result['status_text']}* for {duration} minutes.")


if __name__ == "__main__":
    app.start(port=3000)
