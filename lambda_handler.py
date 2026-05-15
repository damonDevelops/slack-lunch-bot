from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from main import app

slack_handler = SlackRequestHandler(app=app)


def handler(event, context):
    return slack_handler.handle(event, context)
