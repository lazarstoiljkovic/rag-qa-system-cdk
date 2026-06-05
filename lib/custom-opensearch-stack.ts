import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as opensearch from 'aws-cdk-lib/aws-opensearchservice';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import * as path from 'path';

/**
 * Stack for Custom OpenSearch RAG Solution
 * This solution implements custom chunking, embedding, and vector search
 */
export class CustomOpenSearchStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ==================== S3 Buckets ====================
    
    const documentsBucket = new s3.Bucket(this, 'DocumentsBucket', {
      bucketName: `rag-os-documents-${cdk.Stack.of(this).account}-${cdk.Stack.of(this).region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      eventBridgeEnabled: true,
    });

    // ==================== DynamoDB Tables ====================
    
    const queryLogsTable = new dynamodb.Table(this, 'QueryLogsTable', {
      tableName: 'rag-os-query-logs',
      partitionKey: { name: 'queryId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecovery: true,
    });

    // Table for document metadata
    const documentMetadataTable = new dynamodb.Table(this, 'DocumentMetadataTable', {
      tableName: 'rag-os-document-metadata',
      partitionKey: { name: 'documentId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ==================== OpenSearch Domain ====================
    
    const openSearchDomain = new opensearch.Domain(this, 'OpenSearchDomain', {
      version: opensearch.EngineVersion.OPENSEARCH_2_11,
      domainName: 'rag-vector-search',
      capacity: {
        dataNodes: 1,
        dataNodeInstanceType: 't3.small.search',
        masterNodes: 0,
        multiAzWithStandbyEnabled: false, // Explicitly disable Multi-AZ with standby for T3
      },
      ebs: {
        volumeSize: 20,
        volumeType: ec2.EbsDeviceVolumeType.GP3,
      },
      encryptionAtRest: {
        enabled: true,
      },
      nodeToNodeEncryption: true,
      enforceHttps: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      logging: {
        slowSearchLogEnabled: true,
        appLogEnabled: true,
        slowIndexLogEnabled: true,
      },
    });

    // ==================== Lambda Functions ====================
    // Lambda for document processing (chunking and embedding)
    const documentProcessorLambda = new lambda.DockerImageFunction(this, 'DocumentProcessorLambda', {
      functionName: 'rag-os-document-processor',
      code: lambda.DockerImageCode.fromImageAsset('lambda/opensearch/document-processor'),
      memorySize: 2048,
      timeout: cdk.Duration.minutes(10),
      environment: {
        DOCUMENTS_BUCKET: documentsBucket.bucketName,
        OPENSEARCH_ENDPOINT: openSearchDomain.domainEndpoint,
        OPENSEARCH_INDEX: 'documents',
        METADATA_TABLE: documentMetadataTable.tableName,
        REGION: cdk.Stack.of(this).region,
        EMBEDDING_MODEL_ID: 'amazon.titan-embed-text-v2:0',
        CHUNK_SIZE: '512',
        CHUNK_OVERLAP: '50',
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      architecture: lambda.Architecture.ARM_64,
    });

    // Lambda for Q&A query processing
    const qaQueryLambda = new lambda.DockerImageFunction(this, 'QAQueryLambda', {
      functionName: 'rag-os-qa-query',
      code: lambda.DockerImageCode.fromImageAsset('lambda/opensearch/qa-query'),
      memorySize: 1024,
      timeout: cdk.Duration.seconds(30),
      environment: {
        OPENSEARCH_ENDPOINT: openSearchDomain.domainEndpoint,
        OPENSEARCH_INDEX: 'documents',
        LOGS_TABLE: queryLogsTable.tableName,
        REGION: cdk.Stack.of(this).region,
        BEDROCK_MODEL_ID: 'anthropic.claude-3-haiku-20240307-v1:0',
        EMBEDDING_MODEL_ID: 'amazon.titan-embed-text-v2:0',
        TOP_K: '5',
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      architecture: lambda.Architecture.ARM_64,
    });

    // Lambda for document upload handler
    const documentUploadLambda = new lambda.DockerImageFunction(this, 'DocumentUploadLambda', {
      functionName: 'rag-os-document-upload',
      code: lambda.DockerImageCode.fromImageAsset('lambda/opensearch/document-upload'),
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: {
        DOCUMENTS_BUCKET: documentsBucket.bucketName,
        PROCESSOR_FUNCTION: documentProcessorLambda.functionName,
        REGION: cdk.Stack.of(this).region,
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      architecture: lambda.Architecture.ARM_64,
    });

    // ==================== Permissions ====================
    
    // S3 permissions
    documentsBucket.grantReadWrite(documentUploadLambda);
    documentsBucket.grantRead(documentProcessorLambda);

    // DynamoDB permissions
    queryLogsTable.grantWriteData(qaQueryLambda);
    documentMetadataTable.grantReadWriteData(documentProcessorLambda);

    // OpenSearch permissions
    openSearchDomain.grantReadWrite(documentProcessorLambda);
    openSearchDomain.grantReadWrite(qaQueryLambda);

    // Domain access policy — restricts access to Lambda IAM roles only (replaces VPC isolation)
    openSearchDomain.addAccessPolicies(
      new iam.PolicyStatement({
        principals: [documentProcessorLambda.grantPrincipal, qaQueryLambda.grantPrincipal],
        actions: ['es:ESHttp*'],
        resources: [`${openSearchDomain.domainArn}/*`],
      })
    );

    // Lambda invoke permissions
    documentProcessorLambda.grantInvoke(documentUploadLambda);

    // Bedrock permissions
    const bedrockPolicy = new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [
        `arn:aws:bedrock:${cdk.Stack.of(this).region}::foundation-model/amazon.titan-embed-text-v2:0`,
        `arn:aws:bedrock:${cdk.Stack.of(this).region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0`,
      ],
    });

    documentProcessorLambda.addToRolePolicy(bedrockPolicy);
    qaQueryLambda.addToRolePolicy(bedrockPolicy);

    // ==================== S3 Event Trigger ====================
    
    documentsBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new cdk.aws_s3_notifications.LambdaDestination(documentProcessorLambda),
      { prefix: 'uploads/', suffix: '.pdf' }
    );

    documentsBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new cdk.aws_s3_notifications.LambdaDestination(documentProcessorLambda),
      { prefix: 'uploads/', suffix: '.docx' }
    );

    // ==================== API Gateway ====================
    
    const api = new apigateway.RestApi(this, 'OpenSearchApi', {
      restApiName: 'RAG OpenSearch API',
      description: 'API for RAG Q&A system using Custom OpenSearch',
      deployOptions: {
        stageName: 'prod',
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
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

    // Q&A endpoint
    const qa = api.root.addResource('qa');
    const qaQueryIntegration = new apigateway.LambdaIntegration(qaQueryLambda);
    qa.addMethod('POST', qaQueryIntegration);

    // ==================== Outputs ====================
    
    new cdk.CfnOutput(this, 'DocumentsBucketName', {
      value: documentsBucket.bucketName,
      description: 'S3 bucket for storing documents',
      exportName: 'OpenSearch-DocumentsBucket',
    });

    new cdk.CfnOutput(this, 'OpenSearchEndpoint', {
      value: openSearchDomain.domainEndpoint,
      description: 'OpenSearch domain endpoint',
      exportName: 'OpenSearch-DomainEndpoint',
    });

    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: api.url,
      description: 'API Gateway endpoint URL',
      exportName: 'OpenSearch-ApiEndpoint',
    });

    new cdk.CfnOutput(this, 'QueryLogsTableName', {
      value: queryLogsTable.tableName,
      description: 'DynamoDB table for query logs',
      exportName: 'OpenSearch-QueryLogsTable',
    });
  }
}
