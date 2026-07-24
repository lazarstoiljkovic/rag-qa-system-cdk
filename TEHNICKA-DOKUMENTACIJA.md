# Tehnička Dokumentacija — RAG Q&A Sistem na AWS-u

**Projekat:** Diplomski rad — Retrieval-Augmented Generation (RAG) sistem za odgovaranje na pitanja  
**Autor:** Lazar Stoiljković  
**Platforma:** Amazon Web Services (AWS)  
**Infrastruktura kao kod:** AWS CDK (TypeScript)  
**Datum:** 2026.

---

## 1. Pregled sistema

RAG (Retrieval-Augmented Generation) sistem omogućava korisnicima da postavljaju pitanja u prirodnom jeziku i dobijaju odgovore zasnovane isključivo na dokumentima koji su prethodno učitani u sistem. Za razliku od klasičnih LLM modela koji odgovaraju na osnovu svog treninga, RAG sistem prvo pronalazi relevantne delove iz baze dokumenata, a zatim koristi jezik modela samo da formuliše odgovor — čime se sprečava halucinacija i povećava tačnost.

### 1.1 Dva implementirana pristupa

Sistem implementira dva arhitekturalno različita RAG rešenja kako bi se omogućila empirijska komparativna analiza:

| | **Knowledge Base Stack** | **Custom OpenSearch Stack** |
|---|---|---|
| Tip rešenja | Upravljano (managed) | Prilagođeno (custom) |
| Vektorska baza | AWS Bedrock Knowledge Base | Amazon OpenSearch Service |
| Pretraga | Automatska (managed) | k-NN vektorska pretraga |
| Chunking | Automatski (Bedrock) | Ručni (512 znakova, 50 overlap) |
| Embedding generisanje | Automatski (Bedrock) | Eksplicitni poziv Titan Embeddings |
| Kompleksnost | Niža | Viša |
| Kontrola nad procesom | Manja | Potpuna |

### 1.2 Zajednički elementi oba rešenja

- **LLM model:** Amazon Bedrock — Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`)
- **Embedding model:** Amazon Bedrock — Titan Embeddings v2 (`amazon.titan-embed-text-v2:0`, 1024 dimenzije)
- **Jezici:** Srpski (`sr`) i engleski (`en`)
- **API sloj:** AWS API Gateway (REST)
- **Logovanje upita:** Amazon DynamoDB
- **Skladištenje dokumenata:** Amazon S3
- **Lambda arhitektura:** ARM64 (Graviton) — jeftinija i brža

---

## 2. Infrastruktura kao kod (AWS CDK)

### 2.1 Šta je AWS CDK?

AWS Cloud Development Kit (CDK) je framework koji omogućava definisanje cloud infrastrukture kroz programski kod umjesto kroz AWS konzolu ili YAML/JSON fajlove. U ovom projektu korišćen je TypeScript.

**Prednosti CDK pristupa:**
- Cela infrastruktura je verzionisana u Git-u
- Deploy i brisanje jednom komandom
- Lako ponovljivo postavljanje na različitim okruženjima
- Type-safe definicija resursa

### 2.2 Struktura CDK projekta

```
rag-qa-system-cdk/
├── bin/
│   └── rag-qa-system-cdk.ts       # Entry point — instancira stackove
├── lib/
│   ├── knowledge-base-stack.ts    # Definicija Knowledge Base stacka
│   └── custom-opensearch-stack.ts # Definicija OpenSearch stacka
├── lambda/                        # Python Lambda funkcije
├── evaluation/                    # RAGAS evaluacioni framework
├── frontend/                      # Web UI
└── test-documents/                # Testni dokumenti
```

### 2.3 Entry point: `bin/rag-qa-system-cdk.ts`

Ovo je početna tačka CDK aplikacije. Instancira oba stacka i prosleđuje im AWS nalog i region:

```typescript
const app = new cdk.App();

new KnowledgeBaseStack(app, 'KnowledgeBaseStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  }
});

