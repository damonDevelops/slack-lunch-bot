from unittest.mock import MagicMock, patch
from slack_sdk.oauth.installation_store import Installation

import main
from main import _handle_lunch_lazy


class _SlackApiError(Exception):
    def __init__(self, error_code):
        self.response = {"error": error_code}


def _installation(user_token="xoxp-test"):
    inst = MagicMock(spec=Installation)
    inst.user_token = user_token
    return inst


def _body(text="a spicy burrito"):
    return {"text": text, "user_id": "U123", "team_id": "T123"}


def _parse_result(emoji=":burrito:", duration=None):
    return {"emoji": emoji, "status_text": "a spicy burrito", "verb": "Eating", "duration_minutes": duration}


def _run(body, client=None, parse_result=None, side_effects=None, workspace_default=30):
    respond = MagicMock()
    client = client or MagicMock()
    if side_effects is not None:
        client.users_profile_set.side_effect = side_effects
    with (
        patch.object(main.installation_store, "find_installation", return_value=_installation()),
        patch("main.get_workspace_emoji_list", return_value=[":burrito:"]),
        patch("main.parse_lunch", return_value=parse_result or _parse_result()),
        patch("main.resolve_default_duration", return_value=workspace_default),
    ):
        _handle_lunch_lazy(body=body, client=client, respond=respond, context={})
    return respond


# --- duration_minutes bug fix ---

def test_duration_minutes_zero_uses_zero_not_workspace_default():
    # Bug: `result.get("duration_minutes") or default` treats 0 as falsy and
    # falls back to the workspace default. It should respect the explicit 0.
    respond = _run(_body("a burrito 0m"), parse_result=_parse_result(duration=0), workspace_default=30)
    call_text = respond.call_args[0][0]
    assert "for 0 minutes" in call_text


# --- emoji retry loop ---

def test_invalid_emoji_retries_with_fallback_and_sends_quirky_message():
    # First call raises invalid-emoji error; second (fallback) succeeds.
    side_effects = [
        _SlackApiError("profile_status_set_failed_not_valid_emoji"),
        None,  # fallback call succeeds
    ]
    respond = _run(_body(), side_effects=side_effects)
    call_text = respond.call_args[0][0]
    assert "no emoji for that meal" in call_text


def test_invalid_emoji_and_invalid_fallback_returns_error():
    # Both original and fallback emoji are rejected.
    side_effects = [
        _SlackApiError("profile_status_set_failed_not_valid_emoji"),
        _SlackApiError("profile_status_set_failed_not_valid_emoji"),
    ]
    respond = _run(_body(), side_effects=side_effects)
    call_text = respond.call_args[0][0]
    assert "rejected" in call_text.lower() or "emoji" in call_text.lower()


def test_auth_error_includes_reauth_link():
    respond = _run(_body(), side_effects=[_SlackApiError("token_revoked")])
    call_text = respond.call_args[0][0]
    assert "Authorise here" in call_text or "authoris" in call_text.lower()


def test_generic_slack_error_returns_generic_message():
    respond = _run(_body(), side_effects=[_SlackApiError("ratelimited")])
    call_text = respond.call_args[0][0]
    assert "went wrong" in call_text.lower() or "something" in call_text.lower()


# --- /lunch clear and /lunch done ---

def _run_clear(text, side_effect=None):
    respond = MagicMock()
    client = MagicMock()
    if side_effect is not None:
        client.users_profile_set.side_effect = side_effect
    with patch.object(main.installation_store, "find_installation", return_value=_installation()):
        _handle_lunch_lazy(body=_body(text), client=client, respond=respond, context={})
    return respond, client


def test_clear_command_clears_status():
    respond, client = _run_clear("clear")
    client.users_profile_set.assert_called_once()
    profile = client.users_profile_set.call_args[1]["profile"]
    assert profile["status_text"] == ""
    assert profile["status_emoji"] == ""
    respond.assert_called_once_with("Status cleared.")


def test_done_command_clears_status():
    respond, _ = _run_clear("done")
    respond.assert_called_once_with("Status cleared.")


def test_clear_command_api_error_includes_reauth_link():
    respond, _ = _run_clear("clear", side_effect=Exception("fail"))
    call_text = respond.call_args[0][0]
    assert "Authorise here" in call_text or "authoris" in call_text.lower()
