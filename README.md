# Dawnlit

Your morning research signal: an explainable, editable daily feed for trustworthy
large language models. Dawnlit is intentionally local-first: it runs without
paid APIs, stores browser feedback locally, and adds cloud sync only when
configured.

## What works

- Fetches recent papers from `cs.LG`, `cs.AI`, `cs.CL`, `cs.CR`, and `stat.ML`.
- Paginates the configured arXiv query and reports if its safety limit truncates results.
- Keeps a durable index of recommended arXiv IDs, so Today never repeats a
  paper and may contain fewer than the configured feed size.
- Applies an LLM scope gate, with a small separate lane for transferable methods.
- Scores each topic independently instead of using one seed-paper centroid.
- Separates relevance, evidence-quality, novelty, and freshness scores.
- Diversifies the final feed and limits non-LLM transfer papers.
- Produces structured abstract-grounded notes with an optional Workers AI upgrade.
- Supports Today, Weekly, Useful, simple feedback, topic editing, import/export,
  and adding new research directions.
- Archives papers marked “Not useful” or “Irrelevant” in the browser for seven
  days, then clears them automatically. Generated analyses remain cached.
- Ships a dependency-free Web Component for embedding a compact feed in Jekyll,
  Hugo, WordPress, React, or plain HTML sites.
- Includes an optional Cloudflare Worker + D1 API so browser changes affect the
  next scheduled build.
- Installs as a standalone iPhone app from Safari, with an offline app shell and
  cached access to the latest successfully loaded feed.
- Uses explicit Useful/Irrelevant feedback as positive and negative examples
  for an optional Semantic Scholar recommendation signal.

The checked-in feed contains the latest successful live build. A deterministic
fixture remains available for tests and offline UI development.

## Install on your iPhone

No App Store account or native build is required. After GitHub Pages deploys:

1. Open the deployed Dawnlit URL in Safari on your iPhone.
2. Tap **Install on iPhone** for the in-app instructions.
3. Tap Safari's **Share** button, choose **Add to Home Screen**, then tap **Add**.
4. Launch Dawnlit from its Home Screen icon.

The installed app opens without Safari chrome. Its Service Worker keeps the app
shell and the most recently loaded paper data available when the network is
temporarily unavailable. While online, it checks GitHub Pages first for the
latest app files and paper data. Reopening the app, returning to it after five
minutes, or refreshing it picks up a completed Pages deployment automatically.

## Install your own Dawnlit

The fastest path does not require a local development environment:

