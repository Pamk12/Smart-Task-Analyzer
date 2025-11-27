const API_BASE = "http://127.0.0.1:8000/api/tasks";

const el = (id) => document.getElementById(id);

let tasks = [];
let lastResults = [];
let lastWarnings = [];
let lastCycles = [];
let selectedStrategy = "smart_balance";
let expanded = true;

const STRATEGY_LABEL = {
  fastest_wins: "Fastest Wins",
  high_impact: "High Impact",
  deadline_driven: "Deadline Driven",
  smart_balance: "Smart Balance",
};

const SORT_LABEL = {
  score_desc: "Score (high → low)",
  due_asc: "Due date (soonest)",
  impact_desc: "Importance (high → low)",
  hours_asc: "Hours (smallest)",
};

function toast(msg) {
  const t = el("toast");
  el("toastText").textContent = msg;
  t.hidden = false;
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => (t.hidden = true), 1700);
}

function setAlert(id, text, show) {
  const box = el(id);
  if (!show) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  box.hidden = false;
  box.textContent = text;
}

function parseDeps(raw) {
  const s = String(raw || "").trim();
  if (!s) return [];
  return s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean)
    .map((x) => Number(x))
    .filter((n) => Number.isFinite(n));
}

function renderCurrent() {
  el("current").textContent = JSON.stringify(tasks, null, 2);
}

function tier(score) {
  const s = Number(score || 0);
  if (s >= 75) return "high";
  if (s >= 50) return "mid";
  return "low";
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function shortExplain(s) {
  const v = String(s).replace(/\s+/g, " ").trim();
  return v.length > 110 ? v.slice(0, 110) + "…" : v;
}

function sortResults(list) {
  const mode = el("sort").value;
  const copy = [...list];

  if (mode === "score_desc") {
    copy.sort((a, b) => Number(b.score || 0) - Number(a.score || 0));
  } else if (mode === "due_asc") {
    copy.sort((a, b) =>
      String(a.due_date || "9999-12-31").localeCompare(String(b.due_date || "9999-12-31"))
    );
  } else if (mode === "impact_desc") {
    copy.sort((a, b) => Number(b.importance || 0) - Number(a.importance || 0));
  } else if (mode === "hours_asc") {
    copy.sort((a, b) => Number(a.estimated_hours ?? 1e9) - Number(b.estimated_hours ?? 1e9));
  }

  return copy;
}

function filterResults(list) {
  const q = String(el("search").value || "").trim().toLowerCase();
  if (!q) return list;
  return list.filter(
    (t) =>
      String(t.title || "").toLowerCase().includes(q) ||
      String(t.id || "").includes(q)
  );
}

function updateStats() {
  el("statTotal").textContent = String(lastResults.length);
  el("statHigh").textContent = String(lastResults.filter((t) => Number(t.score || 0) >= 75).length);
  el("statCycles").textContent = String((lastCycles || []).length);
  el("statWarnings").textContent = String((lastWarnings || []).length);
}

function renderFocus(top3) {
  const root = el("focus");
  root.innerHTML = "";
  if (!top3 || top3.length === 0) {
    root.innerHTML = `<div class="muted small">No data yet.</div>`;
    return;
  }

  top3.forEach((t, idx) => {
    const d = document.createElement("div");
    d.className = "focus__card";
    d.innerHTML = `
      <div class="muted small">#${idx + 1}</div>
      <h4 class="focus__title">${escapeHtml(t.title || "Untitled")}</h4>
      <div class="focus__score">${Number(t.score ?? 0).toFixed(2)}</div>
      <div class="focus__hint">${escapeHtml(shortExplain(t.explanation || ""))}</div>
    `;
    root.appendChild(d);
  });
}

function renderResults() {
  const root = el("results");
  root.innerHTML = "";

  if (!lastResults || lastResults.length === 0) {
    updateStats();
    renderFocus([]);
    return;
  }

  updateStats();

  const list = sortResults(filterResults(lastResults));

  list.forEach((t) => {
    const level = tier(t.score);
    const badgeClass = level === "high" ? "badge--high" : level === "mid" ? "badge--mid" : "badge--low";

    const deps = (t.dependencies || []).join(", ") || "-";
    const due = t.due_date || "N/A";
    const hours = t.estimated_hours ?? "N/A";
    const imp = t.importance ?? "N/A";
    const score = Number(t.score ?? 0);
    const barWidth = Math.max(0, Math.min(100, score));

    const card = document.createElement("div");
    card.className = `task task--${level}`;
    card.innerHTML = `
      <div class="task__top">
        <div>
          <h4 class="task__title">${escapeHtml(t.title || "Untitled")}</h4>
          <div class="task__meta">
            <span>📅 Due: <b>${escapeHtml(due)}</b></span>
            <span>⏱ Hours: <b>${escapeHtml(hours)}</b></span>
            <span>⭐ Importance: <b>${escapeHtml(imp)}</b></span>
            <span>🔗 Deps: <b>${escapeHtml(deps)}</b></span>
          </div>
        </div>

        <div class="badges">
          <span class="badge ${badgeClass}">${level.toUpperCase()}</span>
          <span class="badge badge--score">Score: ${score.toFixed(2)}</span>
          <button class="btn btn--ghost btn--sm js-toggle" type="button">Details</button>
        </div>
      </div>

      <div class="bar" aria-label="score bar"><div style="width:${barWidth}%"></div></div>

      <div class="task__details" ${expanded ? "" : "hidden"}>
        <div class="mutedline">ID: ${escapeHtml(t.id)} • Explanation</div>
        <div class="explain">${escapeHtml(t.explanation || "No explanation")}</div>
      </div>
    `;

    card.querySelector(".js-toggle").addEventListener("click", () => {
      const details = card.querySelector(".task__details");
      details.hidden = !details.hidden;
    });

    root.appendChild(card);
  });

  renderFocus(lastResults.slice(0, 3));
}

function setSortValue(value) {
  const v = String(value || "score_desc");
  const sel = el("sort");
  if (sel && sel.value !== v) sel.value = v;

  const label = el("sortDDLabel");
  const menu = el("sortDDMenu");
  const dd = el("sortDD");
  const btn = el("sortDDBtn");

  if (label) label.textContent = SORT_LABEL[v] || v;
  if (menu) {
    menu.querySelectorAll(".dd__item").forEach((it) => {
      it.classList.toggle("is-selected", it.dataset.value === v);
    });
  }
  if (dd) dd.classList.remove("is-open");
  if (btn) btn.setAttribute("aria-expanded", "false");

  renderResults();
}

function setStrategy(strategy) {
  selectedStrategy = String(strategy || "smart_balance").trim();
  el("strategyBadge").textContent = `Strategy: ${selectedStrategy}`;

  document.querySelectorAll(".segmented__btn").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.strategy === selectedStrategy);
  });

  const label = el("strategyDDLabel");
  const dd = el("strategyDD");
  const menu = el("strategyDDMenu");
  const btn = el("strategyDDBtn");

  if (label) label.textContent = STRATEGY_LABEL[selectedStrategy] || selectedStrategy;
  if (menu) {
    menu.querySelectorAll(".dd__item").forEach((it) => {
      it.classList.toggle("is-selected", it.dataset.value === selectedStrategy);
    });
  }
  if (dd) dd.classList.remove("is-open");
  if (btn) btn.setAttribute("aria-expanded", "false");
}

