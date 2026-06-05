# RAG Q&A System - AWS CDK Implementation

Implementacija Q&A sistema na osnovu skupa dokumenata koristeći LLM i RAG pristup na AWS infrastrukturi.

## 📋 Pregled / Overview

Ovaj projekat implementira dva različita pristupa za RAG-based Q&A sistem:

1. **Knowledge Base Solution** - Managed rešenje koristeći AWS Bedrock Knowledge Base
2. **Custom OpenSearch Solution** - Custom implementacija sa OpenSearch vektorskom bazom

### Ključne karakteristike

- ✅ Podrška za srpski i engleski jezik
- ✅ Procesiranje PDF i DOCX dokumenata
- ✅ Vektorsko pretraživanje sa OpenSearch k-NN
- ✅ Amazon Bedrock LLM (Claude 3 Sonnet i Titan)
- ✅ Amazon Titan Embeddings v2 (multilingual)
- ✅ Infrastructure as Code sa AWS CDK
- ✅ Automatsko chunking i embedding dokumenata
- ✅ DynamoDB logging i monitoring
- ✅ RESTful API sa API Gateway

## 🏗️ Arhitektura

### Solution 1: Knowledge Base (Managed)

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│        API Gateway (REST)           │
└────────┬────────────┬───────────────┘
         │            │
         ▼            ▼
    ┌────────┐   ┌─────────┐
    │Document│   │   Q&A   │
    │ Upload │   │  Query  │
    │ Lambda │   │ Lambda  │
    └───┬────┘   └────┬────┘
        │             │
        ▼             ▼
    ┌───────────────────────┐
    │    S3 Documents       │
    └───────────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │  Bedrock Knowledge    │
    │       Base            │
    └───────────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │   Bedrock LLM         │
    │  (Claude/Titan)       │
    └───────────────────────┘
```

### Solution 2: Custom OpenSearch

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│        API Gateway (REST)           │
└────────┬────────────┬───────────────┘
         │            │
         ▼            ▼
    ┌────────┐   ┌─────────┐
    │Document│   │   Q&A   │
    │ Upload │   │  Query  │
    │ Lambda │   │ Lambda  │
    └───┬────┘   └────┬────┘
        │             │
        ▼             │
┌───────────────┐     │
│      S3       │     │
│  Documents    │     │
└───────┬───────┘     │
        │             │
        ▼             │
┌───────────────┐     │
│   Document    │     │
│  Processor    │     │
│    Lambda     │     │
└───┬───────────┘     │
    │                 │
    │ Chunking &      │
    │ Embedding       │
    │                 │
    ▼                 ▼
┌───────────────────────────┐
│   OpenSearch Domain       │
│   (Vector Search k-NN)    │
└───────────────────────────┘
            │
            ▼
    ┌──────────────┐
    │ Bedrock LLM  │
    │ (Claude 3)   │
    └──────────────┘
```

## 📦 Tehnologije

- **Infrastructure**: AWS CDK (TypeScript)
- **Compute**: AWS Lambda (Python 3.11)
- **LLM**: Amazon Bedrock (Claude 3 Sonnet, Titan Text)
- **Embeddings**: Amazon Titan Embeddings v2
- **Vector Database**: Amazon OpenSearch Service (k-NN)
- **Storage**: Amazon S3
- **Database**: Amazon DynamoDB
- **API**: Amazon API Gateway (REST)

## 🚀 Deployment

### Prerequisites

1. AWS Account sa odgovarajućim permissions
2. AWS CLI instaliran i konfigurisan
3. Node.js 18+ i npm
4. AWS CDK Toolkit instaliran
5. Docker (za Lambda container images)
6. Bedrock model access (Claude 3 Sonnet, Titan models)

### Instalacija

```bash
# Clone repository
cd /Users/lazarstoiljkovic/Desktop/other/diplomski/
git clone <repository-url>
cd rag-qa-system-cdk

# Install dependencies
npm install

# Bootstrap CDK (first time only)
cdk bootstrap

# Build TypeScript
npm run build
```

### Deploy Stacks

**Deploy Knowledge Base Solution:**
```bash
npm run deploy:knowledge-base
```

