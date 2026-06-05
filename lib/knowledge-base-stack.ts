import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

/**
 * Stack for AWS Bedrock Knowledge Base Solution
 * This is a managed solution that uses AWS Bedrock's built-in RAG capabilities
 */
export class KnowledgeBaseStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ==================== S3 Buckets ====================
    
    // Bucket for storing source documents
    const documentsBucket = new s3.Bucket(this, 'DocumentsBucket', {
      bucketName: `rag-kb-documents-${this.account}-${this.region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(365),
        },
      ],
    });

    // ==================== DynamoDB Table for Logging ====================
    
    const queryLogsTable = new dynamodb.Table(this, 'QueryLogsTable', {
      tableName: 'rag-kb-query-logs',
      partitionKey: { name: 'queryId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecovery: true,
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    // Add GSI for querying by date
    queryLogsTable.addGlobalSecondaryIndex({
      indexName: 'timestamp-index',
      partitionKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ==================== IAM Role for Bedrock Knowledge Base ====================
    
    const knowledgeBaseRole = new iam.Role(this, 'KnowledgeBaseRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Role for Bedrock Knowledge Base to access S3 and invoke models',
    });

    // Grant read access to documents bucket
    documentsBucket.grantRead(knowledgeBaseRole);

    // Grant Bedrock model invocation
    knowledgeBaseRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [
        `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
        `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-text-express-v1`,
      ],
    }));

    // ==================== Lambda Functions ====================

    // Lambda for document upload and preprocessing
    const documentUploadLambda = new lambda.DockerImageFunction(this, 'DocumentUploadLambda', {
      functionName: 'rag-kb-document-upload',
      code: lambda.DockerImageCode.fromImageAsset('lambda/knowledge-base/document-upload'),
      memorySize: 1024,
      timeout: cdk.Duration.minutes(5),
      environment: {
        DOCUMENTS_BUCKET: documentsBucket.bucketName,
        REGION: this.region,
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      architecture: lambda.Architecture.ARM_64,
    });

    // Grant S3 permissions
    documentsBucket.grantReadWrite(documentUploadLambda);

    // Lambda for Q&A queries using Knowledge Base
    const qaQueryLambda = new lambda.DockerImageFunction(this, 'QAQueryLambda', {
      functionName: 'rag-kb-qa-query',
      code: lambda.DockerImageCode.fromImageAsset('lambda/knowledge-base/qa-query'),
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: {
        DOCUMENTS_BUCKET: documentsBucket.bucketName,
        LOGS_TABLE: queryLogsTable.tableName,
        REGION: this.region,
        BEDROCK_MODEL_ID: 'anthropic.claude-3-haiku-20240307-v1:0',
        EMBEDDING_MODEL_ID: 'amazon.titan-embed-text-v2:0',
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      architecture: lambda.Architecture.ARM_64,
    });

    // Grant permissions to Lambda
    documentsBucket.grantRead(qaQueryLambda);
    queryLogsTable.grantWriteData(qaQueryLambda);

    // Grant Bedrock permissions
    qaQueryLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
        'bedrock-agent:Retrieve',
        'bedrock-agent:RetrieveAndGenerate',
        'aws-marketplace:ViewSubscriptions',
        'aws-marketplace:Subscribe'
      ],
      resources: ['*'],
    }));

    // ==================== API Gateway ====================
    
    const api = new apigateway.RestApi(this, 'KnowledgeBaseApi', {
      restApiName: 'RAG Knowledge Base API',
      description: 'API for RAG Q&A system using Bedrock Knowledge Base',
      deployOptions: {
        stageName: 'prod',
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
        metricsEnabled: true,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
    });

    // Documents endpoint
    const documents = api.root.addResource('documents');
    const documentUploadIntegration = new apigateway.LambdaIntegration(documentUploadLambda);
    documents.addMethod('POST', documentUploadIntegration);
    documents.addMethod('GET', documentUploadIntegration);

    // Q&A endpoint
    const qa = api.root.addResource('qa');
    const qaQueryIntegration = new apigateway.LambdaIntegration(qaQueryLambda);
    qa.addMethod('POST', qaQueryIntegration);

    // ==================== Outputs ====================
    
    new cdk.CfnOutput(this, 'DocumentsBucketName', {
      value: documentsBucket.bucketName,
      description: 'S3 bucket for storing documents',
      exportName: 'KnowledgeBase-DocumentsBucket',
    });

    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: api.url,
      description: 'API Gateway endpoint URL',
      exportName: 'KnowledgeBase-ApiEndpoint',
    });

    new cdk.CfnOutput(this, 'QueryLogsTableName', {
      value: queryLogsTable.tableName,
      description: 'DynamoDB table for query logs',
      exportName: 'KnowledgeBase-QueryLogsTable',
    });

    // Note: Knowledge Base must be created manually or via custom resource
    new cdk.CfnOutput(this, 'KnowledgeBaseRoleArn', {
      value: knowledgeBaseRole.roleArn,
      description: 'IAM Role ARN for Bedrock Knowledge Base',
      exportName: 'KnowledgeBase-RoleArn',
    });
  }
}
