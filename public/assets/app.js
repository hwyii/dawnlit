const STORAGE = {
  profile: "dawnlit.profile.v1",
  feedback: "dawnlit.feedback.v1",
  saved: "dawnlit.saved.v1",
  dismissed: "dawnlit.dismissed.v1",
  token: "dawnlit.token",
  theme: "dawnlit.theme.v1",
};

const ARCHIVE_DAYS = 7;
const COPY = {
  en: {
    brandTagline: "your morning research signal",
    install: "Install on iPhone",
    installEyebrow: "PERSONAL IPHONE APP",
    installTitle: "Add Dawnlit to your Home Screen",
    installHint: "Dawnlit will open full screen from its icon and keep the latest feed available offline.",
    today: "Today",
    weekly: "Weekly",
    useful: "Useful",
    preferences: "Preferences",
    currentFocus: "CURRENT FOCUS",
    curatedDaily: "Curated daily, summarized on demand",
    updated: "Updated {date}",
    cloud: "CLOUD ✓",
    local: "LOCAL",
    previousPaper: "Previous paper",
    nextPaper: "Next paper",
    swipeHint: "Swipe for previous / next",
    dailySignal: "DAILY SIGNAL",
    todaysRadar: "Today’s radar",
    todaySubtitle: "New, never-before-recommended LLM papers; quiet days stay intentionally short.",
    weeklyDigest: "WEEKLY DIGEST",
    thisWeek: "This week",
    weeklySubtitle: "The strongest signals from the last seven days, reranked as a weekly digest.",
    yourLibrary: "YOUR LIBRARY",
    usefulPapers: "Useful papers",
    librarySubtitle: "Papers you marked useful, indexed from Today, Weekly, and History.",
    papers: "PAPERS",
    usefulUpper: "USEFUL",
    notUseful: "Not useful",
    irrelevant: "Irrelevant",
    deepDive: "Deep dive ✦",
    aiBrief: "AI brief",
    abstractExtract: "Abstract extract",
    threeLineBrief: "Three-line paper brief",
    researchQuestion: "Research question & thesis",
    methodPipeline: "Method pipeline",
    mechanismTheory: "Mechanism & theory",
    experimentalDesign: "Experimental design",
    resultsEvidence: "Results & evidence",
    contributions: "Contributions",
    limitationsChecks: "Limitations & checks",
    openQuestions: "Open questions",
    fullTextAnalysis: "FULL-TEXT AI ANALYSIS",
    verifyClaims: "Verify important claims in the paper.",
    quietDay: "A quiet day",
    nothingUseful: "Nothing marked useful yet.",
    noSignal: "No signal cleared the threshold. An empty feed is better than filler.",
    controlRoom: "CONTROL ROOM",
    preferenceIntro: "Your profile is explicit, editable, and portable; seed papers remain a weak signal.",
    cloudSync: "CLOUD SYNC",
    localMode: "LOCAL MODE",
    appearanceLanguage: "Appearance & language",
    appearanceHint: "Theme stays on this device. Interface and AI content languages sync independently.",
    theme: "Theme",
    system: "System",
    light: "Light",
    dark: "Dark",
    language: "Interface language",
    contentLanguage: "AI briefs & Deep Dive",
    english: "English",
    chinese: "中文",
    languageRefreshHint: "Paper titles stay in English. AI content language only changes paper briefs and Deep Dive content.",
    quickAdjustment: "Quick adjustment",
    quickHint: "Try “more data selection” or “less OPD,” then save the change.",
    apply: "Apply",
    topicLanes: "Topic lanes",
    topicHint: "Each direction stays independent instead of collapsing into one seed centroid.",
    saveChanges: "Save changes",
    addDirection: "Add a direction",
    addDirectionHint: "The description participates in matching; keywords can be refined later.",
    topicName: "Topic name",
    topicDescription: "Describe what should enter this lane…",
    addTopic: "Add topic",
    archive: "Archive",
    archiveHint: "Not useful and irrelevant papers stay here for {days} days, then disappear automatically.",
    restoreAll: "Restore all",
    restore: "Restore",
    noArchived: "No archived papers.",
    dataOwnership: "Data ownership",
    dataOwnershipHint: "Local mode uploads nothing. Edit the simple interest list for scheduled builds.",
    editInterests: "Edit interests on GitHub ↗",
    exportProfile: "Export profile",
    importProfile: "Import profile",
    exportFeedback: "Export feedback",
    clearFeedback: "Clear feedback",
    saveSync: "Save & sync",
    forgetToken: "Forget token",
    settingsSaved: "Interface language saved: {language}.",
    contentSettingsSaved: "Paper briefs and Deep Dive will use {language}.",
  },
  zh: {
    brandTagline: "你的每日论文信号",
    install: "安装到 iPhone",
    installEyebrow: "你的个人 IPHONE APP",
    installTitle: "将 Dawnlit 添加到主屏幕",
    installHint: "从主屏幕图标打开后会全屏运行，并保留最近的论文供离线查看。",
    today: "今日",
    weekly: "本周",
    useful: "收藏",
    preferences: "设置",
    currentFocus: "当前关注",
    curatedDaily: "每日筛选，需要时深入解析",
    updated: "更新于 {date}",
    cloud: "云端 ✓",
    local: "本地",
    previousPaper: "上一篇论文",
    nextPaper: "下一篇论文",
    swipeHint: "左右滑动切换论文",
    dailySignal: "今日精选",
    todaysRadar: "今日论文",
    todaySubtitle: "只推荐尚未出现过的 LLM 论文；没有合适内容时宁缺毋滥。",
    weeklyDigest: "每周精选",
    thisWeek: "本周论文",
    weeklySubtitle: "将最近七天最强的研究信号重新排序。",
    yourLibrary: "你的收藏",
    usefulPapers: "收藏的论文",
    librarySubtitle: "你标记为有用的论文。",
    papers: "篇论文",
    usefulUpper: "篇收藏",
    notUseful: "没用",
    irrelevant: "不相关",
    deepDive: "深度解析 ✦",
    aiBrief: "AI 摘要",
    abstractExtract: "摘要提取",
    threeLineBrief: "三条论文速览",
    researchQuestion: "研究问题与核心观点",
    methodPipeline: "方法流程",
    mechanismTheory: "机制与理论",
    experimentalDesign: "实验设计",
    resultsEvidence: "结果与证据",
    contributions: "主要贡献",
    limitationsChecks: "局限与核查",
    openQuestions: "开放问题",
    fullTextAnalysis: "全文 AI 解析",
    verifyClaims: "重要结论请回到原论文核实。",
    quietDay: "今天很安静",
    nothingUseful: "还没有收藏论文。",
    noSignal: "今天没有论文达到推荐阈值，空着比凑数更好。",
    controlRoom: "控制中心",
    preferenceIntro: "你的兴趣配置清晰、可编辑，也可以随时导出。",
    cloudSync: "云端同步",
    localMode: "本地模式",
    appearanceLanguage: "外观与语言",
    appearanceHint: "主题保存在当前设备；界面语言和 AI 内容语言分别同步。",
    theme: "主题",
    system: "跟随系统",
    light: "浅色",
    dark: "深色",
    language: "界面语言",
    contentLanguage: "论文总结与 Deep Dive",
    english: "English",
    chinese: "中文",
    languageRefreshHint: "论文标题保留英文；AI 内容语言只改变论文总结与 Deep Dive 正文。",
    quickAdjustment: "快速调整",
    quickHint: "例如输入“more data selection”或“less OPD”，然后保存。",
    apply: "应用",
    topicLanes: "研究方向",
    topicHint: "每个方向独立计分，不会全部压成一个种子论文中心。",
    saveChanges: "保存修改",
    addDirection: "添加方向",
    addDirectionHint: "描述会参与匹配，关键词之后还可以继续调整。",
    topicName: "方向名称",
    topicDescription: "描述哪些论文应该进入这个方向…",
    addTopic: "添加方向",
    archive: "归档",
    archiveHint: "“没用”和“不相关”的论文会保留 {days} 天，然后自动消失。",
    restoreAll: "全部恢复",
    restore: "恢复",
    noArchived: "没有归档论文。",
    dataOwnership: "数据与同步",
    dataOwnershipHint: "本地模式不会上传数据；定时构建使用 GitHub 中的兴趣列表。",
    editInterests: "在 GitHub 编辑兴趣 ↗",
    exportProfile: "导出配置",
    importProfile: "导入配置",
    exportFeedback: "导出反馈",
    clearFeedback: "清除反馈",
    saveSync: "保存并同步",
    forgetToken: "忘记令牌",
    settingsSaved: "界面语言已保存：{language}。",
    contentSettingsSaved: "论文总结与 Deep Dive 将使用{language}。",
  },
};
const runtime = window.PAPER_RADAR_CONFIG || {};
const state = {
  view: "today",
  feed: { papers: [] },
  weekly: { papers: [] },
  history: { papers: [] },
  profile: null,
  feedback: readStorage(STORAGE.feedback, []),
  saved: new Set(readStorage(STORAGE.saved, [])),
  dismissed: readDismissals(),
  apiUrl: (runtime.apiUrl || "").replace(/\/$/, ""),
  token:
    readTextStorage(STORAGE.token) ||
    sessionStorage.getItem(STORAGE.token) ||
    "",
  installPrompt: null,
  lastRefreshAt: 0,
  deckIndex: { today: 0, weekly: 0, saved: 0 },
  cloudConnected: false,
  language:
    (readStorage(STORAGE.profile, {})?.ui_language ||
      readStorage(STORAGE.profile, {})?.language) === "zh"
      ? "zh"
      : "en",
  contentLanguage:
    readStorage(STORAGE.profile, {})?.content_language === "en" ? "en" : "zh",
  theme: ["system", "light", "dark"].includes(readTextStorage(STORAGE.theme))
    ? readTextStorage(STORAGE.theme)
    : "system",
};

