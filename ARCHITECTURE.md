# Architecture Deep Dive

## System Architecture Comparison

### Solution 1: Knowledge Base (Managed)

#### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│                    (Web Browser / API Client)                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Amazon API Gateway (REST)                    │
│  - CORS Enabled                                                 │
│  - Rate Limiting (100 req/s, burst 200)                        │
│  - CloudWatch Logging                                           │
└──────────────────┬─────────────────────────┬────────────────────┘
                   │                         │
         /documents│                         │/qa
                   ▼                         ▼
      ┌─────────────────────┐   ┌───────────────────────┐
      │ Document Upload     │   │ Q&A Query Lambda      │
      │ Lambda              │   │                       │
      │ - Python 3.11       │   │ - Python 3.11         │
      │ - 1GB RAM           │   │ - 512MB RAM           │
      │ - 5min timeout      │   │ - 30s timeout         │
      └──────────┬──────────┘   └──────────┬────────────┘
                 │                         │
                 │ PUT                     │ GET
                 ▼                         │
      ┌──────────────────────┐            │
      │   Amazon S3          │            │
      │   Documents Bucket   │◄───────────┘
      │   - Versioning       │
      │   - Encryption       │
      │   - Lifecycle Rules  │
      └──────────┬───────────┘
                 │
                 │ (Manual/Automatic Sync)
                 ▼
      ┌──────────────────────────────────┐
      │   AWS Bedrock Knowledge Base     │
      │   - Automatic Chunking           │
      │   - Automatic Embedding          │
      │   - Managed Vector Store         │
      └──────────┬───────────────────────┘
                 │
                 │ RetrieveAndGenerate API
                 ▼
      ┌──────────────────────────────────┐
      │   Amazon Bedrock LLM             │
      │   - Claude 3 Sonnet              │
      │   - Titan Text Express           │
      │   - Titan Embeddings v2          │
      └──────────────────────────────────┘
                 │
                 │ Log Results
                 ▼
      ┌──────────────────────────────────┐
      │   DynamoDB                       │
      │   Query Logs Table               │
      │   - Partition: queryId           │
      │   - Sort: timestamp              │
      │   - GSI: timestamp-index         │
      └──────────────────────────────────┘
```

#### Components

**API Gateway**:
- REST API with two endpoints
- `/documents` - POST for upload, GET for list
- `/qa` - POST for queries
- Request validation and throttling

**Lambda Functions**:
1. **Document Upload Lambda**
   - Validates file type (PDF, DOCX, TXT)
   - Decodes base64 content
   - Uploads to S3 with metadata
   - Returns document ID

2. **Q&A Query Lambda**
   - Receives question and language
   - Uses Bedrock RetrieveAndGenerate (simplified in demo)
   - Generates answer using Claude 3 Sonnet
   - Logs query to DynamoDB
   - Returns answer with sources

**S3 Bucket**:
- Stores original documents
- Organized by language: `uploads/{language}/{doc_id}/{filename}`
- Metadata includes document ID, timestamp, language
- Versioning enabled for safety

**Bedrock Knowledge Base** (Manual Setup Required):
- Automatically syncs from S3
- Chunks documents
- Generates embeddings
- Stores in managed vector database
- Provides RetrieveAndGenerate API

**DynamoDB**:
- Logs all queries
- Attributes: queryId, timestamp, question, answer, language, processingTime
- GSI on timestamp for time-based queries

---

### Solution 2: Custom OpenSearch

#### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│                    (Web Browser / API Client)                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Amazon API Gateway (REST)                    │
│  - CORS Enabled                                                 │
│  - Rate Limiting                                                │
└──────────────────┬─────────────────────────┬────────────────────┘
                   │                         │
         /documents│                         │/qa
                   ▼                         ▼
      ┌─────────────────────┐   ┌───────────────────────┐
      │ Document Upload     │   │ Q&A Query Lambda      │
      │ Lambda              │   │ (VPC)                 │
      │ - 512MB RAM         │   │ - 1GB RAM             │
      │ - 30s timeout       │   │ - 30s timeout         │
      └──────────┬──────────┘   └──────────┬────────────┘
                 │                         │
                 │ PUT                     │
                 ▼                         │
      ┌──────────────────────┐            │
      │   Amazon S3          │            │
      │   Documents Bucket   │            │
      │   - uploads/ prefix  │            │
      │   - EventBridge      │            │
      └──────────┬───────────┘            │
                 │                        │
                 │ S3 Event Trigger       │
                 ▼                        │
      ┌─────────────────────────┐        │
      │ Document Processor      │        │
      │ Lambda (VPC)            │        │
      │ - 2GB RAM               │        │
      │ - 10min timeout         │        │
      │                         │        │
      │ Process:                │        │
      │ 1. Extract text         │        │
      │ 2. Chunk (512 chars)    │        │
      │ 3. Generate embeddings  │        │
      │ 4. Index in OpenSearch  │        │
      └──────────┬──────────────┘        │
                 │                       │
                 │ Index                 │ k-NN Search
                 ▼                       │
┌────────────────────────────────────────┼─────────────────┐
│                VPC (Private Subnet)    │                 │
│                                        │                 │
│  ┌─────────────────────────────────────▼──────────────┐ │
│  │        Amazon OpenSearch Domain                    │ │
│  │        - 2x t3.small.search nodes                  │ │
│  │        - 20GB EBS per node                         │ │
│  │        - k-NN plugin enabled                       │ │
│  │        - HNSW algorithm                            │ │
│  │        - Cosine similarity                         │ │
│  │        - 1024 dimension vectors                    │ │
│  │                                                    │ │
│  │  Index Structure:                                  │ │
│  │  {                                                 │ │
│  │    chunk_id: keyword                               │ │
│  │    document_id: keyword                            │ │
│  │    text: text                                      │ │
│  │    embedding: knn_vector[1024]                     │ │
│  │    language: keyword                               │ │
│  │    source_file: keyword                            │ │
│  │  }                                                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  NAT Gateway ────────────────────► Internet              │
└──────────────────────────────────────────────────────────┘
                 │
                 │ Invoke with context
                 ▼
      ┌──────────────────────────────────┐
      │   Amazon Bedrock LLM             │
      │   - Claude 3 Sonnet              │
      │   - Titan Embeddings v2          │
      └──────────┬───────────────────────┘
                 │
                 │ Log Results
                 ▼
      ┌──────────────────────────────────┐
      │   DynamoDB Tables                │
      │   1. Query Logs                  │
      │   2. Document Metadata           │
      └──────────────────────────────────┘
```