new CustomOpenSearchStack(app, 'CustomOpenSearchStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  }
});
```

---

## 3. Knowledge Base Stack (`lib/knowledge-base-stack.ts`)

### 3.1 Pregled

Knowledge Base Stack koristi AWS-ovu upravljanu infrastrukturu za RAG — Bedrock Knowledge Base servis automatski upravlja vektorizacijom i pretraživanjem dokumenata.

### 3.2 AWS resursi koji se kreiraju

#### Amazon S3 — Bucket za dokumente

- **Naziv:** `rag-kb-documents-{account}-{region}`
- **Verzioniranje:** Uključeno
- **Enkripcija:** SSE-S3 (server-side encryption)
- **Javni pristup:** Potpuno blokiran
- **Lifecycle pravila:** Dokumenti se brišu nakon 365 dana
- **EventBridge:** Uključeno (za event-driven arhitekturu)
- **Removal policy:** DESTROY (brisanje sa stackom)

#### Amazon DynamoDB — Tabela za logovanje upita

- **Naziv:** `rag-kb-query-logs`
- **Billing mode:** On-demand (PAY_PER_REQUEST) — plaća se samo po upitu
- **Partition key:** `queryId` (STRING)
- **Sort key:** `timestamp` (STRING)
- **PITR:** Uključeno (point-in-time recovery)
- **Stream:** NEW_AND_OLD_IMAGES
- **GSI:** `timestamp-index` — omogućava pretragu po vremenu
- **Removal policy:** DESTROY

#### AWS Lambda — Document Upload funkcija

- **Naziv:** `rag-kb-document-upload`
- **Runtime:** Docker container (Python 3.11)
- **Memorija:** 1,024 MB
- **Timeout:** 5 minuta
- **Arhitektura:** ARM64
- **CloudWatch log retention:** 7 dana
- **Uloga:** Prihvata dokument od korisnika, enkodira i smješta u S3

#### AWS Lambda — QA Query funkcija

- **Naziv:** `rag-kb-qa-query`
- **Runtime:** Docker container (Python 3.11)
- **Memorija:** 512 MB
- **Timeout:** 30 sekundi
- **Arhitektura:** ARM64
- **CloudWatch log retention:** 7 dana
- **Uloga:** Prima pitanje, pronalazi kontekst iz S3, generiše odgovor

#### API Gateway — REST API

- **Naziv:** `KnowledgeBaseApi`
- **Stage:** `prod`
- **Throttling:** 100 req/s (rate limit), 200 burst
- **CORS:** Omogućen za sve izvore
- **Logovanje:** Uključeno
- **Metrике:** Uključene
- **Endpointi:**
  - `POST /documents` — upload dokumenta
  - `GET /documents` — lista dokumenata
  - `POST /qa` — postavljanje pitanja

#### IAM Role za Bedrock

- **Trust:** `bedrock.amazonaws.com`
- **Permisije:** S3 čitanje, Bedrock InvokeModel, bedrock-agent Retrieve

---

## 4. Custom OpenSearch Stack (`lib/custom-opensearch-stack.ts`)

### 4.1 Pregled

Custom OpenSearch Stack implementira kompletniji i transparentniji RAG pipeline korišćenjem Amazon OpenSearch Service za vektorsku pretragu. Za razliku od Knowledge Base rješenja, ovaj pristup daje potpunu kontrolu nad svakim korakom procesa.

### 4.2 AWS resursi koji se kreiraju

#### Amazon S3 — Bucket za dokumente

- **Naziv:** `rag-os-documents-{account}-{region}`
- **Ista konfiguracija kao KB bucket**
- **Dodatno:** S3 event notifikacije — automatski aktiviraju Document Processor Lambda kada se PDF ili DOCX fajl postavi u `uploads/` prefix

#### Amazon OpenSearch Service — Domen za vektorsku pretragu

- **Naziv:** `rag-vector-search`
- **Engine verzija:** OpenSearch 2.11
- **Broj čvorova:** 1 (svjesna odluka radi troškova)
- **Tip instance:** `t3.small.search`
  - 2 vCPU
  - 4 GB RAM
  - Burstable performance
- **Multi-AZ:** Isključeno (thesis okruženje)
- **Dedicated master čvorovi:** 0
- **EBS Storage:** 20 GB GP3
- **Enkripcija u mirovanju:** Uključena
- **Node-to-node enkripcija:** Uključena
- **HTTPS:** Obavezno
- **Logovanje:** Slow search logs, Application logs, Slow index logs
- **Removal policy:** DESTROY
- **k-NN plugin:** Aktivan — omogućava vektorsku (semantičku) pretragu

#### Amazon DynamoDB — Tabela za logovanje upita

- **Naziv:** `rag-os-query-logs`
- **Ista konfiguracija kao KB tabela**

#### Amazon DynamoDB — Tabela za metapodatke dokumenata

- **Naziv:** `rag-os-document-metadata`
- **Partition key:** `documentId` (STRING)
- **Billing mode:** On-demand
- **Removal policy:** DESTROY
- **Uloga:** Čuva informacije o svakom procesiranom dokumentu (ID, status, broj chunkova, veličina teksta)

#### AWS Lambda — Document Processor

- **Naziv:** `rag-os-document-processor`
- **Runtime:** Docker container (Python 3.11)
- **Memorija:** 2,048 MB (najveća Lambda — teška obrada)
- **Timeout:** 10 minuta (najduži timeout)
- **Arhitektura:** ARM64
- **Okidač:** S3 event (upload PDF/DOCX u `uploads/` prefix)
- **CloudWatch log retention:** 7 dana
- **Uloga:** Ekstraktuje tekst, dijeli na chunkove, generiše embeddings, indeksira u OpenSearch

#### AWS Lambda — QA Query

- **Naziv:** `rag-os-qa-query`
- **Runtime:** Docker container (Python 3.11)
- **Memorija:** 1,024 MB
- **Timeout:** 30 sekundi
- **Arhitektura:** ARM64
- **CloudWatch log retention:** 7 dana
- **Uloga:** Prima pitanje, izvodi k-NN pretragu u OpenSearch, generiše odgovor

#### AWS Lambda — Document Upload

- **Naziv:** `rag-os-document-upload`
- **Runtime:** Docker container (Python 3.11)
- **Memorija:** 512 MB
- **Timeout:** 30 sekundi
- **Arhitektura:** ARM64
- **CloudWatch log retention:** 7 dana
- **Uloga:** Prima fajl od korisnika, čuva u S3 (S3 event zatim pokreće Document Processor)

#### API Gateway — REST API

- **Naziv:** `OpenSearchApi`
- **Ista konfiguracija kao KB API**
- **Endpointi:**
  - `POST /documents` — upload dokumenta
  - `POST /qa` — postavljanje pitanja

---

## 5. Lambda funkcije — Detaljan opis

### 5.1 `lambda/knowledge-base/document-upload/src/index.py`

**Uloga:** Prima dokument od korisnika kroz API Gateway i čuva ga u S3.

**Request format:**
```json
{
  "file": "<base64 enkodiran sadržaj fajla>",
  "filename": "naziv-dokumenta.pdf",
  "language": "sr",
  "metadata": {
    "category": "opciono",
    "author": "opciono"
  }
}
```

**Tok obrade:**
1. Parsira JSON body iz API Gateway eventa
2. Validira da fajl postoji i da je tip podržan (`.pdf`, `.docx`, `.txt`)
3. Dekodira base64 sadržaj
4. Generiše jedinstveni `documentId` (UUID)
5. Postavlja fajl u S3 na putanju `uploads/{language}/{documentId}/{filename}`
6. Dodaje S3 metapodatke: `document-id`, `upload-timestamp`, `language`, `original-filename`
7. Vraća response sa `documentId` i S3 ključem

**Response format:**
```json
{
  "message": "Document uploaded successfully and queued for processing",
  "documentId": "uuid",
  "s3Key": "uploads/sr/uuid/naziv-dokumenta.pdf",
  "bucket": "rag-kb-documents-...",
  "language": "sr",
  "timestamp": "2026-01-01T12:00:00.000000"
}
```

**Environment varijable:**
- `DOCUMENTS_BUCKET` — naziv S3 bucketa
- `REGION` — AWS region

---

### 5.2 `lambda/knowledge-base/qa-query/src/index.py`

**Uloga:** Prima pitanje od korisnika, pronalazi kontekst iz S3 i generiše odgovor pomoću Claude modela.

**Request format:**
```json
{
  "question": "Koliko dana godišnjeg odmora imaju zaposleni?",
  "language": "sr"
}
```

**Tok obrade:**
1. Parsira pitanje i jezik iz request body-a
2. `retrieve_context()` — listavanjem S3 pronalazi do 3 najnovija dokumenta za dati jezik
3. `generate_answer()` — kreira prompt sa kontekstom i poziva Claude 3 Haiku
4. Logovana upit u DynamoDB (`queryId`, pitanje, odgovor, processing time, `solution: 'knowledge-base'`)
5. Vraća odgovor sa izvorima i vremenima obrade

**Prompt šablon (srpski):**
```
Ti si pomoćnik za odgovaranje na pitanja na osnovu datih dokumenata.