function t(key, replacements = {}) {
  let value = COPY[state.language]?.[key] || COPY.en[key] || key;
  Object.entries(replacements).forEach(([name, replacement]) => {
    value = value.replaceAll(`{${name}}`, replacement);
  });
  return value;
}

function resolvedTheme(theme = state.theme) {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyTheme(theme = state.theme, persist = false) {
  state.theme = theme;
  const resolved = resolvedTheme(theme);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
  document.querySelector("#themeColor")?.setAttribute(
    "content",
    resolved === "dark" ? "#111816" : "#f4f1e8",
  );
  if (persist) writeTextStorage(STORAGE.theme, theme);
}

function applyLanguage() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  const steps = document.querySelector("#installSteps");
  if (steps) {
    steps.innerHTML =
      state.language === "zh"
        ? "<li>请先在 Safari 中打开这个页面。</li><li>点击分享按钮 <span aria-hidden=\"true\">□↑</span>。</li><li>选择<strong>添加到主屏幕</strong>，然后点击<strong>添加</strong>。</li>"
        : "<li>Open this page in Safari.</li><li>Tap the Share button <span aria-hidden=\"true\">□↑</span>.</li><li>Choose <strong>Add to Home Screen</strong>, then tap <strong>Add</strong>.</li>";
  }
}

