import logging
import os
import time

from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from store import DynamoDBInstallationStore, DynamoDBOAuthStateStore, get_system_default_duration
from llm import parse_lunch, get_workspace_emoji_list, FALLBACK_EMOJI
from bot_secrets import load_secrets

logger = logging.getLogger(__name__)

installation_store = DynamoDBInstallationStore()
_secrets = load_secrets()

app = App(
    signing_secret=_secrets["SLACK_SIGNING_SECRET"],
    oauth_settings=OAuthSettings(
        client_id=_secrets["SLACK_CLIENT_ID"],
        client_secret=_secrets["SLACK_CLIENT_SECRET"],
        scopes=["commands", "users:read", "emoji:read"],
        user_scopes=["users.profile:write"],
        installation_store=installation_store,
        redirect_uri=os.environ.get("SLACK_REDIRECT_URI"),
        state_store=DynamoDBOAuthStateStore(),
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
        if minutes <= 0 or minutes > 480:
            raise ValueError
    except ValueError:
        respond("Please provide a duration between 1 and 480 minutes, e.g. `/lunch config 45`.")
        return

    user_info = client.users_info(user=user_id)["user"]
    if not (user_info.get("is_admin") or user_info.get("is_owner")):
        respond("Only workspace admins can change the lunch duration default.")
        return

    installation_store.save_workspace_config(team_id, minutes)
    respond(f"Workspace default lunch duration set to *{minutes} minutes*.")


def _ack_lunch(ack):
    ack()


def _handle_lunch_lazy(body, client, respond, context):
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
            logger.exception("Failed to clear Slack status for user %s in team %s", user_id, team_id)
            install_url = f"{APP_BASE_URL}/slack/install"
            respond(f"Couldn't clear your status — try re-authorising. <{install_url}|Authorise here →>")
        return

    emoji_list = get_workspace_emoji_list(client, team_id)
    try:
        result = parse_lunch(user_text, emoji_allowlist=emoji_list)
    except Exception:
        logger.exception("Failed to parse lunch text %r for user %s", user_text, user_id)
        respond("Couldn't figure out that lunch — try describing it differently.")
        return

    duration = min(int(result.get("duration_minutes") or resolve_default_duration(team_id)), 480)
    expiration = int(time.time()) + duration * 60

    token_prefix = (installation.user_token or "")[:10]
    logger.info("Setting status for user %s: emoji=%r text=%r expiration=%s token_prefix=%s",
                user_id, result["emoji"], result["status_text"], expiration, token_prefix)
    try:
        client.users_profile_set(
            user=user_id,
            profile={
                "status_text": f"{result['verb']}: {result['status_text']}",
                "status_emoji": result["emoji"],
                "status_expiration": expiration,
            },
            token=installation.user_token,
        )
    except Exception as exc:
        logger.exception("Failed to set Slack status for user %s in team %s", user_id, team_id)
        response = getattr(exc, "response", None)
        error_code = response["error"] if response is not None else ""
        if error_code == "profile_status_set_failed_not_valid_emoji":
            respond("Couldn't set your status — that emoji doesn't exist in Slack. Try describing your lunch differently.")
        else:
            install_url = f"{APP_BASE_URL}/slack/install"
            respond(f"Couldn't set your status — try re-authorising. <{install_url}|Authorise here →>")
        return

    verb = result["verb"]
    if result["emoji"] == FALLBACK_EMOJI:
        respond(f"{result['emoji']} Status set to *{verb}: {result['status_text']}* for {duration} minutes. _no emoji for that meal... how fancy_")
    else:
        respond(f"{result['emoji']} Status set to *{verb}: {result['status_text']}* for {duration} minutes.")


app.command("/lunch")(ack=_ack_lunch, lazy=[_handle_lunch_lazy])


if __name__ == "__main__":
    app.start(port=3000)
