import json
import logging

from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from main import app

logging.basicConfig(level=logging.INFO)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("botocore.endpoint").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

slack_handler = SlackRequestHandler(app=app)


def handler(event, context):
    logger.debug("Event: %s", json.dumps(event))
    response = slack_handler.handle(event, context)
    logger.debug("Response: %s", json.dumps(response))
    return response
