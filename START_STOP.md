# Start & Stop Infrastructure

> Always uses `lazar-private` AWS profile. Verify identity first.

## Verify Profile

```bash
aws sts get-caller-identity --profile lazar-private
```

---

## Start (Deploy)

```bash
# Option A — OpenSearch stack only (custom RAG)
npx cdk deploy CustomOpenSearchStack --profile lazar-private

# Option B — Knowledge Base stack only (managed Bedrock RAG, cheaper idle cost)
npx cdk deploy KnowledgeBaseStack --profile lazar-private

# Option C — Both stacks
npx cdk deploy --all --profile lazar-private
```

---

## Stop (Destroy)

```bash
# Option A — OpenSearch stack only
npx cdk destroy CustomOpenSearchStack --profile lazar-private

# Option B — Knowledge Base stack only
npx cdk destroy KnowledgeBaseStack --profile lazar-private

# Option C — Both stacks
npx cdk destroy --all --profile lazar-private
npx cdk destroy --all --profile lazar-private --region us-east-1
```

---

## Notes

- Deploy takes ~10–15 min (OpenSearch domain provisioning is slow)
- Destroy takes ~5–10 min
- Prefer `KnowledgeBaseStack` for testing — no idle OpenSearch cost (~$40/mo saved)
- Destroy `CustomOpenSearchStack` when not actively working to avoid NAT Gateway + OpenSearch charges