applyTheme();

if (state.token) writeTextStorage(STORAGE.token, state.token);
sessionStorage.removeItem(STORAGE.token);

const elements = {
  app: document.querySelector("#appContent"),
  loading: document.querySelector("#loadingState"),
  error: document.querySelector("#errorState"),
  nav: document.querySelector("#mainNav"),
  toast: document.querySelector("#toast"),
  importInput: document.querySelector("#profileImport"),
  deepDive: document.querySelector("#deepDiveDialog"),
  installDialog: document.querySelector("#installDialog"),
  installButton: document.querySelector("#installAppButton"),
};

function isStandaloneApp() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

function isIOSDevice() {
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

async function installApp() {
  if (isStandaloneApp()) {
    showToast("Dawnlit is already installed on this device.");
    return;
  }
  if (state.installPrompt) {
    state.installPrompt.prompt();
    const choice = await state.installPrompt.userChoice;
    state.installPrompt = null;
    if (choice.outcome === "accepted") showToast("Dawnlit installed.");
    return;
  }

  const steps = document.querySelector("#installSteps");
  const hint = document.querySelector("#installHint");
  if (!isIOSDevice()) {
    steps.innerHTML = `
      <li>Open your browser menu.</li>
      <li>Choose <strong>Install app</strong> or <strong>Add to Home Screen</strong>.</li>
      <li>Confirm the installation.</li>
    `;
    hint.textContent =
      "If the install option is missing, open this page in Safari or Chrome first.";
  }
  elements.installDialog.showModal();
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("./sw.js")
      .then((registration) => registration.update())
      .catch((error) => {
        console.warn("Dawnlit offline mode is unavailable:", error);
      });
  });
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

function readTextStorage(key) {
  try {
    return localStorage.getItem(key) || "";
  } catch {
    return "";
  }
}

function writeTextStorage(key, value) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    // Local-only mode remains available if persistent storage is blocked.
  }
}

function readDismissals() {
  const stored = readStorage(STORAGE.dismissed, {});
  const now = Date.now();
  const active = Object.fromEntries(
    Object.entries(stored).filter(([, dismissal]) => {
      if (!dismissal || typeof dismissal !== "object") return false;
      return !dismissal.expires_at || Date.parse(dismissal.expires_at) > now;
    }),
  );
  if (Object.keys(active).length !== Object.keys(stored).length) {
    writeStorage(STORAGE.dismissed, active);
  }
  return active;
}

function isDismissed(paperId) {
  return Boolean(state.dismissed[paperId]);
}

function dismissPaper(paper, action) {
  const now = new Date();
  const expiresAt = new Date(
    now.getTime() + ARCHIVE_DAYS * 86400000,
  ).toISOString();
  state.dismissed[paper.id] = {
    paper_id: paper.id,
    title: paper.title,
    action,
    dismissed_at: now.toISOString(),
    expires_at: expiresAt,
  };
  writeStorage(STORAGE.dismissed, state.dismissed);
}

function allPapers() {
  const byId = new Map();
  [state.feed, state.weekly, state.history].forEach((collection) => {
    (collection.papers || []).forEach((paper) => {
      if (!byId.has(paper.id)) byId.set(paper.id, paper);
    });
  });
  return [...byId.values()];
}

function visiblePapers(papers) {
  return papers.filter((paper) => !isDismissed(paper.id));
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
  return new Intl.DateTimeFormat(state.language === "zh" ? "zh-CN" : "en-US", {
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
  const response = await fetch(url, { cache: "no-store", ...options, headers });
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
      state.cloudConnected = true;
      return remote;
    } catch (error) {
      state.cloudConnected = false;
      showToast(
        `Cloud profile unavailable; using local data: ${error.message}`,
      );
    }
  }
  return localProfile || fetchJSON("./data/profile.json");
}

