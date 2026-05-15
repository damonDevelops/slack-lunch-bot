import json
import logging

from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from main import app

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

slack_handler = SlackRequestHandler(app=app)


STAGE_PREFIX = "/default"


def handler(event, context):
    if "rawPath" in event and event["rawPath"].startswith(STAGE_PREFIX):
        event = {**event, "rawPath": event["rawPath"][len(STAGE_PREFIX):] or "/"}
    logger.debug("Event: %s", json.dumps(event))
    response = slack_handler.handle(event, context)
    logger.debug("Response: %s", json.dumps(response))
    return response
