# Deployment Guide

## Prerequisites Check

Before deploying, ensure you have:

- [ ] AWS Account with appropriate permissions
- [ ] AWS CLI installed and configured
- [ ] Node.js 18+ installed
- [ ] Docker installed and running
- [ ] CDK CLI installed (`npm install -g aws-cdk`)
- [ ] Bedrock model access enabled

## Step 1: Request Bedrock Model Access

1. Go to AWS Console → Amazon Bedrock → Model access
2. Request access to the following models:
   - ✅ Claude 3 Sonnet
   - ✅ Amazon Titan Text Express
   - ✅ Amazon Titan Embeddings v2

**Note**: Approval may take a few minutes to hours.

## Step 2: Install Dependencies

```bash
cd /Users/lazarstoiljkovic/Desktop/other/diplomski/rag-qa-system-cdk
npm install
```

## Step 3: Configure AWS

```bash
# Configure AWS credentials
aws configure

# Verify configuration
aws sts get-caller-identity

# Set region (optional)
export AWS_DEFAULT_REGION=us-east-1
```

## Step 4: Bootstrap CDK (First Time Only)

```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

Replace `ACCOUNT-ID` with your AWS account ID and `REGION` with your preferred region.

## Step 5: Build TypeScript

```bash
npm run build
```

## Step 6: Review Changes

```bash
# View all stacks
cdk list

# View changes for Knowledge Base stack
cdk diff KnowledgeBaseStack

# View changes for OpenSearch stack
cdk diff CustomOpenSearchStack
```

## Step 7: Deploy

### Option A: Deploy Knowledge Base Solution Only

```bash
npm run deploy:knowledge-base
export AWS_PROFILE=lazar-private AWS_DEFAULT_REGION=us-east-1 && npm run deploy:knowledge-base --force
```

**Estimated deployment time**: 5-7 minutes

**Resources created**:
- S3 bucket for documents
- 2 Lambda functions (Docker)
- API Gateway REST API
- DynamoDB table
- IAM roles and policies

### Option B: Deploy Custom OpenSearch Solution Only

```bash
npm run deploy:opensearch
export AWS_PROFILE=lazar-private AWS_DEFAULT_REGION=us-east-1 && npm run deploy:opensearch --force
```

**Estimated deployment time**: 20-30 minutes

**Resources created**:
- VPC with public/private subnets
- OpenSearch domain (2 nodes)
- S3 bucket for documents
- 3 Lambda functions (Docker)
- API Gateway REST API
- 2 DynamoDB tables
- Security groups
- NAT Gateway
- IAM roles and policies

### Option C: Deploy Both Solutions

```bash
npm run deploy:all
```

**Note**: This will deploy both stacks. Estimated time: 25-35 minutes.

## Step 8: Note the Outputs

After deployment completes, note the output values:

```
Outputs:
KnowledgeBaseStack.ApiEndpoint = https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/
KnowledgeBaseStack.DocumentsBucketName = rag-kb-documents-xxxxx-us-east-1

CustomOpenSearchStack.ApiEndpoint = https://yyyyy.execute-api.us-east-1.amazonaws.com/prod/
CustomOpenSearchStack.DocumentsBucketName = rag-os-documents-xxxxx-us-east-1
CustomOpenSearchStack.OpenSearchEndpoint = vpc-rag-vector-search-xxxxx.us-east-1.es.amazonaws.com
```

## Step 9: Update Frontend Configuration

Edit `frontend/index.html` and update the API endpoints:

```javascript
const CONFIG = {
    'knowledge-base': {
        apiEndpoint: 'https://xxxxx.execute-api.us-east-1.amazonaws.com/prod'
    },
    'opensearch': {
        apiEndpoint: 'https://yyyyy.execute-api.us-east-1.amazonaws.com/prod'
    }
};
```

## Step 10: Test the Deployment

### Test Document Upload

```bash
# Convert test document to base64
base64 -i test-documents/sr/aws-uvod.txt > aws-uvod-base64.txt

# Get base64 content
BASE64_CONTENT=$(cat aws-uvod-base64.txt)

# Upload (replace with your API endpoint)
curl -X POST https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/documents \
  -H "Content-Type: application/json" \
  -d "{\"file\": \"$BASE64_CONTENT\", \"filename\": \"aws-uvod.txt\", \"language\": \"sr\"}"