async function boot() {
  try {
    const [feed, weekly, history, profile] = await Promise.all([
      fetchJSON("./data/papers.json"),
      fetchJSON("./data/weekly.json").catch(() => ({ papers: [] })),
      fetchJSON("./data/history.json").catch(() => ({ papers: [] })),
      loadProfile(),
    ]);
    state.feed = feed;
    state.weekly = weekly;
    state.history = history;
    state.profile = profile;
    state.language = (profile.ui_language || profile.language) === "zh" ? "zh" : "en";
    state.contentLanguage = profile.content_language === "en" ? "en" : "zh";
    applyLanguage();
    state.lastRefreshAt = Date.now();
    await syncPendingFeedback();
    await pullCloudFeedback();
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
  document.querySelector("#todayCount").textContent = visiblePapers(
    state.feed.papers,
  ).length;
  document.querySelector("#weeklyCount").textContent = visiblePapers(
    state.weekly.papers,
  ).length;
  document.querySelector("#savedCount").textContent = [...state.saved].filter(
    (paperId) => !isDismissed(paperId),
  ).length;
  document.querySelector("#lastUpdated").textContent = t("updated", {
    date: prettyDate(state.feed.generated_at),
  });
  const cloud = Boolean(state.apiUrl && state.token && state.cloudConnected);
  document.querySelector("#modeBadge").textContent = cloud ? t("cloud") : t("local");
  document.querySelector("#modeBadge").title = cloud
    ? "Preferences and feedback sync to the Dawnlit API"
    : "Preferences and feedback stay in this browser";
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
  document.body.classList.toggle("paper-page", state.view !== "preferences");
  elements.nav.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
  if (state.view === "preferences") {
    renderPreferences();
    return;
  }
  const todayPapers = visiblePapers(state.feed.papers);
  const papers =
    state.view === "today"
      ? todayPapers
      : state.view === "weekly"
        ? visiblePapers(state.weekly.papers)
        : allPapers().filter(
            (paper) => state.saved.has(paper.id) && !isDismissed(paper.id),
          );
  renderPaperView(papers);
}

function renderPaperView(papers) {
  const config = {
    today: {
      eyebrow: t("dailySignal"),
      title: t("todaysRadar"),
      subtitle: t("todaySubtitle"),
      date: prettyDate(state.feed.generated_at),
    },
    weekly: {
      eyebrow: t("weeklyDigest"),
      title: t("thisWeek"),
      subtitle: t("weeklySubtitle"),
      date: `${papers.length} ${t("papers")}`,
    },
    saved: {
      eyebrow: t("yourLibrary"),
      title: t("usefulPapers"),
      subtitle: t("librarySubtitle"),
      date: `${papers.length} ${t("usefulUpper")}`,
    },
  }[state.view];

  const topics = new Set(
    papers.map((paper) => paper.topics?.[0]?.name).filter(Boolean),
  );
  const deckIndex = Math.min(
    state.deckIndex[state.view] || 0,
    Math.max(papers.length - 1, 0),
  );
  state.deckIndex[state.view] = deckIndex;
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
        ? `<div class="mobile-deck-controls" data-deck-controls>
            <button type="button" data-deck-action="previous" aria-label="${t("previousPaper")}" ${
              deckIndex === 0 ? "disabled" : ""
            }>←</button>
            <span><strong data-deck-position>${deckIndex + 1} / ${
              papers.length
            }</strong><small>${t("swipeHint")}</small></span>
            <button type="button" data-deck-action="next" aria-label="${t("nextPaper")}" ${
              deckIndex === papers.length - 1 ? "disabled" : ""
            }>→</button>
          </div>
          <div class="paper-list" data-paper-deck>${papers
            .map(paperCard)
            .join("")}</div>`
        : emptyState()
    }
  `;
  if (papers.length) {
    requestAnimationFrame(() => scrollDeckTo(deckIndex, "auto"));
  }
}

function updateDeckPosition(deck, index) {
  const cards = [...deck.querySelectorAll(".paper-card")];
  const safeIndex = Math.max(0, Math.min(index, cards.length - 1));
  state.deckIndex[state.view] = safeIndex;
  const controls = elements.app.querySelector("[data-deck-controls]");
  if (!controls) return;
  controls.querySelector("[data-deck-position]").textContent = `${
    safeIndex + 1
  } / ${cards.length}`;
  controls.querySelector('[data-deck-action="previous"]').disabled =
    safeIndex === 0;
  controls.querySelector('[data-deck-action="next"]').disabled =
    safeIndex === cards.length - 1;
}

function scrollDeckTo(index, behavior = "smooth") {
  const deck = elements.app.querySelector("[data-paper-deck]");
  if (!deck || !window.matchMedia("(max-width: 650px)").matches) return;
  const cards = [...deck.querySelectorAll(".paper-card")];
  const safeIndex = Math.max(0, Math.min(index, cards.length - 1));
  const card = cards[safeIndex];
  if (!card) return;
  const paddingLeft = Number.parseFloat(getComputedStyle(deck).paddingLeft) || 0;
  const left =
    deck.scrollLeft +
    card.getBoundingClientRect().left -
    deck.getBoundingClientRect().left -
    paddingLeft;
  deck.scrollTo({ left, behavior });
  updateDeckPosition(deck, safeIndex);
}

function currentDeckIndex(deck) {
  const paddingLeft = Number.parseFloat(getComputedStyle(deck).paddingLeft) || 0;
  const deckLeft = deck.getBoundingClientRect().left + paddingLeft;
  return [...deck.querySelectorAll(".paper-card")].reduce(
    (best, card, index) => {
      const distance = Math.abs(card.getBoundingClientRect().left - deckLeft);
      return distance < best.distance ? { index, distance } : best;
    },
    { index: 0, distance: Number.POSITIVE_INFINITY },
  ).index;
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
              ? t("abstractExtract")
              : t("aiBrief")
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
        <span>Signals:</span>
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
        }" data-action="useful">
          ${saved ? `◆ ${t("useful")}` : `◇ ${t("useful")}`}
        </button>
        <button class="action-button" data-action="not-useful">${t("notUseful")}</button>
        <button class="action-button" data-action="irrelevant">${t("irrelevant")}</button>
        <button class="action-button deep-dive-button" data-action="deep-dive" ${
          paper.deep_dive ? "" : "disabled"
        } title="${
          paper.deep_dive
            ? "Open the full-text AI analysis"
            : "Deep analysis is unavailable for this paper"
        }">${t("deepDive")}</button>
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
  const analysis = paper.deep_dive;
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
    <div class="three-line-brief" aria-label="${t("threeLineBrief")}">
      ${signals
        .map(
          (signal, index) => `
            <div class="brief-signal">
              <span aria-hidden="true">${briefSignalIcon(
                signal.text || "",
                index,
              )}</span>
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

function briefSignalIcon(text, role) {
  const value = text.toLowerCase();
  const iconFor = (rules, fallback) =>
    rules.find(([needles]) => needles.some((needle) => value.includes(needle)))?.[1] ||
    fallback;
  if (role === 0) {
    return iconFor(
      [
        [["multilingual", "cross-lingual", "language", "arabic", "tokenization", "多语言", "跨语言", "分词", "阿拉伯语"], "🌐"],
        [["agent", "tool use", "workflow", "智能体", "工具调用", "工作流"], "🤖"],
        [["efficient", "cost", "latency", "compute", "效率", "成本", "延迟", "计算"], "⚡"],
        [["safety", "attack", "adversarial", "jailbreak", "robust", "安全", "攻击", "对抗", "越狱", "鲁棒"], "🛡️"],
        [["benchmark", "dataset", "corpus", "基准", "数据集", "语料"], "🗂️"],
        [["interpret", "circuit", "representation", "可解释", "回路", "表征"], "🔎"],
      ],
      "💡",
    );
  }
  if (role === 1) {
    return iconFor(
      [
        [["theorem", "proof", "bound", "equation", "定理", "证明", "界", "方程"], "🧮"],
        [["mechanism", "representation", "latent", "activation", "机制", "表征", "潜在", "激活"], "🔬"],
        [["dataset", "corpus", "curation", "sampling", "数据集", "语料", "采样"], "🗂️"],
        [["retrieval", "search", "index", "检索", "搜索", "索引"], "🔎"],
        [["train", "fine-tun", "pipeline", "framework", "algorithm", "method", "训练", "微调", "流程", "框架", "算法", "方法"], "⚙️"],
      ],
      "🔧",
    );
  }
  return iconFor(
    [
      [["however", "despite", "limit", "caveat", "insufficient", "fail", "remain", "modest", "unimproved", "然而", "尽管", "局限", "不足", "失败", "仍未", "有限"], "⚠️"],
      [["improv", "outperform", "gain", "increase", "restore", "achiev", "提升", "改进", "优于", "增加", "恢复", "达到"], "📈"],
      [["drop", "degrad", "decline", "loss", "worse", "下降", "退化", "损失", "变差"], "📉"],
      [["theorem", "prove", "guarantee", "定理", "证明", "保证"], "✅"],
      [["benchmark", "experiment", "evaluat", "metric", "accuracy", "基准", "实验", "评估", "指标", "准确率"], "📊"],
    ],
    "📊",
  );
}

function detailItems(items = []) {
  if (!Array.isArray(items) || !items.length) {
    return '<p class="deep-dive-missing">Not stated in the available source.</p>';
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
    return '<p class="deep-dive-missing">Not stated in the available source.</p>';
  }
  return `<ul>${items
    .map((item) => `<li>${escapeHTML(item)}</li>`)
    .join("")}</ul>`;
}

function openDeepDive(paper) {
  const analysis = paper.deep_dive;
  if (!analysis) {
    showToast("Deep analysis is unavailable for this paper.");
    return;
  }
  elements.deepDive.innerHTML = `
    <div class="deep-dive-shell">
      <header class="deep-dive-header">
        <div>
          <span class="eyebrow">${t("fullTextAnalysis")}</span>
          <h2 id="deepDiveTitle">${escapeHTML(paper.title)}</h2>
          <p>${escapeHTML((paper.authors || []).join(", "))}</p>
        </div>
        <button type="button" class="dialog-close" data-dialog-close aria-label="Close analysis">×</button>
      </header>
      <div class="deep-dive-content">
        ${threeLineBrief(paper)}
        <section>
          <h3>${t("researchQuestion")}</h3>
          <p>${escapeHTML(
            analysis.overview || "Not stated in the available source.",
          )}</p>
        </section>
        <section>
          <h3>${t("methodPipeline")}</h3>
          ${detailItems(analysis.methodology)}
        </section>
        <section>
          <h3>${t("mechanismTheory")}</h3>
          ${detailItems(analysis.mechanism)}
        </section>
        <section>
          <h3>${t("experimentalDesign")}</h3>
          ${detailItems(analysis.experiments)}
        </section>
        <section>
          <h3>${t("resultsEvidence")}</h3>
          ${detailItems(analysis.findings)}
        </section>
        <div class="deep-dive-columns">
          <section>
            <h3>${t("contributions")}</h3>
            ${textList(analysis.contributions)}
          </section>
          <section>
            <h3>${t("limitationsChecks")}</h3>
            ${textList(analysis.limitations)}
          </section>
        </div>
        <section>
          <h3>${t("openQuestions")}</h3>
          ${textList(analysis.open_questions)}
        </section>
        <footer>
          Generated from
          ${escapeHTML(analysis.source_scope || "the available source")}
          by ${escapeHTML(analysis.generated_by || "an AI model")}.
          ${t("verifyClaims")}
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
      ? t("nothingUseful")
      : t("noSignal");
  return `<div class="empty-state"><h2>${t("quietDay")}</h2><p>${message}</p></div>`;
}

function renderPreferences() {
  const editUrl = interestsEditUrl();
  const hiddenPapers = Object.values(state.dismissed).sort((a, b) =>
    (b.dismissed_at || "").localeCompare(a.dismissed_at || ""),
  );
  elements.app.innerHTML = `
    <section class="view-header">
      <div>
        <span class="eyebrow">${t("controlRoom")}</span>
        <h1>${t("preferences")}</h1>
        <p>${t("preferenceIntro")}</p>
      </div>
      <span class="date-stamp">${
        state.apiUrl && state.token ? t("cloudSync") : t("localMode")
      }</span>
    </section>
    <div class="preference-layout">
      <section class="panel settings-panel">
        <div class="panel-heading">
          <div>
            <h2>${t("appearanceLanguage")}</h2>
            <p>${t("appearanceHint")}</p>
          </div>
        </div>
        <div class="display-settings">
          <div class="setting-row">
            <span>${t("theme")}</span>
            <div class="segmented-control" aria-label="${t("theme")}">
              ${[
                ["system", t("system")],
                ["light", t("light")],
                ["dark", t("dark")],
              ]
                .map(
                  ([value, label]) =>
                    `<button type="button" data-pref-action="set-theme" data-theme-value="${value}" class="${
                      state.theme === value ? "active" : ""
                    }">${label}</button>`,
                )
                .join("")}
            </div>
          </div>
          <div class="setting-row">
            <span>${t("language")}</span>
            <div class="segmented-control" aria-label="${t("language")}">
              ${[
                ["en", t("english")],
                ["zh", t("chinese")],
              ]
                .map(
                  ([value, label]) =>
                    `<button type="button" data-pref-action="set-ui-language" data-language-value="${value}" class="${
                      state.language === value ? "active" : ""
                    }">${label}</button>`,
                )
                .join("")}
            </div>
          </div>
          <div class="setting-row">
            <span>${t("contentLanguage")}</span>
            <div class="segmented-control" aria-label="${t("contentLanguage")}">
              ${[
                ["en", t("english")],
                ["zh", t("chinese")],
              ]
                .map(
                  ([value, label]) =>
                    `<button type="button" data-pref-action="set-content-language" data-language-value="${value}" class="${
                      state.contentLanguage === value ? "active" : ""
                    }">${label}</button>`,
                )
                .join("")}
            </div>
          </div>
        </div>
        <p class="settings-note">${t("languageRefreshHint")}</p>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>${t("quickAdjustment")}</h2>
            <p>${t("quickHint")}</p>
          </div>
        </div>
        <div class="command-box">
          <input id="preferenceCommand" type="text" placeholder="More data selection, less OPD…" />
          <button class="secondary-button" data-pref-action="apply-command">${t("apply")}</button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>${t("topicLanes")}</h2>
            <p>${t("topicHint")}</p>
          </div>
          <button class="primary-button" data-pref-action="save-profile">${t("saveChanges")}</button>
        </div>
        <div class="topic-editor-list">
          ${state.profile.topics.map(topicEditor).join("")}
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>${t("addDirection")}</h2>
            <p>${t("addDirectionHint")}</p>
          </div>
        </div>
        <div class="add-topic-grid">
          <input id="newTopicName" type="text" placeholder="${t("topicName")}" />
          <textarea id="newTopicDescription" placeholder="${t("topicDescription")}"></textarea>
          <button class="secondary-button" data-pref-action="add-topic">${t("addTopic")}</button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>${t("archive")}</h2>
            <p>${t("archiveHint", { days: String(ARCHIVE_DAYS) })}</p>
          </div>
          ${
            hiddenPapers.length
              ? `<button class="secondary-button" data-pref-action="restore-all-papers">${t("restoreAll")}</button>`
              : ""
          }
        </div>
        <div class="hidden-paper-list">
          ${
            hiddenPapers.length
              ? hiddenPapers
                  .map(
                    (paper) => `
                      <div class="hidden-paper-row">
                        <div>
                          <strong>${escapeHTML(paper.title)}</strong>
                          <span>${
                            paper.expires_at
                              ? `Archived until ${prettyDate(paper.expires_at)}`
                              : "Archived"
                          }</span>
                        </div>
                        <button class="secondary-button" data-pref-action="restore-paper" data-paper-id="${escapeHTML(
                          paper.paper_id,
                        )}">${t("restore")}</button>
                      </div>
                    `,
                  )
                  .join("")
              : `<p>${t("noArchived")}</p>`
          }
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>${t("dataOwnership")}</h2>
            <p>${t("dataOwnershipHint")}</p>
          </div>
        </div>
        <div class="preference-actions">
          ${
            editUrl
              ? `<a class="secondary-button" href="${escapeHTML(
                  editUrl,
                )}" target="_blank" rel="noreferrer">${t("editInterests")}</a>`
              : ""
          }
          <button class="secondary-button" data-pref-action="export-profile">${t("exportProfile")}</button>
          <button class="secondary-button" data-pref-action="import-profile">${t("importProfile")}</button>
          <button class="secondary-button" data-pref-action="export-feedback">${t("exportFeedback")}</button>
          <button class="danger-button" data-pref-action="clear-feedback">${t("clearFeedback")}</button>
        </div>
        ${
          state.apiUrl
            ? `<div class="auth-row">
                <input id="apiToken" type="password" placeholder="Personal API token (stored on this device)" value="${escapeHTML(
                  state.token,
                )}" />
                <button class="secondary-button" data-pref-action="connect-api">${t("saveSync")}</button>
                ${
                  state.token
                    ? `<button class="danger-button" data-pref-action="disconnect-api">${t("forgetToken")}</button>`
                    : ""
                }
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
  return allPapers().find((paper) => paper.id === id);
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
  if (action === "not_useful" || action === "irrelevant") {
    state.saved.delete(paper.id);
    writeStorage(STORAGE.saved, [...state.saved]);
    dismissPaper(paper, action);
  }
  if (state.apiUrl && state.token) {
    try {
      await sendFeedbackItem(item);
      item.synced_at = new Date().toISOString();
      state.cloudConnected = true;
      writeStorage(STORAGE.feedback, state.feedback);
    } catch (error) {
      showToast(
        `Feedback was saved locally; cloud sync failed: ${error.message}`,
      );
      return;
    }
  }
  showToast(feedbackMessage(action));
}

async function sendFeedbackItem(item) {
  return fetchJSON(`${state.apiUrl}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(item),
  });
}

