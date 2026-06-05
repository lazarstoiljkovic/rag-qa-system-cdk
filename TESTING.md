# API Testing Examples

## Using curl

### Knowledge Base Solution

#### Upload Document

```bash
# First, convert document to base64
BASE64_CONTENT=$(base64 -i test-documents/sr/aws-uvod.txt)

# Upload
curl -X POST https://YOUR-KB-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod/documents \
  -H "Content-Type: application/json" \
  -d "{
    \"file\": \"$BASE64_CONTENT\",
    \"filename\": \"aws-uvod.txt\",
    \"language\": \"sr\",
    \"metadata\": {
      \"category\": \"technology\",
      \"author\": \"test\"
    }
  }"
```

#### List Documents

```bash
curl -X GET https://YOUR-KB-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod/documents
```

#### Query Q&A (Serbian)

```bash
curl -X POST https://YOUR-KB-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Šta je AWS?",
    "language": "sr"
  }'
```

#### Query Q&A (English)

```bash
curl -X POST https://YOUR-KB-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is AWS Lambda?",
    "language": "en"
  }'
```

### Custom OpenSearch Solution

Same API structure as Knowledge Base solution.

```bash
# Upload
curl -X POST https://YOUR-OS-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod/documents \
  -H "Content-Type: application/json" \
  -d @upload-request.json

# Query
curl -X POST https://YOUR-OS-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Objasni cloud computing koncept",
    "language": "sr",
    "top_k": 5
  }'
```

## Using Python

### Setup

```bash
pip install requests
```

### Upload Document

```python
import requests
import base64
import json

# Read and encode document
with open('test-documents/sr/aws-uvod.txt', 'rb') as f:
    file_content = base64.b64encode(f.read()).decode('utf-8')

# API endpoint
api_endpoint = 'https://YOUR-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod'

# Upload request
upload_data = {
    'file': file_content,
    'filename': 'aws-uvod.txt',
    'language': 'sr',
    'metadata': {
        'category': 'technology'
    }
}

response = requests.post(
    f'{api_endpoint}/documents',
    json=upload_data,
    headers={'Content-Type': 'application/json'}
)

print(json.dumps(response.json(), indent=2, ensure_ascii=False))
```

### Query Q&A

```python
import requests
import json

api_endpoint = 'https://YOUR-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod'

# Query request
query_data = {
    'question': 'Šta je AWS Lambda i kako funkcioniše?',
    'language': 'sr'
}

response = requests.post(
    f'{api_endpoint}/qa',
    json=query_data,
    headers={'Content-Type': 'application/json'}
)

result = response.json()
print(f"Question: {result['question']}")
print(f"\nAnswer: {result['answer']}")
print(f"\nProcessing Time: {result['processingTime']}s")
print(f"\nSources: {result['sources']}")
```

## Using Postman

### Import Collection

Create a new Postman collection with the following requests:

#### 1. Upload Document

```
POST {{baseUrl}}/documents
Content-Type: application/json

{
  "file": "<base64-content>",
  "filename": "document.pdf",
  "language": "sr"
}
```

#### 2. List Documents

```
GET {{baseUrl}}/documents
```

#### 3. Query Q&A

```
POST {{baseUrl}}/qa
Content-Type: application/json

{
  "question": "Your question here",
  "language": "sr"
}
```

### Environment Variables

Set in Postman:
- `baseUrl` - Your API Gateway endpoint

## Test Scenarios

### Scenario 1: Serbian Technical Document

```bash
# 1. Upload document
curl -X POST $API_ENDPOINT/documents \
  -H "Content-Type: application/json" \
  -d @test-uploads/sr-aws-document.json

# 2. Wait a few seconds for processing (OpenSearch solution)

# 3. Ask questions
curl -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Koji su osnovni AWS servisi?",
    "language": "sr"
  }'

curl -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Šta je razlika između EC2 i Lambda?",
    "language": "sr"
  }'

curl -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Kako funkcioniše S3 storage?",
    "language": "sr"
  }'
```

### Scenario 2: English ML Document

```bash
# 1. Upload
curl -X POST $API_ENDPOINT/documents \
  -H "Content-Type: application/json" \
  -d @test-uploads/en-ml-document.json

# 2. Query
curl -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the difference between supervised and unsupervised learning?",
    "language": "en"
  }'

curl -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain deep learning and neural networks",
    "language": "en"
  }'
```

### Scenario 3: Multi-Document Query

```bash
# Upload multiple documents
for file in test-documents/sr/*.txt; do
  BASE64=$(base64 -i "$file")
  FILENAME=$(basename "$file")
  
  curl -X POST $API_ENDPOINT/documents \
    -H "Content-Type: application/json" \
    -d "{\"file\": \"$BASE64\", \"filename\": \"$FILENAME\", \"language\": \"sr\"}"
  
  sleep 2
done

# Query across all documents
curl -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Kako se AWS, cloud computing i machine learning povezuju?",
    "language": "sr"
  }'
```