async function checkBackend() {
  const status = el("backendStatus");
  const dot = status.querySelector(".dot");
  const text = status.querySelector("span:last-child");

  dot.className = "dot dot--idle";
  text.textContent = "Backend: checking…";

  try {
    await fetch(`${API_BASE}/suggest/`, { method: "GET" });
    dot.className = "dot dot--ok";
    text.textContent = "Backend: reachable";
  } catch {
    dot.className = "dot dot--bad";
    text.textContent = "Backend: not reachable";
  }
}

function wireDropdown(ddId, btnId, menuId, onPick) {
  const dd = el(ddId);
  const btn = el(btnId);
  const menu = el(menuId);
  if (!dd || !btn || !menu) return;

  const open = () => {
    dd.classList.add("is-open");
    btn.setAttribute("aria-expanded", "true");
  };
  const close = () => {
    dd.classList.remove("is-open");
    btn.setAttribute("aria-expanded", "false");
  };

  btn.addEventListener("click", () => {
    dd.classList.contains("is-open") ? close() : open();
  });

  menu.querySelectorAll(".dd__item").forEach((item) => {
    item.addEventListener("click", () => {
      onPick(item.dataset.value);
      close();
    });
  });

  document.addEventListener("click", (e) => {
    if (!dd.contains(e.target)) close();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
}

el("copyApiBtn").addEventListener("click", async () => {
  const url = `${API_BASE}/analyze/?strategy=${encodeURIComponent(selectedStrategy)}`;
  try {
    await navigator.clipboard.writeText(url);
    toast("API URL copied");
  } catch {
    toast("Could not copy");
  }
});

document.querySelectorAll(".segmented__btn").forEach((btn) => {
  btn.addEventListener("click", () => setStrategy(btn.dataset.strategy));
});

el("fillDemoBtn").addEventListener("click", () => {
  const demo = [
    { "id": 1, "title": "Fix login bug", "due_date": "2025-11-30", "estimated_hours": 3, "importance": 8, "dependencies": [] },
    { "id": 2, "title": "Write report", "due_date": "2025-11-27", "estimated_hours": 2, "importance": 6, "dependencies": [1] },
    { "id": 6, "title": "Ship onboarding flow", "due_date": "2025-11-28", "estimated_hours": 6, "importance": 9, "dependencies": [] },
    { "id": 7, "title": "Analytics tracking", "due_date": "2025-12-02", "estimated_hours": 4, "importance": 7, "dependencies": [6] }
  ];
  el("bulk").value = JSON.stringify(demo, null, 2);
  toast("Demo JSON added");
});

el("addBtn").addEventListener("click", () => {
  setAlert("errBox", "", false);
  setAlert("warnBox", "", false);
  setAlert("infoBox", "", false);

  const t = {
    id: Number(el("id").value || (tasks.length + 1)),
    title: String(el("title").value || "").trim(),
    due_date: el("due_date").value,
    estimated_hours: el("estimated_hours").value === "" ? null : Number(el("estimated_hours").value),
    importance: el("importance").value === "" ? null : Number(el("importance").value),
    dependencies: parseDeps(el("dependencies").value),
  };

  if (!t.title) return setAlert("errBox", "Title is required.", true);
  if (!t.due_date) return setAlert("errBox", "Due date is required.", true);
  if (t.importance !== null && (!Number.isFinite(t.importance) || t.importance < 1 || t.importance > 10))
    return setAlert("errBox", "Importance must be between 1 and 10.", true);
  if (t.estimated_hours !== null && (!Number.isFinite(t.estimated_hours) || t.estimated_hours < 0))
    return setAlert("errBox", "Estimated hours must be a non-negative number.", true);

  tasks.push(t);
  renderCurrent();
  toast("Task added");
});

el("clearListBtn").addEventListener("click", () => {
  tasks = [];
  renderCurrent();
  toast("List cleared");
});

el("exportListBtn").addEventListener("click", async () => {
  const data = JSON.stringify(tasks, null, 2);
  try {
    await navigator.clipboard.writeText(data);
    toast("List JSON copied");
  } catch {
    toast("Could not copy");
  }
});

el("validateJsonBtn").addEventListener("click", () => {
  setAlert("errBox", "", false);
  try {
    const parsed = JSON.parse(el("bulk").value || "[]");
    if (!Array.isArray(parsed)) throw new Error("JSON must be an array.");
    toast("JSON valid ✅");
  } catch (e) {
    setAlert("errBox", `Invalid JSON: ${e.message}`, true);
  }
});

el("clearJsonBtn").addEventListener("click", () => {
  el("bulk").value = "";
  toast("JSON cleared");
});

el("collapseBtn").addEventListener("click", () => {
  expanded = false;
  document.querySelectorAll(".task__details").forEach((x) => (x.hidden = true));
  toast("Collapsed");
});

el("expandBtn").addEventListener("click", () => {
  expanded = true;
  document.querySelectorAll(".task__details").forEach((x) => (x.hidden = false));
  toast("Expanded");
});

el("search").addEventListener("input", renderResults);

el("sort").addEventListener("change", () => {
  setSortValue(el("sort").value);
});

el("analyzeBtn").addEventListener("click", analyze);

async function analyze() {
  setAlert("errBox", "", false);
  setAlert("warnBox", "", false);
  setAlert("infoBox", "", false);

  let bulk = [];
  const bulkText = String(el("bulk").value || "").trim();
  if (bulkText) {
    try {
      bulk = JSON.parse(bulkText);
      if (!Array.isArray(bulk)) throw new Error("Bulk JSON must be an array.");
    } catch (e) {
      return setAlert("errBox", `Bulk JSON invalid: ${e.message}`, true);
    }
  }

  const payload = [...tasks, ...bulk];
  if (payload.length === 0) return setAlert("errBox", "Add at least one task (manual or JSON).", true);

  const btn = el("analyzeBtn");
  const oldText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Analyzing & Scoring…";

  const url = `${API_BASE}/analyze/?strategy=${encodeURIComponent(selectedStrategy)}`;

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || `API error: ${res.status}`);

    const strategyUsed = (data.strategy_used || data.selected_strategy || selectedStrategy);
    setStrategy(strategyUsed);

    lastResults = Array.isArray(data.tasks) ? data.tasks : [];
    lastWarnings = Array.isArray(data.warnings) ? data.warnings : [];
    lastCycles = Array.isArray(data.cycles) ? data.cycles : [];

    if (lastWarnings.length) setAlert("warnBox", `Warnings:\n- ${lastWarnings.join("\n- ")}`, true);
    if (lastCycles.length) setAlert("infoBox", `Circular dependencies detected:\n${JSON.stringify(lastCycles, null, 2)}`, true);

    renderResults();
    toast("Analysis complete ✅");
  } catch (e) {
    setAlert("errBox", String(e.message || e), true);
  } finally {
    btn.disabled = false;
    btn.textContent = oldText;
  }
}

el("suggestBtn").addEventListener("click", async () => {
  setAlert("errBox", "", false);
  try {
    const res = await fetch(`${API_BASE}/suggest/`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || `API error: ${res.status}`);
    renderFocus(Array.isArray(data.tasks) ? data.tasks : []);
    toast("Top 3 loaded");
  } catch (e) {
    setAlert("errBox", String(e.message || e), true);
  }
});

wireDropdown("strategyDD", "strategyDDBtn", "strategyDDMenu", setStrategy);
wireDropdown("sortDD", "sortDDBtn", "sortDDMenu", setSortValue);

setStrategy("smart_balance");
setSortValue(el("sort").value || "score_desc");
renderCurrent();
renderResults();
checkBackend();
