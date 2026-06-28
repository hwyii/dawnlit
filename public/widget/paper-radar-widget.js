const template = document.createElement("template");

template.innerHTML = `
  <style>
    :host {
      --radar-background: #fffef9;
      --radar-surface: #f4f1e8;
      --radar-ink: #1f2927;
      --radar-muted: #68736e;
      --radar-line: rgba(31, 41, 39, 0.14);
      --radar-accent: #1f6755;
      --radar-accent-soft: #dcebe3;
      --radar-radius: 16px;
      display: block;
      color: var(--radar-ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }

    :host([theme="dark"]) {
      --radar-background: #19201e;
      --radar-surface: #222b28;
      --radar-ink: #edf2ee;
      --radar-muted: #aab6b0;
      --radar-line: rgba(237, 242, 238, 0.13);
      --radar-accent: #78c7a9;
      --radar-accent-soft: rgba(120, 199, 169, 0.14);
    }

    * {
      box-sizing: border-box;
    }

    a {
      color: inherit;
    }

    .shell {
      overflow: hidden;
      background: var(--radar-background);
      border: 1px solid var(--radar-line);
      border-radius: var(--radar-radius);
    }

    .header {
      display: flex;
      gap: 20px;
      align-items: flex-end;
      justify-content: space-between;
      padding: 22px 24px 18px;
      background:
        radial-gradient(circle at 90% 0%, var(--radar-accent-soft), transparent 42%),
        var(--radar-surface);
      border-bottom: 1px solid var(--radar-line);
    }

    .header[hidden] {
      display: none;
    }

    .eyebrow {
      margin: 0 0 4px;
      color: var(--radar-accent);
      font-size: 9px;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }

    h2 {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(24px, 4vw, 34px);
      font-weight: 500;
      line-height: 1.05;
      letter-spacing: -0.025em;
    }

    .description {
      max-width: 520px;
      margin: 7px 0 0;
      color: var(--radar-muted);
      font-size: 12px;
    }

    .count {
      flex: 0 0 auto;
      padding: 5px 8px;
      color: var(--radar-accent);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.08em;
      background: var(--radar-background);
      border: 1px solid var(--radar-line);
      border-radius: 999px;
    }

    .list {
      display: grid;
    }

    article {
      position: relative;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px 18px;
      padding: 19px 24px 18px;
      border-bottom: 1px solid var(--radar-line);
      transition: background 150ms ease;
    }

    article:last-child {
      border-bottom: 0;
    }

    article:hover {
      background: var(--radar-surface);
    }

    .labels {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      align-items: center;
      margin-bottom: 6px;
    }

    .label {
      padding: 3px 7px;
      color: var(--radar-accent);
      font-size: 9px;
      font-weight: 750;
      background: var(--radar-accent-soft);
      border-radius: 999px;
    }

    .label.category {
      color: var(--radar-muted);
      background: var(--radar-surface);
    }

    h3 {
      max-width: 760px;
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(17px, 2.3vw, 21px);
      font-weight: 500;
      line-height: 1.25;
    }

    h3 a {
      text-decoration: none;
    }

    h3 a:hover {
      color: var(--radar-accent);
    }

    .meta {
      margin: 5px 0 0;
      color: var(--radar-muted);
      font-size: 10px;
    }

    .summary {
      grid-column: 1 / -1;
      margin: 5px 0 0;
      color: var(--radar-muted);
      font-size: 12px;
    }

    .score {
      display: grid;
      width: 38px;
      height: 38px;
      color: var(--radar-accent);
      font-size: 10px;
      font-weight: 800;
      place-items: center;
      background:
        radial-gradient(circle, var(--radar-background) 56%, transparent 58%),
        conic-gradient(var(--radar-accent) var(--angle), var(--radar-surface) 0);
      border-radius: 50%;
    }

    .footer {
      display: flex;
      justify-content: flex-end;
      padding: 11px 18px;
      background: var(--radar-surface);
      border-top: 1px solid var(--radar-line);
    }

    .footer[hidden] {
      display: none;
    }

    .more {
      color: var(--radar-accent);
      font-size: 11px;
      font-weight: 700;
      text-decoration: none;
    }

    .status {
      padding: 38px 24px;
      color: var(--radar-muted);
      font-size: 12px;
      text-align: center;
    }

    .status.error {
      color: #a34a3b;
    }

    :host([density="compact"]) article {
      padding-block: 14px;
    }

    :host([density="compact"]) .summary {
      display: none;
    }

    @media (prefers-color-scheme: dark) {
      :host([theme="auto"]) {
        --radar-background: #19201e;
        --radar-surface: #222b28;
        --radar-ink: #edf2ee;
        --radar-muted: #aab6b0;
        --radar-line: rgba(237, 242, 238, 0.13);
        --radar-accent: #78c7a9;
        --radar-accent-soft: rgba(120, 199, 169, 0.14);
      }
    }

    @media (max-width: 560px) {
      .header {
        padding: 18px;
      }

      article {
        padding-inline: 18px;
      }

      .description,
      .summary {
        font-size: 11px;
      }
    }
  </style>
  <section class="shell" aria-live="polite">
    <header class="header">
      <div>
        <p class="eyebrow">Research signal</p>
        <h2></h2>
        <p class="description"></p>
      </div>
      <span class="count"></span>
    </header>
    <div class="list">
      <div class="status">Loading research signals…</div>
    </div>
    <footer class="footer" hidden>
      <a class="more">Open full radar →</a>
    </footer>
  </section>
`;