#### Components

**VPC**:
- 2 Availability Zones
- Public subnets for NAT Gateway
- Private subnets for OpenSearch and Lambda
- Security groups for isolation

**API Gateway**: Same as Knowledge Base solution

**Lambda Functions**:

1. **Document Upload Lambda**
   - Validates and uploads to S3
   - Uploads to `uploads/` prefix trigger processing
   - No VPC attachment (faster cold start)

2. **Document Processor Lambda** (VPC)
   - Triggered by S3 events
   - Extracts text from PDF/DOCX
   - Implements chunking strategy:
     - Size: 512 characters
     - Overlap: 50 characters
   - Generates embeddings via Bedrock Titan v2
   - Indexes chunks in OpenSearch with k-NN
   - Saves metadata to DynamoDB

3. **Q&A Query Lambda** (VPC)
   - Receives question
   - Generates question embedding
   - Performs k-NN search in OpenSearch
   - Retrieves top-k relevant chunks (default: 5)
   - Constructs prompt with context
   - Calls Bedrock Claude 3 for answer
   - Logs to DynamoDB

**OpenSearch Domain**:
- 2-node cluster for high availability
- k-NN plugin enabled
- Index mapping:
  ```json
  {
    "embedding": {
      "type": "knn_vector",
      "dimension": 1024,
      "method": {
        "name": "hnsw",
        "space_type": "cosinesimil",
        "engine": "nmslib"
      }
    }
  }
  ```

**DynamoDB Tables**:
1. **Query Logs**: Same as KB solution
2. **Document Metadata**: Tracks processed documents
   - documentId, sourceFile, totalChunks, chunkIds, status

---

## Data Flow

### Knowledge Base Solution

1. **Document Upload Flow**:
   ```
   Client → API Gateway → Lambda → S3 → [Manual] KB Sync
   ```

2. **Query Flow**:
   ```
   Client → API Gateway → Lambda → Bedrock KB → LLM → DynamoDB → Response
   ```

### Custom OpenSearch Solution

1. **Document Upload and Processing Flow**:
   ```
   Client → API Gateway → Upload Lambda → S3
   ↓ (S3 Event)
   Processor Lambda → Extract Text → Chunk → Bedrock (Embedding)
   ↓
   OpenSearch Index → DynamoDB (Metadata)
   ```

2. **Query Flow**:
   ```
   Client → API Gateway → Query Lambda
   ↓
   Generate Embedding (Bedrock Titan)
   ↓
   k-NN Search (OpenSearch) → Top-K Chunks
   ↓
   Construct Prompt + Context
   ↓
   Bedrock Claude 3 → Generate Answer
   ↓
   DynamoDB (Log) → Response
   ```

---

## Technical Details

### Chunking Strategy

**Why Chunking?**
- LLMs have token limits
- Better semantic matching with smaller chunks
- Improved retrieval accuracy

**Implementation**:
```python
def create_chunks(text: str, chunk_size: int, overlap: int):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks
```

**Parameters**:
- Chunk size: 512 characters
- Overlap: 50 characters (preserves context at boundaries)

### Vector Embeddings

**Model**: Amazon Titan Embeddings v2
- Dimension: 1024
- Multilingual support (Serbian, English, 100+ languages)
- Max input: 8192 tokens
- Optimized for semantic search

**Similarity Metric**: Cosine Similarity
$$
\text{similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}
$$

### k-NN Search in OpenSearch

**Algorithm**: HNSW (Hierarchical Navigable Small World)
- Efficient approximate nearest neighbor search
- Trade-off between accuracy and speed

**Parameters**:
- `ef_construction`: 512 (build quality)
- `m`: 16 (connections per layer)
- `ef_search`: 512 (search quality)