**Deploy Custom OpenSearch Solution:**
```bash
npm run deploy:opensearch
```

**Deploy Both Solutions:**
```bash
npm run deploy:all
```

### Destroy Stacks

```bash
npm run destroy:all
```

## 📝 API Usage

### 1. Upload Document

**Endpoint:** `POST /documents`

**Request:**
```json
{
  "file": "<base64-encoded-content>",
  "filename": "document.pdf",
  "language": "sr",
  "metadata": {
    "author": "John Doe",
    "category": "Technical"
  }
}
```

**Response:**
```json
{
  "message": "Document uploaded successfully",
  "documentId": "uuid",
  "s3Key": "uploads/sr/uuid/document.pdf",
  "bucket": "bucket-name",
  "language": "sr",
  "timestamp": "2026-02-15T12:00:00Z"
}
```

### 2. Query Q&A

**Endpoint:** `POST /qa`

**Request:**
```json
{
  "question": "Šta je AWS Lambda?",
  "language": "sr",
  "top_k": 5
}
```

**Response:**
```json
{
  "queryId": "uuid",
  "question": "Šta je AWS Lambda?",
  "answer": "AWS Lambda je serverless computing servis...",
  "language": "sr",
  "processingTime": 1.234,
  "sources": [
    {
      "filename": "aws-guide.pdf",
      "score": 0.89
    }
  ]
}
```

## 🧪 Testing

### Manual Testing

**Upload test document:**
```bash
# Convert document to base64
base64 -i test-document.pdf -o document-base64.txt

# Upload via API
curl -X POST https://<api-endpoint>/prod/documents \
  -H "Content-Type: application/json" \
  -d @upload-request.json
```

**Query Q&A:**
```bash
curl -X POST https://<api-endpoint>/prod/qa \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Koji su glavni servisi AWS-a?",
    "language": "sr"
  }'
```

### Test Documents

Test dokumenti se nalaze u `test-documents/` folder-u:
- `test-documents/sr/` - Srpski dokumenti
- `test-documents/en/` - Engleski dokumenti

## 📊 Monitoring

### CloudWatch Logs

Sve Lambda funkcije loguju u CloudWatch Logs Groups:
- `/aws/lambda/rag-kb-document-upload`
- `/aws/lambda/rag-kb-qa-query`
- `/aws/lambda/rag-os-document-processor`
- `/aws/lambda/rag-os-qa-query`
- `/aws/lambda/rag-os-document-upload`

### DynamoDB Query Logs

Query history se čuva u DynamoDB tabelama:
- `rag-kb-query-logs` (Knowledge Base)
- `rag-os-query-logs` (OpenSearch)

Query attributes:
- `queryId` - Unique query identifier
- `timestamp` - Query timestamp
- `question` - User question
- `answer` - Generated answer
- `language` - Query language
- `processingTime` - Processing time in seconds
- `sources` - Retrieved document sources

## 🔐 Security

- **S3 Buckets**: Encryption at rest (S3-managed keys)
- **OpenSearch**: VPC isolation, encryption at rest and in transit
- **API Gateway**: CORS enabled, rate limiting
- **Lambda**: Least privilege IAM roles
- **DynamoDB**: Point-in-time recovery enabled

## 💡 Chunking Strategy

Custom OpenSearch solution koristi sliding window chunking:
- **Chunk Size**: 512 karaktera
- **Overlap**: 50 karaktera
- **Rationale**: Balans između konteksta i granularnosti

## 🎯 Vector Search

OpenSearch k-NN configuration:
- **Algorithm**: HNSW (Hierarchical Navigable Small World)
- **Space Type**: Cosine Similarity
- **Engine**: nmslib
- **Dimension**: 1024 (Titan Embeddings v2)
- **ef_construction**: 512
- **m**: 16

## 📈 Performance Considerations

### Knowledge Base Solution
- ✅ Managed service - manje održavanja
- ✅ Automatsko skaliranje
- ⚠️ Ograničena kontrola nad chunking strategijom
- ⚠️ Dodatni troškovi za Knowledge Base

