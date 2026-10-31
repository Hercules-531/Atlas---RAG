# Answer explanation and evidence quality fix

## Reproduced cause

The user's DreamDiffusion definition question had been sent to the local model with only `[S1] Dream; Diffusion` as evidence. The refusal was consistent with the grounding policy. PDF line breaks had split substantive passages into fragments, while index-context relevance let short title fragments dominate compression. A SAMGA explanation similarly received incomplete clauses.

## Changes

- Preserve complete soft-wrapped PDF sentences; keep blank-line paragraph boundaries and raw source offsets.
- Normalize Unicode ligatures and CamelCase for lexical matching.
- Prefer substantive candidate passages, add a modest definition/mechanism preference for overview questions, and penalize dense numeric tables for these questions. Supporting/antecedent sentences remain bounded; privacy detection and the 2048 estimated-context-token cap still apply.
- Ask for a direct answer plus moderately detailed explanation (soft target 80–140 words), keeping simple lookups brief, benchmark numbers selective and abstention for genuinely unsupported questions. Output cap stays 512 tokens.
- Validate and display grouped source citations without treating numerical arrays as citation groups.

## Measured checks

- Real local DreamDiffusion response: **132 words**, explaining EEG-to-image generation, temporal masked signal modeling, and CLIP alignment rather than refusing.
- Real local SAMGA response: **161 words**, explaining subject-aware multi-granularity alignment and its mechanism rather than disconnected clauses. The style target is deliberately soft and does not guarantee an exact paragraph/word count.
- A simple leave-entitlement lookup remained **8 words** with the correct 24-day fact and citation.
- An unsupported private bank-account question identified that the supplied evidence lacked that information (**38 words**), without inventing an account number.
- All four request sessions reported **0 external requests**. Full paper passages and generated explanations remain in ignored local data; this report commits only aggregate checks.
- Existing 36 gold retrieval cases: **36/36** first-parent facts retained, **36/36** facts survived compression, **0 raw canary strings** in minimized contexts. This is not a new cloud answer-accuracy evaluation.
- **91 unit/integration tests passed** and TypeScript/Vite production build passed. New regressions cover wrapped definitions, paragraph boundaries, ligature/CamelCase matching and title-fragment suppression.

Limitations: retrieval and extraction can still miss content, and some source PDFs have broken private-use font mappings. The fix does not invent replacements for unknown glyphs or guarantee that every response is complete/correct. More explanatory wording is still constrained to evidence.