Kontekst iz dokumenata:
{context}

Pitanje: {question}

Molim te da odgovoriš koristeći isključivo informacije iz datog konteksta.
Ako odgovor nije u kontekstu, reci da ne znaš.
```

**Parametri LLM poziva:**
- `max_tokens`: 1000
- `temperature`: 0.3 (deterministički odgovor)
- `top_p`: 0.9

**Napomena o ograničenjima:** Ova implementacija koristi pojednostavljen pristup — pronalazi dokumente po S3 prefiksu umjesto stvarne semantičke pretrage. Produkcijska verzija bi koristila Bedrock `RetrieveAndGenerate` API.

**Environment varijable:**
- `DOCUMENTS_BUCKET` — naziv S3 bucketa
- `LOGS_TABLE` — naziv DynamoDB tabele
- `BEDROCK_MODEL_ID` — `anthropic.claude-3-haiku-20240307-v1:0`
- `EMBEDDING_MODEL_ID` — `amazon.titan-embed-text-v2:0`
- `REGION` — AWS region

---

### 5.3 `lambda/opensearch/document-upload/src/index.py`

**Uloga:** Identična kao KB document-upload. Prima fajl, čuva u S3. S3 event automatski pokreće Document Processor Lambda.

**Razlika od KB verzije:** Upload u S3 okida S3 event notifikaciju koja pokreće `document-processor` Lambda — procesiranje je asinhronо.

---

### 5.4 `lambda/opensearch/document-processor/src/index.py`

**Uloga:** Najkompleksnija Lambda u sistemu. Obrađuje dokument u potpunosti: ekstrakcija teksta → chunking → embedding → indeksiranje u OpenSearch.

**Okidač:** S3 event (automatski poziv kada se fajl postavi u `uploads/` prefix)

**Tok obrade:**

**Korak 1 — Preuzimanje dokumenta iz S3**
```python
s3_client.download_file(bucket, key, local_path)
```

**Korak 2 — Ekstrakcija teksta**
- **PDF:** Koristi `PyPDF2` — iterira kroz stranice i spaja tekst
- **DOCX:** Koristi `python-docx` — iterira kroz paragrafe
- **TXT:** Direktno UTF-8 dekodiranje

**Korak 3 — Chunking (dijeljenje na dijelove)**
- Veličina chunka: **512 znakova**
- Overlap (preklapanje): **50 znakova**
- Algoritam: Klizni prozor sa preklapanjem
- Razlog za overlap: Sprečava gubitak konteksta na granicama chunkova

Primjer chunking-a:
```
Tekst:    [----chunk 1 (512)----][overlap(50)][----chunk 2 (512)----]
                              ^---------^
                         isti tekst u oba chunka
