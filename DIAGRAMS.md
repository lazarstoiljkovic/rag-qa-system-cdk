# Visual Guide for Thesis Presentation

## Architecture Diagrams (ASCII Art for Documentation)

### Solution 1: Knowledge Base Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│                    (Browser / API Client)                           │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AMAZON API GATEWAY                               │
│  ┌──────────────────┐                   ┌──────────────────┐       │
│  │  /documents      │                   │     /qa          │       │
│  │  POST - Upload   │                   │  POST - Query    │       │
│  │  GET  - List     │                   │                  │       │
│  └──────────────────┘                   └──────────────────┘       │
└────────────┬────────────────────────────────────┬───────────────────┘
             │                                    │
             ▼                                    ▼
┌─────────────────────────┐        ┌─────────────────────────┐
│  Document Upload Lambda │        │   Q&A Query Lambda      │
│  • Python 3.11          │        │   • Python 3.11         │
│  • 1GB RAM              │        │   • 512MB RAM           │
│  • 5min timeout         │        │   • 30s timeout         │
│  • Base64 decode        │        │   • Bedrock invoke      │
└──────────┬──────────────┘        └──────────┬──────────────┘
           │ PUT                              │ GET
           ▼                                  │
┌─────────────────────────┐                  │
│     AMAZON S3           │                  │
│  Documents Bucket       │◄─────────────────┘
│  • Versioning: ON       │
│  • Encryption: SSE-S3   │
│  • uploads/{lang}/...   │
└──────────┬──────────────┘
           │
           │ (Manual/Auto Sync)
           ▼
┌─────────────────────────────────────────────┐
│   AWS BEDROCK KNOWLEDGE BASE (MANAGED)      │
│   ┌─────────────────────────────────────┐   │
│   │  Automatic Processing:              │   │
│   │  • Document Ingestion               │   │
│   │  • Chunking                         │   │
│   │  • Embedding (Titan v2)             │   │
│   │  • Vector Storage                   │   │
│   └─────────────────────────────────────┘   │
└──────────┬──────────────────────────────────┘
           │ RetrieveAndGenerate
           ▼
┌─────────────────────────────────────────────┐
│        AMAZON BEDROCK - LLM LAYER           │
│  ┌─────────────────────────────────────┐    │
│  │  Claude 3 Sonnet                    │    │
│  │  • Temperature: 0.3                 │    │
│  │  • Max tokens: 1500                 │    │
│  │  • Multilingual support             │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │  Titan Embeddings v2                │    │
│  │  • Dimension: 1024                  │    │
│  │  • Multilingual                     │    │
│  └─────────────────────────────────────┘    │
└──────────┬──────────────────────────────────┘
           │ Log Results
           ▼