## Performance Testing

### Load Test with ab (Apache Bench)

```bash
# Install ab
# macOS: brew install httpd
# Ubuntu: sudo apt-get install apache2-utils

# Create request file
cat > query-request.json << EOF
{
  "question": "Šta je AWS?",
  "language": "sr"
}
EOF

# Run load test (100 requests, 10 concurrent)
ab -n 100 -c 10 -p query-request.json -T application/json \
  https://YOUR-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod/qa
```

### Measure Response Time

```bash
# Using curl with timing
curl -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "Šta je AWS?", "language": "sr"}' \
  -w "\n\nTime: %{time_total}s\n"
```

## Monitoring Queries

### View CloudWatch Logs

```bash
# Knowledge Base query logs
aws logs tail /aws/lambda/rag-kb-qa-query --follow

# OpenSearch query logs
aws logs tail /aws/lambda/rag-os-qa-query --follow
```

### Query DynamoDB Logs

```bash
# Get recent queries
aws dynamodb query \
  --table-name rag-kb-query-logs \
  --index-name timestamp-index \
  --key-condition-expression "timestamp > :timestamp" \
  --expression-attribute-values '{":timestamp":{"S":"2026-02-15T00:00:00Z"}}' \
  --scan-index-forward false \
  --limit 10

# Get specific query
aws dynamodb get-item \
  --table-name rag-kb-query-logs \
  --key '{"queryId":{"S":"YOUR-QUERY-ID"},"timestamp":{"S":"TIMESTAMP"}}'
```

## Error Handling Tests

### Test Invalid File Type

```bash
curl -X POST $API_ENDPOINT/documents \
  -H "Content-Type: application/json" \
  -d '{
    "file": "dGVzdA==",
    "filename": "test.exe",
    "language": "sr"
  }'
# Expected: 400 Bad Request
```

### Test Missing Question

```bash
curl -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{
    "language": "sr"
  }'
# Expected: 400 Bad Request
```

### Test Large File

```bash
# Generate large file (>10MB)
dd if=/dev/zero of=large-file.txt bs=1M count=15

# Try to upload
BASE64=$(base64 -i large-file.txt)
curl -X POST $API_ENDPOINT/documents \
  -H "Content-Type: application/json" \
  -d "{\"file\": \"$BASE64\", \"filename\": \"large-file.txt\", \"language\": \"sr\"}"
# May timeout or fail depending on Lambda configuration
```

## Comparison Testing

### Compare Both Solutions

```bash
# Upload same document to both solutions
BASE64=$(base64 -i test-documents/sr/aws-uvod.txt)

# Knowledge Base
curl -X POST $KB_API_ENDPOINT/documents \
  -H "Content-Type: application/json" \
  -d "{\"file\": \"$BASE64\", \"filename\": \"aws-uvod.txt\", \"language\": \"sr\"}"

# OpenSearch
curl -X POST $OS_API_ENDPOINT/documents \
  -H "Content-Type: application/json" \
  -d "{\"file\": \"$BASE64\", \"filename\": \"aws-uvod.txt\", \"language\": \"sr\"}"

# Ask same question to both
QUESTION='{"question": "Šta je AWS Lambda?", "language": "sr"}'

echo "Knowledge Base Answer:"
curl -X POST $KB_API_ENDPOINT/qa -H "Content-Type: application/json" -d "$QUESTION"

echo "\n\nOpenSearch Answer:"
curl -X POST $OS_API_ENDPOINT/qa -H "Content-Type: application/json" -d "$QUESTION"
```

## Automated Test Suite

Create `test-suite.sh`:

```bash
#!/bin/bash

API_ENDPOINT="$1"

echo "🧪 Running API Test Suite..."

# Test 1: Upload document
echo "\n1️⃣ Testing document upload..."
UPLOAD_RESPONSE=$(curl -s -X POST $API_ENDPOINT/documents \
  -H "Content-Type: application/json" \
  -d '{"file":"'$(base64 -i test-documents/sr/aws-uvod.txt)'","filename":"aws-uvod.txt","language":"sr"}')

if echo "$UPLOAD_RESPONSE" | grep -q "documentId"; then
  echo "✅ Upload successful"
else
  echo "❌ Upload failed"
  exit 1
fi

# Test 2: Query Q&A
echo "\n2️⃣ Testing Q&A query..."
QUERY_RESPONSE=$(curl -s -X POST $API_ENDPOINT/qa \
  -H "Content-Type: application/json" \
  -d '{"question":"Šta je AWS?","language":"sr"}')

if echo "$QUERY_RESPONSE" | grep -q "answer"; then
  echo "✅ Query successful"
else
  echo "❌ Query failed"
  exit 1
fi

echo "\n✅ All tests passed!"
```

Run with:
```bash
chmod +x test-suite.sh
./test-suite.sh https://YOUR-API-ENDPOINT.execute-api.REGION.amazonaws.com/prod
```

---

These testing examples provide comprehensive coverage for validating both RAG solutions.