```

**Korak 4 — Generisanje embeddings**
Za svaki chunk poziva se Bedrock Titan Embeddings v2:
```python
bedrock_runtime.invoke_model(
    modelId='amazon.titan-embed-text-v2:0',
    body=json.dumps({"inputText": chunk_text})
)
# → vraća vektor od 1024 dimenzija
```

**Korak 5 — Kreiranje OpenSearch indeksa (ako ne postoji)**

OpenSearch index mapping:
```json
{
  "settings": {
    "index": {
      "knn": true,
      "knn.algo_param.ef_search": 512
    }
  },
  "mappings": {
    "properties": {
      "chunk_id": {"type": "keyword"},
      "document_id": {"type": "keyword"},
      "chunk_index": {"type": "integer"},
      "text": {"type": "text", "analyzer": "standard"},
      "embedding": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib",
          "parameters": {"ef_construction": 512, "m": 16}
        }
      },
      "language": {"type": "keyword"},
      "original_filename": {"type": "keyword"},
      "timestamp": {"type": "date"}
    }
  }
}
```

**HNSW algoritam:** Hierarchical Navigable Small World — efikasna struktura za approximate nearest neighbor pretragu. `m: 16` kontroliše broj veza po čvoru, `ef_construction: 512` kontroliše tačnost tokom izgradnje indeksa.

**Korak 6 — Indeksiranje u OpenSearch**
Svaki chunk se indeksira kao dokument:
```json
{
  "chunk_id": "doc_uuid_chunk_0",
  "document_id": "doc_uuid",
  "chunk_index": 0,
  "text": "sadržaj chunka...",
  "embedding": [0.123, -0.456, ...],  // 1024 vrijednosti
  "language": "sr",
  "original_filename": "godisnji-odmor.txt",
  "timestamp": "2026-01-01T12:00:00Z"
}
```

**Korak 7 — Čuvanje metapodataka u DynamoDB**
```json
{
  "documentId": "uuid",
  "filename": "godisnji-odmor.txt",
  "language": "sr",
  "status": "processed",
  "chunkCount": 12,
  "textLength": 5840,
  "timestamp": "..."
}
```

**Environment varijable:**
- `OPENSEARCH_ENDPOINT` — endpoint OpenSearch domena
- `OPENSEARCH_INDEX` — `documents`
- `DOCUMENT_METADATA_TABLE` — DynamoDB tabela za metapodatke
- `BEDROCK_MODEL_ID` — Claude 3 Haiku
- `EMBEDDING_MODEL_ID` — Titan Embeddings v2
- `CHUNK_SIZE` — 512
- `CHUNK_OVERLAP` — 50
- `REGION` — AWS region

---

### 5.5 `lambda/opensearch/qa-query/src/index.py`

**Uloga:** Srce OpenSearch RAG rješenja. Prima pitanje, izvodi semantičku pretragu, generiše odgovor.

**Request format:**
```json
{
  "question": "Koliko traje sprint?",
  "language": "sr",
  "top_k": 5
}
```

**Tok obrade:**

**Korak 1 — Generisanje embedding-a za pitanje**
```python
bedrock_runtime.invoke_model(
    modelId='amazon.titan-embed-text-v2:0',
    body=json.dumps({"inputText": question})
)
# → vektor od 1024 dimenzija koji reprezentuje semantičko značenje pitanja
```

**Korak 2 — k-NN vektorska pretraga u OpenSearch**

OpenSearch query:
```json
{
  "size": 5,
  "query": {
    "bool": {
      "must": [
        {
          "knn": {
            "embedding": {
              "vector": [0.123, -0.456, ...],
              "k": 5
            }
          }
        }
      ],
      "filter": [
        {"term": {"language": "sr"}}
      ]
    }
  },
  "_source": ["text", "document_id", "chunk_index", "original_filename"]
}
```

Pretraga pronalazi 5 najsličnijih chunkova mjerenjem **kosinusne sličnosti** između vektora pitanja i vektora svakog chunka u indeksu.

**Korak 3 — Generisanje odgovora**

Pronađeni chunkovi se spajaju u kontekst i šalju Claude-u:
```
[Dokument 1: godisnji-odmor.txt]
Standardna alokacija: 20 radnih dana...

