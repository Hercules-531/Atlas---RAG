# Atlas-RAG

**Minimum necessary, with proof.** Ask questions across local PDF, DOCX, TXT, MD, CSV, XLSX and JSON documents. EmbeddingGemma 2 generates embeddings locally; embedded persistent Chroma stores and searches them locally. Inspect exactly what the application sends through Prune, and what it withholds.

## Run on this machine

```powershell
uv sync --python 3.12
uv run atlas setup-models
cd frontend
npm ci
cd ..
uv run atlas dev
```

Open **http://127.0.0.1:8765**. Port 8000 was already occupied by Unsloth; Atlas uses 8765. The single `atlas dev` command builds the UI, starts available local model servers, and starts FastAPI. `atlas serve` skips the frontend build.

The supplied Prune credential is in this checkout's **ignored `.env`**, not source control. For another checkout, copy `.env.example` to `.env` and set `PRUNE_API_KEY`. Gemini provider credentials stay in Prune's vault. No provider key belongs in this repository or browser bundle.

Use **Load demo data** in Add documents. Wait for files to become ready. Select a document to scope a question, or search all ready documents by leaving the selection empty.

## Local models: reuse Unsloth

The launcher detects the existing Unsloth llama.cpp runtime under `~/.unsloth/llama.cpp/build/bin/Release/` and cached `gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` weights. It never downloads an LLM automatically.

- Generation: existing Gemma 4 E4B, loopback port **8766**.
- Embeddings: existing EmbeddingGemma 2 GGUF converted locally to **F32**, CPU inference with F32 KV types, loopback port **8767**. This text-only model has 768-dimensional outputs; vectors are validated and normalized.
- Conversion from cached F16 weights to F32 avoids FP16 runtime arithmetic but **does not recover any precision already lost in the source weights**. Retrieval quality must be measured. Source weights are left untouched.
- Without compatible cached GGUF/runtime assets, `setup-models` downloads the official SentenceTransformers model; unused vision/audio encoders are disabled during load. Inference uses BF16 where supported or FP32. No FP16 or remote embedding fallback.
- `ATLAS_LLAMA_SERVER` and `ATLAS_LOCAL_GGUF` override local binary/model paths. `ATLAS_LOCAL_BASE_URL` can point to another OpenAI-compatible **HTTP loopback** generation server. External destinations are rejected.
- Local NER uses spaCy `en_core_web_sm`. This environment obtained 3.7.1 from the official spaCy Hugging Face repository after the 3.8.0 release download failed. It loads under spaCy 3.8.18 with a compatibility warning; detector quality is not guaranteed. Standard setup attempts the compatible 3.8.0 model.

Model downloads and conversion are setup actions, outside the local-mode request audit. Both locally spawned servers are terminated when the app exits; existing servers are reused.

## Modes and disclosure

**Local** uses a local LLM directly. A deployable local Prune gateway was not established, so this is the explicitly documented exception to the hackathon's every-LLM-call-through-Prune rule. Local answers have no Prune signed receipt. The external request counter covers Atlas-owned generation requests for that answer's session; it is not machine-wide traffic monitoring or a privacy guarantee.

**Privacy** retrieves locally, removes unrelated sensitive fields/sentences, tokenizes needed values, asks consent, and calls Gemini through `https://api.withprune.com/v1/proxy/gemini/generateContent`. Prune sees the minimized request; Gemini free-tier data-use terms apply. Necessary values are restored locally in the answer. Identifying values can require consent even for a nonsensitive requested field, because the record relationship must remain consistent.

Consent expires after ten minutes or document/policy changes. Declining sends no generation request. The current UI permits tokenized use only; it does not offer raw sensitive-value overrides or real-document full-context overrides. Synthetic baseline evaluation is separately authorized by its explicit CLI flag.

