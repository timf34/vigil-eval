# Website handoff — model page UI cleanup

Goal: make the public-facing model page (`/model/<slug>`) clean and easy to read by leading with the one-sentence model characterization. Strip out internal/operational metadata that doesn't help a public reader.

## What's wrong now

On `/model/<slug>` (e.g. Claude Sonnet 4.6) the page leads with a "Run Provenance" card that includes content like:

- "Current single-model run for Claude Sonnet 4.6."
- "Dedicated benchmark run for Claude Sonnet 4.6."
- A "Current" status pill
- Batch / Evaluator / Profile model meta grid

This is operator-facing metadata that means nothing to a public reader. The actual interesting content — the **one-sentence model characterization** and **summary blurb** — is buried below.

Desired hierarchy (top to bottom):

1. **Model name** (already there, in the header)
2. **Signature** — the 2–5 word short label
3. **Model characterization** — the one-sentence clinical summary, displayed prominently and large. This is THE thing.
4. **Summary blurb** — supporting 2–3 sentences
5. **Warning labels** — the 0–4 specific concerns
6. **Behavioral rates / patterns** — quantitative drilldown

Run provenance should either be:
- A small disclosure footer (collapsed by default), OR
- Moved to a separate `/runs/<run-id>` page linked from a small "View run details" link

## Specific cuts

In `src/pages/model/[slug].astro` the entire `<section class="run-provenance-section">` (currently lines ~124–155) needs to be either removed from the main flow or de-prioritized to a footer/disclosure.

Fields to drop or de-emphasize from the public view:
- `recommended_use` — internal note, not for end users
- `notes` — internal note
- `status_label` ("Current", "Rejudge needed", "Reference") — internal
- `run_label` ("Claude Sonnet 4.6", "April 7 Multi-Model Rejudge v4") — internal naming

Fields worth keeping (somewhere quieter):
- Evaluator model name (small footer)
- Profile/synth model name (small footer)
- Link to the underlying run (if useful)

## Data layout (what's already in place)

The build pipeline reads litmus model cards and generates three artifacts in `public/`:

- `public/leaderboard-data.json` — list of all runs/models for the leaderboard
- `public/model-cards.json` — keyed by `<model-slug>--<run-timestamp>`, contains all the synthesized fields
- `public/state-pages/<model-slug>--<run-timestamp>/<state>.json` — per-state pages

To regenerate after any litmus-side change:

```
python scripts/build_site_data.py
```

The canonical source-of-truth for which runs feed the website is `scripts/run_registry.json` (and the human-readable index lives at `../MentalHealthLLMs/litmus/RUNS.md`).

## Source data layout

Litmus writes per-model results to `../MentalHealthLLMs/litmus/vigil-results/<benchmark-timestamp>/<model_dir>/`. The build script reads `model_card.json` from there. Key fields actually used:

| Field | Use |
|---|---|
| `short_label` | "Signature" line (2–5 words) |
| `model_characterization` | One-sentence headline summary — **this is the thing to lead with** |
| `summary_blurb` | 2–3 sentence supporting paragraph |
| `warning_labels` | List of 0–4 specific clinical concerns |
| `behavior_rates` | Quantitative metrics |
| `core_metrics.weighted_mean` | Severity score |
| `recurring_protective_patterns` / `recurring_risky_patterns` | Tag aggregates |

The full per-model run index, including which run is canonical for each model, lives in:
`../MentalHealthLLMs/litmus/RUNS.md`

## Known data gaps

Three models currently have empty `short_label` / `model_characterization` / `summary_blurb` because the synth model returned text without the expected XML tags:

- `openai/gpt-5.1`
- `openai/gpt-5.2`
- `openrouter/openai/gpt-oss-120b`

The full text is preserved in `synth_raw_response` inside their `model_card.json`. Two ways to fix:

1. **Re-run stage 5** for those models from the litmus repo (see RUNS.md). Takes ~30s per model.
2. **Add a fallback parser** in `build_site_data.py` that, when the structured fields are empty but `synth_raw_response` exists, tries to extract them or just falls back to displaying the raw response.

The website should also handle this case gracefully — currently a missing characterization will render a blank space.

## Suggested incremental scope

Smallest meaningful change:

1. Move the Run Provenance section out of the page lead (make it a small footer or disclosure). It'll dramatically improve the at-a-glance read.
2. Promote `model_characterization` to be the visual headline of the page — large type, plenty of breathing room.
3. Add a fallback in the build script so missing characterizations don't render as blanks.

Bigger scope (optional):

4. Add a `/runs/<run-id>` page that contains all the provenance metadata and link to it from the model page.
5. Sort/group leaderboard models by some clinically meaningful axis (severity, archetype) rather than just batch.

## Files most likely to touch

- `src/pages/model/[slug].astro` — the model page itself
- `src/pages/index.astro` — leaderboard
- `scripts/build_site_data.py` — data layer (e.g. for the missing-field fallback)
- `scripts/run_registry.json` — only if adding/removing official runs

## Testing

```
npm run dev   # local preview
npm run build # production build
```