async function syncPendingFeedback({ notify = false } = {}) {
  if (!state.apiUrl || !state.token) return 0;
  const pending = state.feedback.filter((item) => !item.synced_at);
  let synced = 0;
  for (const item of pending) {
    try {
      await sendFeedbackItem(item);
      item.synced_at = new Date().toISOString();
      state.cloudConnected = true;
      synced += 1;
    } catch {
      break;
    }
  }
  if (synced) {
    writeStorage(STORAGE.feedback, state.feedback);
    if (notify) {
      showToast(
        `Synced ${synced} pending feedback item${synced === 1 ? "" : "s"}.`,
      );
    }
  }
  return synced;
}

async function pullCloudFeedback() {
  if (!state.apiUrl || !state.token) return 0;
  try {
    const result = await fetchJSON(`${state.apiUrl}/api/feedback?limit=1000`);
    const remoteItems = Array.isArray(result.items) ? result.items : [];
    const merged = new Map(state.feedback.map((item) => [item.id, item]));
    remoteItems.forEach((item) => {
      merged.set(item.id, {
        ...merged.get(item.id),
        ...item,
        synced_at: merged.get(item.id)?.synced_at || item.created_at,
      });
    });
    state.feedback = [...merged.values()].sort((a, b) =>
      (a.created_at || "").localeCompare(b.created_at || ""),
    );

    const latestByPaper = new Map();
    [...state.feedback]
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))
      .forEach((item) => {
        if (item.paper_id && !latestByPaper.has(item.paper_id)) {
          latestByPaper.set(item.paper_id, item);
        }
      });
    latestByPaper.forEach((item, paperId) => {
      if (["save", "useful"].includes(item.action)) {
        state.saved.add(paperId);
        delete state.dismissed[paperId];
      } else if (["unsave", "restore"].includes(item.action)) {
        state.saved.delete(paperId);
        delete state.dismissed[paperId];
      } else if (["not_useful", "irrelevant", "not_llm"].includes(item.action)) {
        state.saved.delete(paperId);
        const dismissedAt = new Date(item.created_at || Date.now());
        const expiresAt = new Date(
          dismissedAt.getTime() + ARCHIVE_DAYS * 86400000,
        );
        if (expiresAt.getTime() > Date.now()) {
          state.dismissed[paperId] = {
            paper_id: paperId,
            title: item.title || paperId,
            action: item.action,
            dismissed_at: dismissedAt.toISOString(),
            expires_at: expiresAt.toISOString(),
          };
        } else {
          delete state.dismissed[paperId];
        }
      }
    });
    writeStorage(STORAGE.feedback, state.feedback);
    writeStorage(STORAGE.saved, [...state.saved]);
    writeStorage(STORAGE.dismissed, state.dismissed);
    state.cloudConnected = true;
    return remoteItems.length;
  } catch (error) {
    state.cloudConnected = false;
    console.warn("Cloud feedback unavailable:", error);
    return 0;
  }
}

