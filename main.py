import os
from slack_bolt import App

# Initialize your app with your tokens
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Listen for the /lunch command
@app.command("/lunch")
def handle_lunch_command(ack, body, client):
    # Acknowledge the command request immediately (Slack requires this within 3 seconds)
    ack()
    
    # 1. Grab what the user typed (e.g., "a spicy burrito")
    user_text = body["text"]
    user_id = body["user_id"]
    
    # 2. Vibe check with the LLM (Psuedocode)
    # emoji = ask_llm_for_emoji(user_text)
    
    # 3. Update the user's status!
    client.users_profile_set(
        user=user_id,
        profile={
            "status_text": f"Eating: {user_text}",
            "status_emoji": emoji,
            "status_expiration": 0 # You can calculate a unix timestamp for 1 hour from now!
        }
    )

# Start your local server
if __name__ == "__main__":
    app.start(port=3000)