[Dokument 2: scrum-guide.txt]
SPRINT STRUKTURA - Dužina sprinta: 2 nedelje...

Pitanje: Koliko traje sprint?
→ Claude odgovara samo na osnovu ovog konteksta
```

**Korak 4 — Logovanje i response**

Response uključuje:
- `answer` — generisani odgovor
- `contexts` — stvarni tekstovi chunkova (za RAGAS evaluaciju)
- `sources` — nazivi fajlova sa relevantnim skorovima
- `processingTime` — ukupno vreme obrade

**Environment varijable:**
- `OPENSEARCH_ENDPOINT`, `OPENSEARCH_INDEX`
- `LOGS_TABLE`, `BEDROCK_MODEL_ID`, `EMBEDDING_MODEL_ID`
- `TOP_K` — 5 (broj chunkova za pretragu)
- `REGION`

---

## 6. Evaluacioni framework (`evaluation/`)

### 6.1 Motivacija

Da bi se empirijski uporedila dva RAG rješenja, implementiran je evaluacioni framework baziran na RAGAS biblioteci. RAGAS koristi LLM kao sudiju za automatsko ocjenjivanje bez potrebe za ljudskim anotatorima.

### 6.2 Struktura evaluacije

```
evaluation/
├── dataset.json          # 20 Q&A parova sa ground truth odgovorima
├── evaluate.py           # Glavni evaluacioni skript
├── requirements.txt      # Python zavisnosti
├── config.example.json   # Šablon za API URL-ove
└── results/              # JSON rezultati evaluacije (gitignored)
```

### 6.3 `evaluation/dataset.json`

Sadrži 20 evaluacionih pitanja sa tačnim odgovorima (ground truth):

- **10 srpskih pitanja** iz oblasti:
  - HR politike (godišnji odmor, sick days)
  - Scrum procesi (trajanje sprinta, ceremony-i)

- **10 engleskih pitanja** iz oblasti:
  - Code review smjernice (veličina PR-a, broj reviewera)
  - Incident response (severity nivoi, response timovi)
  - Monitoring alati

Svaki zapis ima:
```json
{
  "question": "Koliko traje sprint?",
  "ground_truth": "Sprint traje 2 nedelje (10 radnih dana)...",
  "language": "sr",
  "category": "Scrum"
}
```

### 6.4 `evaluation/evaluate.py`

**Tok evaluacije:**

1. Učitava `config.json` (API URL-ovi) i `dataset.json` (pitanja)
2. Za svaki stack (OpenSearch i Knowledge Base):
   - Poziva `/qa` endpoint za svako pitanje
   - Prikuplja: pitanje, odgovor, kontekste, ground truth, processing time
3. Kreira RAGAS dataset sa svim prikupljenim podacima
4. Pokreće 4 RAGAS metrike
5. Štampa tabelu poređenja
6. Čuva kompletne rezultate u `results/evaluation_{timestamp}.json`

**Konfiguracija RAGAS LLM sudije:**

RAGAS koristi Claude 3 Haiku (isti model) kao sudiju za ocjenjivanje:
```python
ragas_llm = LangchainLLMWrapper(
    ChatBedrock(model_id="anthropic.claude-3-haiku-20240307-v1:0")
)
ragas_embeddings = LangchainEmbeddingsWrapper(
    BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0")
)
```

### 6.5 RAGAS metrike — Detaljan opis

#### Faithfulness (Vjernost)
**Šta mjeri:** Da li je odgovor zasnovan isključivo na pronađenom kontekstu? Sprečava halucinaciju.  
**Potrebno:** odgovor + konteksti  
**Formula:** `broj tvrdnji iz odgovora podržanih kontekstom / ukupan broj tvrdnji`  
**Idealna vrijednost:** 1.0

#### Answer Relevancy (Relevantnost odgovora)
**Šta mjeri:** Da li odgovor zaista odgovara na postavljeno pitanje?  
**Potrebno:** pitanje + odgovor + konteksti  
**Formula:** Kosinusna sličnost između embeddinga pitanja i embeddinga generisanih pitanja iz odgovora  
**Idealna vrijednost:** 1.0

#### Context Recall (Pokrivenost kontekstom)
**Šta mjeri:** Da li je pronađeni kontekst sadržao sve informacije potrebne za tačan odgovor?  
**Potrebno:** konteksti + ground truth  
**Formula:** `broj rečenica iz ground truth pokrivenih kontekstom / ukupan broj rečenica u ground truth`  
**Idealna vrijednost:** 1.0

#### Context Precision (Preciznost konteksta)
**Šta mjeri:** Da li su pronađeni konteksti korisni i relevantni (bez šuma)?  
**Potrebno:** pitanje + konteksti + ground truth  
**Formula:** Udio relevantnih rankova u pronađenim kontekstima  
**Idealna vrijednost:** 1.0

---

## 7. Web korisnički interfejs (`frontend/index.html`)

Kompletni web UI implementiran kao jedna HTML stranica bez potrebe za serverom (otvara se direktno u browseru).

### 7.1 Funkcionalnosti

- **Odabir rješenja:** Prebacivanje između Knowledge Base i OpenSearch rješenja
- **Konfiguracija API URL-ova:** Polja za unos URL-ova nakon svakog deploy-a (ne hardcoded)
- **Upload dokumenta:** File picker → base64 enkodiranje u browseru → slanje na API
- **Q&A interfejs:** Unos pitanja, odabir jezika, prikaz odgovora i izvora
- **Prikaz izvora:** Nazivi fajlova sa relevantnim skorovima
- **Processing time:** Prikaz vremena generisanja odgovora

### 7.2 Kako radi upload u browseru

Browser čita fajl kao base64 string i šalje ga kao JSON:
```javascript
const reader = new FileReader();
reader.onload = (e) => {
    const base64Content = e.target.result.split(',')[1]; // uklanja data: prefiks
    fetch(apiUrl + '/documents', {
        method: 'POST',
        body: JSON.stringify({ file: base64Content, filename: file.name, language })
    });
};
reader.readAsDataURL(file);
```

### 7.3 Pokretanje

Dupli klik na `frontend/index.html` — otvara se u browseru. Nema potrebe za web serverom.

---

## 8. Testni dokumenti (`test-documents/`)

### 8.1 Struktura

```
test-documents/
├── sr/                    # Srpski dokumenti — AWS i tehnologije
│   ├── aws-uvod.txt
│   ├── cloud-computing.txt
│   └── machine-learning.txt
├── en/                    # Engleski dokumenti — AWS i tehnologije
│   └── aws-intro.txt
└── company/               # Kompanijski dokumenti (TechSolutions d.o.o.)
    ├── sr/
    │   ├── benefiti.txt
    │   ├── godisnji-odmor.txt
    │   ├── onboarding-procedura.txt
    │   ├── politika-rada-na-daljinu.txt
    │   ├── sajber-bezbednost.txt
    │   ├── scrum-guide.txt
    │   ├── finansijski-izvestaj-q4-2025.txt
    │   └── strateski-plan-2026-2028.txt
    └── en/
        ├── code-review-guidelines.txt
        ├── customer-success-playbook.txt
        ├── deployment-process.txt
        ├── incident-response.txt
        ├── performance-review.txt
        └── product-roadmap-2026.txt
