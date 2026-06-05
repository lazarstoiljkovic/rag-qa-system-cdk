import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { KnowledgeBaseStack } from '../lib/knowledge-base-stack';
import { CustomOpenSearchStack } from '../lib/custom-opensearch-stack';

describe('RAG Q&A System Stacks', () => {
  let app: cdk.App;

  beforeEach(() => {
    app = new cdk.App();
  });

  describe('KnowledgeBaseStack', () => {
    test('creates S3 bucket for documents', () => {
      const stack = new KnowledgeBaseStack(app, 'TestKBStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::S3::Bucket', 1);
      template.hasResourceProperties('AWS::S3::Bucket', {
        VersioningConfiguration: {
          Status: 'Enabled'
        }
      });
    });

    test('creates Lambda functions', () => {
      const stack = new KnowledgeBaseStack(app, 'TestKBStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::Lambda::Function', 2);
    });

    test('creates API Gateway', () => {
      const stack = new KnowledgeBaseStack(app, 'TestKBStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
      template.hasResourceProperties('AWS::ApiGateway::RestApi', {
        Name: 'RAG Knowledge Base API'
      });
    });

    test('creates DynamoDB table', () => {
      const stack = new KnowledgeBaseStack(app, 'TestKBStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::DynamoDB::Table', 1);
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        BillingMode: 'PAY_PER_REQUEST'
      });
    });

    test('creates IAM role for Bedrock', () => {
      const stack = new KnowledgeBaseStack(app, 'TestKBStack');
      const template = Template.fromStack(stack);

      template.hasResourceProperties('AWS::IAM::Role', {
        AssumedByServicePrincipal: {
          Service: 'bedrock.amazonaws.com'
        }
      });
    });
  });

  describe('CustomOpenSearchStack', () => {
    test('creates VPC with correct configuration', () => {
      const stack = new CustomOpenSearchStack(app, 'TestOSStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::EC2::VPC', 1);
      template.hasResourceProperties('AWS::EC2::VPC', {
        EnableDnsHostnames: true,
        EnableDnsSupport: true
      });
    });

    test('creates OpenSearch domain', () => {
      const stack = new CustomOpenSearchStack(app, 'TestOSStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::OpenSearchService::Domain', 1);
      template.hasResourceProperties('AWS::OpenSearchService::Domain', {
        DomainName: 'rag-vector-search'
      });
    });

    test('creates Lambda functions in VPC', () => {
      const stack = new CustomOpenSearchStack(app, 'TestOSStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::Lambda::Function', 3);
    });

    test('creates security groups', () => {
      const stack = new CustomOpenSearchStack(app, 'TestOSStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::EC2::SecurityGroup', 2);
    });

    test('creates two DynamoDB tables', () => {
      const stack = new CustomOpenSearchStack(app, 'TestOSStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::DynamoDB::Table', 2);
    });

    test('creates S3 bucket with event notifications', () => {
      const stack = new CustomOpenSearchStack(app, 'TestOSStack');
      const template = Template.fromStack(stack);

      template.resourceCountIs('AWS::S3::Bucket', 1);
      template.hasResourceProperties('AWS::S3::Bucket', {
        NotificationConfiguration: {
          LambdaConfigurations: [
            {
              Event: 's3:ObjectCreated:*'
            }
          ]
        }
      });
    });
  });

  describe('Stack Outputs', () => {
    test('KnowledgeBase stack exports required outputs', () => {
      const stack = new KnowledgeBaseStack(app, 'TestKBStack');
      const template = Template.fromStack(stack);

      template.hasOutput('DocumentsBucketName', {});
      template.hasOutput('ApiEndpoint', {});
      template.hasOutput('QueryLogsTableName', {});
    });

    test('OpenSearch stack exports required outputs', () => {
      const stack = new CustomOpenSearchStack(app, 'TestOSStack');
      const template = Template.fromStack(stack);

      template.hasOutput('DocumentsBucketName', {});
      template.hasOutput('OpenSearchEndpoint', {});
      template.hasOutput('ApiEndpoint', {});
      template.hasOutput('QueryLogsTableName', {});
    });
  });
});
