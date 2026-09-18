# Konkretizacija teme diplomskog rada

**Radni naslov:** Self-hosted RAG sistem za pitanja i odgovore nad multimodalnom internom dokumentacijom fiktivne IT kompanije

**Autor:** Lazar Stoiljković
**Datum:** Jul 2026.

---

## 1. Motivacija za konkretizaciju

Prethodna verzija rada je poredila dva RAG rešenja koja oba koriste isti upravljani (managed) LLM servis — Amazon Bedrock — i razlikuju se samo u načinu vektorske pretrage (Bedrock Knowledge Base naspram sopstvenog OpenSearch indeksa). Na konsultacijama je ocenjeno da je ovakav opseg previše opšt: rad u velikoj meri demonstrira korišćenje AWS servisa, a ne rešava konkretan istraživački problem.

Tema je konkretizovana u tri pravca:

1. **Definisan je konkretan skup dokumenata** — mešavina čisto tekstualnih i "born-digital" dokumenata sa ugrađenim slikama (dijagrami, grafikoni), čime se otvara pitanje multimodalne obrade dokumenata u RAG sistemu.
2. **Implementira se jedan, do kraja razrađen end-to-end pipeline**, umesto poređenja dva paralelna managed rešenja.
3. **Generativni deo sistema (LLM), embedding model i model za opis slika su self-hosted** — pokreću se na sopstvenoj GPU infrastrukturi, a ne kroz upravljani AI servis.

---

## 2. Pojmovno objašnjenje: šta znači "self-hosted RAG"?

### 2.1 RAG (Retrieval-Augmented Generation)

RAG sistem ima dve suštinske komponente:

- **Retrieval** — embedding model + vektorska baza + pretraga → pronalazi relevantne delove dokumenata.
- **Generation** — LLM → uzima pronađeni kontekst i pitanje, i formuliše konačan odgovor u prirodnom jeziku.

Bez LLM-a (generation dela), sistem bi bio samo pretraživač koji vraća sirove delove teksta, a ne formulisan odgovor. Bez retrieval dela, LLM bi bio običan chatbot koji odgovara isključivo iz sopstvenog pretreniranog znanja, bez oslonca na konkretne dokumente — što je upravo ono što RAG pokušava da spreči (halucinacije, needostatak grounding-a).

### 2.2 Managed naspram self-hosted pristupa

- **Managed** (npr. Amazon Bedrock) — poziva se tuđ servis preko API-ja; model radi na infrastrukturi provajdera; plaća se po pozivu/tokenu; nema pristupa težinama modela niti kontrole nad hardverom na kom radi.
- **Self-hosted** (novi pravac) — open-weight model (npr. Mistral-7B) se preuzima i pokreće na sopstvenoj infrastrukturi (EC2 GPU instanca koja se sama provisionira i njome se upravlja), uz serving softver poput vLLM-a. Vlasnik sistema je odgovoran za GPU, skaliranje i dostupnost, ali ima potpunu kontrolu nad modelom.

### 2.3 Šta se konkretno dobija self-hostingom LLM-a

Self-hosting ne garantuje bolji kvalitet odgovora — mali open-weight model (7B) realno neće nadmašiti Claude 3 Haiku po kvalitetu generisanja. Dobitak je drugačije prirode:

1. **Demonstracija razumevanja inference serving-a** — sposobnost da se postavi i konfiguriše pravi serving sloj (vLLM, continuous batching, upravljanje KV cache-om), a ne samo pozivanje tuđeg API-ja. Ovo je akademski najvredniji deo — dokazuje dublje tehničko razumevanje kako LLM inference stvarno radi.
2. **Empirijski materijal za poređenje** — merljiva latencija po fazi, trošak (GPU po satu naspram pay-per-token modela) i kvalitet odgovora (RAGAS) self-hosted naspram managed pristupa. Ovo je konkretan istraživački doprinos koji prethodna verzija rada nije imala (poredila je dva managed pristupa koja koriste isti LLM).
3. **Nezavisnost od cloud provajdera** — podaci (interna dokumentacija fiktivne kompanije) nikad ne napuštaju sopstvenu infrastrukturu; nema zavisnosti od dostupnosti, cenovnika ili politike jednog vendora.
4. **Potpuna kontrola nad modelom** — mogućnost izbora tačne verzije/kvantizacije modela, i teorijski, mogućnost fine-tuninga (vidi 2.4), što managed servisi ne dozvoljavaju.

Ukratko: dobitak nije "bolji odgovori", nego dublja kontrola, merljivost i nezavisnost.

### 2.4 Fine-tuning (napomena)

Fine-tuning je dodatno treniranje već pretreniranog modela na sopstvenim, specifičnim podacima radi prilagođavanja konkretnom zadatku ili domenu — npr. treniranje Mistral-7B na Q&A parovima iz korpusa fiktivne kompanije (efikasnije preko LoRA/QLoRA), radi boljeg poznavanja terminologije, stila odgovora ili boljeg rada na srpskom jeziku.

Kod self-hosted modela ovo je moguće jer postoji pristup sirovim težinama modela; kod managed servisa (Bedrock) to generalno nije moguće ili je jako ograničeno. Fine-tuning **trenutno nije deo obima ovog rada** — pominje se ovde samo kao teorijska prednost self-hostinga i mogući pravac budućeg proširenja, ne kao planirana implementacija.

---

## 3. Skup dokumenata (korpus)