```

### 8.2 Sadržaj kompanijskih dokumenata

| Dokument | Sadržaj |
|----------|---------|
| `godisnji-odmor.txt` | Politika godišnjeg odmora, sick days, plaćena odsustva |
| `scrum-guide.txt` | Sprint struktura, Scrum uloge, ceremony-i, Definition of Done |
| `sajber-bezbednost.txt` | Politika lozinki, prijavljivanje incidenata, pravila pristupa |
| `onboarding-procedura.txt` | Prvog dana, mentor sistem, podešavanje alata |
| `benefiti.txt` | Zdravstveno osiguranje, benefiti, bonus politika |
| `code-review-guidelines.txt` | Veličina PR-a, broj reviewera, SLA za review |
| `incident-response.txt` | Severity nivoi, response timovi, komunikacija, post-mortem |
| `deployment-process.txt` | Pipeline okruženja, deploy proces, rollback |

---

## 9. Infrastrukturne odluke i kompromisi

### 9.1 Zašto ARM64 Lambda arhitektura?

ARM64 (Graviton2) Lambda funkcije su ~20% jeftinije od x86_64 za isti workload. Za sistem koji može primiti veliki broj upita, ovo je značajna ušteda. Svi Docker image-i su build-ovani sa `--platform linux/arm64`.

### 9.2 Zašto `t3.small.search` za OpenSearch?

Najmanji dostupni tip instance koji podržava k-NN plugin. Za thesis projekat sa malim brojem dokumenata i upita, ovo je sasvim dovoljno. Produkcijski sistem bi koristio minimum `r6g.large.search` (memory-optimized za vektorske operacije).

### 9.3 Zašto je Multi-AZ isključeno?

Multi-AZ zahtijeva minimum 2 data čvora i dedicated master čvorove, što troškove diže sa ~$40/mj na ~$120+/mj. Za thesis istraživanje ovo nije opravdano. U produkciji bi Multi-AZ bio obavezan.

### 9.4 Zašto On-demand DynamoDB billing?

On-demand billing znači $0 troška kada se sistem ne koristi. Za thesis projekat koji se koristi povremeno, ovo je optimalno — nema minimalnih troškova za provisioniranu kapacitet.

### 9.5 Zašto RemovalPolicy.DESTROY?

Omogućava potpuno brisanje svih resursa jednom komandom `cdk destroy`. Alternativa `RETAIN` bi ostavila resurse (i troškove) i nakon brisanja stacka. Za thesis okruženje, `DESTROY` je praktičniji.

---

## 10. Sigurnosna konfiguracija

- **S3 bucket:** Sav javni pristup blokiran, server-side enkripcija
- **OpenSearch:** Enkripcija u mirovanju i u transportu, HTTPS obavezno, pristup samo kroz IAM
- **Lambda IAM:** Princip najmanjeg privilegija — svaka Lambda ima samo permisije koje su joj potrebne
- **API Gateway:** CORS konfigurisan (za thesis otvoreno za sve izvore)
- **DynamoDB:** PITR uključen za point-in-time oporavak
- **CloudWatch:** Logovi čuvani 7 dana, zatim automatski brišu

---

## 11. Monitoring i observability

- **Lambda logovi:** CloudWatch Logs (7 dana retencije)
- **OpenSearch logovi:** Slow search, slow index, application logs
- **API Gateway:** Metrике i access logovi
- **DynamoDB:** Svaki upit loguje se sa `queryId`, pitanjem, odgovorom i processing time-om
- **Document Metadata:** Svaki procesiran dokument evidentiran u DynamoDB sa statusom

---

## 12. Tok podataka — End-to-end

### 12.1 Upload dokumenta (OpenSearch Stack)

```
Korisnik (Browser/curl)
    ↓ POST /documents (base64 fajl)
