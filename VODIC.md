# Vodič za Deploy i Testiranje — RAG Q&A Sistem

## Preduslovi

- AWS CLI konfigurisan sa profilom `lazar-private`
- Node.js v18+ (nvm)
- Python 3.11+
- Docker (mora biti pokrenut — potreban za Lambda Docker build)

Provjeri da sve radi:
```bash
aws sts get-caller-identity --profile lazar-private
node --version
docker info
```

---

## Korak 1 — Build projekta

```bash
cd ~/Desktop/other/diplomski/rag-qa-system-cdk
npm install
npm run build
```

Ako nema grešaka, nastavi dalje.

---

## Korak 2 — CDK Bootstrap (samo prvi put)

Ovo je potrebno uraditi jednom da bi CDK mogao da deploy-uje na tvoj AWS nalog.

```bash
npx cdk bootstrap --profile lazar-private --region us-east-1
```

---

## Korak 3 — Deploy

### Opcija A — Samo OpenSearch stack (preporučeno za testiranje)
```bash
npx cdk deploy CustomOpenSearchStack --profile lazar-private --region us-east-1
```

### Opcija B — Samo Knowledge Base stack
```bash
npx cdk deploy KnowledgeBaseStack --profile lazar-private --region us-east-1
```

### Opcija C — Oba stacka odjednom
```bash
npx cdk deploy --all --profile lazar-private --region us-east-1
```

> Deploy traje **10–15 minuta** jer OpenSearch domain treba vremena da se pokrene.

Na kraju deploy-a, u terminalu ćeš videti URL-ove:
```
Outputs:
CustomOpenSearchStack.OpenSearchApiEndpoint = https://XXXX.execute-api.us-east-1.amazonaws.com/prod
KnowledgeBaseStack.KnowledgeBaseApiEndpoint = https://YYYY.execute-api.us-east-1.amazonaws.com/prod
```

**Sačuvaj ove URL-ove** — trebaće ti za testiranje i evaluaciju.

---

## Korak 4 — Upload dokumenata

Dokumenti moraju biti base64 enkodirani pre upload-a.

```bash
# Enkoduj dokument
base64 test-documents/company/sr/godisnji-odmor.txt > /tmp/doc.b64

# Upload na OpenSearch stack
curl -X POST https://XXXX.execute-api.us-east-1.amazonaws.com/prod/documents \
  -H "Content-Type: application/json" \
  -d "{\"file\": \"$(cat /tmp/doc.b64)\", \"filename\": \"godisnji-odmor.txt\", \"language\": \"sr\"}"
```

Uploaduj sve ključne dokumente (ponovi za svaki):

| Fajl | Jezik |
|------|-------|
| `test-documents/company/sr/godisnji-odmor.txt` | sr |
| `test-documents/company/sr/scrum-guide.txt` | sr |
| `test-documents/company/sr/sajber-bezbednost.txt` | sr |
| `test-documents/company/sr/onboarding-procedura.txt` | sr |
| `test-documents/company/en/code-review-guidelines.txt` | en |
| `test-documents/company/en/incident-response.txt` | en |
| `test-documents/company/en/deployment-process.txt` | en |

> Sačekaj **2 minuta** nakon uploada da OpenSearch indeksira dokumente.

---

## Korak 5 — Testiranje upitima

### Test 1 — Srpsko pitanje (OpenSearch)
```bash
curl -X POST https://XXXX.execute-api.us-east-1.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "Koliko dana godišnjeg odmora imaju zaposleni?", "language": "sr"}'
```

Očekivan odgovor: *"20 radnih dana, +2 za staž, +5 za senior pozicije..."*

---

### Test 2 — Englesko pitanje (OpenSearch)
```bash
curl -X POST https://XXXX.execute-api.us-east-1.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the severity levels for incidents?", "language": "en"}'
```

Očekivan odgovor: *"Sev1 Critical, Sev2 High, Sev3 Medium, Sev4 Low..."*

---

### Test 3 — Halucinacioni test (pitanje van konteksta)
```bash
curl -X POST https://XXXX.execute-api.us-east-1.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the CEO salary?", "language": "en"}'
```

Očekivan odgovor: *"Ne znam"* ili *"Informacija nije u dokumentima"*

> Ovo je važno — sistem ne sme da izmišlja odgovor ako ga nema u dokumentima.

---

### Test 4 — Isti upit na oba stacka (poređenje)
```bash
# OpenSearch
curl -X POST https://XXXX.execute-api.us-east-1.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "Koliko traje sprint?", "language": "sr"}'

# Knowledge Base
curl -X POST https://YYYY.execute-api.us-east-1.amazonaws.com/prod/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "Koliko traje sprint?", "language": "sr"}'
```

Uporedi odgovore i `contexts` polje u responsu — OpenSearch vraća stvarne tekstualne delove iz dokumenata, KB vraća samo nazive fajlova.

---

## Korak 6 — RAGAS Evaluacija

```bash
# 1. Instaliraj zavisnosti
cd evaluation
pip install -r requirements.txt

# 2. Kreiraj config fajl
cp config.example.json config.json
# Otvori config.json i upiši URL-ove iz Koraka 3
```

```json
{
  "opensearch_api_url": "https://XXXX.execute-api.us-east-1.amazonaws.com/prod",
  "knowledge_base_api_url": "https://YYYY.execute-api.us-east-1.amazonaws.com/prod",
  "aws_region": "us-east-1",
  "aws_profile": "lazar-private"
}
```

```bash
# 3. Pokreni evaluaciju (~15 minuta)
python evaluate.py
```

Rezultat će izgledati ovako:
```
Metric                 OpenSearch  KnowledgeBase   Winner
faithfulness               0.87           0.43  OpenSearch
answer_relevancy           0.91           0.65  OpenSearch
context_recall             0.78           0.31  OpenSearch
context_precision          0.82           0.39  OpenSearch
AVERAGE                    0.85           0.45  OpenSearch
```

Rezultati se čuvaju u `evaluation/results/` folderu.

---

## Korak 7 — Gašenje infrastrukture

**Uvek ugasi kada završiš** da ne bi plaćao (~$80/mesec dok radi).

```bash
npx cdk destroy --all --profile lazar-private --region us-east-1
```

Potvrdi sa `y` kada pita za svaki stack.

Provjeri da su stackovi obrisani:
```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --profile lazar-private \
  --region us-east-1 \
  --query 'StackSummaries[*].[StackName,StackStatus]' \
  --output table
```

---

## Česti problemi

| Problem | Rješenje |
|---------|---------|
| `Cannot find name 'process'` | `npm install --save-dev @types/node` |
| `Cannot find name 'describe'` | `npm install --save-dev @types/jest` |
| Deploy ne radi bez `--region` | Uvek dodaj `--region us-east-1` |
| OpenSearch ne vraća rezultate | Sačekaj 2 min nakon uploada dokumenta |
| RAGAS greška `config.json not found` | `cp config.example.json config.json` i upiši URL-ove |
| Stack se ne briše | Otvori AWS Console → CloudFormation → Delete stack ručno |
