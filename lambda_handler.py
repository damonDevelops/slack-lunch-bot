import json
import logging

import slack_bolt
import slack_sdk
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from main import app

logging.getLogger().setLevel(logging.INFO)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("botocore.endpoint").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.info("slack-bolt==%s slack-sdk==%s", slack_bolt.__version__, slack_sdk.__version__)

slack_handler = SlackRequestHandler(app=app)


def handler(event, context):
    if event.get("source") == "aws.events":
        return {"statusCode": 200}
    logger.debug("Event: %s", json.dumps(event))
    response = slack_handler.handle(event, context)
    logger.debug("Response: %s", json.dumps(response))
    return response
