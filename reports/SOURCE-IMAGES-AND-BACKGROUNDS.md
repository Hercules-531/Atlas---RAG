# Atlas source images and backgrounds

## Implemented

- Display name: **Atlas**, from the existing central app configuration.
- Local previews of embedded PDF, Word and spreadsheet images; vector PDF pages can expose labelled page previews.
- Image gallery below the answer, linked to the local source and its citation. Images are associated by page/paragraph/anchor, not interpreted by the text-only model.
- Bounded previews and atomic manifests under ignored local uploads/media; source deletion removes these assets.
- Side panels enter and exit using opacity/translation; outgoing content is retained and inert while exiting.
- Warmer brown/mustard paper.
- Privacy mode uses the supplied Orbit GIF, converted locally to a pausable looped MP4 with a static first-frame poster. The original GIF is retained as an asset.
- Local mode rotates locally stored public-domain Starry Night, Wanderer above the Sea of Fog and Water Lilies. Their original reproduced paint texture is retained. Credits follow the active artwork.

## Measured validation

- **70 tests passed**, including PDF embedded images, vector-page preview, Word paragraph association, spreadsheet image anchors, source image serving, safe path checks, deletion, image-only sources, cache-limit invalidation and an extraction check with Python network connections blocked.
- TypeScript and Vite production build passed.
- Real local answer: “There were 18 telescope sessions recorded in June [S1].” It included **1 source-image preview**, whose endpoint returned HTTP 200.
- That answer's generation audit showed **0 external requests**, no source-image URL in the exact model payload and no image data URI. Source image metadata is attached after text generation; it is not sent to either model mode.
- Browser title and heading: **Atlas**.
- Side panel entry: active opacity and transform transitions measured at **240 ms**. Exit DOM retention, inert state, and removal after exit were verified.
- Privacy background: Orbit video readyState **4**, playback active; mode-switch opacity transition measured at **1800 ms**.
- Reduced motion: video paused and hidden behind its static poster; background transition duration **0 s**. Restoring motion resumed playback.
- Actual local gallery transition observed from **Wanderer to Water Lilies**, after the earlier Starry Night scene. Configured interval is **36 seconds**.
- Paper CSS color: **RGB(221, 197, 142)**, combined with the retained fine paper texture.
- Desktop and mobile source-image views were visually inspected. No new frame-rate claim is made.

## Limits

These are local previews, not vision-language analysis, OCR, or semantic image retrieval. Office vector shapes/native spreadsheet charts are not rendered. Previews are matched by source location and may include an unrelated figure on the same cited page. Large/unsupported images can be omitted with manifest warnings. An image-only source can expose a preview while its pixel content remains uninterpreted. Provider usage and the earlier cloud evaluation were not rerun or recharacterized for this feature.

Visibility-change pause handlers are implemented, but actual hidden-tab behavior could not be independently verified with this headless browser because it reported document.hidden=false in both tabs. Reduced-motion pause/resume was verified.
