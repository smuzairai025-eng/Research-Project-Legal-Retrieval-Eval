# Stage 4B · Dense retrieval prototype

## Preflight · 26 November 2026

**Status:** Awaiting spending and collection approval, paid project limits, and live cluster capacity. No model API requests or Qdrant operations were made during preflight.

### Frozen experiment inputs

- The 890-chunk export matches the Stage 4A SHA-256, `e5cbaa3bd1d8db0d38f136c9322e883a5aecd9963f926243daaf6bdff93bdbab`. [Chunk export](../data/processed/prototype-c-v1/chunks.jsonl)
- The existing 20 formulations and their candidate labels are unchanged. The evaluation file SHA-256 is `0f8104358c85003e4c5fb911649408d6b7ba1f602de57880e3bd9786f78b36f6`. All labels are pending human verification. DEV-04 remains a single-chunk coverage failure. [Development pairs](../evaluation/development-pairs-c-v1.json)

### Model and quota checks

Google documents `gemini-embedding-001` as a stable text embedding model with support for 1,536 output dimensions and a 2,048-token input limit. Use `RETRIEVAL_DOCUMENT` for passages and `RETRIEVAL_QUERY` for queries. Validate each vector’s dimension, finiteness and nonzero norm, then L2-normalize it before caching. Google specifies manual normalization for this model at reduced dimensionality and lists a scheduled shutdown date of 14 May 2028. Project-specific availability and paid limits remain unverified. [Embedding guide](https://ai.google.dev/gemini-api/docs/embeddings) · [Task types](https://ai.google.dev/api/embeddings) · [Shutdown schedule](https://ai.google.dev/gemini-api/docs/deprecations)

Obtain the project’s active RPM, TPM, and RPD for this model to configure rate limiting. No Gemini or Qdrant credentials were available in the local environment at preflight. [Google AI Studio rate limits](https://aistudio.google.com/rate-limit)

### Token and cost estimate

The measured character counts exclude request serialization. Estimates use four characters per token. Actual billable tokens may differ.

| Inputs | Count | Characters | Estimated tokens |
|---|---:|---:|---:|
| Documents | 890 | 1,282,543 | 320,636 |
| Queries | 20 | 2,541 | 635 |
| Total | 910 | 1,285,084 | 321,271 |

The published standard paid rate is US$0.15 per million input tokens, for an estimated **US$0.048** before retries. The published batch rate of US$0.075 per million would imply US$0.024 if used for every input. A 3.5–5 characters-per-token scenario gives about 257,000–367,000 tokens and US$0.039–0.055 at the standard rate. **Proposed maximum Gemini spend is US$0.50**, including the pilot and retries. The proposed limit covers this prototype only. [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing/#gemini-embedding)

### Qdrant capacity and proposed collection

Proposed collection **`pklr_dense_c_v1_stage4b`**, with 1,536-dimensional float32 vectors, cosine similarity, exact prototype queries where supported, and source metadata including the original chunk IDs. Use deterministic UUID point IDs derived from chunk IDs. The 890 document vectors require **5.21 MiB** raw per replica. The full local cache including the 20 query vectors requires **5.33 MiB** raw. Collection storage will be higher with point metadata, segments, and write overhead. Verify free disk and available memory against live cluster metrics before creating the collection. Current cluster capacity and collection-name availability are unverified. This proposal assumes an existing cluster. [Qdrant sizing guidance](https://qdrant.tech/documentation/cloud/capacity-sizing/) · [Qdrant Cloud monitoring](https://qdrant.tech/documentation/cloud/cluster-monitoring/)
