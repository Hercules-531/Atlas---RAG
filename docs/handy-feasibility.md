# Handy feasibility for Atlas

Recommendation: use Handy as an **optional companion dictation application** rather than embedding its full desktop application inside Atlas. Its native hotkey/paste workflow can target an ordinary text field. For a future in-app microphone, reuse Atlas's existing local Whisper code/weights and add recording controls, editable text and an explicit Ask action.

Handy is a native Rust/Tauri application with local ASR, global hotkeys, clipboard/native input integration and microphone permissions. It is not a drop-in React/FastAPI component. Native embedding would add another runtime, packaging/lifecycle work and platform permissions. It improves input convenience/accessibility; it does not itself improve RAG retrieval or answer correctness. Dictation can mishear names/IDs, so editable review is useful.

## Resources

- Extra native/WebView process, model files and a loaded speech model consume disk/RAM. Transcription creates CPU work; GPU acceleration can compete with Gemma. Exact Handy RAM/latency/VRAM were **not measured**, because Handy was not installed.
- Current machine observation while Atlas ran: **8690 MiB / 12227 MiB GPU memory used**, **31.43 GiB system RAM**, **11.5 GiB RAM available**. These are machine-wide snapshots, not Handy benchmarks or per-process attribution. The limited GPU headroom favors CPU dictation.
- Start with push-to-talk, CPU acceleration and idle model unloading. Handy exposes CPU/GPU selection and model unloading. Atlas's CTranslate2 Whisper assets are a different runtime format from Handy's native GGUF/ggml engines; do not assume the two apps share loaded model memory or directly reuse model files.
- Plain local dictation needs no additional LLM. Keep optional text post-processing disabled, local, or explicitly routed through Prune to preserve Atlas's routing/privacy policy. No microphone was accessed and Handy was not installed or integrated during this assessment.

Feasible on this hardware for a CPU-based companion workflow, subject to profiling the chosen model. Reusing Atlas's ASR for an in-app mic would avoid packaging a second dictation desktop application.

Sources (reviewed November 1, 2026):
- https://github.com/cjpais/Handy
- https://handy.computer/
- https://github.com/cjpais/Handy/blob/main/src-tauri/src/settings.rs
- https://github.com/cjpais/Handy/blob/main/src-tauri/Cargo.toml
