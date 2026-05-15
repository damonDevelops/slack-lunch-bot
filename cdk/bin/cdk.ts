#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { SlackLunchBotStack } from '../lib/slack-lunch-bot-stack';

const app = new cdk.App();
new SlackLunchBotStack(app, 'SlackLunchBotStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
