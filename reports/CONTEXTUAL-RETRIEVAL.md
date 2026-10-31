# Contextual retrieval: decision and measured checks

Previously, Atlas had hybrid dense/BM25 retrieval, bounded parent expansion and local extractive contextual compression. It did not contextualize chunks before indexing.

The new implementation adds a bounded local prefix derived from existing document names, locations, section openings or record field names. Both dense embeddings and BM25 index that context with the child. Reranking also uses local context, and explicit multiword source-name matches can focus ambiguous documents. The prefix is extractive, capped at 80 words, and does not require an LLM-generated summary. Original source text/citation IDs stay intact; prefixes are not automatically exposed to answer generation.

## Measurements

- Eight **manufactured ambiguous agreement fixtures**: hybrid top-1 retrieval improved from **2/8 to 8/8**; dense top-1 improved from **1/8 to 8/8**. These cases isolate missing source context and are not a representative answer-quality benchmark.
- Existing 36 gold retrieval cases: **36/36** first-parent fact retention before and after; **36/36** facts survived compression before and after; **0 raw canary strings** in minimized contexts in both runs.
- Existing index: **66 chunks updated**, preserving text, IDs, citations and history, with **0 extra LLM calls**. No raw documents were reparsed and no media descriptions/transcripts regenerated.
- Unit/integration suite: **86 passed**. Context tests cover bounds, field-name/value separation, contextual BM25 insertion/deletion and index-only context exclusion from generated evidence.
- Frontend production build passed. Browser check: Privacy active scene was `privacy-video`, video playback was active, and **0 flower nodes** were present.

No new cloud answer-accuracy or cost evaluation was performed. Better retrieval can improve answers when evidence was previously missed, but it does not guarantee answer correctness. The method follows the contextual-indexing principle using a lightweight extractive implementation rather than copying a benchmark's LLM-generated-context workflow.

Reference: https://www.anthropic.com/research/contextual-retrieval

A final local answer smoke check returned “The governing law is Fictionland [S1].” Its audited answer payload contained neither the index-context prefix nor the source filename, and observed external requests were 0. The removed flower asset endpoint returned HTTP 404.
