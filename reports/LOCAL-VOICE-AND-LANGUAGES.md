# Local dictation and multilingual search

Verified on 1 November 2026, using the existing local model assets. Machine-readable observations: `local-voice-multilingual.json`. Automated checks: `local-dictation-tests.xml`.

## Shipped behavior

Both search bars have microphone and language controls. Browser MediaRecorder sends audio only to the loopback backend. A supervised worker decodes a bounded number of audio samples, then runs cached multilingual Whisper on CPU/int8. No browser speech-recognition service, translation API or cloud ASR is used. Native-script text is retained rather than translated. A larger, already-downloaded compatible faster-whisper model can be selected using `ATLAS_SPEECH_MODEL_DIR`; incomplete assets fail instead of fetching a tokenizer remotely.

Recordings and temporary transcription results are removed after processing, including worker errors/timeouts. Audio is not ingested into sources/history/audits. Text is editable before asking. Dictation selects Local mode for document questions; UI/API defaults are also Local. Explicit Privacy-mode selection continues to use Prune as documented elsewhere.

Limits: 60 seconds plus one second of decoder tolerance, 8 MiB, one worker, 90-second deadline, 4,000 transcript characters. Browser tracks stop on cancellation/unmount. Browser WebM often lacks duration metadata; decoded sample counting enforces the limit without relying on that metadata. Worker startup/model loading time is included in the observed transcription time.

Language options: automatic detection, English, Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Urdu, Assamese, Nepali, Sanskrit and Sindhi. Options were checked against installed Whisper language codes. Selecting an option is not evidence of reliable recognition for that language.

## Measured checks

- Existing synthetic English audio, 9.087875 decoded seconds: local transcription returned the expected telescope/session/project-code wording in 2.541 seconds. No temporary recording directory remained afterward. This is one observation, not a latency guarantee.
- Actual Chromium MediaRecorder using a synthetic microphone fixture produced a usable WebM/Opus recording. The transcript included the expected telescope wording. Browser checks verified cancellation ended all tracked audio tracks, starting dictation switched Privacy to Local, no question was automatically submitted, and media search waited for explicit review. Zero external browser requests were observed during that bounded test. This is not machine-wide traffic monitoring.
- English, Hindi and Tamil questions about annual leave all returned the expected 24-day fact from the English synthetic PDF, with citations and zero external requests in each local answer session. These three examples are not a generated-answer accuracy benchmark.
- Native-script “blue flower” media queries found intended flower media in Hindi, Bengali, Tamil, Telugu, Marathi, Kannada, Malayalam and Punjabi. Gujarati and Urdu queries returned no match. Marathi found the video but missed the image. English also found both. This narrow sample gives 8/10 Indian-language queries with at least one intended result; it does not establish broad multilingual search accuracy.
- All 115 automated tests passed. TypeScript checking and the Vite production build passed. Desktop and 390px mobile browser checks showed no horizontal page overflow.

No actual user microphone was accessed for verification. Indian-language speech, accents, code-switching/Hinglish and noisy microphone input were not benchmarked. The base speech model can misrecognize these. Larger local speech-model performance/resource use was not measured. No new speech/embedding model was downloaded for this feature.

## Retrieval and privacy limits

EmbeddingGemma 2 already provides multilingual vectors; no index rebuild or cloud translation is required. Term normalization now preserves Indic combining marks. The answer prompt requests the question's language. Cross-language similarity and heuristic relevance gates can still miss results. Table-field selection and English local NER remain language-limited; no sensitivity gate was relaxed to compensate. Romanized languages are best effort. Retrieval, generated answers and transcripts can be wrong.

## Primary references checked

- [Google EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2): multilingual embeddings and query/document prefixes.
- [Whisper language definitions](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py): supported language codes.
- [faster-whisper implementation](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py): local assets, CPU/int8 and transcription language/task options.
