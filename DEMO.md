# Thesis Demo Guide

## Before the Demo (Day Before)

- [ ] Charge laptop
- [ ] Deploy both stacks (takes 15 min — do this the night before)
- [ ] Upload all test documents to both stacks
- [ ] Run one test query on each stack to confirm everything works
- [ ] Copy API URLs from CloudFormation outputs into `evaluation/config.json`
- [ ] Have Postman or terminal open and ready
- [ ] Have AWS Console open in browser (CloudFormation → Stacks)

---

## Deploy Stacks

```bash
npx cdk deploy --all --profile lazar-private --region us-east-1
```

Get the API URLs from the output (you'll need them for queries and evaluation):
```bash
aws cloudformation describe-stacks \
  --stack-name CustomOpenSearchStack \
  --profile lazar-private --region us-east-1 \
  --query 'Stacks[0].Outputs'

aws cloudformation describe-stacks \
  --stack-name KnowledgeBaseStack \
  --profile lazar-private --region us-east-1 \
  --query 'Stacks[0].Outputs'
```

---

## Upload Test Documents

Upload Serbian documents to both stacks. Replace `YOUR_OS_API` and `YOUR_KB_API` with your actual URLs.

```bash
# Encode a document
base64 test-documents/company/sr/godisnji-odmor.txt > /tmp/doc_b64.txt

# Upload to OpenSearch stack
curl -X POST YOUR_OS_API/documents \
  -H "Content-Type: application/json" \
  -d "{\"file\": \"$(cat /tmp/doc_b64.txt)\", \"filename\": \"godisnji-odmor.txt\", \"language\": \"sr\"}"

# Upload to Knowledge Base stack
curl -X POST YOUR_KB_API/documents \
  -H "Content-Type: application/json" \
  -d "{\"file\": \"$(cat /tmp/doc_b64.txt)\", \"filename\": \"godisnji-odmor.txt\", \"language\": \"sr\"}"
```

Repeat for all key documents:
- `test-documents/company/sr/scrum-guide.txt`
- `test-documents/company/sr/sajber-bezbednost.txt`
- `test-documents/company/en/code-review-guidelines.txt`
- `test-documents/company/en/incident-response.txt`

> Wait ~2 minutes after upload for OpenSearch to process and index the documents.

---

## Demo Flow (Suggested Order)

### Part 1 — Architecture Overview (5 min)

Show the AWS Console → CloudFormation → Stacks.

**Say:** *"I implemented two different RAG architectures on AWS. Both answer questions from company documents, but they differ in how they retrieve context."*

Point out:
- `CustomOpenSearchStack` — custom vector search with OpenSearch k-NN
- `KnowledgeBaseStack` — managed retrieval via Bedrock Knowledge Base

Show the architecture diagram if available, or draw on whiteboard:
```
User Question → API Gateway → Lambda → [OpenSearch k-NN / Bedrock KB] → Claude Haiku → Answer
```

---

### Part 2 — Live Query Demo (10 min)

#### Query 1 — Simple Serbian fact retrieval
```bash
curl -X POST YOUR_OS_API/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "Koliko dana godišnjeg odmora imaju zaposleni?", "language": "sr"}'
```

Expected answer mentions: *20 radnih dana, +2 dana za staž, +5 dana senior*

Run the same query against the KB stack. Compare the answers side by side.

#### Query 2 — English multi-fact question
```bash
curl -X POST YOUR_OS_API/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the severity levels for incidents?", "language": "en"}'
```

Expected answer mentions: *Sev1 Critical, Sev2 High, Sev3 Medium, Sev4 Low with response times*

#### Query 3 — Hallucination test (question not in documents)
```bash
curl -X POST YOUR_OS_API/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the CEO salary?", "language": "en"}'
```

**Expected:** The system should say it doesn't know. This shows the RAG system does NOT hallucinate when context is missing.

**Say:** *"This is important — a naive LLM would guess. Our system responds only from retrieved context."*

---

### Part 3 — Show Retrieved Context (5 min)

Point out the `contexts` field in the response. This shows what chunks the model actually used.

**Say:** *"The OpenSearch stack uses k-NN vector search to retrieve the most semantically similar chunks. The Knowledge Base stack uses AWS managed retrieval. The quality of these retrieved chunks directly affects the answer quality — which brings us to the evaluation."*

---

### Part 4 — RAGAS Evaluation Results (10 min)

> Run the evaluation before the demo (it takes ~15 min). Show pre-computed results.

```bash
cd evaluation
python evaluate.py
```

Show the printed comparison table. Explain each metric:

| Metric | What it measures |
|--------|-----------------|
| **Faithfulness** | Is the answer grounded in the retrieved context? (no hallucination) |
| **Answer Relevancy** | Does the answer actually address the question? |
| **Context Recall** | Did retrieval find all the information needed to answer? |
| **Context Precision** | Were the retrieved chunks useful, or noisy? |

**Key talking point:** *"RAGAS uses Claude as a judge LLM — the same model family used in the RAG pipeline — to score each answer automatically, without human annotation."*

Show the results JSON in `evaluation/results/` for per-question breakdown.

---

### Part 5 — Infrastructure & Cost (3 min)

Show AWS Cost Explorer screenshot.

**Say:** *"For a thesis project, cost awareness matters. The biggest expense was the NAT Gateway ($46) and OpenSearch domain ($41) running 24/7. I optimized by tearing down the infrastructure between development sessions."*

Point out the CDK code showing:
- Single-node OpenSearch (`t3.small`) — conscious tradeoff for cost
- `RemovalPolicy.DESTROY` — everything cleans up on stack deletion
- ARM64 Lambdas — 20% cheaper than x86

---

## Likely Questions from the Committee

**Q: Why two implementations?**
> To compare managed vs. custom RAG architectures empirically, not just theoretically. RAGAS gives us quantitative evidence.

**Q: Why OpenSearch for vector search and not a dedicated vector DB?**
> OpenSearch k-NN plugin supports HNSW indexing with cosine similarity — the same approach as dedicated vector databases like Pinecone, but within AWS without introducing external dependencies.

**Q: Why Claude Haiku and not a larger model?**
> Cost and latency. Haiku is the fastest and cheapest Claude model. For a retrieval-augmented system, the quality of retrieval matters more than raw LLM size. The RAGAS results validate this choice.

**Q: What are the limitations?**
> Single-node OpenSearch (no HA), character-based chunking (not semantic), and the Knowledge Base implementation is simplified — it does not use the full Bedrock RetrieveAndGenerate API.

**Q: How would you improve it?**
> Semantic chunking, re-ranking retrieved results, multi-node OpenSearch for production, and a proper Bedrock KB integration using the `RetrieveAndGenerate` API.

---

## After the Demo

```bash
# Destroy everything to stop billing
npx cdk destroy --all --profile lazar-private --region us-east-1
```