API Gateway
    ↓ invoke
Document Upload Lambda
    ↓ PutObject
Amazon S3 (uploads/sr/uuid/fajl.txt)
    ↓ S3 Event Notification
Document Processor Lambda
    ├─ Ekstrakcija teksta (PyPDF2 / python-docx / txt)
    ├─ Chunking (512 znakova, 50 overlap)
    ├─ Za svaki chunk:
    │   ├─ Bedrock Titan Embeddings v2 → vektor [1024 dim]
    │   └─ OpenSearch index (tekst + vektor + metapodaci)
    └─ DynamoDB (metapodaci dokumenta)
```

### 12.2 Postavljanje pitanja (OpenSearch Stack)

```
Korisnik (Browser/curl)
    ↓ POST /qa (pitanje, jezik)
API Gateway
    ↓ invoke
QA Query Lambda
    ├─ Bedrock Titan Embeddings v2 → vektor pitanja [1024 dim]
    ├─ OpenSearch k-NN pretraga → top-5 najsličnijih chunkova
    ├─ Bedrock Claude 3 Haiku → generisanje odgovora
    └─ DynamoDB (log upita)
    ↓ Response
Korisnik ← { answer, contexts, sources, processingTime }
```

---

## 13. Konverzija ovog dokumenta u Word/PDF

Da biste konvertovali ovaj Markdown fajl u Word ili PDF:

### Opcija A — Pandoc (preporučeno)
```bash
# Instaliraj pandoc
brew install pandoc

# Konvertuj u Word
pandoc TEHNICKA-DOKUMENTACIJA.md -o dokumentacija.docx

# Konvertuj u PDF
pandoc TEHNICKA-DOKUMENTACIJA.md -o dokumentacija.pdf
```

### Opcija B — VS Code ekstenzija
Instalirajte "Markdown PDF" ekstenziju u VS Code → desni klik na fajl → "Markdown PDF: Export (pdf)"

### Opcija C — Online alat
Kopirajte sadržaj na `markdowntoword.com` ili `md2pdf.netlify.app`
