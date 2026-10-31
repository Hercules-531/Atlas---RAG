# Gemma 12B, uploaded media and visual refinement

## What changed

Local generation uses the cached **Gemma 4 12B QAT GGUF** (6,716,356,800 bytes) and cached **mmproj-F16.gguf** (175,115,840 bytes). No replacement LLM weights were downloaded. CUDA0 handles generation, with a 4096-token context/Q8 KV cache; the vision projector stays on CPU. EmbeddingGemma 2 remains text-only and FP32 on CPU.

Image search indexes local Gemma descriptions; video search indexes descriptions of bounded sampled frames plus speech; audio search indexes local Whisper-base transcripts. These descriptions/transcripts are embedded with the same local embedder. Search is caption/transcript-based, not direct pixel/acoustic-vector retrieval. The new Search media panel supports type filters, local previews, timestamped excerpts and playback. Raw media is blocked from cloud dispatch.

A one-time local Whisper-base asset download was needed because no cached ASR model was found. Runtime loads local assets only. PyAV was pinned to tested 16.x after version 19 broke the released faster-whisper decoder's metadata_errors argument. Reindex maintenance now delegates to the running app to prevent stale/cross-process embedded-Chroma state. Search returned HTTP 200 after the delegated rebuild.

## Measured checks

- **81 unit/integration tests passed**, including real WAV decoding, duration limits, bounded timestamps, raw-image cloud rejection, local caption dispatch, media upload acceptance, no-LLM search, media parent boundaries and reindex ownership.
- TypeScript/Vite production build passed.
- Real image upload indexed and returned a description of the supplied glowing blue flower.
- Real synthetic speech upload indexed two timestamped transcript segments, recovering “18 sessions in June” and “the project code is amber.”
- Real synthetic video upload indexed a sampled flower-frame description and three speech segments. Browser search returned four local video results with four previews and four players.
- Local Gemma 12B answered: **“The project code mentioned is amber [S1].”** Its usage reported 127 prompt tokens and 11 completion tokens, with **0 external requests** in that answer session.
- GPU snapshot during that check: **8594 MiB / 12227 MiB** on the RTX 5070 Ti. This is a runtime observation, not a performance benchmark.
- A separate real local ASR check with Python socket connections blocked observed **0 network connection attempts** and returned the transcript. This is not OS-wide traffic certification.
- Search bar measured **483.796875 px compact / 590 px focused**, with **52 px height in both states**.
- First Local background loaded the antique Blaeu map at **3840 px** width. Rotation interval is **18 seconds**, fade duration **900 ms**. Actual flower-to-video transition and video playback were observed in the browser.
- Desktop and mobile views were inspected. Paper uses a more visible neutral fiber tile; Privacy uses the supplied centered flower on black and supplied video. A layout-transition lint warning is intentionally retained for width-only interpolation in the fixed-height isolated search control; no frame-rate claim is made.

## Limits

Captions and speech recognition can miss or invent details. Video uses at most eight sampled frames and does not analyze every frame. GIFs use the first frame. Audio search is speech-based, not general music/sound recognition. Source timestamps are approximate and clamped to duration. Default clip limit is 15 minutes; uploads retain the 100 MiB cap. Browser playback depends on codec support. Local captioning uses the documented direct-local-model Prune exception; cloud answer calls still go through Prune and can receive only selected derived text through the existing minimization/consent pipeline. Uploaded search data and setup model weights remain ignored; explicitly requested background assets are included. Earlier cloud evaluation results remain historical and were not rerun for this upgrade.