Korpus namerno **ne** koristi opšte javno dostupno tehničko znanje (npr. uvodni tekstovi o AWS-u ili mašinskom učenju), jer bi takav sadržaj mogao biti deo pretreninga generativnog modela — u tom slučaju model može dati tačan odgovor i bez ispravnog retrievala, što obesmišljava merenje faithfulness metrike (da li je odgovor stvarno zasnovan na pronađenom kontekstu).

Umesto toga, korpus je **uzak i izmišljen (sintetički)**: interna tehnička dokumentacija fiktivne kompanije (npr. "TechSolutions d.o.o.") koja opisuje arhitekturu njenog sopstvenog softverskog sistema. Sadržaj (imena servisa, brojevi, dijagrami, metrike) je izmišljen i ne postoji nigde javno, čime se garantuje da model ne može odgovoriti tačno bez retrievala iz dokumenata. Korpus se sastoji od dve kategorije:

- **Čisto tekstualni dokumenti** — npr. opis mikroservisa, tehničke specifikacije, changelog, runbook-ovi za incidente.
- **Born-digital dokumenti sa ugrađenim slikama** — PDF/DOCX fajlovi kod kojih je tekst selektabilan, ali sadrže i dijagrame arhitekture sistema, flowchart-ove deployment procesa i grafikone performansi/troškova koji nose deo informacije nezavisno od okolnog teksta.

Ova kombinacija omogućava direktno poređenje kvaliteta odgovora na pitanja koja zahtevaju isključivo tekstualni kontekst naspram pitanja koja zahtevaju informaciju sadržanu isključivo u slici (npr. "Koje slojeve ima arhitektura sistema X?" — odgovor je vidljiv samo na dijagramu, ne i u pratećem tekstu).

---

## 4. Arhitektura sistema

### 4.1 Obrada dokumenata (ingestion)

```
Dokument (PDF/DOCX)
   │
   ├─ Ekstrakcija teksta ──────────────► Chunking (512 znakova, 50 overlap)
   │
   └─ Ekstrakcija slika
          │
          ▼
   Captioning model (self-hosted)
   generiše tekstualni opis slike
          │
          ▼
   Opis slike se tretira kao dodatni chunk
          │
          ▼
   Embedding model (self-hosted) ──► vektor
          │
          ▼
   Indeksiranje u OpenSearch (tekst + vektor + metapodaci)
```

### 4.2 Odgovaranje na pitanje (query)

```
Pitanje korisnika
   │
   ▼
Embedding model (self-hosted) ──► vektor pitanja
   │
   ▼
k-NN vektorska pretraga u OpenSearch ──► top-k najrelevantnijih chunkova
   │                                     (tekstualni i captioni slika)
   ▼
Generativni LLM (self-hosted) ──► odgovor zasnovan na pronađenom kontekstu
```

### 4.3 Self-hosted komponente

Sve tri AI komponente pokreću se na sopstvenoj GPU infrastrukturi (EC2 GPU instanca), umesto kroz Amazon Bedrock:

| Komponenta | Uloga | Kandidat model |
|---|---|---|
| Embedding model | Pretvara tekst i opise slika u vektore (sr + en) | BAAI/bge-m3 |
| Captioning model | Generiše tekstualni opis dijagrama/grafikona | BLIP-2 |
| Generativni LLM | Generiše finalni odgovor na osnovu pronađenog konteksta | Mistral-7B-Instruct (vLLM serving) |

Generativni model se servira preko **vLLM**-a (OpenAI-compatible API, continuous batching, upravljanje KV cache-om), što omogućava teorijsku diskusiju o pravom inference serving-u, a ne samo pozivanju modela.

Procena GPU resursa: tri modela zajedno (Mistral-7B FP16 ~15GB, BLIP-2 ~5-6GB, bge-m3 ~2GB) zahtevaju `g5.xlarge` (24GB VRAM, A10G) uz eventualnu 4-bit kvantizaciju generativnog modela radi rezerve memorije, ili `g5.2xlarge` bez kvantizacije.

---

## 5. Odnos prema prethodnoj verziji rada

- **Custom OpenSearch rešenje** (vektorska baza, chunking, k-NN pretraga) se zadržava kao osnova — infrastruktura oko OpenSearch-a, S3-a i DynamoDB-a ostaje ista.
- **Bedrock pozivi** (Titan Embeddings, Claude 3 Haiku) se **zamenjuju** pozivima ka self-hosted modelima na GPU instanci.
- **Knowledge Base rešenje** (Bedrock managed pristup) se uklanja iz aktivnog fokusa rada i pominje se u dokumentaciji samo kao napušten pravac — poređenje dva managed pristupa više nije centralna tema rada.
- Rezultat je **jedan, dublje razrađen sistem**, umesto dva plića.

---

## 6. Plan evaluacije

Zadržava se postojeći RAGAS evaluacioni okvir (faithfulness, answer relevancy, context recall, context precision), primenjen sada nad self-hosted sistemom. Dataset pitanja se proširuje pitanjima koja zahtevaju informaciju isključivo iz slike, kako bi se posebno mogao izmeriti doprinos captioning koraka.

Dodatno se mere:
- **Latencija** po fazi (embedding, retrieval, captioning, generisanje) — poredi se sa prethodno izmerenim Bedrock latencijama.
- **Troškovi** — GPU instanca po satu naspram pay-per-token Bedrock modela, uz analizu break-even tačke u zavisnosti od obima saobraćaja.

---

## 7. Otvorena pitanja za konsultacije

- Da li GPU instanca treba da radi 24/7 tokom razvoja ili se pali/gasi po potrebi (uticaj na testiranje i troškove)?
- Obim poglavlja u samom radu koji se posvećuje teorijskom pregledu vision-language modela.
