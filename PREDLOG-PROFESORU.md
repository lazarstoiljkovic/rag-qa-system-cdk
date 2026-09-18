# Konkretizacija teme diplomskog rada

**Radni naslov:** Self-hosted RAG sistem za pitanja i odgovore nad multimodalnom internom dokumentacijom fiktivne IT kompanije

**Autor:** Lazar Stoiljković
**Datum:** Jul 2026.

---

## 1. Ideja rada

Prethodna verzija rada je poredila dva RAG (Retrieval-Augmented Generation) rešenja koja oba koriste isti upravljani (managed) LLM servis — Amazon Bedrock — i razlikuju se samo u načinu vektorske pretrage. Na konsultacijama je ocenjeno da je ovakav opseg previše opšt, jer rad u velikoj meri demonstrira korišćenje gotovih AWS servisa, a ne rešava konkretan istraživački problem.

Tema je konkretizovana u tri pravca:

1. **Konkretan, uzak skup dokumenata** — mešavina čisto tekstualnih i "born-digital" dokumenata sa ugrađenim slikama (dijagrami arhitekture, grafikoni), čime se otvara pitanje multimodalne obrade sadržaja u RAG sistemu.
2. **Jedan, do kraja razrađen end-to-end pipeline**, umesto poređenja dva paralelna managed rešenja.
3. **Potpuno self-hosted AI sloj** — embedding model, model za opis slika (captioning) i generativni LLM rade na sopstvenoj GPU infrastrukturi, umesto kroz upravljani cloud AI servis.

Cilj rada postaje: implementirati i empirijski evaluirati sistem koji sam upravlja celokupnim RAG pipeline-om — od pripreme multimodalnih dokumenata do generisanja odgovora — bez oslanjanja na upravljane AI servise, i uporediti ga (kvalitet, latencija, troškovi) sa prethodno izmerenim managed pristupom.

---

## 2. Skup dokumenata (korpus)

Korpus namerno **ne** koristi opšte javno dostupno tehničko znanje, jer bi takav sadržaj mogao biti deo pretreninga generativnog modela — model bi tada mogao dati tačan odgovor i bez ispravnog retrievala, što bi obesmislilo merenje faithfulness metrike (da li je odgovor stvarno zasnovan na pronađenom kontekstu).

Umesto toga, korpus je **uzak i sintetički**: interna tehnička dokumentacija fiktivne kompanije, koja opisuje arhitekturu njenog sopstvenog softverskog sistema. Sadržaj (imena servisa, brojevi, dijagrami, metrike) je izmišljen i ne postoji nigde javno, čime se garantuje da model ne može odgovoriti tačno bez retrievala. Korpus obuhvata:

- **Tekstualne dokumente** — opis mikroservisa, tehničke specifikacije, changelog, runbook-ovi za incidente.
- **Born-digital dokumente sa slikama** — PDF/DOCX fajlovi sa selektabilnim tekstom koji sadrže i dijagrame arhitekture, flowchart-ove deployment procesa i grafikone performansi/troškova — informacija koja nije opisana u pratećem tekstu.

Ovo omogućava poređenje kvaliteta odgovora na pitanja koja zahtevaju isključivo tekstualni kontekst naspram pitanja čiji je odgovor sadržan isključivo u slici.

---

## 3. Arhitektura i infrastruktura

**Priprema dokumenata (ingestion):**

```
Dokument (PDF/DOCX)
   ├─ Ekstrakcija teksta ──► Chunking (512 znakova, 50 overlap)
   └─ Ekstrakcija slika ──► Captioning model (self-hosted) ──► opis slike kao dodatni chunk
                                                                       │
                                                                       ▼
                                        Embedding model (self-hosted) ──► vektor
                                                                       │
                                                                       ▼
                                        Indeksiranje u OpenSearch (tekst + vektor + metapodaci)
```

**Odgovaranje na pitanje (query):**

```
Pitanje ──► Embedding model (self-hosted) ──► k-NN pretraga u OpenSearch (top-k chunkova)
                                                                       │
                                                                       ▼
                                        Generativni LLM (self-hosted) ──► odgovor
```

**Self-hosted AI komponente** (sve rade na sopstvenoj GPU EC2 instanci, ne kroz Bedrock):

| Komponenta | Uloga | Kandidat model |
|---|---|---|
| Embedding model | Pretvara tekst i opise slika u vektore (sr + en) | BAAI/bge-m3 |
| Captioning model | Generiše tekstualni opis dijagrama/grafikona | BLIP-2 |
| Generativni LLM | Generiše finalni odgovor na osnovu konteksta | Mistral-7B-Instruct (vLLM serving) |

Generativni model se servira preko **vLLM**-a (OpenAI-compatible API, continuous batching, upravljanje KV cache-om), što omogućava analizu pravog inference serving sloja, a ne samo pozivanje gotovog API-ja.

Procena GPU resursa: tri modela zajedno (Mistral-7B FP16 ~15GB, BLIP-2 ~5-6GB, bge-m3 ~2GB) zahtevaju instancu tipa `g5.xlarge` (24GB VRAM, NVIDIA A10G), uz eventualnu 4-bit kvantizaciju generativnog modela radi rezerve memorije.

Ostatak infrastrukture (S3 za dokumente, OpenSearch za vektorsku pretragu, DynamoDB za logovanje, API Gateway) ostaje nepromenjen u odnosu na postojeće rešenje — menja se samo AI sloj.

---

## 4. Prednosti pristupa u odnosu na prethodnu verziju

Self-hosting ne garantuje bolji kvalitet odgovora — mali open-weight model (7B parametara) realno neće nadmašiti Claude 3 Haiku po kvalitetu generisanja. Vrednost pristupa je drugačije prirode:

- **Dublje tehničko razumevanje** — implementacija pravog inference serving sloja (vLLM, batching, upravljanje memorijom), umesto pozivanja gotovog API-ja.
- **Merljivo empirijsko poređenje** — konkretni brojevi za latenciju, trošak (GPU po satu naspram pay-per-token modela) i kvalitet odgovora (RAGAS) self-hosted naspram managed pristupa — čega u prethodnoj verziji rada nije bilo.
- **Nezavisnost od cloud provajdera** — podaci nikad ne napuštaju sopstvenu infrastrukturu.
- **Potpuna kontrola nad modelom** — izbor verzije/kvantizacije, i mogućnost budućeg fine-tuninga, što managed servisi ne dozvoljavaju.

---

## 5. Plan evaluacije

Zadržava se postojeći RAGAS evaluacioni okvir (faithfulness, answer relevancy, context recall, context precision), primenjen nad novim self-hosted sistemom. Dataset pitanja se proširuje pitanjima čiji je odgovor sadržan isključivo u slici, radi merenja doprinosa captioning koraka. Dodatno se mere latencija po fazi pipeline-a i trošak GPU infrastrukture naspram ranije izmerenih Bedrock troškova.

---

## 6. Pitanja za konsultaciju

- Da li predloženi obim (korpus + arhitektura + self-hosted infrastruktura + evaluacija) odgovara očekivanom nivou za diplomski rad?
- Da li GPU instanca treba da radi kontinuirano tokom razvoja ili se pali/gasi po potrebi?
- Koliki obim teorijskog dela rada posvetiti pregledu vision-language modela i LLM inference serving-a?
