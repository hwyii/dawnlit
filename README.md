# Dawnlit

Your morning research signal: an explainable, editable daily feed for trustworthy
large language models. Dawnlit is intentionally local-first: it runs without
paid APIs, stores browser feedback locally, and adds cloud sync only when
configured.

## What works

- Fetches recent papers from `cs.LG`, `cs.AI`, `cs.CL`, `cs.CR`, and `stat.ML`.
- Applies an LLM scope gate, with a small separate lane for transferable methods.
- Scores each topic independently instead of using one seed-paper centroid.
- Separates relevance, evidence-quality, novelty, and freshness scores.
- Diversifies the final feed and limits non-LLM transfer papers.
- Produces structured abstract-grounded notes with an optional Workers AI upgrade.
- Supports Today, Weekly, Saved, detailed feedback, topic editing, import/export,
  and adding new research directions.
- Ships a dependency-free Web Component for embedding a compact feed in Jekyll,
  Hugo, WordPress, React, or plain HTML sites.
- Includes an optional Cloudflare Worker + D1 API so browser changes affect the
  next scheduled build.

The checked-in feed contains the latest successful live build. A deterministic
fixture remains available for tests and offline UI development.

## Why Dawnlit is different

Most paper products optimize one of three things: a large searchable corpus,
community popularity, or opaque similarity to saved papers. Dawnlit starts from
a different premise: a researcher should own and understand the filter.

- **Portable by design.** The full app, generated JSON, and embeddable widget
  can live on a personal website instead of behind a product account.
- **An explicit research profile.** Topics, weights, hard scope rules, and
  transferable-method exceptions are readable and version-controlled.
- **Typed feedback.** “Wrong topic,” “weak evidence,” “not now,” and
  “transferable method” do not collapse into one thumbs-down signal.
- **Explainable selection.** Relevance, evidence quality, novelty, and freshness
  remain separate, and every card shows why it matched.
- **A willingness to return nothing.** A paper must clear the relevance
  threshold; the feed does not fill a quota with weak matches.
- **Local-first and open.** The baseline needs no paid AI API, and optional cloud
  services can be replaced without changing the feed format.

The current version is intentionally not a claim to beat mature products
everywhere. It is arXiv-only, uses transparent lexical/topic matching rather
than a production semantic index, and has not yet been evaluated on long-term
user feedback. Semantic retrieval, broader sources, and ranking evaluation are
the next technical milestones.

## Run locally

No Python packages are required.

```bash
python3 scripts/build_radar.py --no-ai
python3 -m http.server 8000 --directory public
```

Then open `http://localhost:8000`.

The full application is at:

```text
http://localhost:8000/
```

The standalone widget demo is at:

```text
http://localhost:8000/widget-demo.html
```

To exercise the UI without calling arXiv:

```bash
python3 scripts/build_radar.py \
  --fixture tests/fixtures/arxiv_feed.xml \
  --now 2026-06-27T12:00:00+00:00 \
  --no-ai
```

Run the tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Edit the research profile

The canonical local profile is [`config/profile.json`](config/profile.json).
The web UI keeps edits in browser storage by default. Use **Export profile** and
replace the canonical file when you want scheduled builds to use those edits.

The initial lanes are:

1. Efficient adversarial training for LLMs
2. LLM loss landscape
3. Data selection for LLMs
4. On-policy distillation
5. Trustworthy LLM
6. Statistical theory for LLMs

`phrases` are strong matches, `terms` are weaker matches, and `exclude` applies
inside a topic. Global LLM and transfer gating lives under `scope`.

## Embed it in any personal site

The compact feed is a native Web Component with isolated styles and no runtime
dependencies:

```html
<script
  type="module"
  src="https://hwyii.github.io/dawnlit/widget/paper-radar-widget.js?v=1"
></script>

<paper-radar-widget
  feed="https://hwyii.github.io/dawnlit/data/papers.json"
  limit="3"
  theme="auto"
  heading="Recent papers"
  description="Selected around my current research interests."
  more-url="https://hwyii.github.io/dawnlit/"
></paper-radar-widget>
```