**Query Example**:
```json
{
  "size": 5,
  "query": {
    "knn": {
      "embedding": {
        "vector": [0.1, 0.2, ...],
        "k": 5
      }
    }
  }
}
```

### Prompt Engineering

**Template Structure**:
```
System: You are a helpful assistant...

Context from documents:
[Retrieved Chunk 1]
[Retrieved Chunk 2]
...

Question: [User Question]

Instructions: Answer using only the context provided...
```

**Language-Specific Prompts**:
- Serbian: Uses Serbian instructions and formatting
- English: Uses English instructions and formatting

### LLM Configuration

**Claude 3 Sonnet Parameters**:
- `max_tokens`: 1500
- `temperature`: 0.3 (low for factual answers)
- `top_p`: 0.9

**Why Claude 3?**
- Excellent multilingual support
- Strong reasoning capabilities
- Good at following instructions
- Context window: 200k tokens

---

## Performance Characteristics

### Knowledge Base Solution

**Pros**:
- ✅ Fast deployment (5-7 minutes)
- ✅ Managed service (less maintenance)
- ✅ Automatic scaling
- ✅ Built-in optimizations

**Cons**:
- ⚠️ Less control over chunking
- ⚠️ Limited customization
- ⚠️ Additional service costs

**Typical Response Times**:
- Document upload: 1-3 seconds
- Query processing: 2-5 seconds

### Custom OpenSearch Solution

**Pros**:
- ✅ Full control over pipeline
- ✅ Custom chunking strategies
- ✅ Optimizable vector search
- ✅ Advanced analytics possible

**Cons**:
- ⚠️ Longer deployment (20-30 minutes)
- ⚠️ More complex architecture
- ⚠️ Requires VPC management
- ⚠️ OpenSearch maintenance

**Typical Response Times**:
- Document upload: 1-2 seconds
- Document processing: 10-60 seconds (async)
- Query processing: 1-3 seconds

---

## Security Architecture

### Knowledge Base Solution

**Data Protection**:
- S3 encryption at rest (SSE-S3)
- HTTPS for all API calls
- IAM role-based access

**Network Security**:
- Public API Gateway with CORS
- Lambda in AWS managed network

**Access Control**:
- API Gateway throttling
- IAM policies on Lambda roles
- S3 bucket policies

### Custom OpenSearch Solution

**Data Protection**:
- S3 encryption at rest
- OpenSearch encryption at rest and in transit
- HTTPS for all communications

**Network Security**:
- OpenSearch in private VPC
- Security groups for network isolation
- Lambda in VPC with NAT Gateway
- No direct internet access to OpenSearch

**Access Control**:
- VPC security groups
- OpenSearch fine-grained access control
- IAM policies
- API Gateway throttling

---

## Monitoring and Observability

### Metrics to Monitor

**API Gateway**:
- Request count
- 4xx/5xx errors
- Latency (p50, p95, p99)
- Throttled requests

**Lambda**:
- Invocations
- Duration
- Errors
- Concurrent executions
- Memory usage

**OpenSearch** (Custom solution):
- Cluster health (red/yellow/green)
- CPU utilization
- JVM memory pressure
- Disk usage
- Search latency
- Indexing latency

**Bedrock**:
- Model invocations
- Token usage
- Throttling
- Errors

### CloudWatch Dashboards

Create custom dashboards with:
- Request/response metrics
- Error rates
- Processing times
- Cost tracking
- Resource utilization

### Logging Strategy

**Structured Logging**:
```python
{
  "timestamp": "2026-02-15T12:00:00Z",
  "level": "INFO",
  "service": "qa-query",
  "queryId": "uuid",
  "processingTime": 2.3,
  "retrievedChunks": 5,
  "language": "sr"
}
```

**Log Retention**:
- Lambda logs: 7 days (development)
- API Gateway: 7 days
- Production: 30-90 days recommended

---

## Scalability Considerations

### Knowledge Base Solution

**Horizontal Scaling**:
- Lambda automatically scales
- API Gateway handles bursts
- Bedrock KB scales automatically

**Limits**:
- Lambda concurrent executions: 1000 (account level)
- API Gateway: 10,000 req/s (account level)
- Bedrock throttling: Model-dependent

### Custom OpenSearch Solution

**Horizontal Scaling**:
- Add more OpenSearch nodes
- Increase Lambda concurrency
- Use multiple NAT Gateways

**Vertical Scaling**:
- Larger OpenSearch instance types
- More Lambda memory
- Larger EBS volumes

**Limits**:
- OpenSearch: 200 nodes per domain
- VPC: 5 per region (can be increased)

---

## Cost Optimization Strategies

1. **Right-size OpenSearch instances**
2. **Use S3 Lifecycle policies**
3. **Enable DynamoDB on-demand billing**
4. **Monitor and optimize Lambda memory**
5. **Use Reserved Instances for predictable workloads**
6. **Implement caching where applicable**
7. **Clean up old documents and logs**

---

This architecture document provides a comprehensive understanding of both solutions, their trade-offs, and implementation details.
