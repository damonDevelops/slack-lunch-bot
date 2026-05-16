import os
import time
from dotenv import load_dotenv

load_dotenv()

from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.state_store import FileOAuthStateStore
from store import DynamoDBInstallationStore, get_system_default_duration
from llm import parse_lunch

installation_store = DynamoDBInstallationStore()

app = App(
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    oauth_settings=OAuthSettings(
        client_id=os.environ["SLACK_CLIENT_ID"],
        client_secret=os.environ["SLACK_CLIENT_SECRET"],
        scopes=["commands", "users:read"],
        user_scopes=["users.profile:write"],
        installation_store=installation_store,
        redirect_uri=os.environ.get("SLACK_REDIRECT_URI"),
        state_store=FileOAuthStateStore(expiration_seconds=300, base_dir="/tmp/slack-oauth-state"),
        install_page_rendering_enabled=False,
    ),
    process_before_response=True,
)

APP_BASE_URL = os.environ.get("APP_BASE_URL", "")


def resolve_default_duration(team_id: str) -> int:
    config = installation_store.get_workspace_config(team_id)
    if config:
        return config["default_duration_minutes"]
    return get_system_default_duration()


def _handle_config_command(args: str, user_id: str, team_id: str, client, respond):
    if not args:
        config = installation_store.get_workspace_config(team_id)
        if config:
            respond(f"Current workspace default is *{config['default_duration_minutes']} minutes* (workspace setting).")
        else:
            default = get_system_default_duration()
            respond(f"Current workspace default is *{default} minutes* (system default — no workspace override set).")
        return

    if args.lower() == "reset":
        user_info = client.users_info(user=user_id)["user"]
        if not (user_info.get("is_admin") or user_info.get("is_owner")):
            respond("Only workspace admins can change the lunch duration default.")
            return
        installation_store.delete_workspace_config(team_id)
        default = get_system_default_duration()
        respond(f"Workspace default reset. Using system default of *{default} minutes*.")
        return

    raw = args.rstrip("mM")
    try:
        minutes = int(raw)
        if minutes <= 0:
            raise ValueError
    except ValueError:
        respond("Please provide a valid duration, e.g. `/lunch config 45` or `/lunch config 45m`.")
        return

    user_info = client.users_info(user=user_id)["user"]
    if not (user_info.get("is_admin") or user_info.get("is_owner")):
        respond("Only workspace admins can change the lunch duration default.")
        return

    installation_store.save_workspace_config(team_id, minutes)
    respond(f"Workspace default lunch duration set to *{minutes} minutes*.")


@app.command("/lunch")
def handle_lunch_command(ack, body, client, respond, context):
    ack()

    user_text = body.get("text", "").strip()
    user_id = body["user_id"]
    team_id = body["team_id"]

    if user_text.lower().startswith("config"):
        args = user_text[len("config"):].strip()
        _handle_config_command(args, user_id, team_id, client, respond)
        return

    if not user_text:
        respond("Tell me what you're eating! e.g. `/lunch a spicy burrito 45m`")
        return

    installation = installation_store.find_installation(
        enterprise_id=context.get("enterprise_id"),
        team_id=team_id,
        user_id=user_id,
    )

    if not installation or not installation.user_token:
        install_url = f"{APP_BASE_URL}/slack/install"
        respond(f"Before I can set your status, connect your account first. <{install_url}|Authorise here →>")
        return

    if user_text.lower() in ("clear", "done"):
        try:
            client.users_profile_set(
                user=user_id,
                profile={"status_text": "", "status_emoji": "", "status_expiration": 0},
                token=installation.user_token,
            )
            respond("Status cleared.")
        except Exception:
            install_url = f"{APP_BASE_URL}/slack/install"
            respond(f"Couldn't clear your status — try re-authorising. <{install_url}|Authorise here →>")
        return

    try:
        result = parse_lunch(user_text)
    except Exception:
        respond("Couldn't figure out that lunch — try describing it differently.")
        return

    duration = result.get("duration_minutes") or resolve_default_duration(team_id)
    expiration = int(time.time()) + duration * 60

    try:
        client.users_profile_set(
            user=user_id,
            profile={
                "status_text": f"Eating: {result['status_text']}",
                "status_emoji": result["emoji"],
                "status_expiration": expiration,
            },
            token=installation.user_token,
        )
    except Exception:
        install_url = f"{APP_BASE_URL}/slack/install"
        respond(f"Couldn't set your status — try re-authorising. <{install_url}|Authorise here →>")
        return

    respond(f"{result['emoji']} Status set to *Eating: {result['status_text']}* for {duration} minutes.")


if __name__ == "__main__":
    app.start(port=3000)
