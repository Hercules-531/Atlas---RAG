# Measured validation

All figures below are observed on this machine, not targets or privacy guarantees.

- Unit/integration tests: **43 passed** (reports/tests.xml).
- Full paired cloud evaluation: **72 completed requests**, no failed requests.
- Baseline correctness: **36/36**; pipeline correctness: **35/36** in the original run.
- The failed governing-law case was fixed and passed a separate real, signed retest; the original failure remains in the report. A complete rerun after that fix was not performed.
- Pipeline unrelated canary occurrences in serialized outbound requests: **0 across 36 pipeline requests**. Synthetic baseline exposure is separately recorded.
- Prune signatures verified offline: **72/72**, public key included.
- Provider input tokens: **28,424 baseline / 6,817 pipeline** (76.02% fewer).
- Provider output tokens: **529 baseline / 993 pipeline**.
- Paid-list-price equivalents across 36 tasks: **$0.00984970 baseline / $0.00452760 pipeline** (54.03% reduction). These are estimates from observed usage at published rates, not actual billed money or free-tier cash savings. Actual provider billing was not independently verified.
- Application context withholding: **89.69% average**, estimated by UTF-8 bytes/3, not a Gemini tokenizer.
- Prune reported savings in the paired run: **$0**; never added to app savings.
- Separate exact-cache experiment: miss then hit, both signatures verified (cache-experiment.json).
- Local check: 768-dimensional embeddings plus Chroma retrieval, **0 external Python connection attempts**, **1.391 seconds**. Scope is Python-owned connections, not OS-wide model-server tracing.
- Two embedding vectors were validated in **0.188 seconds** in an earlier smoke test; this is not a benchmark distribution.
- Foreground browser rAF sample: **119 intervals**, median and p95 **4.2 ms**. This is not a compositor-FPS guarantee.

## Important limitations

The cached EmbeddingGemma 2 F16 weights were converted to F32 for CPU inference. This does not recover precision lost in the source weights. Local generation reuses the user's installed Unsloth Gemma 4 E4B model and bypasses Prune as the documented local-mode exception. The locally available spaCy 3.7.1 NER model emits a compatibility warning under spaCy 3.8.18. Retrieval, entity detection, prompt injection resistance and generic arithmetic are bounded and imperfect; no guaranteed-private claim is made. Gold scoring uses deterministic expected substrings and does not constitute an independent broad-domain accuracy benchmark.