function feedbackMessage(action) {
  return (
    {
      useful: "Marked useful and saved.",
      unsave: "Removed from useful papers.",
      not_useful: `Archived for ${ARCHIVE_DAYS} days and recorded as a weak signal.`,
      irrelevant: `Archived for ${ARCHIVE_DAYS} days and recorded as irrelevant.`,
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

elements.app.addEventListener("click", async (event) => {
  const deckButton = event.target.closest("[data-deck-action]");
  const actionButton = event.target.closest("[data-action]");
  const preferenceButton = event.target.closest("[data-pref-action]");

  if (deckButton) {
    const direction = deckButton.dataset.deckAction === "next" ? 1 : -1;
    scrollDeckTo((state.deckIndex[state.view] || 0) + direction);
    return;
  }

  if (actionButton) {
    const card = actionButton.closest(".paper-card");
    const paper = paperById(card.dataset.paperId);
    const action = actionButton.dataset.action;
    if (action === "deep-dive") {
      openDeepDive(paper);
    } else if (action === "useful") {
      if (state.saved.has(paper.id)) {
        state.saved.delete(paper.id);
        await recordFeedback(paper, "unsave");
      } else {
        state.saved.add(paper.id);
        await recordFeedback(paper, "useful");
      }
      writeStorage(STORAGE.saved, [...state.saved]);
      updateChrome();
      render();
    } else if (action === "not-useful" || action === "irrelevant") {
      await recordFeedback(
        paper,
        action === "not-useful" ? "not_useful" : "irrelevant",
      );
      updateChrome();
      render();
    }
    return;
  }

  if (!preferenceButton) return;
  const action = preferenceButton.dataset.prefAction;
  try {
    if (action === "set-theme") {
      applyTheme(preferenceButton.dataset.themeValue, true);
      renderPreferences();
    }
    if (action === "set-ui-language") {
      syncEditorsToProfile();
      state.language = preferenceButton.dataset.languageValue === "zh" ? "zh" : "en";
      state.profile.ui_language = state.language;
      state.profile.updated_at = new Date().toISOString().slice(0, 10);
      writeStorage(STORAGE.profile, state.profile);
      if (state.apiUrl && state.token) {
        await fetchJSON(`${state.apiUrl}/api/profile`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state.profile),
        });
      }
      applyLanguage();
      updateChrome();
      renderPreferences();
      showToast(
        t("settingsSaved", {
          language: state.language === "zh" ? "中文" : "English",
        }),
      );
    }
    if (action === "set-content-language") {
      syncEditorsToProfile();
      state.contentLanguage =
        preferenceButton.dataset.languageValue === "en" ? "en" : "zh";
      state.profile.content_language = state.contentLanguage;
      state.profile.updated_at = new Date().toISOString().slice(0, 10);
      writeStorage(STORAGE.profile, state.profile);
      if (state.apiUrl && state.token) {
        await fetchJSON(`${state.apiUrl}/api/profile`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state.profile),
        });
      }
      renderPreferences();
      showToast(
        t("contentSettingsSaved", {
          language: state.contentLanguage === "zh" ? "中文" : "English",
        }),
      );
    }
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
    if (action === "restore-paper") {
      const paperId = preferenceButton.dataset.paperId;
      const paper = paperById(paperId) || state.dismissed[paperId];
      delete state.dismissed[paperId];
      writeStorage(STORAGE.dismissed, state.dismissed);
      if (paper?.id || paper?.paper_id) {
        await recordFeedback(
          paper.id ? paper : { ...paper, id: paper.paper_id, abstract: "", topics: [] },
          "restore",
        );
      }
      updateChrome();
      renderPreferences();
      showToast("Paper restored.");
    }
    if (action === "restore-all-papers") {
      const restored = Object.values(state.dismissed);
      state.dismissed = {};
      writeStorage(STORAGE.dismissed, {});
      for (const paper of restored) {
        await recordFeedback(
          { ...paper, id: paper.paper_id, abstract: "", topics: [] },
          "restore",
        );
      }
      updateChrome();
      renderPreferences();
      showToast("All hidden papers restored.");
    }
    if (action === "connect-api") {
      state.token = document.querySelector("#apiToken").value.trim();
      writeTextStorage(STORAGE.token, state.token);
      try {
        state.profile = await fetchJSON(`${state.apiUrl}/api/profile`);
      } catch (error) {
        state.token = "";
        writeTextStorage(STORAGE.token, "");
        throw error;
      }
      writeStorage(STORAGE.profile, state.profile);
      const synced = await syncPendingFeedback();
      await pullCloudFeedback();
      updateChrome();
      renderPreferences();
      showToast(
        synced
          ? `Connected and synced ${synced} feedback item${synced === 1 ? "" : "s"}.`
          : "Connected to the Dawnlit API.",
      );
    }
    if (action === "disconnect-api") {
      state.token = "";
      state.cloudConnected = false;
      writeTextStorage(STORAGE.token, "");
      updateChrome();
      renderPreferences();
      showToast("API token removed from this device.");
    }
  } catch (error) {
    showToast(`Action failed: ${error.message}`);
  }
});

