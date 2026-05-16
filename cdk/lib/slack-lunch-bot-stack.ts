import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { HttpApi, HttpMethod } from 'aws-cdk-lib/aws-apigatewayv2';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { Construct } from 'constructs';

export class SlackLunchBotStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const defaultDurationParam = new ssm.StringParameter(this, 'DefaultDurationParam', {
      parameterName: '/slack-lunch-bot/default_duration_minutes',
      stringValue: '30',
      description: 'System-wide default lunch duration in minutes',
    });

    const table = new dynamodb.Table(this, 'InstallationTable', {
      tableName: 'slack-lunch-bot',
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecovery: true,
      timeToLiveAttribute: 'ttl',
    });

    const secret = secretsmanager.Secret.fromSecretNameV2(
      this, 'BotSecret', 'slack-lunch-bot-secrets'
    );

    const fnName = 'slack-lunch-bot';

    const fn = new lambda.Function(this, 'LunchBotFunction', {
      functionName: fnName,
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
              '&& cp main.py llm.py lambda_handler.py store.py bot_secrets.py /asset-output',
            ].join(' '),
          ],
        },
      }),
      environment: {
        BOT_SECRET_ARN: secret.secretArn,
      },
    });

    table.grantReadWriteData(fn);
    secret.grantRead(fn);
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParameter'],
      resources: [defaultDurationParam.parameterArn],
    }));
    // Slack Bolt lazy listeners invoke the same Lambda asynchronously to run
    // the actual handler after immediately acking the slash command.
    // Use a plain string ARN (not fn.functionArn) to avoid a CDK circular
    // dependency between the function resource and its own IAM policy.
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['lambda:InvokeFunction'],
      resources: [`arn:aws:lambda:${this.region}:${this.account}:function:${fnName}`],
    }));

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

    new events.Rule(this, 'WarmingRule', {
      schedule: events.Schedule.rate(cdk.Duration.minutes(5)),
      targets: [new targets.LambdaFunction(fn)],
    });

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url!,
      description: 'Paste this into the Slack app config for slash command and OAuth redirect URLs',
    });
  }
}
