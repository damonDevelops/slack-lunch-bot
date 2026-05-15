import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { HttpApi, HttpMethod } from 'aws-cdk-lib/aws-apigatewayv2';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { Construct } from 'constructs';

export class SlackLunchBotStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const table = new dynamodb.Table(this, 'InstallationTable', {
      tableName: 'slack-lunch-bot',
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const slackSecret = secretsmanager.Secret.fromSecretNameV2(
      this, 'SlackSecret', 'slack-lunch-bot/slack'
    );
    const anthropicSecret = secretsmanager.Secret.fromSecretNameV2(
      this, 'AnthropicSecret', 'slack-lunch-bot/anthropic'
    );

    const fn = new lambda.Function(this, 'LunchBotFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'lambda_handler.handler',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          platform: 'linux/amd64',
          command: [
            'bash', '-c',
            [
              'pip install -r requirements-prod.txt',
              '--platform manylinux2014_x86_64',
              '--target /asset-output',
              '--only-binary=:all:',
              '--python-version 3.12 -q',
              '&& cp main.py llm.py lambda_handler.py store.py /asset-output',
            ].join(' '),
          ],
        },
      }),
      environment: {
        SLACK_SIGNING_SECRET: slackSecret.secretValueFromJson('SLACK_SIGNING_SECRET').unsafeUnwrap(),
        SLACK_CLIENT_ID: slackSecret.secretValueFromJson('SLACK_CLIENT_ID').unsafeUnwrap(),
        SLACK_CLIENT_SECRET: slackSecret.secretValueFromJson('SLACK_CLIENT_SECRET').unsafeUnwrap(),
        ANTHROPIC_API_KEY: anthropicSecret.secretValueFromJson('ANTHROPIC_API_KEY').unsafeUnwrap(),
        DEFAULT_LUNCH_DURATION_MINUTES: '30',
      },
    });

    table.grantReadWriteData(fn);
    slackSecret.grantRead(fn);
    anthropicSecret.grantRead(fn);

    const integration = new HttpLambdaIntegration('LunchBotIntegration', fn);

    const api = new HttpApi(this, 'LunchBotApi', {
      apiName: 'slack-lunch-bot',
    });

    api.addRoutes({ path: '/slack/events', methods: [HttpMethod.POST], integration });
    api.addRoutes({ path: '/slack/install', methods: [HttpMethod.GET], integration });
    api.addRoutes({ path: '/slack/oauth_redirect', methods: [HttpMethod.GET], integration });

    // APP_BASE_URL and SLACK_REDIRECT_URI reference api.url (a CloudFormation token)
    // so they must be added after the api construct is created
    fn.addEnvironment('APP_BASE_URL', api.url!);
    fn.addEnvironment('SLACK_REDIRECT_URI', `${api.url!}slack/oauth_redirect`);

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url!,
      description: 'Paste this into the Slack app config for slash command and OAuth redirect URLs',
    });
  }
}
