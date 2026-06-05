#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { KnowledgeBaseStack } from '../lib/knowledge-base-stack';
import { CustomOpenSearchStack } from '../lib/custom-opensearch-stack';

const app = new cdk.App();

// Stack for AWS Bedrock Knowledge Base solution
new KnowledgeBaseStack(app, 'KnowledgeBaseStack', {
  description: 'RAG Q&A System using AWS Bedrock Knowledge Base (Managed Solution)',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  tags: {
    Project: 'RAG-QA-System',
    Solution: 'Knowledge-Base',
    Environment: 'Production'
  }
});

// Stack for Custom OpenSearch solution
new CustomOpenSearchStack(app, 'CustomOpenSearchStack', {
  description: 'RAG Q&A System using Custom OpenSearch with Vector Search',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  tags: {
    Project: 'RAG-QA-System',
    Solution: 'Custom-OpenSearch',
    Environment: 'Production'
  }
});

app.synth();