Receipts show exact request bodies, withheld labels, local reveal, estimates, observed provider usage, original `prune_metadata`, and Ed25519 verification status. App minimization savings and Prune savings are separate. Prune's signature authenticates its metadata, not all application behavior. Provider billing is unverified; list-price equivalents are not bills or actual free-tier cash savings.

## Storage and limits

Everything persistent is under ignored `data/`: original uploads, SQLite text/provenance/history/budgets, Chroma vectors, payload audit, and model setup assets. `reports/` contains synthetic evaluation artifacts only; do not commit reports containing real user data.

Defaults: **100 MiB/file**, **1,000 PDF pages**, **250,000 table rows**, **50 MiB extracted UTF-8 text**, **512 MiB uncompressed DOCX/XLSX archives**, and a **15-minute parsing deadline**. MiB means 1,048,576 bytes. Limits are independent. Uploads are bounded while receiving and while copying file bytes. Parsing is cancellable and indexing batches eight chunks. Scanned PDFs need OCR, which is not implemented.

Defaults are in `config/app.toml`; override numeric settings through `ATLAS_` plus uppercase key (examples in `.env.example`). Larger uploads do not increase cloud prompt budgets: approximately 2,048 context tokens, 512 output tokens and 50,000 reserved session tokens. The local UTF-8-byte token estimator is not a Gemini tokenizer or a formal upper bound.

Generic table sums, averages, minima, maxima and counts run locally. Select explicit documents to avoid counting CSV/XLSX duplicates twice. Calculations require plain numeric values and at most 10,000 chunks. General date arithmetic, joins and arbitrary analysis are not implemented.

Delete this file removes its vectors and original/text content, and clears history/audits that could contain derived information. Delete-all also clears reports and remaining application records. Downloaded models remain installed. Deletion is not a forensic secure-erase guarantee. Backups and SSD behavior are outside the app's control.

## Test and evaluate

```powershell
uv run pytest -q
uv run atlas eval
uv run atlas eval --live --synthetic-full-context --resume
```

Offline evaluation exercises minimization over 36 generated gold cases. It is **not** measured LLM accuracy, a real outbound canary test, or paid savings. Live evaluation requires indexed demo documents and uses actual local Chroma retrieval for the pipeline arm. It inspects audited serialized requests, compares against the full synthetic source baseline, scores deterministic expected answers, preserves receipts, and saves `reports/evaluation.json` and `reports/evaluation.md` after each request.

Live evaluation runs serially with bounded requests/tokens and pauses on quota exhaustion. Rerun with `--resume` to keep completed results. No paid fallback or LLM judge. Gold-manifest sensitive cases authorize tokenized use on generated fixtures. Actual free-tier availability is controlled by the user's provider account, not by the app.

Accuracy uses expected fact substrings; citation validity is checked on interactive answers but is not yet part of the gold correctness score. The harness reports incomplete runs honestly. Cache is off by default; the adapter supports `cache='exact'` for a separate synthetic repeat experiment. No separate cache benchmark has been completed unless explicitly present in reports.

## Reliability and limitations

Requests reserve session budgets atomically. The exact body is persisted before dispatch; audit-write failure blocks dispatch. Shield rejection is terminal. Only connection failures have bounded retries; read timeouts do not retry an ambiguously dispatched request. Cloud generation never bypasses Prune. The backend binds to loopback and rejects unexpected browser origins.

Retrieval and sensitivity detectors can miss information. Regex/NER/field heuristics are not comprehensive classification or legal compliance. Semantic selection is heuristic, and the app can abstain or answer incorrectly. Prompt injection defenses are instruction separation and constrained evidence, not a guarantee. There is no OS-level sandbox for model servers or parsers. Gemini free quota and Prune availability can prevent evaluation completion. The painting uses slow CSS transforms rather than a WebGL swirling shader; reduced motion and hidden-tab pause are supported. Performance must be measured on the target machine.

See [PLAN.md](PLAN.md), [demo script](docs/demo-script.md), [pitch](docs/pitch.md), and the [artwork attribution](frontend/public/ATTRIBUTION.txt).
