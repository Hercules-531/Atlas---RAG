# Dictation quality and microphone selection

Verified on 1 November 2026. The user requested better English / Indian English recognition. Actual user microphone input and Indian-English accent accuracy were not recorded or benchmarked; the checks below use synthetic English speech.

## Changes

- Select and remember an explicit microphone. Show the actual input label. Disconnected saved devices fail clearly instead of silently switching inputs.
- Add a local live meter and a 15-second **Check microphone** action that sends no audio to the backend. Stop and release tracks/audio contexts on completion, cancellation, device loss and component unmount.
- Request mono audio, 48 kHz where supported, browser noise/echo reduction and automatic gain. Record at 128 kbit/s where supported. Expose raw capture when browser processing distorts a particular microphone.
- Default new dictation settings to English. Preserve existing explicit language choices. Show a clear Listening state so users can wait for device startup before speaking.
- Add optional local vocabulary hints for names. Cap hints at 500 characters and 96 speech-model tokens to leave decoding room. Hints can bias recognition and should be short.
- Prefer a complete local **Whisper large-v3-turbo** installation over base. Keep explicit model-directory overrides authoritative. Run CPU/int8, with no GPU contention with Gemma, runtime downloads, cloud ASR or transcript-rewriting LLM.
- Remove DC offset, apply at most 18 dB bounded gain to quiet input, preserve speech padding, and report quiet/clipped audio. Reject near-silence and very low model log-probability transcripts. These thresholds are heuristics, not calibrated correctness guarantees.
- Keep the one-worker/60-second/8 MiB limits and temporary-recording deletion. Raise the processing deadline to 150 seconds for the larger CPU model, with a matching browser timeout.

## Model provenance

Downloaded the CTranslate2 conversion from [dropbox-dash/faster-whisper-large-v3-turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo), revision `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`. Model weights: 1,617,884,929 bytes; verified SHA-256 `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da`. Assets live in ignored local data; only synthetic test audio is committed. Model download requires network access during setup; recordings do not leave the loopback app for transcription.

The [original model card](https://huggingface.co/openai/whisper-large-v3-turbo) and [faster-whisper implementation](https://github.com/SYSTRAN/faster-whisper) were checked for multilingual transcription and CPU/int8 compatibility. Those sources do not establish accuracy on this user's voice.

## Before/after synthetic regression

Run `uv run python -m atlas.voice_benchmark` with both local models installed. This uses committed synthetic speech, deterministic Gaussian noise (seed 531), an attenuated/DC-offset variant and an isolated Dream Diffusion/RAG question. WER uses case-insensitive words and ignores punctuation. Full transcripts, timings and errors are in `dictation-quality.json`.

| Case | Base WER | Turbo + new pipeline WER | Base decode seconds | Upgraded decode seconds |
| --- | ---: | ---: | ---: | ---: |
| Clean | 0% | 0% | 0.613 | 4.477 |
| Quiet with DC offset | 0% | 0% | 0.454 | 4.908 |
| Noise, +5 dB SNR | 0% | 0% | 0.442 | 5.022 |
| Noise, 0 dB SNR | 0% | 0% | 0.431 | 5.082 |
| Noise, −5 dB SNR | 5.56% | 0% | 0.444 | 4.973 |
| Dream Diffusion / retrieval question | 0% | 0% | 0.418 | 5.103 |

The base model replaced “amber” with “Amazon” in the −5 dB case; the upgraded pipeline preserved “amber.” Both models emitted zero words for silence and noise-only input. The upgraded pipeline returned clear retry errors for those inputs. This is one corrected word in a narrow synthetic sample, not a broad accent/noise accuracy improvement percentage. The upgrade combines model and preprocessing changes; this is not an isolated model ablation.

Model loading was measured separately: base 0.319 seconds, turbo 2.662 seconds. A real browser MediaRecorder request with a 9-second synthetic clip took **8.127 seconds** including worker startup/model loading, returning the expected wording. Larger CPU inference is slower; no GPU or persistent warm-worker performance was measured.

## Browser and automated verification

- Actual Chromium MediaRecorder, supplied a synthetic microphone fixture; no user microphone accessed.
- Explicit device constraints honored, raw filters disabled as selected, meter responded, and all tracked microphone tracks ended after checks.
- Microphone-only checks sent zero transcription requests. End-to-end dictation sent one loopback transcription request, zero automatic question requests and zero external browser requests. Optional hints reached the local ASR request.
- An unavailable saved input failed without switching to another microphone or dispatching another recording.
- Desktop/mobile popover checks; microphone meter and selected input remain visible at recording start. Details scroll inside the bounded panel without triggering answer/background scroll controls.
- All **124 automated tests passed**; TypeScript checking and the Vite production build passed. Automated tests cover native-script preservation, local model selection, missing tokenizer failures, decoding limits, vocabulary bounds, quiet gain, clipping warnings, near-silence rejection, weak transcript rejection and worker cleanup. See `dictation-quality-tests.xml` for results.

Real-world performance still depends on microphone placement, gain, background voices, accent and vocabulary. Optional hints can introduce bias. Browser device IDs may change when permissions or hardware change; reselect the microphone when the saved input is unavailable. Review transcripts before submitting them.