1. [Create a repository from the Dawnlit template](https://github.com/new?template_name=dawnlit&template_owner=hwyii).
2. Edit [`config/interests.txt`](config/interests.txt) in GitHub's web editor.
3. In **Settings → Pages**, choose **GitHub Actions** as the source.
4. Open your deployed `/install.html` page to generate the embed code.

The hosted installer is also available at
[`https://hwyii.github.io/dawnlit/install.html`](https://hwyii.github.io/dawnlit/install.html).
Enter your GitHub username and repository name; it generates the correct
Web Component snippet and direct configuration links.

Saving `config/interests.txt` triggers an immediate feed rebuild. The scheduled
workflow also refreshes every day at 06:17 in `America/Detroit`.

## Why Dawnlit is different

Most paper products optimize one of three things: a large searchable corpus,
community popularity, or opaque similarity to saved papers. Dawnlit starts from
a different premise: a researcher should own and understand the filter.

- **Portable by design.** The full app, generated JSON, and embeddable widget
  can live on a personal website instead of behind a product account.
- **An explicit research profile.** Topics, weights, hard scope rules, and
  transferable-method exceptions are readable and version-controlled.
- **Simple feedback.** Each card has three research triage choices: useful, not
  useful, or irrelevant. On phones, papers form a swipeable previous/next deck;
  desktop keeps the full vertical list.
- **Explainable selection.** Relevance, evidence quality, novelty, and freshness
  remain separate, and every card shows why it matched.
- **A willingness to return nothing.** A paper must clear the relevance
  threshold; the feed does not fill a quota with weak matches.
- **Local-first and open.** The baseline needs no paid AI API, and optional cloud
  services can be replaced without changing the feed format.

The current version is intentionally not a claim to beat mature products
everywhere. It is arXiv-only and uses transparent lexical/topic gates augmented
by optional Semantic Scholar feedback recommendations, rather than its own
production semantic index. Long-term ranking evaluation and a local scientific
embedding index remain the next technical milestones.

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

For most users, the canonical interest list is
[`config/interests.txt`](config/interests.txt). It uses one line per direction:

```text
Mechanistic interpretability @ 0.8 :: sparse autoencoders, circuits, activation probing
```

The weight and comma-separated keywords are optional. Saving the file in
GitHub immediately rebuilds and deploys the feed.

[`config/profile.json`](config/profile.json) remains the advanced configuration
for retrieval scope, ranking weights, exclusions, and detailed topic rules.
When a name in `interests.txt` matches an advanced topic, Dawnlit retains those
rules and applies the simple weight and extra keywords on top.

The web Preferences page keeps interactive edits in browser storage by default.
Its **Edit interests on GitHub** button opens the durable simple configuration;
**Export profile** remains available for advanced edits.

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

| Attribute      | Default                  | Purpose                                        |
| -------------- | ------------------------ | ---------------------------------------------- |
| `feed`         | required                 | URL of a Dawnlit-compatible `papers.json` feed |
| `limit`        | `3`                      | Maximum number of cards                        |
| `theme`        | `auto`                   | `auto`, `light`, or `dark`                     |
| `density`      | `comfortable`            | Set `compact` to hide takeaways                |
| `heading`      | `Today’s research radar` | Widget title                                   |
| `description`  | built-in text            | Short introduction                             |
| `show-header`  | `true`                   | Set `false` for cards only                     |
| `show-summary` | `true`                   | Set `false` to hide takeaways                  |
| `show-score`   | `true`                   | Set `false` to hide score rings                |
| `more-url`     | unset                    | Link to the full standalone app                |
| `more-label`   | `Open full radar →`      | Footer link text                               |

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

## AI morning briefs

The scheduled workflow sends only the final selected papers to Cloudflare
Workers AI. The default full-text model is `@cf/openai/gpt-oss-120b`; if it is
unavailable or returns an invalid schema, Dawnlit retries with
`@cf/qwen/qwen3-30b-a3b-fp8`. Override these with the repository variables
`CLOUDFLARE_MODEL` and `CLOUDFLARE_FALLBACK_MODEL` when using direct
Cloudflare credentials. The bundled Worker proxy intentionally allows only the
two documented models.

The deployed personal Worker exposes an admin-token-protected AI proxy backed
by its native Workers AI binding. Therefore the scheduled build can reuse the
existing `RADAR_API_URL` and `RADAR_ADMIN_TOKEN`; separate Cloudflare AI secrets
in GitHub are optional direct-call fallbacks.

Each brief is grounded in the extracted paper text when available, or the title
and abstract as a fallback. The card turns the analysis into a dense three-line
scan covering the central finding, method, and strongest available evidence.

For each selected paper, the workflow also downloads up to the first 30 PDF
pages, extracts high-signal regions from the introduction, method, experiments,
results, limitations, and conclusion within an 18,000-character request budget,
and asks the model for a grounded deep dive. The **Deep dive** dialog includes:

- three complementary research signals;
- a detailed research question and thesis;
- the method pipeline and mechanism or theory;
- experimental design with named models, datasets, baselines, and metrics;
- results tied to concrete evidence;
- contributions, limitations, and open questions.

Successful analyses are cached by arXiv ID and prompt/schema version. An
unchanged paper reuses its validated deep dive, while stale weekly analyses are
refreshed gradually (three per build by default) so a prompt upgrade does not
create a cost spike. Set `AI_CACHE_REFRESH_LIMIT` to change that limit.

PDFs are capped at 25 MB. If full-text extraction fails, the analysis is
explicitly marked as abstract-based. Missing evidence must be stated rather
than invented. If model inference is unavailable or invalid, Dawnlit falls back
to an extractive brief and disables the deep-dive button.

Add these repository secrets to use AI analysis:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

The default primary model is:

```text
@cf/openai/gpt-oss-120b
```

## GitHub Pages deployment

1. Create a repository with **Use this template**.
2. In **Settings → Pages**, select **GitHub Actions** as the source.
3. Edit `config/interests.txt`; this triggers the first personalized build.
4. Run **Deploy Dawnlit** manually only if Pages was enabled after the first
   deployment attempt.

The resulting URL is:

```text
https://hwyii.github.io/dawnlit/
```

The update workflow runs every day at 06:17 in `America/Detroit`. It avoids the
start of the hour because scheduled GitHub workflows can be delayed under heavy
load. Changes to `config/**` or `scripts/**` also trigger an immediate update.

The arXiv query covers only the previous 24 hours. IDs already present in
`public/data/seen.json` are excluded before ranking, and Today stays short—even
empty—when fewer than six unseen papers clear the relevance threshold.

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

Add the same admin token as the GitHub secret `RADAR_ADMIN_TOKEN`. In the
installed iPhone app, open **Preferences**, enter the token under **Data
ownership**, and tap **Save & sync**. The token stays on that device until you
tap **Forget token**; it is never committed to the public Pages site.

Initialize the remote profile:

```bash
curl -X PUT "$RADAR_API_URL/api/profile" \
  -H "Authorization: Bearer $RADAR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @config/profile.json
```

D1 retains profile versions, while feedback types remain simple:

- `useful` is a strong positive preference signal.
- `not_useful` is a weak negative signal; `irrelevant` is a strong negative
  signal. Both enter the seven-day browser archive.

The lexical preference model uses the most recent label for each paper and a
120-day half-life, so recent choices matter most without permanently locking
the feed into early feedback. Similar papers are reranked before the daily
relevance threshold and diversity pass.

Feedback is posted to D1 immediately. If the phone is offline or the Worker is
temporarily unavailable, the feedback remains in a local pending queue and is
retried when the app next starts, reconnects, or returns online. The next
scheduled GitHub Action reads that D1 feedback through `RADAR_API_URL`, uses it
in ranking, commits the new feed, and deploys it to Pages. The installed app
then fetches that feed the next time it becomes active.

On startup, each connected browser also reads the latest D1 feedback and
reconstructs Useful and seven-day hidden-paper state. Enter the same personal
API token once on the iPhone and desktop; the `CLOUD ✓` badge confirms that
device state is connected. Feed JSON is always fetched with cache bypass so
both devices see the same deployed recommendation batch.

Once at least one positive paper is synced, the scheduled build asks Semantic
Scholar for papers related to the latest positive and negative examples and
uses matching arXiv IDs as an extra ranking signal. This is enabled by default.
Set `SEMANTIC_SCHOLAR_RECOMMENDATIONS=0` in the workflow environment to disable
it, or add the optional `SEMANTIC_SCHOLAR_API_KEY` repository secret for an
authenticated request. A failed request is non-fatal and falls back to the
local ranking pipeline.

## Data and arXiv use

The project stores descriptive metadata and generated notes, and links users to
the arXiv abstract/PDF pages. It does not redistribute PDFs. Requests use one
paginated query per build, with a three-second pause between pages. The default
scope is `cs.LG`, `cs.AI`, `cs.CL`, `cs.CR`, and `stat.ML` over the previous
24 hours, with a 2,000-result safety limit. Generated feeds expose
`source_total` and `source_truncated`, so incomplete retrieval is visible rather
than silently presented as complete.

Thank you to arXiv for use of its open access interoperability.

## License

MIT