┌─────────────────────────────────────────────┐
│         AMAZON DYNAMODB                     │
│  Query Logs Table                           │
│  • queryId (PK)                             │
│  • timestamp (SK)                           │
│  • question, answer                         │
│  • language, processingTime                 │
│  • GSI: timestamp-index                     │
└─────────────────────────────────────────────┘
```

---

### Solution 2: Custom OpenSearch Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AMAZON API GATEWAY                               │
└────────────┬────────────────────────────────────┬───────────────────┘
             │                                    │
             ▼                                    ▼
┌──────────────────────┐              ┌───────────────────────┐
│ Document Upload      │              │  Q&A Query Lambda     │
│ Lambda               │              │  (VPC)                │
└──────────┬───────────┘              └──────────┬────────────┘
           │ PUT                                 │
           ▼                                     │
┌─────────────────────────┐                     │
│     AMAZON S3           │                     │
│  • uploads/ prefix      │                     │
│  • Event notifications  │                     │
└──────────┬──────────────┘                     │
           │ S3 Event Trigger                   │
           ▼                                     │
┌──────────────────────────────────────────┐    │
│    Document Processor Lambda (VPC)       │    │
│                                          │    │
│    ┌──────────────────────────────────┐ │    │
│    │ 1. Extract Text (PDF/DOCX)       │ │    │
│    │    • PyPDF2                      │ │    │
│    │    • python-docx                 │ │    │
│    └──────────────────────────────────┘ │    │
│    ┌──────────────────────────────────┐ │    │
│    │ 2. Chunk Text                    │ │    │
│    │    • Size: 512 chars             │ │    │
│    │    • Overlap: 50 chars           │ │    │
│    └──────────────────────────────────┘ │    │
│    ┌──────────────────────────────────┐ │    │
│    │ 3. Generate Embeddings           │ │    │
│    │    • Bedrock Titan v2            │ │    │
│    │    • 1024 dimensions             │ │    │
│    └──────────────────────────────────┘ │    │
└──────────┬───────────────────────────────┘    │
           │ Index                               │ k-NN Search
           ▼                                     │
┌────────────────────────────────────────────────┼─────────────┐
│               VPC (Private Subnet)             │             │
│                                                │             │
│  ┌─────────────────────────────────────────────▼──────────┐  │
│  │      AMAZON OPENSEARCH DOMAIN                         │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────┐     │  │
│  │  │  Index: documents                            │     │  │
│  │  │  ┌────────────────────────────────────────┐  │     │  │
│  │  │  │ Document Structure:                    │  │     │  │
│  │  │  │ • chunk_id: keyword                    │  │     │  │
│  │  │  │ • document_id: keyword                 │  │     │  │
│  │  │  │ • text: text (searchable)              │  │     │  │
│  │  │  │ • embedding: knn_vector[1024]          │  │     │  │
│  │  │  │ • language: keyword                    │  │     │  │
│  │  │  │ • source_file: keyword                 │  │     │  │
│  │  │  └────────────────────────────────────────┘  │     │  │
│  │  └──────────────────────────────────────────────┘     │  │
│  │                                                        │  │
│  │  k-NN Configuration:                                  │  │
│  │  • Algorithm: HNSW                                    │  │
│  │  • Space: Cosine Similarity                           │  │
│  │  • ef_construction: 512                               │  │
│  │  • m: 16                                              │  │
│  │                                                        │  │
│  │  Cluster: 2x t3.small.search nodes                    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  NAT Gateway ────────────────────► Internet                  │
└───────────────────────────────────────────────────────────────┘
           │
           │ Retrieved Chunks
           ▼
┌─────────────────────────────────────────────┐
│        AMAZON BEDROCK - LLM LAYER           │
│  ┌─────────────────────────────────────┐    │
│  │  Prompt Engineering:                │    │
│  │  Context + Question → LLM           │    │
│  │                                     │    │
│  │  Claude 3 Sonnet                    │    │
│  │  • Context window: 200k tokens      │    │
│  │  • Temperature: 0.3                 │    │
│  │  • Multilingual                     │    │
│  └─────────────────────────────────────┘    │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│         AMAZON DYNAMODB                     │
│  ┌─────────────────────────────────────┐    │
│  │  Query Logs Table                   │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │  Document Metadata Table            │    │
│  │  • documentId, totalChunks          │    │
│  │  • chunkIds, status                 │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### Document Processing Flow (OpenSearch)

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ 1. Upload Document (Base64)
     ▼
┌──────────────────────┐
│  Upload Lambda       │
│  • Validate format   │
│  • Decode base64     │
└────┬─────────────────┘
     │ 2. Store in S3
     ▼
┌──────────────────────┐
│  Amazon S3           │
│  uploads/{lang}/...  │
└────┬─────────────────┘
     │ 3. S3 Event
     ▼
┌──────────────────────────────────┐
│  Processor Lambda                │
│  ┌────────────────────────────┐  │
│  │ A. Extract Text            │  │
│  │    PDF → PyPDF2            │  │
│  │    DOCX → python-docx      │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │ B. Chunk                   │  │
│  │    Start: 0                │  │
│  │    Loop:                   │  │
│  │      chunk = text[s:s+512] │  │
│  │      s += 512 - 50         │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │ C. For each chunk:         │  │
│  │    embedding = bedrock()   │  │
│  └────────────────────────────┘  │
└────┬─────────────────────────────┘
     │ 4. Index chunks
     ▼
┌──────────────────────────────────┐
│  OpenSearch                      │
│  POST /documents/_doc/{chunk_id} │
│  {                               │
│    "text": "...",                │
│    "embedding": [0.1, ...],      │
│    "language": "sr"              │
│  }                               │
└────┬─────────────────────────────┘
     │ 5. Save metadata
     ▼
┌──────────────────────┐
│  DynamoDB            │
│  • documentId        │
│  • totalChunks: N    │
│  • status: indexed   │
└──────────────────────┘
```

### Query Processing Flow (OpenSearch)

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ 1. Ask Question
     │    {"question": "Šta je AWS?", "language": "sr"}
     ▼
┌──────────────────────────────────┐
│  Q&A Lambda                      │
│  ┌────────────────────────────┐  │
│  │ A. Generate Question       │  │
│  │    Embedding               │  │
│  │    bedrock.invoke_model()  │  │
│  │    → [0.1, 0.2, ...]      │  │
│  └────────────────────────────┘  │
└────┬─────────────────────────────┘
     │ 2. Vector Search
     ▼
┌──────────────────────────────────┐
│  OpenSearch k-NN Query           │
│  {                               │
│    "query": {                    │
│      "knn": {                    │
│        "embedding": {            │
│          "vector": [...],        │
│          "k": 5                  │
│        }                         │
│      },                          │
│      "filter": {                 │
│        "term": {"language": "sr"}│
│      }                           │
│    }                             │
│  }                               │
└────┬─────────────────────────────┘
     │ 3. Return Top-K Chunks
     │    [chunk1, chunk2, chunk3, chunk4, chunk5]
     ▼
┌──────────────────────────────────┐
│  Q&A Lambda (continued)          │
│  ┌────────────────────────────┐  │
│  │ B. Build Prompt            │  │
│  │    Context:                │  │
│  │    [Dokument 1]: chunk1    │  │
│  │    [Dokument 2]: chunk2    │  │
│  │    ...                     │  │
│  │                            │  │
│  │    Pitanje: Šta je AWS?    │  │
│  └────────────────────────────┘  │
└────┬─────────────────────────────┘
     │ 4. Call LLM
     ▼
