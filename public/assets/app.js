const STORAGE = {
  profile: "dawnlit.profile.v1",
  feedback: "dawnlit.feedback.v1",
  saved: "dawnlit.saved.v1",
  token: "dawnlit.token",
  language: "dawnlit.analysis-language.v1",
};

const runtime = window.PAPER_RADAR_CONFIG || {};
const state = {
  view: "today",
  feed: { papers: [] },
  weekly: { papers: [] },
  profile: null,
  feedback: readStorage(STORAGE.feedback, []),
  saved: new Set(readStorage(STORAGE.saved, [])),
  analysisLanguage: readStorage(STORAGE.language, "en"),
  apiUrl: (runtime.apiUrl || "").replace(/\/$/, ""),
  token: sessionStorage.getItem(STORAGE.token) || "",
};

const elements = {
  app: document.querySelector("#appContent"),
  loading: document.querySelector("#loadingState"),
  error: document.querySelector("#errorState"),
  nav: document.querySelector("#mainNav"),
  toast: document.querySelector("#toast"),
  importInput: document.querySelector("#profileImport"),
  deepDive: document.querySelector("#deepDiveDialog"),
  languageToggle: document.querySelector("#languageToggle"),
};

function t(english, chinese) {
  return state.analysisLanguage === "zh-CN" ? chinese : english;
}

function localizedAnalysis(paper) {
  if (state.analysisLanguage === "zh-CN") {
    return paper.deep_dive_i18n?.["zh-CN"] || paper.deep_dive;
  }
  return paper.deep_dive;
}

function inferRepository() {
  if (runtime.repository) return runtime.repository;
  if (!window.location.hostname.endsWith(".github.io")) return "";
  const owner = window.location.hostname.split(".")[0];
  const repository = window.location.pathname.split("/").filter(Boolean)[0];
  return owner && repository ? `${owner}/${repository}` : "";
}

function interestsEditUrl() {
  const repository = inferRepository();
  return repository
    ? `https://github.com/${repository}/edit/main/config/interests.txt`
    : "";
}