### Custom OpenSearch Solution
- ✅ Potpuna kontrola nad RAG pipeline-om
- ✅ Custom chunking i embedding strategije
- ✅ Optimizacija vector search parametara
- ⚠️ Više složenosti u implementaciji
- ⚠️ Potrebno upravljanje OpenSearch klasterom

## 🔄 Document Processing Flow

### Knowledge Base
1. Upload document → S3
2. Manual Knowledge Base sync (or automatic)
3. Bedrock automatski procesira dokument
4. Query → Bedrock RetrieveAndGenerate API

### Custom OpenSearch
1. Upload document → S3 (uploads/ prefix)
2. S3 Event → Document Processor Lambda
3. Extract text (PDF/DOCX)
4. Chunk text (512 chars, 50 overlap)
5. Generate embeddings (Titan v2)
6. Index in OpenSearch
7. Save metadata → DynamoDB
8. Query → Generate embedding → k-NN search → LLM

## 🌐 Multi-language Support

Sistem podržava srpski i engleski jezik:
- **Language Detection**: Client specifies language
- **Document Segregation**: Dokumenti se čuvaju po jeziku
- **Query Filtering**: Pretraga filtrira po jeziku
- **Prompt Engineering**: Prompts prilagođeni jeziku

## 📚 Sample Prompts

**Serbian:**
```
Ti si pomoćnik za odgovaranje na pitanja na osnovu datih dokumenata.
Odgovori jasno i koncizno na srpskom jeziku.
```

**English:**
```
You are a helpful assistant that answers questions based on provided documents.
Answer clearly and concisely in English.
```

## 🛠️ Development

### Project Structure

```
rag-qa-system-cdk/
├── bin/
│   └── rag-qa-system-cdk.ts          # CDK app entry point
├── lib/
│   ├── knowledge-base-stack.ts        # Knowledge Base stack
│   └── custom-opensearch-stack.ts     # OpenSearch stack
├── lambda/
│   ├── knowledge-base/
│   │   ├── document-upload/           # Document upload handler
│   │   └── qa-query/                  # Q&A query handler
│   └── opensearch/
│       ├── document-upload/           # Document upload handler
│       ├── document-processor/        # Chunking & embedding
│       └── qa-query/                  # Vector search & LLM
├── test-documents/                    # Sample documents
├── frontend/                          # Simple web UI
├── package.json
├── tsconfig.json
├── cdk.json
└── README.md
```

### Local Development

```bash
# Watch mode for TypeScript
npm run watch

# Run tests
npm test

# Synthesize CloudFormation
cdk synth

# View diff
cdk diff
```

## 🐛 Troubleshooting

### Common Issues

**1. OpenSearch domain creation fails**
- Check VPC subnet availability
- Verify instance type availability in region

**2. Lambda timeout on document processing**
- Increase timeout (currently 10 minutes)
- Check document size (<10MB recommended)

**3. Bedrock model access denied**
- Request model access in Bedrock console
- Wait for approval (Claude 3, Titan models)

**4. Vector search returns no results**
- Verify documents are indexed (check OpenSearch)
- Check language filter matches document language

## 💰 Cost Estimation

**Knowledge Base Solution (monthly):**
- S3: ~$1-5
- Lambda: ~$5-20
- API Gateway: ~$3-10
- Bedrock: Pay per token (~$10-50)
- DynamoDB: ~$1-5
- **Total: ~$20-90/month**

**Custom OpenSearch Solution (monthly):**
- S3: ~$1-5
- Lambda: ~$10-30
- API Gateway: ~$3-10
- OpenSearch (2x t3.small): ~$50-70
- Bedrock: Pay per token (~$10-50)
- DynamoDB: ~$1-5
- NAT Gateway: ~$32
- **Total: ~$107-202/month**

## 📖 References

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Amazon OpenSearch Service](https://docs.aws.amazon.com/opensearch-service/)
- [AWS CDK Guide](https://docs.aws.amazon.com/cdk/)
- [Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)

## 📄 License

MIT License

## 👤 Author

Lazar Stoiljkovic

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

---

**Note**: Ovaj projekat je razvijen za diplomski rad na temu implementacije RAG Q&A sistema na AWS infrastrukturi.