elements.app.addEventListener(
  "scroll",
  (event) => {
    const deck = event.target.closest?.("[data-paper-deck]");
    if (!deck) return;
    clearTimeout(deck.positionTimer);
    deck.positionTimer = setTimeout(() => {
      updateDeckPosition(deck, currentDeckIndex(deck));
    }, 80);
  },
  true,
);

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

elements.deepDive.addEventListener("click", (event) => {
  if (
    event.target.closest("[data-dialog-close]") ||
    event.target === elements.deepDive
  ) {
    elements.deepDive.close();
  }
});

elements.installButton.addEventListener("click", installApp);

elements.installDialog.addEventListener("click", (event) => {
  if (
    event.target.closest("[data-install-close]") ||
    event.target === elements.installDialog
  ) {
    elements.installDialog.close();
  }
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  state.installPrompt = event;
});

window.addEventListener("appinstalled", () => {
  state.installPrompt = null;
  elements.installButton.classList.add("hidden");
  showToast("Dawnlit is ready on your Home Screen.");
});

window.addEventListener("online", () => {
  syncPendingFeedback({ notify: true });
});

window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", () => {
    if (state.theme === "system") applyTheme("system");
  });

document.addEventListener("visibilitychange", () => {
  const staleFor = Date.now() - state.lastRefreshAt;
  if (document.visibilityState === "visible" && staleFor > 5 * 60 * 1000) {
    boot();
  }
});

if (isStandaloneApp()) elements.installButton.classList.add("hidden");

registerServiceWorker();
boot();
