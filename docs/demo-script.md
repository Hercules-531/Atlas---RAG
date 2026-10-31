# Three-minute demo

Use generated fixtures only. Check the current report immediately before presenting; never substitute target numbers for incomplete or failed results.

**0:00–0:25 — Upload.** Open Add documents, load demo data or upload a generated customer CSV, and show local indexing. “EmbeddingGemma 2 and Chroma run on this device.”

**0:25–0:55 — Useful answer.** Select employees.pdf; ask “What is the annual leave entitlement?” Expand the bottom drawer and inspect the cited source. If retrieval fails, show the failure rather than a canned answer.

**0:55–1:30 — Disclosure.** Open Privacy. Compare exact Sent JSON with Withheld labels; locally reveal an omitted fake identifier. Explain that Prune sees what was sent and detectors can miss. Show signature status and original Prune metadata, keeping its savings separate from Atlas estimates.

**1:30–2:00 — Evidence and cost.** Display the real evaluation report and its completed-question count. Read the actual pipeline canary count and accuracy denominators. Show provider token usage and list-price equivalents; free-tier billing is not a measured paid bill. If quota blocked the run, say so.

**2:00–2:30 — Consent.** Select customers.csv; ask “What is the salary for CLIENT-1?” Inspect the tokenized preview, then allow. Original salary stays in a local map and is restored only after the answer returns. Alternatively decline and show that no request was dispatched.

**2:30–3:00 — Local mode.** Switch to Local and repeat a scoped question. Show the application-observed external request count. Explicitly disclose the direct local-model exception and lack of Prune signature. End: “Minimum necessary, with proof—honest about what our measurements establish.”