Supported attributes:

| Attribute | Default | Purpose |
| --- | --- | --- |
| `feed` | required | URL of a Dawnlit-compatible `papers.json` feed |
| `limit` | `3` | Maximum number of cards |
| `theme` | `auto` | `auto`, `light`, or `dark` |
| `density` | `comfortable` | Set `compact` to hide takeaways |
| `heading` | `Today’s research radar` | Widget title |
| `description` | built-in text | Short introduction |
| `show-header` | `true` | Set `false` for cards only |
| `show-summary` | `true` | Set `false` to hide takeaways |
| `show-score` | `true` | Set `false` to hide score rings |
| `more-url` | unset | Link to the full standalone app |
| `more-label` | `Open full radar →` | Footer link text |

The component emits `paper-radar-loaded`, `paper-radar-error`, and
`paper-radar-select` DOM events. JavaScript applications can also assign a feed
object directly through the element's `data` property.

Ready-to-copy integrations live in:

- [`integrations/html/embed.html`](integrations/html/embed.html)
- [`integrations/jekyll/_includes/paper-radar.liquid`](integrations/jekyll/_includes/paper-radar.liquid)

An iframe remains the broadest fallback for platforms that block custom
JavaScript:

```html
<iframe
  src="https://hwyii.github.io/dawnlit/"
  title="Dawnlit"
  loading="lazy"
  style="width:100%;min-height:720px;border:0"
></iframe>
```

## Optional AI summaries

Without credentials, summaries are extractive and explicitly labeled
`abstract · extractive`. To enable an open-model API through Workers AI, add
these GitHub repository secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Optionally set the repository variable `CLOUDFLARE_MODEL`. The default is:

```text
@cf/meta/llama-3.2-3b-instruct
```

Only the selected papers are sent for summarization. The prompt requires the
model to stay within the supplied title and abstract.

## GitHub Pages deployment

1. Create a public repository named `dawnlit`.
2. Push this directory to its `main` branch.
3. In **Settings → Pages**, select **GitHub Actions** as the source.
4. Run **Deploy Dawnlit** once.
5. Run **Update Dawnlit** once to replace demo data.

The resulting URL is:

```text
https://hwyii.github.io/dawnlit/
```

The update workflow runs at 06:17 in `America/Detroit` on weekdays. It avoids
the start of the hour because scheduled GitHub workflows can be delayed under
heavy load.

## Optional preference and feedback sync

Static mode is enough to evaluate the ranking. For interactive sync:

```bash
cd worker
npm install
npx wrangler d1 create dawnlit
```

Put the returned database ID in `worker/wrangler.jsonc`, then:

```bash
npm run db:init:remote
npx wrangler secret put ADMIN_TOKEN
npm run deploy
```

Set the deployed Worker URL in:

1. `public/runtime-config.js` as `apiUrl`
2. GitHub repository variable `RADAR_API_URL`

Add the same admin token as the GitHub secret `RADAR_ADMIN_TOKEN`. In the web
Preferences page, enter it once per browser tab to connect.

Initialize the remote profile:

```bash
curl -X PUT "$RADAR_API_URL/api/profile" \
  -H "Authorization: Bearer $RADAR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @config/profile.json
```

D1 retains profile versions, while feedback types remain distinct:

- `more_method` and `more_topic` are positive preference signals.
- `not_llm` is a scope negative.
- `low_quality` does not lower topic relevance.
- `not_now` intentionally does not change the long-term profile.
- `transferable` marks a useful cross-modality method.

## Data and arXiv use

The project stores descriptive metadata and generated notes, and links users to
the arXiv abstract/PDF pages. It does not redistribute PDFs. Requests use one
connection and one batched API query per build.

Thank you to arXiv for use of its open access interoperability.

## License

MIT
