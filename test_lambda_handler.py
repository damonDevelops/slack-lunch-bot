from unittest.mock import patch
from lambda_handler import handler


def test_warming_event_short_circuits_to_200():
    event = {"source": "aws.events", "detail-type": "Scheduled Event"}
    assert handler(event, {}) == {"statusCode": 200, "body": ""}


def test_non_warming_eventbridge_event_is_not_short_circuited():
    # A non-warming EventBridge event (e.g. a scheduled cleaner) must not be
    # swallowed by the warm-up guard — it should reach the Slack handler.
    event = {"source": "aws.events", "detail-type": "Custom Cleanup Event"}
    mock_response = {"statusCode": 200, "body": "processed"}
    with patch("lambda_handler.slack_handler.handle", return_value=mock_response) as mock_handle:
        result = handler(event, {})
    mock_handle.assert_called_once_with(event, {})
    assert result == mock_response
