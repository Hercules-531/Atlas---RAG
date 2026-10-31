# Retrieval and UI upgrade: measured findings

## Decisions

- Previous: 300-word windows, 40-word overlap, whole table rows, dense-only top-8 search, and lexical field/sentence extraction.
- Default now: sentence-preserving children (maximum target 240 words, short intact-sentence overlap); bounded local prose parents; whole isolated table rows; Chroma dense + SQLite FTS5 BM25 reciprocal rank fusion; local embedding/lexical extractive contextual compression.
- Semantic topic breakpoints are implemented as an **optional indexing flag**, disabled by default. The boundary stress test showed no added coverage above sentence-aware splitting.
- Late chunking is not implemented: the running GGUF endpoint returns pooled vectors, while late chunking requires token-level contextual representations before span pooling. No measured gain justified changing the runtime.
- Parent expansion stays local. Privacy detection, reversible tokens, consent and prompt budgets still run before Prune.
- Hybrid search adds an exact-term retrieval path. A broad accuracy increase from hybrid search alone was **not** established on the current demo set.

## Measurements

- Original 36 gold retrieval cases: **36/36** expected facts in the first dense result and in top 8.
- Updated 36 cases: **36/36** expected facts retained by retrieval and the extractive compressor, **0 raw canary strings** in minimized contexts. This is a local context-retention check, not a fresh 36-answer cloud evaluation.
- Eight **manufactured boundary/rare-ID stress cases**: complete identifier-and-fact coverage in the top child was **0/8** with the original word windows, **8/8** with sentence-aware children, and **8/8** with semantic breakpoints. Local parent expansion recovered complete paired evidence for **8/8**, including the fixed-window variant. These deliberately manufactured cases are not representative broad-domain accuracy.
- Unit/integration tests: **56 passed** (retrieval-ui-tests.xml).
- Dedicated generation GPU: **CUDA0**, existing RTX 5070 Ti and existing Unsloth weights. DLL discovery was fixed by adding existing CUDA dependencies only to the child-process environment. The runtime check observed **2968 MiB / 12227 MiB** GPU memory in use and a correct cited local answer in **2.094 s** with **0 external requests**. The prompt cache was warm (105 cached prompt tokens), so this is a smoke check, not a cold benchmark.
- Embeddings remain local FP32 CPU inference. No embedding or LLM model-weight download was needed for this upgrade.
- Desktop search measured **483.8 px compact / 590 px focused**.
- Source-number click was verified to open/focus local evidence and set the source fragment. Original PDFs are served locally with page anchors; path escapes and missing sources are tested.

## UI

OLED-black shell and side panels, dark liquid-glass controls, thinner focus-expanding ask bar, smooth bounded background zoom, wheel/touch/drag answer opening and dismissal, textured paper answer surface, larger serif answer text and a divided source column. Narrow screens place sources below a horizontal divider. Only citations actually used in an answer appear in its source column. Reduced motion and hidden-tab pause are retained.

The earlier 72-call report in MEASURED.md remains historical for the preceding implementation; its paid-price equivalents and generated-answer accuracy were not rerun for this retrieval upgrade. No fresh cash-savings or compositor-FPS claim is made.
