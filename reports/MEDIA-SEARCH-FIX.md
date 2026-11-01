# Media search: visual scenes versus spoken words

Verified locally on 1 November 2026. See `media-search-check.json` for individual API results and measured request times.

## Cause

The existing synthetic `observatory-video.mp4` fixture shows a flower and has an audio track saying “The telescope recorded 18 sessions in June.” Its transcript therefore legitimately matches a speech search for telescope. The previous search mixed frame descriptions and speech without identifying the reason for a match. It also returned nearest neighbors without a relevance gate, including unrelated flower descriptions and project-code transcript segments.

## Change

- Default search uses visual descriptions for images/videos, and speech for standalone audio files.
- “Match content” allows visuals only, speech including videos, or all indexed content.
- Results label visual versus spoken-word matches. Video speech results explicitly say they may not match the scene and omit unrelated frame thumbnails; playback seeks to the matching timestamp.
- Rerank actual descriptions/transcripts, excluding contextual filenames and boilerplate. Apply heuristic cosine/lexical relevance gates and retain the strongest timestamp per file and content type. Semantic synonyms can still match without exact words.
- Keep up to 64 retrieval candidates and return up to 12 results. Existing document question answering keeps its original defaults. Search invokes local embeddings, without LLM generation or cloud calls.

## Measured verification

Eleven live API cases on the existing local media fixtures:

| Search | Content | Observed result |
| --- | --- | --- |
| telescope | default, all media | Matching audio file only; no flower video/image |
| telescope | default, video | No matches |
| telescope | visual | No matches |
| telescope | video speech | Matching video transcript at 00:00:03.280 |
| flower | default | Flower image and video |
| blossom | visual | Flower image and video |
| a blue bloom | visual | Flower image and video |
| astronomy | default | Observatory audio |
| submarine | all content | No matches |
| dinosaur | all content | No matches |
| project amber | all content | Relevant audio and video speech segments |

All 98 automated tests passed; TypeScript checking and the Vite production build passed. Browser checks cover the default result, empty video result, and explicit speech mode.

These checks are a regression sample, not a general media accuracy score. Relevance thresholds are heuristics, not calibrated confidence probabilities. They may omit weak paraphrases or admit false matches on other data. Captions/transcripts can be wrong, and sampled video frames can miss objects. No claim of exhaustive visual recognition is made. Original uploads and their existing index remain intact; re-uploading is unnecessary.