function readStorage(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function escapeHTML(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function prettyDate(value) {
  if (!value) return "unknown";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function percent(value) {
  return Math.round(Number(value || 0) * 100);
}

async function fetchJSON(url, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(url, { ...options, headers });
  if (!response.ok)
    throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function loadProfile() {
  const localProfile = readStorage(STORAGE.profile, null);
  if (state.apiUrl && state.token) {
    try {
      const remote = await fetchJSON(`${state.apiUrl}/api/profile`);
      writeStorage(STORAGE.profile, remote);
      return remote;
    } catch (error) {
      showToast(
        `Cloud profile unavailable; using local data: ${error.message}`,
      );
    }
  }
  return localProfile || fetchJSON("./data/profile.json");
}

async function boot() {
  try {
    const [feed, weekly, profile] = await Promise.all([
      fetchJSON("./data/papers.json"),
      fetchJSON("./data/weekly.json").catch(() => ({ papers: [] })),
      loadProfile(),
    ]);
    state.feed = feed;
    state.weekly = weekly;
    state.profile = profile;
    elements.loading.classList.add("hidden");
    elements.app.classList.remove("hidden");
    updateChrome();
    render();
  } catch (error) {
    elements.loading.classList.add("hidden");
    elements.error.classList.remove("hidden");
    elements.error.innerHTML = `<h2>No radar signal yet</h2><p>${escapeHTML(
      error.message,
    )}</p><p>Open the site through a local HTTP server, or run the data build first.</p>`;
  }
}

function updateChrome() {
  document.querySelector("#todayCount").textContent = state.feed.papers.length;
  document.querySelector("#weeklyCount").textContent =
    state.weekly.papers.length;
  document.querySelector("#savedCount").textContent = state.saved.size;
  document.querySelector("#lastUpdated").textContent = `Updated ${prettyDate(
    state.feed.generated_at,
  )}`;
  const cloud = Boolean(state.apiUrl && state.token);
  document.querySelector("#modeBadge").textContent = cloud ? "SYNCED" : "LOCAL";
  document.querySelector("#modeBadge").title = cloud
    ? "Preferences and feedback sync to the Dawnlit API"
    : "Preferences and feedback stay in this browser";
  elements.languageToggle.textContent =
    state.analysisLanguage === "zh-CN" ? "EN" : "中文";
  elements.languageToggle.title =
    state.analysisLanguage === "zh-CN"
      ? "Switch analysis to English"
      : "切换为中文解读";
  renderFocus();
}

function renderFocus() {
  const topics = (state.profile?.topics || [])
    .filter((topic) => topic.enabled && topic.weight > 0)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 5);
  document.querySelector("#focusList").innerHTML = topics
    .map(
      (topic) => `
        <div class="focus-item">
          <i></i>
          <span>${escapeHTML(topic.name)}</span>
          <b>${Number(topic.weight).toFixed(1)}</b>
        </div>`,
    )
    .join("");
}

function render() {
  elements.nav.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
  if (state.view === "preferences") {
    renderPreferences();
    return;
  }
  const papers =
    state.view === "today"
      ? state.feed.papers
      : state.view === "weekly"
        ? state.weekly.papers
        : [...state.feed.papers, ...state.weekly.papers].filter(
            (paper, index, all) =>
              state.saved.has(paper.id) &&
              all.findIndex((item) => item.id === paper.id) === index,
          );
  renderPaperView(papers);
}

function renderPaperView(papers) {
  const config = {
    today: {
      eyebrow: "DAILY SIGNAL",
      title: "Today’s radar",
      subtitle:
        "Core LLM research signals, with relevance, quality, and exploration scored separately.",
      date: prettyDate(state.feed.generated_at),
    },
    weekly: {
      eyebrow: "WEEKLY DIGEST",
      title: "This week",
      subtitle:
        "The strongest signals from the last seven days, reranked as a weekly digest.",
      date: `${papers.length} PAPERS`,
    },
    saved: {
      eyebrow: "YOUR LIBRARY",
      title: "Saved papers",
      subtitle:
        "Saved papers provide a light preference signal without locking the whole profile.",
      date: `${papers.length} SAVED`,
    },
  }[state.view];

  const topics = new Set(
    papers.map((paper) => paper.topics?.[0]?.name).filter(Boolean),
  );
  elements.app.innerHTML = `
    <section class="view-header">
      <div>
        <span class="eyebrow">${config.eyebrow}</span>
        <h1>${config.title}</h1>
        <p>${config.subtitle}</p>
      </div>
      <span class="date-stamp">${escapeHTML(config.date)}</span>
    </section>
    <div class="summary-strip">
      ${
        state.feed.demo
          ? '<span class="summary-chip"><strong>DEMO</strong> fixture data</span>'
          : ""
      }
      <span class="summary-chip"><strong>${
        papers.length
      }</strong> selected</span>
      <span class="summary-chip"><strong>${
        topics.size
      }</strong> topic lanes</span>
      <span class="summary-chip"><strong>${
        papers.filter((p) => p.lane === "transferable").length
      }</strong> transferable</span>
    </div>
    ${
      papers.length
        ? `<div class="paper-list">${papers.map(paperCard).join("")}</div>`
        : emptyState()
    }
  `;
}

function paperCard(paper) {
  const score = percent(paper.scores?.total);
  const topic = paper.topics?.[0] || { name: "Exploration", matched: [] };
  const authors = (paper.authors || []).slice(0, 4).join(", ");
  const moreAuthors = (paper.authors || []).length > 4 ? " et al." : "";
  const saved = state.saved.has(paper.id);
  const signals = (paper.quality_signals || []).slice(0, 4);
  const summary = paper.summary || {};
  return `
    <article class="paper-card" data-paper-id="${escapeHTML(paper.id)}">
      <div class="paper-topline">
        <div class="paper-labels">
          <span class="topic-chip ${
            paper.lane === "transferable" ? "transferable" : ""
          }">
            ${paper.lane === "transferable" ? "Transfer · " : ""}${escapeHTML(
              topic.name,
            )}
          </span>
          <span class="topic-chip category-chip">${escapeHTML(
            paper.primary_category,
          )}</span>
          <span class="topic-chip brief-source-chip">${
            summary.generated_by === "extractive"
              ? t("Abstract extract", "摘要摘录")
              : t("AI brief", "AI 解读")
          }</span>
        </div>
        <span class="score" style="--score-angle: ${
          score * 3.6
        }deg" title="Overall score ${score}">${score}</span>
      </div>
      <h2>${escapeHTML(paper.title)}</h2>
      <p class="paper-meta">${escapeHTML(authors)}${moreAuthors} · ${prettyDate(
        paper.published,
      )} · arXiv:${escapeHTML(paper.id)}</p>
      ${threeLineBrief(paper)}
      <div class="match-line">
        <span>${t("Signals:", "匹配信号：")}</span>
        ${(topic.matched || [])
          .slice(0, 4)
          .map((item) => `<span class="signal-chip">${escapeHTML(item)}</span>`)
          .join("")}
        ${signals
          .map(
            (item) => `<span class="signal-chip">✓ ${escapeHTML(item)}</span>`,
          )
          .join("")}
      </div>
      <div class="paper-actions">
        <button class="action-button save-button ${
          saved ? "active" : ""
        }" data-action="save">
          ${saved ? "◆ Saved" : "◇ Save"}
        </button>
        <button class="action-button" data-action="read">✓ Read</button>
        <div class="feedback-menu">
          <button class="action-button" data-action="feedback-menu">Tune signal ▾</button>
          <div class="feedback-popover">
            <button data-feedback="more_method">More methods like this</button>
            <button data-feedback="more_topic">Increase this topic</button>
            <button data-feedback="low_quality">Relevant, but weak evidence</button>
            <button data-feedback="not_now">Not interested right now</button>
            <button data-feedback="not_llm">Not the LLM work I need</button>
            <button data-feedback="transferable">Non-LLM, but transferable</button>
          </div>
        </div>
        <button class="action-button deep-dive-button" data-action="deep-dive" ${
          paper.deep_dive ? "" : "disabled"
        } title="${
          paper.deep_dive
            ? t("Open the full-text AI analysis", "打开全文 AI 深度解读")
            : t(
                "Deep analysis is unavailable for this paper",
                "这篇论文暂时没有深度解读",
              )
        }">${t("Deep dive ✦", "深度解读 ✦")}</button>
        <button class="action-button expand-button" data-action="expand">Structured note ＋</button>
        <a class="link-button" href="${escapeHTML(
          paper.abs_url,
        )}" target="_blank" rel="noreferrer">arXiv ↗</a>
        <a class="link-button" href="${escapeHTML(
          paper.pdf_url,
        )}" target="_blank" rel="noreferrer">PDF ↗</a>
      </div>
      <div class="paper-details">
        <div class="summary-grid">
          ${summaryCell("Problem", summary.problem)}
          ${summaryCell("Method", summary.method)}
          ${summaryCell("Evidence", summary.evidence)}
          ${summaryCell("Limitations", summary.limitations)}
          ${summaryCell("Why for you", summary.why_for_you)}
          ${summaryCell(
            "Summary source",
            `${summary.source || "abstract"} · ${
              summary.generated_by || "unknown"
            }`,
          )}
        </div>
        <p class="abstract"><strong>Abstract.</strong> ${escapeHTML(
          paper.abstract,
        )}</p>
      </div>
    </article>
  `;
}

function threeLineBrief(paper) {
  const summary = paper.summary || {};
  const analysis = localizedAnalysis(paper);
  const signals =
    Array.isArray(analysis?.signals) && analysis.signals.length === 3
      ? analysis.signals
      : [
          { icon: "🧠", text: summary.takeaway || paper.abstract },
          {
            icon: "🛠️",
            text:
              summary.method ||
              "Method details are not stated in the abstract.",
          },
          {
            icon: "📊",
            text: summary.evidence || "Evidence is not stated in the abstract.",
          },
        ];
  return `
    <div class="three-line-brief" aria-label="${t(
      "Three-line paper brief",
      "三行论文摘要",
    )}">
      ${signals
        .map(
          (signal) => `
            <div class="brief-signal">
              <span aria-hidden="true">${escapeHTML(signal.icon || "•")}</span>
              <p>${escapeHTML(
                signal.text || "Not stated in the available source.",
              )}</p>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function detailItems(items = []) {
  if (!Array.isArray(items) || !items.length) {
    return `<p class="deep-dive-missing">${t(
      "Not stated in the available source.",
      "现有材料中没有说明。",
    )}</p>`;
  }
  return `
    <div class="deep-dive-items">
      ${items
        .map(
          (item) => `
            <article>
              <h4>${escapeHTML(item.title || "Detail")}</h4>
              <p>${escapeHTML(item.detail || "")}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function textList(items = []) {
  if (!Array.isArray(items) || !items.length) {
    return `<p class="deep-dive-missing">${t(
      "Not stated in the available source.",
      "现有材料中没有说明。",
    )}</p>`;
  }
  return `<ul>${items
    .map((item) => `<li>${escapeHTML(item)}</li>`)
    .join("")}</ul>`;
}

function openDeepDive(paper) {
  const analysis = localizedAnalysis(paper);
  if (!analysis) {
    showToast(
      t(
        "Deep analysis is unavailable for this paper.",
        "这篇论文暂时没有深度解读。",
      ),
    );
    return;
  }
  elements.deepDive.innerHTML = `
    <div class="deep-dive-shell">
      <header class="deep-dive-header">
        <div>
          <span class="eyebrow">${t(
            "FULL-TEXT AI ANALYSIS",
            "全文 AI 深度解读",
          )}</span>
          <h2 id="deepDiveTitle">${escapeHTML(paper.title)}</h2>
          <p>${escapeHTML((paper.authors || []).join(", "))}</p>
        </div>
        <button type="button" class="dialog-close" data-dialog-close aria-label="${t(
          "Close analysis",
          "关闭解读",
        )}">×</button>
      </header>
      <div class="deep-dive-content">
        ${threeLineBrief(paper)}
        <section>
          <h3>${t("Research question & thesis", "研究问题与核心论点")}</h3>
          <p>${escapeHTML(
            analysis.overview || "Not stated in the available source.",
          )}</p>
        </section>
        <section>
          <h3>${t("Method pipeline", "核心方法与流程")}</h3>
          ${detailItems(analysis.methodology)}
        </section>
        <section>
          <h3>${t("Mechanism & theory", "机制与理论分析")}</h3>
          ${detailItems(analysis.mechanism)}
        </section>
        <section>
          <h3>${t("Experimental design", "实验设计")}</h3>
          ${detailItems(analysis.experiments)}
        </section>
        <section>
          <h3>${t("Results & evidence", "主要结果与证据")}</h3>
          ${detailItems(analysis.findings)}
        </section>
        <div class="deep-dive-columns">
          <section>
            <h3>${t("Contributions", "主要贡献")}</h3>
            ${textList(analysis.contributions)}
          </section>
          <section>
            <h3>${t("Limitations & checks", "局限与核查要点")}</h3>
            ${textList(analysis.limitations)}
          </section>
        </div>
        <section>
          <h3>${t("Open questions", "值得继续追问的问题")}</h3>
          ${textList(analysis.open_questions)}
        </section>
        <footer>
          ${t("Generated from", "内容生成自")}
          ${escapeHTML(
            analysis.source_scope || t("the available source", "现有材料"),
          )}
          ${t("by", "；模型：")}
          ${escapeHTML(analysis.generated_by || t("an AI model", "AI 模型"))}.
          ${t(
            "Verify important claims in the paper.",
            "重要结论请回到论文原文核查。",
          )}
        </footer>
      </div>
    </div>
  `;
  elements.deepDive.showModal();
}

function summaryCell(label, value = "Not stated in the abstract") {
  return `<div class="summary-cell"><h3>${label}</h3><p>${escapeHTML(
    value,
  )}</p></div>`;
}

function emptyState() {
  const message =
    state.view === "saved"
      ? "Nothing saved yet. Save a paper when it deserves a closer read."
      : "No signal cleared the threshold. An empty feed is better than filler.";
  return `<div class="empty-state"><h2>A quiet day</h2><p>${message}</p></div>`;
}

function renderPreferences() {
  const editUrl = interestsEditUrl();
  elements.app.innerHTML = `
    <section class="view-header">
      <div>
        <span class="eyebrow">CONTROL ROOM</span>
        <h1>Preferences</h1>
        <p>Your profile is explicit, editable, and portable; seed papers remain a weak signal.</p>
      </div>
      <span class="date-stamp">${
        state.apiUrl && state.token ? "CLOUD SYNC" : "LOCAL MODE"
      }</span>
    </section>
    <div class="preference-layout">
      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>Quick adjustment</h2>
            <p>Try “more data selection” or “less OPD,” then save the change.</p>
          </div>
        </div>
        <div class="command-box">
          <input id="preferenceCommand" type="text" placeholder="More data selection, less OPD…" />
          <button class="secondary-button" data-pref-action="apply-command">Apply</button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>Topic lanes</h2>
            <p>Each direction stays independent instead of collapsing into one seed centroid.</p>
          </div>
          <button class="primary-button" data-pref-action="save-profile">Save changes</button>
        </div>
        <div class="topic-editor-list">
          ${state.profile.topics.map(topicEditor).join("")}
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>Add a direction</h2>
            <p>The description participates in matching; keywords can be refined later.</p>
          </div>
        </div>
        <div class="add-topic-grid">
          <input id="newTopicName" type="text" placeholder="Topic name" />
          <textarea id="newTopicDescription" placeholder="Describe what should enter this lane…"></textarea>
          <button class="secondary-button" data-pref-action="add-topic">Add topic</button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>Data ownership</h2>
            <p>Local mode uploads nothing. Edit the simple interest list for scheduled builds.</p>
          </div>
        </div>
        <div class="preference-actions">
          ${
            editUrl
              ? `<a class="secondary-button" href="${escapeHTML(
                  editUrl,
                )}" target="_blank" rel="noreferrer">Edit interests on GitHub ↗</a>`
              : ""
          }
          <button class="secondary-button" data-pref-action="export-profile">Export profile</button>
          <button class="secondary-button" data-pref-action="import-profile">Import profile</button>
          <button class="secondary-button" data-pref-action="export-feedback">Export feedback</button>
          <button class="danger-button" data-pref-action="clear-feedback">Clear feedback</button>
        </div>
        ${
          state.apiUrl
            ? `<div class="auth-row">
                <input id="apiToken" type="password" placeholder="Admin token (kept in this tab only)" value="${escapeHTML(
                  state.token,
                )}" />
                <button class="secondary-button" data-pref-action="connect-api">Connect API</button>
              </div>`
            : ""
        }
      </section>
    </div>
  `;
}

function topicEditor(topic, index) {
  return `
    <div class="topic-editor" data-topic-index="${index}">
      <div class="topic-name-field">
        <input type="checkbox" data-topic-field="enabled" ${
          topic.enabled ? "checked" : ""
        } aria-label="Enable ${escapeHTML(topic.name)}" />
        <div>
          <input type="text" data-topic-field="name" value="${escapeHTML(
            topic.name,
          )}" aria-label="Topic name" />
          <textarea data-topic-field="description" aria-label="Topic description">${escapeHTML(
            topic.description || "",
          )}</textarea>
        </div>
      </div>
      <label class="weight-control">
        <input type="range" min="0" max="1" step="0.1" value="${Number(
          topic.weight || 0,
        )}" data-topic-field="weight" />
        <output>${Number(topic.weight || 0).toFixed(1)}</output>
      </label>
      <select data-topic-field="status" aria-label="Topic status">
        ${["core", "emerging", "watch", "background"]
          .map(
            (status) =>
              `<option value="${status}" ${
                topic.status === status ? "selected" : ""
              }>${status}</option>`,
          )
          .join("")}
      </select>
      <button class="remove-topic" data-pref-action="remove-topic" title="Remove topic">×</button>
    </div>
  `;
}

function paperById(id) {
  return [...state.feed.papers, ...state.weekly.papers].find(
    (paper) => paper.id === id,
  );
}

async function recordFeedback(paper, action) {
  const item = {
    id: crypto.randomUUID(),
    paper_id: paper.id,
    action,
    title: paper.title,
    abstract: paper.abstract,
    topics: (paper.topics || []).map((topic) => topic.id),
    created_at: new Date().toISOString(),
  };
  state.feedback.push(item);
  writeStorage(STORAGE.feedback, state.feedback);
  if (action === "more_topic" && paper.topics?.[0]) {
    const topic = state.profile.topics.find(
      (candidate) => candidate.id === paper.topics[0].id,
    );
    if (topic) {
      topic.weight = Math.min(1, Number(topic.weight || 0) + 0.1);
      writeStorage(STORAGE.profile, state.profile);
    }
  }
  if (state.apiUrl && state.token) {
    try {
      await fetchJSON(`${state.apiUrl}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item),
      });
      if (action === "more_topic") {
        await fetchJSON(`${state.apiUrl}/api/profile`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state.profile),
        });
      }
    } catch (error) {
      showToast(
        `Feedback was saved locally; cloud sync failed: ${error.message}`,
      );
      return;
    }
  }
  showToast(feedbackMessage(action));
}