```

### Test Q&A Query

```bash
# Query (replace with your API endpoint)
curl -X POST https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "Šta je AWS?", "language": "sr"}'
```

### Open Frontend

Simply open `frontend/index.html` in your browser to use the web interface.

## Monitoring

### CloudWatch Logs

View Lambda logs:
```bash
# Knowledge Base upload logs
aws logs tail /aws/lambda/rag-kb-document-upload --follow

# Knowledge Base query logs
aws logs tail /aws/lambda/rag-kb-qa-query --follow

# OpenSearch processor logs
aws logs tail /aws/lambda/rag-os-document-processor --follow

# OpenSearch query logs
aws logs tail /aws/lambda/rag-os-qa-query --follow
```

### DynamoDB Query Logs

```bash
# Scan Knowledge Base logs
aws dynamodb scan --table-name rag-kb-query-logs

# Scan OpenSearch logs
aws dynamodb scan --table-name rag-os-query-logs
```

### OpenSearch Dashboard (for Custom OpenSearch stack)

The OpenSearch domain is in a VPC, so you'll need:
1. VPN or bastion host access to the VPC
2. Or modify security group to allow your IP

```bash
# Get OpenSearch endpoint
aws cloudformation describe-stacks \
  --stack-name CustomOpenSearchStack \
  --query 'Stacks[0].Outputs[?OutputKey==`OpenSearchEndpoint`].OutputValue' \
  --output text
```

## Troubleshooting

### Docker Build Fails

```bash
# Ensure Docker is running
docker ps

# Clean Docker cache
docker system prune -a
```

### Lambda Timeout

If document processing times out:
1. Check document size (<10MB recommended)
2. Increase Lambda timeout in stack definition
3. Check CloudWatch logs for errors

### Bedrock Access Denied

```bash
# Verify model access
aws bedrock list-foundation-models --region us-east-1

# Check IAM permissions
aws iam get-role --role-name <lambda-role-name>
```

### OpenSearch Connection Issues

1. Check security group rules
2. Verify Lambda is in correct VPC subnets
3. Check NAT Gateway configuration

## Updating the Stack

```bash
# Make changes to code
npm run build

# Deploy updates
cdk deploy KnowledgeBaseStack
# or
cdk deploy CustomOpenSearchStack
```

## Cleanup / Destroy

⚠️ **Warning**: This will delete all resources and data.

```bash
# Destroy single stack
cdk destroy KnowledgeBaseStack
# or
cdk destroy CustomOpenSearchStack

# Destroy all stacks
npm run destroy:all
```

**Note**: You may need to manually empty S3 buckets first if they contain data.

```bash
# Empty buckets
aws s3 rm s3://rag-kb-documents-xxxxx-us-east-1 --recursive
aws s3 rm s3://rag-os-documents-xxxxx-us-east-1 --recursive
```

## Cost Management

### Monitor Costs

```bash
# View current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

### Cost Optimization Tips

1. **Use Reserved Instances** for OpenSearch if running long-term
2. **Enable S3 Lifecycle Policies** for old documents
3. **Set up CloudWatch Alarms** for unexpected usage
4. **Use Savings Plans** for Bedrock if usage is predictable
5. **Delete unused stacks** when not needed

## Next Steps

1. Upload more test documents
2. Test queries in both languages (Serbian & English)
3. Compare results between Knowledge Base and OpenSearch solutions
4. Monitor performance and costs
5. Customize chunking strategy if needed
6. Add more document formats (if required)
7. Implement authentication for production use

## Production Considerations

Before using in production:

- [ ] Enable API Gateway authentication (API Keys, Cognito, IAM)
- [ ] Set up custom domain names
- [ ] Configure WAF rules for API Gateway
- [ ] Enable VPC endpoints for enhanced security
- [ ] Set up automated backups
- [ ] Implement rate limiting
- [ ] Add comprehensive error handling
- [ ] Set up alerting and monitoring dashboards
- [ ] Document business continuity plan
- [ ] Conduct security audit

## Support

If you encounter issues:

1. Check CloudWatch Logs
2. Review AWS CDK documentation
3. Check Bedrock service quotas
4. Verify IAM permissions
5. Contact AWS Support if needed

---

**Deployment Complete!** 🎉

Your RAG Q&A system is now ready to use.