┌──────────────────────────────────┐
│  Bedrock Claude 3 Sonnet         │
│  • Read context + question       │
│  • Generate coherent answer      │
│  • Extract relevant info         │
│  → Answer: "AWS je..."          │
└────┬─────────────────────────────┘
     │ 5. Log & Return
     ▼
┌──────────────────────┐
│  DynamoDB            │
│  • Save query        │
│  • Save answer       │
│  • Save metrics      │
└────┬─────────────────┘
     │ 6. Response
     ▼
┌──────────┐
│  Client  │
│  {       │
│    answer│
│    sources│
│    time  │
│  }       │
└──────────┘
```

---

## Component Interaction Matrix

```
┌─────────────┬────┬────┬────────┬───────┬─────────┬─────┐
│ Component   │ S3 │ LM │ OpenS. │ DynDB │ Bedrock │ API │
├─────────────┼────┼────┼────────┼───────┼─────────┼─────┤
│ API Gateway │    │ ✓  │        │       │         │  -  │
│ Upload LM   │ ✓  │    │        │       │         │  ✓  │
│ Proc. LM    │ ✓  │    │   ✓    │  ✓    │    ✓    │     │
│ Query LM    │    │    │   ✓    │  ✓    │    ✓    │  ✓  │
│ S3          │ -  │ ✓  │        │       │         │     │
│ OpenSearch  │    │ ✓  │   -    │       │         │     │
│ DynamoDB    │    │ ✓  │        │   -   │         │     │
│ Bedrock     │    │ ✓  │        │       │    -    │     │
└─────────────┴────┴────┴────────┴───────┴─────────┴─────┘

Legend: LM = Lambda, OpenS. = OpenSearch, DynDB = DynamoDB
```

---

## Technology Stack Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                   │
│  ┌───────────────────────────────────────────────────┐  │
│  │  HTML/JavaScript Frontend                         │  │
│  │  • Document upload UI                             │  │
│  │  • Q&A interface                                  │  │
│  │  • Real-time responses                            │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     API LAYER                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Amazon API Gateway (REST)                        │  │
│  │  • CORS, Throttling, Logging                      │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   COMPUTE LAYER                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  AWS Lambda (Python 3.11)                         │  │
│  │  • Document upload handler                        │  │
│  │  • Document processor (chunking & embedding)      │  │
│  │  • Q&A query handler                              │  │
│  │  • Docker containers                              │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────┐  ┌────────────────┐  ┌──────────────┐
│   STORAGE    │  │  VECTOR DB     │  │   DATABASE   │
│              │  │                │  │              │
│  Amazon S3   │  │  OpenSearch    │  │  DynamoDB    │
│  • Docs      │  │  • k-NN Index  │  │  • Logs      │
│  • Versioned │  │  • HNSW        │  │  • Metadata  │
└──────────────┘  └────────────────┘  └──────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   AI/ML LAYER                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Amazon Bedrock                                   │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  Claude 3 Sonnet                            │  │  │
│  │  │  • Text Generation                          │  │  │
│  │  │  • Multilingual                             │  │  │
│  │  │  • 200k context                             │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  Titan Embeddings v2                        │  │  │
│  │  │  • 1024 dimensions                          │  │  │
│  │  │  • Multilingual                             │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 INFRASTRUCTURE LAYER                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │  AWS CDK (TypeScript)                             │  │
│  │  • Infrastructure as Code                         │  │
│  │  • VPC, Security Groups                           │  │
│  │  • IAM Roles & Policies                           │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Deployment Pipeline

```
┌──────────────┐
│  Developer   │
│  Workstation │
└──────┬───────┘
       │ 1. npm install
       ▼
┌──────────────┐
│  Install     │
│  Dependencies│
└──────┬───────┘
       │ 2. npm run build
       ▼
┌──────────────┐
│  TypeScript  │
│  Compilation │
└──────┬───────┘
       │ 3. cdk synth
       ▼
┌──────────────┐
│  Generate    │
│  CloudForm.  │
└──────┬───────┘
       │ 4. cdk deploy
       ▼
┌──────────────────────────────────┐
│  AWS CloudFormation              │
│  • Create/Update Stack           │
│  • VPC, Subnets, Security Groups │
│  • S3, DynamoDB, OpenSearch      │
│  • Lambda Functions (Docker)     │
│  • API Gateway                   │
│  • IAM Roles & Policies          │
└──────┬───────────────────────────┘
       │ 5. Stack Ready
       ▼
┌──────────────┐
│  Production  │
│  Environment │
└──────────────┘
```

---

These visual diagrams can be included in your thesis to illustrate:
1. System architecture
2. Component interactions
3. Data flows
4. Technology stack
5. Deployment process

You can also create these as proper diagrams using tools like:
- draw.io (diagrams.net)
- Lucidchart
- Microsoft Visio
- PlantUML