function feedbackMessage(action) {
  return (
    {
      save: "Saved and recorded as a light positive signal.",
      unsave: "Removed from saved papers and positive signals.",
      read: "Marked as read.",
      more_method: "Similar methods will receive more weight.",
      more_topic: "This topic received more weight.",
      low_quality: "Recorded as relevant, but weak evidence.",
      not_now: "Snoozed without changing long-term interests.",
      not_llm: "Recorded as a negative scope signal.",
      transferable: "Recorded as a transferable method.",
    }[action] || "Feedback recorded."
  );
}

function syncEditorsToProfile() {
  elements.app.querySelectorAll(".topic-editor").forEach((editor) => {
    const topic = state.profile.topics[Number(editor.dataset.topicIndex)];
    if (!topic) return;
    editor.querySelectorAll("[data-topic-field]").forEach((input) => {
      const field = input.dataset.topicField;
      topic[field] =
        input.type === "checkbox"
          ? input.checked
          : input.type === "range"
            ? Number(input.value)
            : input.value;
    });
  });
  state.profile.updated_at = new Date().toISOString().slice(0, 10);
}

async function saveProfile() {
  syncEditorsToProfile();
  writeStorage(STORAGE.profile, state.profile);
  if (state.apiUrl && state.token) {
    await fetchJSON(`${state.apiUrl}/api/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.profile),
    });
  }
  updateChrome();
  showToast(
    state.apiUrl && state.token
      ? "Profile synced. The next build will use it."
      : "Profile saved locally. Export it for scheduled builds.",
  );
}

function applyPreferenceCommand(command) {
  const lowered = command.toLowerCase();
  const increase = /(more|increase|raise|focus|prioritize)/i.test(command);
  const decrease = /(less|decrease|reduce|lower)/i.test(command);
  const mute = /(mute|exclude|disable|remove)/i.test(command);
  const matched = state.profile.topics.filter((topic) => {
    const aliases = [
      topic.name,
      topic.id,
      topic.id.replaceAll("_", " "),
      ...(topic.phrases || []),
      ...(topic.terms || []),
    ];
    return aliases.some((alias) => lowered.includes(alias.toLowerCase()));
  });
  if (!matched.length) {
    showToast("No existing topic matched. Add a new direction below.");
    return;
  }
  syncEditorsToProfile();
  matched.forEach((topic) => {
    if (mute) {
      topic.enabled = false;
    } else if (increase) {
      topic.weight = Math.min(1, Number(topic.weight) + 0.1);
    } else if (decrease) {
      topic.weight = Math.max(0, Number(topic.weight) - 0.1);
    }
  });
  renderPreferences();
  showToast(`Adjusted: ${matched.map((topic) => topic.name).join(", ")}`);
}

function addTopic() {
  syncEditorsToProfile();
  const name = document.querySelector("#newTopicName").value.trim();
  const description = document
    .querySelector("#newTopicDescription")
    .value.trim();
  if (!name || !description) {
    showToast("Enter both a topic name and description.");
    return;
  }
  const id = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
  state.profile.topics.push({
    id: id || `topic_${Date.now()}`,
    name,
    description,
    weight: 0.7,
    status: "emerging",
    enabled: true,
    phrases: [],
    terms: description
      .toLowerCase()
      .split(/[,，;；]/)
      .map((item) => item.trim())
      .filter(Boolean),
    exclude: [],
  });
  renderPreferences();
  showToast(`Added ${name}.`);
}

function downloadJSON(filename, data) {
  const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], {
    type: "application/json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 500);
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(
    () => elements.toast.classList.remove("visible"),
    2600,
  );
}

elements.nav.addEventListener("click", (event) => {
  const button = event.target.closest("[data-view]");
  if (!button) return;
  state.view = button.dataset.view;
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

elements.languageToggle.addEventListener("click", () => {
  state.analysisLanguage = state.analysisLanguage === "zh-CN" ? "en" : "zh-CN";
  writeStorage(STORAGE.language, state.analysisLanguage);
  if (elements.deepDive.open) elements.deepDive.close();
  updateChrome();
  render();
});

elements.app.addEventListener("click", async (event) => {
  const actionButton = event.target.closest("[data-action]");
  const feedbackButton = event.target.closest("[data-feedback]");
  const preferenceButton = event.target.closest("[data-pref-action]");

  if (feedbackButton) {
    const card = feedbackButton.closest(".paper-card");
    const paper = paperById(card.dataset.paperId);
    await recordFeedback(paper, feedbackButton.dataset.feedback);
    feedbackButton.closest(".feedback-menu").classList.remove("open");
    return;
  }

  if (actionButton) {
    const card = actionButton.closest(".paper-card");
    const paper = paperById(card.dataset.paperId);
    const action = actionButton.dataset.action;
    if (action === "deep-dive") {
      openDeepDive(paper);
    } else if (action === "expand") {
      card.classList.toggle("expanded");
      actionButton.textContent = card.classList.contains("expanded")
        ? "Structured note −"
        : "Structured note ＋";
    } else if (action === "feedback-menu") {
      actionButton.closest(".feedback-menu").classList.toggle("open");
    } else if (action === "save") {
      if (state.saved.has(paper.id)) {
        state.saved.delete(paper.id);
        await recordFeedback(paper, "unsave");
      } else {
        state.saved.add(paper.id);
        await recordFeedback(paper, "save");
      }
      writeStorage(STORAGE.saved, [...state.saved]);
      updateChrome();
      render();
    } else if (action === "read") {
      await recordFeedback(paper, "read");
      actionButton.classList.add("active");
      actionButton.textContent = "✓ Read";
    }
    return;
  }

  if (!preferenceButton) return;
  const action = preferenceButton.dataset.prefAction;
  try {
    if (action === "save-profile") await saveProfile();
    if (action === "apply-command") {
      applyPreferenceCommand(
        document.querySelector("#preferenceCommand").value.trim(),
      );
    }
    if (action === "add-topic") addTopic();
    if (action === "remove-topic") {
      syncEditorsToProfile();
      const editor = preferenceButton.closest(".topic-editor");
      state.profile.topics.splice(Number(editor.dataset.topicIndex), 1);
      renderPreferences();
    }
    if (action === "export-profile") {
      syncEditorsToProfile();
      downloadJSON("dawnlit-profile.json", state.profile);
    }
    if (action === "import-profile") elements.importInput.click();
    if (action === "export-feedback") {
      downloadJSON("dawnlit-feedback.json", state.feedback);
    }
    if (action === "clear-feedback") {
      state.feedback = [];
      writeStorage(STORAGE.feedback, []);
      showToast("Local feedback cleared.");
    }
    if (action === "connect-api") {
      state.token = document.querySelector("#apiToken").value.trim();
      sessionStorage.setItem(STORAGE.token, state.token);
      state.profile = await loadProfile();
      updateChrome();
      renderPreferences();
      showToast("Connected to the Dawnlit API.");
    }
  } catch (error) {
    showToast(`Action failed: ${error.message}`);
  }
});

elements.app.addEventListener("input", (event) => {
  if (event.target.type === "range") {
    event.target
      .closest(".weight-control")
      .querySelector("output").textContent = Number(event.target.value).toFixed(
      1,
    );
  }
});

elements.importInput.addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  try {
    const profile = JSON.parse(await file.text());
    if (!Array.isArray(profile.topics))
      throw new Error("The profile has no topics array");
    state.profile = profile;
    writeStorage(STORAGE.profile, profile);
    updateChrome();
    renderPreferences();
    showToast("Profile imported.");
  } catch (error) {
    showToast(`Import failed: ${error.message}`);
  } finally {
    event.target.value = "";
  }
});

document.addEventListener("click", (event) => {
  document.querySelectorAll(".feedback-menu.open").forEach((menu) => {
    if (!menu.contains(event.target)) menu.classList.remove("open");
  });
});

elements.deepDive.addEventListener("click", (event) => {
  if (
    event.target.closest("[data-dialog-close]") ||
    event.target === elements.deepDive
  ) {
    elements.deepDive.close();
  }
});

boot();