class PaperRadarWidget extends HTMLElement {
  static observedAttributes = [
    "feed",
    "limit",
    "heading",
    "description",
    "theme",
    "show-header",
    "show-summary",
    "show-score",
    "more-url",
    "more-label",
  ];

  #requestId = 0;
  #data = null;

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.append(template.content.cloneNode(true));
  }

  connectedCallback() {
    if (!this.hasAttribute("theme")) this.setAttribute("theme", "auto");
    this.#load();
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (!this.isConnected || oldValue === newValue) return;
    if (name === "feed") {
      this.#load();
    } else {
      this.#render();
    }
  }

  set data(value) {
    this.#data = value;
    this.#render();
  }

  get data() {
    return this.#data;
  }

  async #load() {
    const feed = this.getAttribute("feed");
    if (!feed) {
      this.#renderStatus("Add a feed URL to display papers.", true);
      return;
    }
    const requestId = ++this.#requestId;
    this.#renderStatus("Loading research signals…");
    try {
      const response = await fetch(feed, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const data = await response.json();
      if (requestId !== this.#requestId) return;
      this.#data = data;
      this.#render();
      this.dispatchEvent(
        new CustomEvent("paper-radar-loaded", {
          detail: { count: data.papers?.length || 0 },
          bubbles: true,
        }),
      );
    } catch (error) {
      if (requestId !== this.#requestId) return;
      this.#renderStatus(`Could not load the paper feed: ${error.message}`, true);
      this.dispatchEvent(
        new CustomEvent("paper-radar-error", {
          detail: { error },
          bubbles: true,
        }),
      );
    }
  }

  #render() {
    if (!this.#data) return;
    const papers = Array.isArray(this.#data.papers) ? this.#data.papers : [];
    const limit = Math.max(1, Number.parseInt(this.getAttribute("limit") || "3", 10));
    const selected = papers.slice(0, limit);
    const heading = this.getAttribute("heading") || "Today’s research radar";
    const description =
      this.getAttribute("description") ||
      "A compact, explainable selection from the latest research.";
    const showHeader = this.getAttribute("show-header") !== "false";
    const moreUrl = this.getAttribute("more-url");

    const header = this.shadowRoot.querySelector(".header");
    header.hidden = !showHeader;
    header.querySelector("h2").textContent = heading;
    header.querySelector(".description").textContent = description;
    header.querySelector(".count").textContent = `${selected.length} selected`;

    const list = this.shadowRoot.querySelector(".list");
    list.innerHTML = selected.length
      ? selected.map((paper) => this.#paperMarkup(paper)).join("")
      : '<div class="status">No paper cleared the current threshold.</div>';

    list.querySelectorAll("[data-paper-id]").forEach((link) => {
      link.addEventListener("click", () => {
        const paper = selected.find((item) => item.id === link.dataset.paperId);
        this.dispatchEvent(
          new CustomEvent("paper-radar-select", {
            detail: { paper },
            bubbles: true,
          }),
        );
      });
    });

    const footer = this.shadowRoot.querySelector(".footer");
    footer.hidden = !moreUrl;
    if (moreUrl) {
      const link = footer.querySelector(".more");
      link.href = moreUrl;
      link.textContent = this.getAttribute("more-label") || "Open full radar →";
    }
  }

  #paperMarkup(paper) {
    const topic = paper.topics?.[0]?.name || "Exploration";
    const score = Math.round(Number(paper.scores?.total || 0) * 100);
    const showSummary = this.getAttribute("show-summary") !== "false";
    const showScore = this.getAttribute("show-score") !== "false";
    const authors = (paper.authors || []).slice(0, 3).join(", ");
    const authorSuffix = (paper.authors || []).length > 3 ? " et al." : "";
    const date = paper.published
      ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(
          new Date(paper.published),
        )
      : "";
    const summary = paper.summary?.takeaway || paper.abstract || "";
    return `
      <article>
        <div>
          <div class="labels">
            <span class="label">${escapeMarkup(topic)}</span>
            <span class="label category">${escapeMarkup(paper.primary_category || "")}</span>
          </div>
          <h3>
            <a
              href="${escapeMarkup(paper.abs_url || "#")}"
              target="_blank"
              rel="noreferrer"
              data-paper-id="${escapeMarkup(paper.id || "")}"
            >${escapeMarkup(paper.title || "Untitled paper")}</a>
          </h3>
          <p class="meta">${escapeMarkup(authors)}${authorSuffix} · ${escapeMarkup(date)}</p>
        </div>
        ${showScore ? `<span class="score" style="--angle:${score * 3.6}deg" title="Overall score ${score}">${score}</span>` : ""}
        ${showSummary ? `<p class="summary">${escapeMarkup(summary)}</p>` : ""}
      </article>
    `;
  }

  #renderStatus(message, error = false) {
    const list = this.shadowRoot.querySelector(".list");
    list.innerHTML = `<div class="status ${error ? "error" : ""}">${escapeMarkup(message)}</div>`;
  }
}

function escapeMarkup(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

if (!customElements.get("paper-radar-widget")) {
  customElements.define("paper-radar-widget", PaperRadarWidget);
}

export { PaperRadarWidget };
