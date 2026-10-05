/* PRALAYX Master Application JavaScript -- Pure Frontend Consumer of Existing Platform APIs */

const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));

function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return hash;
}

async function api(path, opt = {}) {
  const r = await fetch(path, {
    ...opt,
    headers: {
      "Content-Type": "application/json",
      ...(opt.headers || {})
    }
  });

  let d = {};
  try {
    d = await r.json();
  } catch {}

  if (!r.ok) {
    const detail = d?.detail;
    if (Array.isArray(detail)) {
      const message = detail.map(x => (typeof x === "string" ? x : x?.msg || JSON.stringify(x))).join("; ");
      throw Error(message || `HTTP ${r.status}`);
    }
    if (detail && typeof detail === "object") {
      throw Error(detail.msg || JSON.stringify(detail));
    }
    throw Error(String(detail || `HTTP ${r.status}`));
  }

  return d;
}

function typeBadgeClass(type) {
  const t = String(type || "").toLowerCase();
  if (t === "handle" || t === "username" || t === "actor") return "blue";
  if (t.includes("crypto") || t.includes("btc") || t.includes("xmr") || t.includes("wallet")) return "amber";
  if (t === "email") return "purple";
  if (t.includes("tls") || t.includes("server") || t.includes("banner") || t.includes("ip") || t.includes("port")) return "red";
  return "green";
}

function renderStatus(v) {
  const s = String(v || "UNKNOWN").toUpperCase();
  const cls = ["ACTIVE", "RUNNING", "CONFIRMED", "COMPLETED"].includes(s) ? "green" : (["HIGH", "CRITICAL", "PAUSED", "ERROR", "FAILED"].includes(s) ? "red" : "amber");
  return `<span class="badge ${cls}">${esc(s)}</span>`;
}

// ------------------------------------------------------------------
// GLOBAL NAVIGATION & APPLICATION SHELL (Streamlined)
// ------------------------------------------------------------------

const NAV = `
<div class="brand">
  <div class="logo-mark">◒</div>
  <div class="logo-info">
    <div class="logo-name">PRALAY<em>X</em></div>
    <span class="logo-sub">Threat Intelligence</span>
  </div>
</div>
<div class="sidebar-status">
  <span class="status-dot"></span>
  <span>Platform Online</span>
</div>
<nav class="nav">
  <div class="nav-title">OPERATIONS</div>
  <a data-page="dashboard" href="/web/index.html">
    <div class="nav-item-left"><span class="nav-ico">⌂</span><span class="nav-label">Dashboard</span></div>
  </a>
  <a data-page="investigations" href="/web/investigations.html">
    <div class="nav-item-left"><span class="nav-ico">📋</span><span class="nav-label">Investigations</span></div>
  </a>
  <a data-page="crawl" href="/web/crawl.html">
    <div class="nav-item-left"><span class="nav-ico">＋</span><span class="nav-label">Dark Web Crawler</span></div>
  </a>
  <a data-page="monitoring" href="/web/monitoring.html">
    <div class="nav-item-left"><span class="nav-ico">◉</span><span class="nav-label">Monitoring & Alerts</span></div>
  </a>

  <div class="nav-title">INTELLIGENCE</div>
  <a data-page="correlation" href="/web/correlation.html">
    <div class="nav-item-left"><span class="nav-ico">⌘</span><span class="nav-label">Attribution Graph</span></div>
  </a>
  <a data-page="osint" href="/web/osint.html">
    <div class="nav-item-left"><span class="nav-ico">◎</span><span class="nav-label">OSINT Engine</span></div>
  </a>
  <a data-page="actors" href="/web/actors.html">
    <div class="nav-item-left"><span class="nav-ico">👤</span><span class="nav-label">Threat Actors</span></div>
  </a>
  <a data-page="stylometry" href="/web/stylometry.html">
    <div class="nav-item-left"><span class="nav-ico">⌁</span><span class="nav-label">Persona Profiler</span></div>
    <span class="nav-badge">NLP</span>
  </a>

  <div class="nav-title">EVIDENCE & DOSSIERS</div>
  <a data-page="findings" href="/web/findings.html">
    <div class="nav-item-left"><span class="nav-ico">🔐</span><span class="nav-label">Evidence Vault</span></div>
  </a>
  <a data-page="reports" href="/web/reports.html">
    <div class="nav-item-left"><span class="nav-ico">▤</span><span class="nav-label">Reports & Dossiers</span></div>
  </a>
  <a data-page="settings" href="/web/settings.html">
    <div class="nav-item-left"><span class="nav-ico">⚙</span><span class="nav-label">System Settings</span></div>
  </a>
</nav>
<div class="sidebar-foot">
  <button id="btn-toggle-sidebar" type="button" class="btn ghost sm" style="width:100%">◀ Collapse Sidebar</button>
</div>`;

function initShell() {
  const s = document.querySelector(".sidebar");
  if (s) s.innerHTML = NAV;

  const savedTheme = localStorage.getItem("pralayx-theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);

  const sidebarEl = document.querySelector(".sidebar");
  const toggleBtn = document.querySelector("#btn-toggle-sidebar");
  if (sidebarEl && toggleBtn) {
    toggleBtn.onclick = () => {
      sidebarEl.classList.toggle("collapsed");
      const isCollapsed = sidebarEl.classList.contains("collapsed");
      toggleBtn.innerHTML = isCollapsed ? "▶" : "◀ Collapse Sidebar";
    };
  }

  const p = location.pathname;
  const currentId = new URLSearchParams(location.search).get("id") || "";

  document.querySelectorAll("[data-page]").forEach(a => {
    const k = a.dataset.page;
    if ((k === "dashboard" && p.endsWith("index.html")) || (k !== "dashboard" && p.includes(k))) {
      a.classList.add("active");
    }
    const baseHref = (a.getAttribute("href") || "").split('?')[0];
    if (currentId && baseHref && ["investigation", "investigations", "correlation", "osint", "analysis", "reports", "findings", "stylometry", "infrastructure", "crawl", "monitoring", "actors"].includes(k)) {
      a.setAttribute("href", `${baseHref}?id=${encodeURIComponent(currentId)}`);
    }
  });

  renderContextBar(currentId);
}

async function renderContextBar(invId) {
  const holder = document.querySelector("#investigation-context-root");
  if (!holder || !invId) return;
  holder.innerHTML = `<div class="investigation-context-bar"><div class="context-info"><div class="skeleton skeleton-line" style="width:300px;height:12px"></div></div></div>`;
  let target = "—", status = "UNKNOWN", lastActivity = "—";
  try {
    const data = await api("/api/investigations");
    const list = (data.investigations || (Array.isArray(data) ? data : [])) || [];
    const inv = list.find(i => (i.investigation_id || i.id) === invId);
    if (inv) {
      target = inv.target || "—";
      status = inv.status || "UNKNOWN";
      lastActivity = (inv.updated_at || inv.created_at || "—").slice(0, 16).replace("T", " ");
    }
  } catch(e) { /* non-critical */ }

  holder.innerHTML = `
    <div class="investigation-context-bar">
      <div class="context-info">
        <div class="context-item">
          <span class="context-label">INVESTIGATION</span>
          <span class="context-val" style="color:var(--blue)">${esc(invId)}</span>
        </div>
        <div class="context-item">
          <span class="context-label">TARGET</span>
          <span class="context-val">${esc(target)}</span>
        </div>
        <div class="context-item">
          <span class="context-label">STATUS</span>
          ${renderStatus(status)}
        </div>
        <div class="context-item">
          <span class="context-label">LAST ACTIVITY</span>
          <span class="context-val" style="color:var(--text-muted)">${esc(lastActivity)}</span>
        </div>
      </div>
      <div class="context-actions">
        <a href="/web/crawl.html?id=${encodeURIComponent(invId)}" class="btn ghost sm">+ Crawl</a>
        <a href="/web/investigation.html?id=${encodeURIComponent(invId)}&tab=osint" class="btn ghost sm" id="ctx-osint-btn">◎ OSINT</a>
        <a href="/web/stylometry.html?id=${encodeURIComponent(invId)}" class="btn ghost sm">⇁ Compare</a>
        <a href="/web/correlation.html?id=${encodeURIComponent(invId)}" class="btn primary sm">⌘ Graph</a>
      </div>
    </div>`;

  const ctxOsintBtn = document.getElementById("ctx-osint-btn");
  if (ctxOsintBtn && location.pathname.includes("investigation.html")) {
    ctxOsintBtn.onclick = (e) => {
      e.preventDefault();
      const osintTabBtn = document.querySelector(`.workspace-tab[data-tab="osint"]`);
      if (osintTabBtn) osintTabBtn.click();
    };
  }
}

// ------------------------------------------------------------------
// 1. DASHBOARD
// ------------------------------------------------------------------
async function dashboard() {
  const recent = document.querySelector("#recent-investigations");
  if (!recent && !document.querySelector("#stat-active-cases")) return;

  try {
    const d = await api("/api/dashboard");
    const summary = d.summary || {};

    const sa = document.querySelector("#stat-active-cases");
    const sm = document.querySelector("#stat-sources-count");
    const nf = document.querySelector("#stat-new-findings");
    const cd = document.querySelector("#stat-changes-detected");
    const sal = document.querySelector("#stat-active-alerts");

    if (sa) sa.textContent = summary.active_scans ?? 0;
    if (sm) sm.textContent = summary.sources_monitored ?? 0;
    if (nf) nf.textContent = summary.new_findings_24h ?? 0;
    if (cd) cd.textContent = summary.changes_detected ?? 0;
    if (sal) sal.textContent = summary.active_alerts ?? 0;

    const monitoredBox = document.querySelector("#monitored-sources-list");
    if (monitoredBox) {
      const items = d.monitored_sources || [];
      monitoredBox.innerHTML = items.length
        ? `<table class="table">
            <thead><tr><th>Target</th><th>Interval</th><th>Last Scan</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              ${items.slice(0, 5).map(x => `
                <tr>
                  <td><strong style="color:var(--text-main);font-size:12px">${esc(x.target)}</strong></td>
                  <td>${esc(x.interval_minutes)}m</td>
                  <td style="font-size:11px;color:var(--text-muted)">${esc((x.last_scan_at || "Never").replace('T', ' ').slice(0, 16))}</td>
                  <td>${renderStatus(x.status || "ACTIVE")}</td>
                  <td><button class="btn ghost sm" onclick="triggerWatchScan('${esc(x.watch_id)}', this)">Scan</button></td>
                </tr>`).join("")}
            </tbody>
          </table>`
        : `<div class="empty">No monitored sources configured.</div>`;
    }

    const activityBox = document.querySelector("#recent-activity");
    if (activityBox) {
      const acts = d.recent_activity || [];
      activityBox.innerHTML = acts.length
        ? acts.map(x => `
          <div style="padding:8px 0;border-bottom:1px solid var(--border-line);display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <span class="badge blue" style="font-size:9px;margin-bottom:2px">${esc(x.event_type || "EVENT")}</span>
              <div style="color:var(--text-main);font-weight:600;font-size:12px">${esc(x.message)}</div>
            </div>
            <span style="font-size:10px;color:var(--text-muted);white-space:nowrap;margin-left:8px">${esc((x.created_at || "").replace('T', ' ').slice(0, 16))}</span>
          </div>`).join("")
        : `<div class="empty">No recent activity recorded.</div>`;
    }

    const alertsBox = document.querySelector("#dashboard-alerts");
    if (alertsBox) {
      const alerts = d.alerts || [];
      alertsBox.innerHTML = alerts.length
        ? alerts.map(x => `
          <div style="padding:10px;background:var(--panel-card);border-radius:6px;border-left:4px solid var(--red);border-top:1px solid var(--border-line);border-right:1px solid var(--border-line);border-bottom:1px solid var(--border-line);margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
            <div>
              <div style="display:flex;gap:6px;align-items:center">
                <span class="badge red" style="font-size:9px">${esc(x.severity || "HIGH")}</span>
                <strong style="font-size:12px;color:var(--text-main)">${esc(x.alert_type)}</strong>
              </div>
              <div style="font-size:11px;color:var(--text-sub);margin-top:2px">${esc(x.message)}</div>
            </div>
            <button class="btn ghost sm" onclick="acknowledgeAlert('${esc(x.alert_id)}', this)">Action</button>
          </div>`).join("")
        : `<div class="empty">No active alerts.</div>`;
    }

    if (recent) {
      const invs = d.recent_investigations || [];
      recent.innerHTML = invs.length
        ? invs.slice(0, 5).map(x => {
            const id = x.investigation_id || x.id;
            return `<div style="padding:10px;border-bottom:1px solid var(--border-line);display:flex;justify-content:space-between;align-items:center">
              <div>
                <strong style="font-size:13px;color:var(--text-main)">${esc(id)}</strong>
                <div style="font-size:11px;color:var(--text-muted)">Target: <span style="color:var(--cyan)">${esc(x.target || "—")}</span></div>
              </div>
              <div style="display:flex;gap:6px;align-items:center">
                ${renderStatus(x.status)}
                <a class="btn primary sm" href="/web/investigation.html?id=${encodeURIComponent(id)}">Workspace ➔</a>
              </div>
            </div>`;
          }).join("")
        : `<div class="empty">No investigations recorded. Click '+ New Investigation' above to begin.</div>`;
    }
  } catch (e) {
    console.error("Dashboard load error:", e);
  }
}

window.acknowledgeAlert = async function(alertId, btnEl) {
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = "Resolving...";
  }
  try {
    await api(`/api/alerts/${encodeURIComponent(alertId)}/acknowledge`, { method: "POST" });
    const card = btnEl ? btnEl.closest("div[style*='padding']") : null;
    if (card) {
      card.style.transition = "opacity 0.3s ease, transform 0.3s ease";
      card.style.opacity = "0";
      card.style.transform = "translateX(20px)";
      setTimeout(() => {
        card.remove();
        const alertsBox = document.querySelector("#dashboard-alerts");
        if (alertsBox && !alertsBox.children.length) {
          alertsBox.innerHTML = `<div class="empty">No active alerts.</div>`;
        }
      }, 300);
    }
    const sal = document.querySelector("#stat-active-alerts");
    if (sal) {
      const current = parseInt(sal.textContent) || 0;
      sal.textContent = Math.max(0, current - 1);
    }
  } catch(e) {
    alert("Failed to update alert: " + e.message);
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.textContent = "Action";
    }
  }
};

window.triggerWatchScan = async function(watchId, btnEl) {
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = "Scanning...";
  }

  try {
    const res = await api(`/api/watchlist/${encodeURIComponent(watchId)}/scan-now`, {
      method: "POST"
    });

    if (btnEl) {
      btnEl.textContent = "Done ✓";
      btnEl.style.color = "var(--green)";
      setTimeout(() => {
        btnEl.disabled = false;
        btnEl.textContent = "Scan";
        btnEl.style.color = "";
      }, 3000);
    }

    if (typeof dashboard === "function" && location.pathname.includes("index.html")) {
      setTimeout(dashboard, 1000);
    }
    if (typeof monitoringPage === "function" && location.pathname.includes("monitoring.html")) {
      setTimeout(monitoringPage, 1000);
    }
  } catch(err) {
    alert("Watchlist scan failed: " + (err.message || err));
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.textContent = "Scan";
    }
  }
};

// ------------------------------------------------------------------
// 2. INVESTIGATION WORKSPACE PAGE (investigation.html)
// ------------------------------------------------------------------
async function investigationPage() {
  const titleEl = document.getElementById("case-title");
  const statusBadge = document.getElementById("case-status-badge");
  const exportBtn = document.getElementById("case-export-btn");
  const summaryEl = document.getElementById("case-summary");
  const personaLink = document.getElementById("persona-compare-link");
  const invId = new URLSearchParams(location.search).get("id") || "";

  if (!invId) {
    if (titleEl) titleEl.textContent = "No Investigation Selected";
    if (statusBadge) { statusBadge.textContent = "NONE"; statusBadge.className = "badge amber"; }
    return;
  }

  if (exportBtn) exportBtn.href = `/api/export/${encodeURIComponent(invId)}/pdf`;
  if (personaLink) personaLink.href = `/web/stylometry.html?id=${encodeURIComponent(invId)}`;

  ["pdf", "html", "json", "csv"].forEach(fmt => {
    const btn = document.getElementById(`rpt-${fmt}-btn`);
    if (btn) btn.href = `/api/export/${encodeURIComponent(invId)}/${fmt}`;
  });

  try {
    const data = await api("/api/investigations");
    const list = (data.investigations || (Array.isArray(data) ? data : [])) || [];
    const inv = list.find(i => (i.investigation_id || i.id) === invId);
    if (inv) {
      if (titleEl) titleEl.textContent = `${invId} — ${inv.target || "Target"}`;
      if (statusBadge) {
        statusBadge.textContent = (inv.status || "UNKNOWN").toUpperCase();
        statusBadge.className = `badge ${inv.status === "completed" ? "green" : inv.status === "running" ? "blue" : "amber"}`;
      }
      const targetInput = document.getElementById("case-osint-target");
      if (targetInput && !targetInput.value) {
        targetInput.value = (inv.target || "").replace(/^https?:\/\//, "").replace(/\/.*$/, "");
      }
    } else {
      if (titleEl) titleEl.textContent = invId;
    }
  } catch(e) {
    if (titleEl) titleEl.textContent = invId;
  }

  // Load Metrics Summary Cards
  if (summaryEl) {
    try {
      const fd = await api(`/api/investigations/${encodeURIComponent(invId)}/findings`);
      const findings = fd.findings || (Array.isArray(fd) ? fd : []);
      const td = await api(`/api/investigations/${encodeURIComponent(invId)}/timeline`).catch(() => []);
      const events = Array.isArray(td) ? td : td.events || [];

      const handles = findings.filter(f => {
        const t = (f.finding_type || f.type || "").toLowerCase();
        return t === "handle" || t === "username" || t === "actor" || t === "alias";
      });
      const wallets = findings.filter(f => {
        const t = (f.finding_type || f.type || "").toLowerCase();
        return t.includes("crypto") || t.includes("btc") || t.includes("xmr") || t.includes("wallet");
      });

      summaryEl.innerHTML = `
        <div class="metric-card"><div class="metric-label"><span>FINDINGS</span><span>🔍</span></div><div class="metric-value">${findings.length}</div><div class="metric-sub">Extracted indicators</div></div>
        <div class="metric-card"><div class="metric-label"><span>TIMELINE</span><span>📋</span></div><div class="metric-value">${events.length}</div><div class="metric-sub">Logged events</div></div>
        <div class="metric-card"><div class="metric-label"><span>ACTOR HANDLES</span><span>👤</span></div><div class="metric-value">${handles.length}</div><div class="metric-sub">Unique handles</div></div>
        <div class="metric-card"><div class="metric-label"><span>CRYPTO WALLETS</span><span>💰</span></div><div class="metric-value">${wallets.length}</div><div class="metric-sub">BTC / XMR</div></div>`;
    } catch(e) {
      summaryEl.innerHTML = Array(4).fill(`<div class="metric-card"><div class="metric-value">—</div></div>`).join("");
    }
  }

  // Wire Tab Buttons
  const tabs = document.querySelectorAll("#case-workspace-tabs .workspace-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const tabName = tab.dataset.tab;
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));
      const pane = document.getElementById(`pane-${tabName}`);
      if (pane) pane.classList.add("active");

      if (tabName === "overview") loadCaseOverview(invId);
      if (tabName === "findings") loadCaseFindingsFull(invId);
      if (tabName === "osint") loadCaseOsint(invId);
      if (tabName === "persona") loadCasePersona(invId);
      if (tabName === "graph") loadCaseGraph(invId);
      if (tabName === "timeline") loadCaseTimelineFull(invId);
      if (tabName === "evidence") loadCaseEvidence(invId);
      if (tabName === "monitoring") loadCaseMonitoring(invId);
    });
  });

  // Wire In-Workspace Manual OSINT Button
  const runOsintBtn = document.getElementById("btn-run-case-osint");
  if (runOsintBtn) {
    runOsintBtn.onclick = async () => {
      const target = document.getElementById("case-osint-target")?.value?.trim();
      const targetType = document.getElementById("case-osint-type")?.value || "username";
      if (!target) {
        alert("Please enter a target observable (handle, domain, IP, or wallet).");
        return;
      }
      runOsintBtn.disabled = true;
      runOsintBtn.textContent = "Running OSINT...";

      const resultsEl = document.getElementById("case-osint-results");
      if (resultsEl) {
        resultsEl.innerHTML = `
          <div style="padding:14px;background:#0d1117;border-radius:6px;font-family:monospace;font-size:11.5px;color:#c9d1d9;min-height:120px" id="case-osint-live-terminal">
            <span class="terminal-line info">[PRALAYX] Initiating OSINT execution for ${esc(target)} (${esc(targetType)})...</span>\n
          </div>`;
      }

      try {
        const res = await api(`/api/investigations/${encodeURIComponent(invId)}/osint`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target, target_type: targetType, investigation_id: invId })
        });
        const jobId = res.job_id;
        // Persist active job across pages
        localStorage.setItem("pralayx_last_osint_job", JSON.stringify({ jobId, invId, target, targetType, timestamp: Date.now() }));

        const term = document.getElementById("case-osint-live-terminal");
        if (term) term.innerHTML += `<span class="terminal-line success">[OK] Background OSINT job started: ${esc(jobId)}. Querying providers...</span>\n`;
        if (jobId) {
          await pollOsintJob(jobId, term, null, invId);
          await loadCaseOsint(invId);
          loadCaseOverview(invId);
        }
      } catch(err) {
        const term = document.getElementById("case-osint-live-terminal");
        if (term) term.innerHTML += `<span class="terminal-line error">[ERROR] OSINT failed: ${esc(err.message)}</span>\n`;
      } finally {
        runOsintBtn.disabled = false;
        runOsintBtn.textContent = "Run OSINT";
      }
    };
  }

  // Check for recent running OSINT job on page return
  checkRecentOsintJob(invId);

  // Load default tab or tab from URL param
  const urlTab = new URLSearchParams(location.search).get("tab") || location.hash.replace("#", "");
  if (urlTab) {
    const targetTabBtn = document.querySelector(`#case-workspace-tabs .workspace-tab[data-tab="${urlTab}"]`);
    if (targetTabBtn) {
      targetTabBtn.click();
      return;
    }
  }

  loadCaseOverview(invId);
}

async function checkRecentOsintJob(currentInvId) {
  try {
    const saved = localStorage.getItem("pralayx_last_osint_job");
    if (!saved) return;
    const { jobId, invId, target } = JSON.parse(saved);
    if (invId !== currentInvId) return;

    const data = await api(`/api/jobs/${encodeURIComponent(jobId)}`).catch(() => null);
    if (!data) return;

    const job = data.job || data;
    const status = (job.status || "UNKNOWN").toUpperCase();

    // If running or recently updated within 10 minutes
    if (status === "RUNNING") {
      const osintTabBtn = document.querySelector(`.workspace-tab[data-tab="osint"]`);
      if (osintTabBtn) osintTabBtn.click();

      const resultsEl = document.getElementById("case-osint-results");
      if (resultsEl) {
        resultsEl.innerHTML = `
          <div style="padding:14px;background:#0d1117;border-radius:6px;font-family:monospace;font-size:11.5px;color:#c9d1d9;min-height:120px" id="case-osint-live-terminal">
            <span class="terminal-line info">[PRALAYX] Resumed live stream for active background scan: ${esc(jobId)} (${esc(target)})</span>\n
          </div>`;
        const term = document.getElementById("case-osint-live-terminal");
        pollOsintJob(jobId, term, null, invId).then(() => loadCaseOsint(invId));
      }
    } else if (status === "FAILED" || status === "ERROR") {
      const errReason = job.error || "No response received from external OSINT provider";
      const osintResults = document.getElementById("case-osint-results");
      if (osintResults) {
        osintResults.innerHTML = `
          <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:14px;margin-bottom:12px">
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-size:18px">❌</span>
              <div>
                <strong style="color:#b91c1c;font-size:13px">Previous Manual OSINT Scan Failed</strong>
                <p style="margin:4px 0 0 0;font-size:12px;color:#7f1d1d">Target: <code>${esc(target)}</code> • Reason: <strong>${esc(errReason)}</strong></p>
              </div>
            </div>
            <div style="margin-top:8px;font-size:11px;color:#991b1b">Check provider API keys in <a href="/web/settings.html" style="color:#2563eb;text-decoration:underline">Settings</a> or ensure network connectivity to darknet relays.</div>
          </div>`;
      }
    }
  } catch(e) { /* ignore */ }
}

async function loadCaseOverview(invId) {
  const findingsEl = document.getElementById("overview-findings");
  const timelineEl = document.getElementById("case-timeline");
  if (findingsEl) {
    try {
      const d = await api(`/api/investigations/${encodeURIComponent(invId)}/findings`);
      const f = (d.findings || (Array.isArray(d) ? d : [])).slice(0, 8);
      findingsEl.innerHTML = f.length
        ? f.map(x => `<div style="padding:8px 0;border-bottom:1px solid var(--border-line);display:flex;justify-content:space-between;align-items:center"><div><span class="badge ${typeBadgeClass(x.finding_type||x.type)}" style="margin-right:6px">${esc(x.finding_type||x.type||"finding")}</span><code style="font-size:11px;font-weight:600">${esc(x.value||x.finding_value||"")}</code></div><span style="font-size:10px;color:var(--text-muted)">${esc((x.created_at||"").slice(0,10))}</span></div>`).join("")
        : `<div class="empty">No findings yet. Start a crawl or run OSINT to collect indicators.</div>`;
    } catch(e) { findingsEl.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>${esc(e.message)}</div>`; }
  }
  if (timelineEl) {
    try {
      const d = await api(`/api/investigations/${encodeURIComponent(invId)}/timeline`);
      const ev = (Array.isArray(d) ? d : d.events || []).slice(0, 10);
      timelineEl.innerHTML = ev.length
        ? ev.map(x => `<div style="padding:8px 0;border-bottom:1px solid var(--border-line)"><div style="display:flex;align-items:center;gap:8px"><span class="badge blue" style="font-size:9px">${esc(x.event_type||"EVENT")}</span><span style="font-size:11px;color:var(--text-muted)">${esc((x.created_at||x.timestamp||"").slice(0,19).replace("T"," "))}</span></div><div style="font-size:12px;color:var(--text-main);margin-top:3px">${esc(x.description||x.detail||x.message||"")}</div></div>`).join("")
        : `<div class="empty">No timeline events recorded yet.</div>`;
    } catch(e) { timelineEl.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>${esc(e.message)}</div>`; }
  }
}

async function loadCaseFindingsFull(invId) {
  const tbody = document.getElementById("case-findings-tbody");
  if (!tbody || !invId) return;
  try {
    const d = await api(`/api/investigations/${encodeURIComponent(invId)}/findings`);
    const findings = d.findings || (Array.isArray(d) ? d : []);
    tbody.innerHTML = findings.length
      ? findings.map(f => `<tr>
          <td><span class="badge ${typeBadgeClass(f.finding_type||f.type)}">${esc(f.finding_type||f.type||"finding")}</span></td>
          <td><code style="font-size:11.5px;font-weight:600">${esc(f.value||f.finding_value||"")}</code></td>
          <td style="font-size:11px;color:var(--text-muted);max-width:240px;overflow:hidden;text-overflow:ellipsis">${esc(f.source_url||f.source||"—")}</td>
          <td><span class="badge ${parseFloat(f.confidence||0)>0.7?"green":"amber"}">${Math.round((parseFloat(f.confidence)||0.5)*100)}%</span></td>
          <td style="font-size:11px;color:var(--text-muted)">${esc((f.created_at||f.evidence_collected_at||"").slice(0,16).replace("T"," "))}</td>
        </tr>`).join("")
      : `<tr><td colspan="5" class="empty">No findings for this investigation.</td></tr>`;
  } catch(e) { tbody.innerHTML = `<tr><td colspan="5" class="error-state">${esc(e.message)}</td></tr>`; }
}

async function loadCaseOsint(invId) {
  const container = document.getElementById("case-osint-results");
  if (!container || !invId) return;

  try {
    const d = await api(`/api/investigations/${encodeURIComponent(invId)}/findings`);
    const all = d.findings || (Array.isArray(d) ? d : []);
    const osintFindings = all.filter(f => {
      const src = (f.source_url || f.source || "").toLowerCase();
      const t = (f.finding_type || f.type || "").toLowerCase();
      return src.includes("shodan") || src.includes("virustotal") || src.includes("whois") || src.includes("censys") || src.includes("osint") || t === "ip" || t === "domain" || t === "email" || t.includes("osint");
    });

    if (osintFindings.length === 0) {
      container.innerHTML = `
        <div class="empty" style="padding:28px 16px">
          <div style="font-size:28px;margin-bottom:8px">◎</div>
          <strong>No OSINT enrichment records yet for this case.</strong>
          <div style="font-size:11.5px;color:var(--text-muted);margin-top:4px">Enter a domain, handle, IP, or BTC wallet above and click <strong>Run OSINT</strong> to query live OSINT providers.</div>
        </div>`;
    } else {
      container.innerHTML = `
        <h4 style="margin:0 0 10px 0;font-size:13px;color:var(--text-sub)">Enriched OSINT Indicators (${osintFindings.length})</h4>
        <div class="table-container">
          <table class="table">
            <thead><tr><th>Type</th><th>Observable</th><th>Source / Provider</th><th>Confidence</th><th>Timestamp</th></tr></thead>
            <tbody>` +
            osintFindings.map(f => `<tr>
              <td><span class="badge ${typeBadgeClass(f.finding_type||f.type)}">${esc(f.finding_type||f.type||"osint")}</span></td>
              <td><code style="font-size:12px;font-weight:600">${esc(f.value||f.finding_value||"")}</code></td>
              <td style="font-size:11px;color:var(--text-muted)">${esc(f.source_url||f.source||"OSINT Provider")}</td>
              <td><span class="badge ${parseFloat(f.confidence||0)>0.7?"green":"amber"}">${Math.round((parseFloat(f.confidence)||0.5)*100)}%</span></td>
              <td style="font-size:11px;color:var(--text-muted)">${esc((f.created_at||f.evidence_collected_at||"").slice(0,16).replace("T"," "))}</td>
            </tr>`).join("") + `</tbody>
          </table>
        </div>`;
    }
  } catch(e) {
    container.innerHTML = `<div class="error-state">${esc(e.message)}</div>`;
  }
}

async function loadCasePersona(invId) {
  const container = document.getElementById("case-persona-content");
  if (!container || !invId) return;
  try {
    const data = await api(`/api/investigations/${encodeURIComponent(invId)}/persona`);
    const personaFindings = data.persona_findings || [];
    if (personaFindings.length === 0) {
      container.innerHTML = `
        <div class="empty" style="padding:28px 16px">
          <div style="font-size:28px;margin-bottom:8px">📈</div>
          <strong>No AI behavioral or stylometric profile extracted yet.</strong>
          <div style="font-size:12px;color:var(--text-muted);margin:6px 0 14px 0">Compare target text samples with dark web forum handles in the Persona Compare workspace.</div>
          <a href="/web/stylometry.html?id=${encodeURIComponent(invId)}" class="btn primary">Open Persona Compare & Profiler ➔</a>
        </div>`;
    } else {
      container.innerHTML = `
        <div class="grid g2" style="margin-bottom:14px">
          <div class="metric-card">
            <div class="metric-label"><span>ATTRIBUTED ACTOR</span><span>👤</span></div>
            <div class="metric-value" style="font-size:16px">${esc(data.actor_id || "Unattributed")}</div>
            <div class="metric-sub">${esc(data.target || "Target")}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label"><span>STYLES & MARKERS</span><span>⌁</span></div>
            <div class="metric-value" style="font-size:16px">${personaFindings.length} Markers</div>
            <div class="metric-sub">Punctuation, emoji & vocabulary</div>
          </div>
        </div>
        <div class="table-container">
          <table class="table">
            <thead><tr><th>Marker Type</th><th>Value</th><th>Confidence</th><th>Source</th></tr></thead>
            <tbody>` +
            personaFindings.map(p => `<tr>
              <td><span class="badge blue">${esc(p.finding_type || "Stylometry")}</span></td>
              <td><code style="font-size:11.5px">${esc(p.value || p.finding_value || "")}</code></td>
              <td><span class="badge green">${Math.round((parseFloat(p.confidence)||0.85)*100)}%</span></td>
              <td style="font-size:11px;color:var(--text-muted)">${esc(p.source || "Persona Engine")}</td>
            </tr>`).join("") + `</tbody>
          </table>
        </div>`;
    }
  } catch(e) {
    container.innerHTML = `<div class="error-state">${esc(e.message)}</div>`;
  }
}

async function loadCaseTimelineFull(invId) {
  const el = document.getElementById("case-timeline-full");
  if (!el || !invId) return;
  try {
    const d = await api(`/api/investigations/${encodeURIComponent(invId)}/timeline`);
    const ev = (Array.isArray(d) ? d : d.events || []) || [];
    el.innerHTML = ev.length
      ? ev.map(x => `
        <div style="padding:12px;border:1px solid var(--border-line);border-radius:6px;background:var(--panel-card);margin-bottom:8px;display:flex;gap:12px;align-items:flex-start">
          <div style="min-width:140px;font-size:11px;color:var(--text-muted);font-family:monospace">${esc((x.created_at||x.timestamp||"").slice(0,19).replace("T"," "))}</div>
          <div style="flex:1">
            <span class="badge blue" style="font-size:9.5px;margin-bottom:4px">${esc(x.event_type||"EVENT")}</span>
            <div style="font-size:12.5px;font-weight:600;color:var(--text-main);margin-top:2px">${esc(x.description||x.detail||x.message||"")}</div>
          </div>
        </div>`).join("")
      : `<div class="empty">No timeline events recorded yet.</div>`;
  } catch(e) {
    el.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>${esc(e.message)}</div>`;
  }
}

async function loadCaseEvidence(invId) {
  const el = document.getElementById("case-evidence-vault");
  if (!el || !invId) return;
  try {
    const d = await api(`/api/investigations/${encodeURIComponent(invId)}/findings`);
    const findings = d.findings || (Array.isArray(d) ? d : []);
    el.innerHTML = findings.length
      ? `<div class="grid g2">` + findings.map(f => `
        <div style="padding:12px;border:1px solid var(--border-line);border-radius:6px;background:var(--panel-card)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <code style="font-size:10.5px;color:var(--cyan)">${esc(f.evidence_id || f.finding_id || "EVD-" + Math.abs(hashCode(f.value || "")))}</code>
            <span class="badge ${typeBadgeClass(f.finding_type || f.type)}">${esc(f.finding_type || f.type || "finding")}</span>
          </div>
          <div style="font-size:13px;font-weight:600;color:var(--text-main);word-break:break-all;margin-bottom:4px">${esc(f.value || f.finding_value || "")}</div>
          <div style="font-size:11px;color:var(--text-muted)">Source: ${esc(f.source_url || f.source || "Dark Web")}</div>
          <div style="font-size:10px;color:var(--text-sub);margin-top:6px;display:flex;justify-content:space-between">
            <span>Confidence: ${Math.round((parseFloat(f.confidence)||0.5)*100)}%</span>
            <span>${esc((f.created_at || f.evidence_collected_at || "").slice(0,16).replace("T"," "))}</span>
          </div>
        </div>`).join("") + `</div>`
      : `<div class="empty">No evidence artifacts stored yet.</div>`;
  } catch(e) {
    el.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>${esc(e.message)}</div>`;
  }
}

async function loadCaseMonitoring(invId) {
  const el = document.getElementById("case-monitoring-content");
  if (!el || !invId) return;
  try {
    const md = await api(`/api/monitoring?investigation_id=${encodeURIComponent(invId)}`).catch(() => ({ watchlist: [] }));
    const ad = await api(`/api/alerts?investigation_id=${encodeURIComponent(invId)}`).catch(() => ({ alerts: [] }));
    const wl = md.watchlist || [];
    const al = ad.alerts || [];

    el.innerHTML = `
      <div class="grid g2" style="margin-bottom:16px">
        <div>
          <h4 style="margin:0 0 8px 0;font-size:12px;color:var(--text-muted);text-transform:uppercase">Surveillance Watchlist (${wl.length})</h4>
          ${wl.length ? wl.map(w => `
            <div style="padding:10px;border:1px solid var(--border-line);border-radius:6px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
              <div>
                <strong style="font-size:12px;color:var(--text-main)">${esc(w.target_url || w.target || "—")}</strong>
                <div style="font-size:11px;color:var(--text-muted)">Interval: ${w.interval_minutes || 60}m • Last: ${esc((w.last_scan_at || "Never").slice(0,16).replace("T"," "))}</div>
              </div>
              <div style="display:flex;gap:6px;align-items:center">
                ${renderStatus(w.status)}
                <button class="btn ghost sm" onclick="triggerWatchScan('${esc(w.watch_id)}', this)">Scan</button>
              </div>
            </div>`).join("") : `<div class="empty">No active targets on watchlist for this case.</div>`}
        </div>
        <div>
          <h4 style="margin:0 0 8px 0;font-size:12px;color:var(--text-muted);text-transform:uppercase">Investigation Alerts (${al.length})</h4>
          ${al.length ? al.map(a => `
            <div style="padding:10px;border:1px solid var(--border-line);border-radius:6px;margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span class="badge red">${esc(a.severity || "HIGH")}</span>
                <span style="font-size:10px;color:var(--text-muted)">${esc((a.created_at || "").slice(0,16).replace("T"," "))}</span>
              </div>
              <strong style="font-size:12px;color:var(--text-main)">${esc(a.alert_type || "Alert")}</strong>
              <div style="font-size:11.5px;color:var(--text-muted);margin-top:2px">${esc(a.message || "")}</div>
            </div>`).join("") : `<div class="empty">No alerts triggered for this case.</div>`}
        </div>
      </div>`;
  } catch(e) {
    el.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>${esc(e.message)}</div>`;
  }
}

// ------------------------------------------------------------------
// 3. FULL OSINT ENGINE PAGE (/web/osint.html)
// ------------------------------------------------------------------
async function osintPage() {
  const invId = new URLSearchParams(location.search).get("id") || "";
  const invField = document.getElementById("osint-investigation");
  if (invField && invId) invField.value = invId;

  await loadOsintHistory(invId);

  // Resume running job if any
  try {
    const saved = localStorage.getItem("pralayx_last_osint_job");
    if (saved) {
      const { jobId, target } = JSON.parse(saved);
      const data = await api(`/api/jobs/${encodeURIComponent(jobId)}`).catch(() => null);
      if (data) {
        const job = data.job || data;
        const status = (job.status || "").toUpperCase();
        if (status === "RUNNING") {
          const resSec = document.getElementById("osint-result");
          const term = document.getElementById("osint-terminal");
          const sBadge = document.getElementById("osint-status-badge");
          if (resSec) resSec.classList.remove("hidden");
          if (term) term.innerHTML = `<span class="terminal-line info">[PRALAYX] Resumed live stream for active background scan: ${esc(jobId)} (${esc(target)})</span>\n`;
          if (sBadge) { sBadge.textContent = "RUNNING"; sBadge.className = "badge amber"; }
          pollOsintJob(jobId, term, sBadge, invId).then(() => loadOsintHistory(invId));
        } else if (status === "FAILED" || status === "ERROR") {
          const resSec = document.getElementById("osint-result");
          const term = document.getElementById("osint-terminal");
          const sBadge = document.getElementById("osint-status-badge");
          if (resSec) resSec.classList.remove("hidden");
          if (sBadge) { sBadge.textContent = "FAILED"; sBadge.className = "badge red"; }
          if (term) {
            term.innerHTML = `<span class="terminal-line error">[ERROR] Scan failed: ${esc(job.error || "Unknown provider error")}</span>\n`;
            (data.events || []).forEach(e => {
              term.innerHTML += `<span class="terminal-line ${e.event_type === 'error' ? 'error' : 'dim'}">${esc(e.message || '')}</span>\n`;
            });
          }
        }
      }
    }
  } catch(e) {}

  const form = document.getElementById("osint-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const inv = document.getElementById("osint-investigation")?.value?.trim();
    const target = document.getElementById("osint-target")?.value?.trim();
    const targetType = document.getElementById("osint-type")?.value || "username";

    if (!target) return;

    const resultSection = document.getElementById("osint-result");
    const terminal = document.getElementById("osint-terminal");
    const statusBadge = document.getElementById("osint-status-badge");
    const invBadge = document.getElementById("osint-inv-badge");

    if (resultSection) resultSection.classList.remove("hidden");
    if (terminal) terminal.innerHTML = `<span class="terminal-line info">[PRALAYX] Starting OSINT scan for: ${esc(target)} (${esc(targetType)})</span>\n`;
    if (statusBadge) { statusBadge.textContent = "RUNNING"; statusBadge.className = "badge amber"; }
    if (invBadge && inv) invBadge.textContent = inv;

    try {
      let endpoint = "/api/investigate";
      let payload = { target, target_type: targetType };
      if (inv) {
        endpoint = `/api/investigations/${encodeURIComponent(inv)}/osint`;
        payload.investigation_id = inv;
      }

      const res = await api(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const jobId = res.job_id;
      const newInvId = res.investigation_id || inv;

      localStorage.setItem("pralayx_last_osint_job", JSON.stringify({ jobId, invId: newInvId, target, targetType, timestamp: Date.now() }));

      if (terminal) terminal.innerHTML += `<span class="terminal-line success">[OK] Job started: ${esc(jobId)}</span>\n`;
      if (terminal) terminal.innerHTML += `<span class="terminal-line info">[INFO] Investigation: ${esc(newInvId)}</span>\n`;
      if (invBadge) invBadge.textContent = newInvId;

      if (jobId) await pollOsintJob(jobId, terminal, statusBadge, newInvId);
      await loadOsintHistory(newInvId);
    } catch(err) {
      if (terminal) terminal.innerHTML += `<span class="terminal-line error">[ERROR] ${esc(err.message || String(err))}</span>\n`;
      if (statusBadge) { statusBadge.textContent = "ERROR"; statusBadge.className = "badge red"; }
    }
  });
}

async function pollOsintJob(jobId, terminal, statusBadge, invId) {
  let attempts = 0;
  const maxAttempts = 60;
  const interval = 3500;

  return new Promise((resolve) => {
    const tick = async () => {
      attempts++;
      try {
        const data = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
        const job = data.job || data;
        const status = (job.status || "UNKNOWN").toUpperCase();
        const evts = data.events || [];

        if (evts.length && terminal) {
          const existing = terminal.querySelectorAll(".terminal-line").length;
          evts.slice(existing - 2).forEach(ev => {
            const line = ev.message || "";
            const cls = line.toLowerCase().includes("error") ? "error"
                      : line.toLowerCase().includes("[+]") || line.toLowerCase().includes("found") ? "success"
                      : line.toLowerCase().includes("warn") ? "warn" : "info";
            terminal.innerHTML += `<span class="terminal-line ${cls}">${esc(line)}</span>\n`;
          });
          terminal.scrollTop = terminal.scrollHeight;
        }

        if (status === "COMPLETED" || status === "COMPLETE" || status === "DONE") {
          if (statusBadge) { statusBadge.textContent = "COMPLETE"; statusBadge.className = "badge green"; }
          if (terminal) terminal.innerHTML += `<span class="terminal-line success">[PRALAYX] Scan complete. Indicators attributed to case ${esc(invId)}.</span>\n`;
          if (invId && terminal) {
            terminal.innerHTML += `<span class="terminal-line data">[RESULT] <a href="/web/investigation.html?id=${encodeURIComponent(invId)}" style="color:var(--cyan)">Open Case Workspace →</a></span>\n`;
          }
          resolve();
          return;
        } else if (status === "FAILED" || status === "ERROR") {
          const errReason = job.error || "Execution terminated";
          if (statusBadge) { statusBadge.textContent = "FAILED"; statusBadge.className = "badge red"; }
          if (terminal) {
            terminal.innerHTML += `<span class="terminal-line error">[ERROR] OSINT Scan Failed: ${esc(errReason)}</span>\n`;
            terminal.innerHTML += `<span class="terminal-line warn">[DIAGNOSTIC] Check API keys in Settings or verify target address format.</span>\n`;
          }
          resolve();
          return;
        }

        if (attempts < maxAttempts) {
          setTimeout(tick, interval);
        } else {
          if (statusBadge) { statusBadge.textContent = "TIMEOUT"; statusBadge.className = "badge amber"; }
          resolve();
        }
      } catch(e) {
        if (attempts < maxAttempts) setTimeout(tick, interval);
        else resolve();
      }
    };
    setTimeout(tick, 1000);
  });
}

async function loadOsintHistory(invId) {
  const el = document.getElementById("osint-history");
  const countEl = document.getElementById("osint-history-count");
  if (!el) return;
  try {
    const endpoint = invId
      ? `/api/investigations/${encodeURIComponent(invId)}/findings`
      : null;
    if (!endpoint) { if (countEl) countEl.textContent = "0 RECORDS"; el.innerHTML = `<div class="empty-state"><p>Open an investigation to view findings.</p></div>`; return; }
    const data = await api(endpoint);
    const findings = data.findings || (Array.isArray(data) ? data : []);
    if (countEl) countEl.textContent = `${findings.length} RECORDS`;
    el.innerHTML = findings.length
      ? `<table class="table"><thead><tr><th>Type</th><th>Observable Value</th><th>Provider / Source</th><th>Confidence</th><th>Seen</th></tr></thead><tbody>` +
        findings.slice(0, 25).map(f => `<tr>
          <td><span class="badge ${typeBadgeClass(f.finding_type||f.type)}">${esc(f.finding_type||f.type||"finding")}</span></td>
          <td><code style="font-size:11.5px;font-weight:600">${esc(f.value||f.finding_value||"")}</code></td>
          <td style="font-size:11px;color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis">${esc(f.source_url||f.source||"—")}</td>
          <td><span class="badge ${parseFloat(f.confidence||0)>0.7?"green":"amber"}">${Math.round((parseFloat(f.confidence)||0.5)*100)}%</span></td>
          <td style="font-size:11px;color:var(--text-muted)">${esc((f.created_at||f.evidence_collected_at||"").slice(0,16).replace("T"," "))}</td>
        </tr>`).join("") + `</tbody></table>`
      : `<div class="empty">No OSINT findings yet. Enter target observable above to begin scan.</div>`;
  } catch(e) {
    el.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>${esc(e.message)}</div>`;
  }
}

// ------------------------------------------------------------------
// 4. PERSONA COMPARISON WORKSTATION (/web/stylometry.html)
// ------------------------------------------------------------------
async function stylometryPage() {
  const btn = document.getElementById("btn-compare-personas");
  const resultsEl = document.getElementById("persona-compare-results");
  if (!btn || !resultsEl) return;

  const invId = new URLSearchParams(location.search).get("id") || "";

  /*
   * Existing PRALAYX Persona comparison workflow.
   *
   * This keeps the existing /api/persona/compare endpoint and UI.
   * The important change is that returned AI analysis is surfaced when
   * the Persona service provides it, without inventing fallback scores.
   */

  btn.onclick = async () => {
    const textA = document.getElementById("persona-text-a")?.value?.trim();
    const textB = document.getElementById("persona-text-b")?.value?.trim();

    if (!textA || !textB) {
      alert(
        "Please provide both Reference Text A and Candidate Text B for stylometric comparison."
      );
      return;
    }

    btn.disabled = true;
    btn.textContent = "Analyzing Linguistic Patterns...";
    resultsEl.classList.remove("hidden");

    resultsEl.innerHTML = `
      <div class="panel-pad">
        <div class="skeleton skeleton-line wide"></div>
        <div class="skeleton skeleton-line med"></div>
        <div class="skeleton skeleton-line" style="width:70%"></div>
      </div>`;

    try {
      const payload = {
        reference_text: textA,
        candidate_text: textB,
        investigation_id: invId || null
      };

      const res = await api("/api/persona/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      /*
       * Never manufacture a similarity score.
       * Different Persona versions may expose different field names.
       */
      const rawSimilarity =
        res.similarity_score ??
        res.overall_similarity ??
        res.confidence ??
        null;

      const similarity =
        typeof rawSimilarity === "number"
          ? Math.round(rawSimilarity * 100)
          : null;

      const metricValue = value => {
        if (typeof value !== "number") return "—";
        return `${Math.round(value * 100)}%`;
      };

      const lexical =
        res.lexical_similarity ??
        res.style_similarity ??
        res.signals?.style_similarity ??
        null;

      const syntactic =
        res.syntactic_similarity ??
        res.punctuation_similarity ??
        res.signals?.syntactic_similarity ??
        null;

      const slang =
        res.slang_overlap ??
        res.function_word_similarity ??
        res.signals?.slang_overlap ??
        null;

      /*
       * AI analysis may be returned by the updated Persona comparison
       * implementation. Keep it optional so classical comparison continues
       * to work when Gemini is unavailable.
       */
      const ai =
        res.ai_analysis ||
        res.ai_profile_comparison ||
        res.ai_comparison ||
        null;

      const aiStatus = String(
        ai?.status ||
        ai?.provider_status ||
        res.ai_status ||
        ""
      ).toUpperCase();

      const aiAvailable =
        ai &&
        (
          aiStatus === "SUCCESS" ||
          aiStatus === "COMPLETED" ||
          aiStatus === "AVAILABLE" ||
          Object.keys(ai).length > 0
        );

      const sharedCharacteristics =
        ai?.shared_characteristics ||
        ai?.common_characteristics ||
        ai?.similarities ||
        [];

      const differences =
        ai?.differences ||
        ai?.distinguishing_characteristics ||
        [];

      const aiSummary =
        ai?.summary ||
        ai?.assessment ||
        ai?.explanation ||
        "";

      const aiProvider =
        ai?.provider ||
        res.ai_provider ||
        "AI linguistic profiler";

      let resultLabel = "INCONCLUSIVE";

      if (similarity !== null) {
        if (similarity >= 70) {
          resultLabel = "STRONG STYLISTIC SIMILARITY";
        } else if (similarity >= 50) {
          resultLabel = "MODERATE STYLISTIC SIMILARITY";
        } else {
          resultLabel = "LOW STYLISTIC SIMILARITY";
        }
      }

      const renderList = items => {
        if (!Array.isArray(items) || !items.length) {
          return `<span style="color:var(--text-muted)">No additional characteristics returned.</span>`;
        }

        return `
          <ul style="margin:6px 0 0 18px;padding:0;color:var(--text-sub);font-size:11.5px;line-height:1.6">
            ${items
              .slice(0, 12)
              .map(item => `<li>${esc(typeof item === "string" ? item : JSON.stringify(item))}</li>`)
              .join("")}
          </ul>`;
      };

      resultsEl.innerHTML = `
        <div
          style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:12px;
            margin-bottom:16px;
            border-bottom:1px solid var(--border-line);
            padding-bottom:12px;
          "
        >
          <div>
            <span class="kicker">STYLOMETRIC COMPARISON RESULT</span>

            <h2
              style="
                margin:2px 0 0 0;
                font-size:18px;
                color:var(--text-main);
              "
            >
              Stylistic Similarity:
              <span
                style="
                  color:${similarity === null
                    ? "var(--text-muted)"
                    : similarity >= 70
                      ? "var(--green)"
                      : "var(--amber)"};
                "
              >
                ${similarity === null ? "—" : `${similarity}%`}
              </span>
            </h2>

            ${
              invId
                ? `<div style="font-size:10.5px;color:var(--text-muted);margin-top:4px">
                    Investigation: ${esc(invId)}
                   </div>`
                : ""
            }
          </div>

          <span
            class="badge ${
              similarity === null
                ? "amber"
                : similarity >= 70
                  ? "green"
                  : "amber"
            }"
            style="font-size:11px;padding:4px 10px"
          >
            ${esc(resultLabel)}
          </span>
        </div>

        <div
          style="
            margin-bottom:16px;
            padding:10px 12px;
            border:1px solid var(--border-line);
            border-radius:6px;
            background:var(--bg-main);
            font-size:11px;
            color:var(--text-muted);
            line-height:1.55;
          "
        >
          <strong style="color:var(--text-main)">Interpretation:</strong>
          This result indicates similarity between the supplied writing
          samples. It is an analytical lead, not proof of authorship,
          identity, or real-world attribution.
        </div>

        <div class="grid g3" style="margin-bottom:16px">

          <div class="metric-card">
            <div class="metric-label">
              <span>VOCABULARY / STYLE</span>
              <span>📖</span>
            </div>

            <div class="metric-value">
              ${metricValue(lexical)}
            </div>

            <div class="metric-sub">
              Returned lexical/style signal
            </div>
          </div>

          <div class="metric-card">
            <div class="metric-label">
              <span>SYNTAX / PUNCTUATION</span>
              <span>⌁</span>
            </div>

            <div class="metric-value">
              ${metricValue(syntactic)}
            </div>

            <div class="metric-sub">
              Returned structural signal
            </div>
          </div>

          <div class="metric-card">
            <div class="metric-label">
              <span>LANGUAGE / SLANG</span>
              <span>🗣</span>
            </div>

            <div class="metric-value">
              ${metricValue(slang)}
            </div>

            <div class="metric-sub">
              Returned language signal
            </div>
          </div>

        </div>

        ${
          aiAvailable
            ? `
              <div
                class="panel panel-pad"
                style="
                  margin-bottom:16px;
                  background:var(--bg-main);
                  border:1px solid var(--border-line);
                "
              >
                <div
                  style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    gap:10px;
                    margin-bottom:8px;
                  "
                >
                  <div>
                    <span class="kicker">AI LINGUISTIC ANALYSIS</span>

                    <h4
                      style="
                        margin:2px 0 0 0;
                        font-size:13px;
                        color:var(--text-main);
                      "
                    >
                      AI-assisted observable writing comparison
                    </h4>
                  </div>

                  <span class="badge green">
                    ${esc(aiProvider)}
                  </span>
                </div>

                ${
                  aiSummary
                    ? `
                      <p
                        style="
                          margin:0 0 12px 0;
                          font-size:12px;
                          color:var(--text-sub);
                          line-height:1.6;
                        "
                      >
                        ${esc(aiSummary)}
                      </p>
                    `
                    : ""
                }

                ${
                  sharedCharacteristics.length
                    ? `
                      <div style="margin-top:10px">
                        <strong
                          style="
                            font-size:11.5px;
                            color:var(--text-main);
                          "
                        >
                          Shared observable characteristics
                        </strong>

                        ${renderList(sharedCharacteristics)}
                      </div>
                    `
                    : ""
                }

                ${
                  differences.length
                    ? `
                      <div style="margin-top:12px">
                        <strong
                          style="
                            font-size:11.5px;
                            color:var(--text-main);
                          "
                        >
                          Distinguishing characteristics
                        </strong>

                        ${renderList(differences)}
                      </div>
                    `
                    : ""
                }

                <div
                  style="
                    margin-top:12px;
                    padding-top:9px;
                    border-top:1px solid var(--border-line);
                    font-size:10.5px;
                    color:var(--text-muted);
                    line-height:1.5;
                  "
                >
                  AI analysis describes observable linguistic
                  characteristics. It does not establish a person's identity
                  or authorship.
                </div>
              </div>
            `
            : `
              <div
                class="panel panel-pad"
                style="
                  margin-bottom:16px;
                  background:var(--bg-main);
                  border:1px solid var(--border-line);
                "
              >
                <span class="kicker">AI LINGUISTIC ANALYSIS</span>

                <h4
                  style="
                    margin:2px 0 6px 0;
                    font-size:13px;
                    color:var(--text-main);
                  "
                >
                  AI augmentation unavailable
                </h4>

                <p
                  style="
                    margin:0;
                    font-size:11.5px;
                    color:var(--text-sub);
                    line-height:1.55;
                  "
                >
                  The comparison response did not contain an AI linguistic
                  analysis. Classical stylometric results shown above are
                  retained. This does not mean that AI analysis failed; it
                  means no AI result was returned by the current Persona
                  service.
                </p>
              </div>
            `
        }

        <div
          class="panel panel-pad"
          style="
            background:var(--bg-main);
            border:1px solid var(--border-line);
          "
        >
          <h4
            style="
              margin:0 0 6px 0;
              font-size:12.5px;
              color:var(--text-main);
            "
          >
            Analytical Forensic Assessment
          </h4>

          <p
            style="
              margin:0;
              font-size:12px;
              color:var(--text-sub);
              line-height:1.6;
            "
          >
            ${esc(
              res.assessment ||
              res.summary ||
              (
                similarity !== null
                  ? `The supplied writing samples produced a measured stylistic similarity of ${similarity}%. Review the underlying evidence and source samples before drawing any attribution conclusion.`
                  : "The Persona service returned a comparison without a directly usable overall similarity score."
              )
            )}
          </p>

          <div
            style="
              margin-top:10px;
              padding-top:9px;
              border-top:1px solid var(--border-line);
              font-size:10.5px;
              color:var(--text-muted);
              line-height:1.5;
            "
          >
            Persona analysis is a decision-support signal. Similarity alone
            must not be presented as confirmed identity or proof of common
            authorship.
          </div>
        </div>
      `;

    } catch (err) {
      resultsEl.innerHTML = `
        <div class="error-state">
          <div class="error-icon">⚠️</div>
          Comparison failed: ${esc(err.message)}
        </div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "⚡ Execute Stylometric Comparison";
    }
  };
}

// ------------------------------------------------------------------
// 5. CRAWLER OPERATIONS (/web/crawl.html)
// ------------------------------------------------------------------
async function crawlPage() {
  const torBadge = document.getElementById("tor-status-badge");
  try {
    const health = await api("/api/health");
    if (torBadge) {
      const torOk = health.tor_proxy === true || health.tor === "ok" || health.tor_proxy === "ok";
      torBadge.textContent = torOk ? "TOR PROXY READY" : "TOR NOT CONNECTED";
      torBadge.className = `badge ${torOk ? "green" : "red"}`;
    }
  } catch(e) {
    if (torBadge) { torBadge.textContent = "STATUS UNKNOWN"; torBadge.className = "badge amber"; }
  }

  await loadCrawlJobs();

  const form = document.getElementById("crawl-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = document.getElementById("crawl-url")?.value?.trim();
    const username = document.getElementById("crawl-username")?.value?.trim() || "";
    const workers = parseInt(document.getElementById("crawl-workers")?.value || "2");

    if (!url) return;

    const liveSection = document.getElementById("live-session");
    const terminal = document.getElementById("crawl-terminal");
    const statusBadge = document.getElementById("crawl-status-badge");
    const invBadge = document.getElementById("crawl-inv-badge");

    if (liveSection) liveSection.classList.remove("hidden");
    if (terminal) terminal.innerHTML = `<span class="terminal-line info">[PRALAYX] Starting crawl: ${esc(url)}</span>\n`;
    if (statusBadge) { statusBadge.textContent = "RUNNING"; statusBadge.className = "badge amber"; }

    try {
      const payload = { urls: [url], workers };
      if (username) payload.target = username;

      const res = await api("/api/crawl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const jobId = res.job_id;
      const newInvId = res.investigation_id;

      if (terminal) terminal.innerHTML += `<span class="terminal-line success">[OK] Crawl job started: ${esc(jobId)}</span>\n`;
      if (terminal) terminal.innerHTML += `<span class="terminal-line info">[INFO] Investigation: ${esc(newInvId)}</span>\n`;
      if (invBadge && newInvId) invBadge.textContent = newInvId;

      if (jobId) await pollCrawlJob(jobId, terminal, statusBadge, newInvId);
      await loadCrawlJobs();
    } catch(err) {
      if (terminal) terminal.innerHTML += `<span class="terminal-line error">[ERROR] ${esc(err.message || String(err))}</span>\n`;
      if (statusBadge) { statusBadge.textContent = "ERROR"; statusBadge.className = "badge red"; }
    }
  });
}

async function pollCrawlJob(jobId, terminal, statusBadge, invId) {
  let attempts = 0;
  const maxAttempts = 90;
  const interval = 5000;
  let lastLogCount = 0;

  return new Promise((resolve) => {
    const tick = async () => {
      attempts++;
      try {
        const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
        const status = (job.status || "UNKNOWN").toUpperCase();
        const logs = job.log_lines || job.logs || [];
        if (logs.length > lastLogCount && terminal) {
          logs.slice(lastLogCount).forEach(line => {
            const cls = line.includes("[ERROR]") ? "error"
                      : line.includes("[+]") || line.includes("[SUCCESS]") ? "success"
                      : line.includes("[WARN]") ? "warn" : "info";
            terminal.innerHTML += `<span class="terminal-line ${cls}">${esc(line)}</span>\n`;
          });
          lastLogCount = logs.length;
          terminal.scrollTop = terminal.scrollHeight;
        }
        if (status === "COMPLETE" || status === "DONE" || status === "COMPLETED") {
          if (statusBadge) { statusBadge.textContent = "COMPLETE"; statusBadge.className = "badge green"; }
          if (terminal) terminal.innerHTML += `<span class="terminal-line success">[DONE] Crawl complete. Findings saved.</span>\n`;
          if (invId && terminal) terminal.innerHTML += `<span class="terminal-line data">[RESULT] <a href="/web/investigation.html?id=${encodeURIComponent(invId)}" style="color:var(--cyan)">Open Investigation Workspace →</a></span>\n`;
          resolve(); return;
        }
        if (status === "FAILED" || status === "ERROR") {
          if (statusBadge) { statusBadge.textContent = "FAILED"; statusBadge.className = "badge red"; }
          if (terminal) terminal.innerHTML += `<span class="terminal-line error">[FAILED] ${esc(job.error || "Unknown error")}</span>\n`;
          resolve(); return;
        }
        if (attempts < maxAttempts) setTimeout(tick, interval);
        else { if (statusBadge) { statusBadge.textContent = "TIMEOUT"; statusBadge.className = "badge amber"; } resolve(); }
      } catch(e) {
        if (terminal) terminal.innerHTML += `<span class="terminal-line warn">[WARN] ${esc(e.message)}</span>\n`;
        if (attempts < maxAttempts) setTimeout(tick, interval * 2);
        else resolve();
      }
    };
    setTimeout(tick, 2000);
  });
}

async function loadCrawlJobs() {
  const el = document.getElementById("crawl-jobs-list");
  const countEl = document.getElementById("crawl-jobs-count");
  if (!el) return;
  try {
    const data = await api("/api/jobs?type=crawl&limit=20");
    const jobs = data.jobs || (Array.isArray(data) ? data : []);
    if (countEl) countEl.textContent = `${jobs.length} JOBS`;
    el.innerHTML = jobs.length
      ? `<table class="table"><thead><tr><th>Job ID</th><th>Investigation</th><th>Status</th><th>Started</th><th>Actions</th></tr></thead><tbody>` +
        jobs.map(j => `<tr>
          <td><code style="font-size:11px;color:var(--cyan)">${esc(j.job_id||j.id||"")}</code></td>
          <td><code style="font-size:11px">${esc(j.investigation_id||"")}</code></td>
          <td>${renderStatus(j.status)}</td>
          <td style="font-size:11px;color:var(--text-muted)">${esc((j.created_at||"").slice(0,16).replace("T"," "))}</td>
          <td>${j.investigation_id ? `<a href="/web/investigation.html?id=${encodeURIComponent(j.investigation_id)}" class="btn ghost sm">View</a>` : ""}</td>
        </tr>`).join("") + `</tbody></table>`
      : `<div class="empty">No crawl jobs yet. Submit a target URL above to begin.</div>`;
  } catch(e) {
    el.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>${esc(e.message)}</div>`;
  }
}

// ------------------------------------------------------------------
// 6. HIGHLY INTERACTIVE ATTRIBUTION GRAPH WORKSTATION
// ------------------------------------------------------------------
let globalGraphNodes = [];
let globalGraphEdges = [];

async function loadCaseGraph(invId, filterCategory = "all", searchQuery = "") {
  const container = document.getElementById("case-graph-container") || document.getElementById("graph-container");
  const detailsEl = document.getElementById("case-node-details") || document.getElementById("node-details-container");
  if (!container || !invId) return;

  try {
    const data = await api(`/api/investigations/${encodeURIComponent(invId)}/graph`);
    globalGraphNodes = data.nodes || [];
    globalGraphEdges = data.edges || [];

    if (globalGraphNodes.length <= 1) {
      container.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;min-height:360px;color:var(--text-muted);padding:40px;text-align:center">
          <div style="font-size:36px;margin-bottom:12px">🕸️</div>
          <strong style="font-size:14px;color:var(--text-main)">No relationship data available for this investigation</strong>
          <p style="font-size:12px;margin-top:6px;max-width:400px">Run a dark web crawl or OSINT scan to extract technical observables, handles, TLS certificates, and cryptocurrency wallets to populate the attribution network.</p>
        </div>`;
      return;
    }

    renderFilteredGraph(container, detailsEl, filterCategory, searchQuery);
  } catch(e) {
    container.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>Failed to load relationship graph: ${esc(e.message)}</div>`;
  }
}

function renderFilteredGraph(container, detailsEl, filterCategory, searchQuery) {
  let nodes = globalGraphNodes;
  let edges = globalGraphEdges;

  if (filterCategory && filterCategory !== "all") {
    nodes = nodes.filter(n => {
      const cat = (n.category || n.type || "").toLowerCase();
      if (filterCategory === "technical") return cat.includes("tls") || cat.includes("server") || cat.includes("ip") || cat.includes("infra") || cat.includes("domain");
      if (filterCategory === "entity") return cat.includes("actor") || cat.includes("crypto") || cat.includes("wallet") || cat.includes("target");
      if (filterCategory === "persona") return cat.includes("handle") || cat.includes("username") || cat.includes("persona") || cat.includes("stylometry");
      return true;
    });
    const nodeIds = new Set(nodes.map(n => n.id));
    edges = edges.filter(e => {
      const s = typeof e.source === 'object' ? e.source.id : e.source;
      const t = typeof e.target === 'object' ? e.target.id : e.target;
      return nodeIds.has(s) && nodeIds.has(t);
    });
  }

  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    nodes = nodes.map(n => ({
      ...n,
      highlighted: (n.label || n.id || "").toLowerCase().includes(q)
    }));
  }

  renderInteractiveCanvasGraph(container, detailsEl, nodes, edges);
}

function renderInteractiveCanvasGraph(container, detailsEl, nodes, edges) {
  container.innerHTML = "";

  // Overlay Toolbar (Zoom Controls + Reset + Help)
  const toolbar = document.createElement("div");
  toolbar.style.cssText = "position:absolute;top:12px;right:12px;z-index:20;display:flex;gap:6px;background:rgba(15,23,42,0.85);backdrop-filter:blur(4px);padding:6px;border-radius:6px;border:1px solid #334155";
  toolbar.innerHTML = `
    <button id="graph-btn-zoom-in" class="btn ghost sm" style="color:#e2e8f0;font-size:13px;padding:2px 8px" title="Zoom In">🔍 +</button>
    <button id="graph-btn-zoom-out" class="btn ghost sm" style="color:#e2e8f0;font-size:13px;padding:2px 8px" title="Zoom Out">🔍 -</button>
    <button id="graph-btn-reset" class="btn ghost sm" style="color:#e2e8f0;font-size:11px;padding:2px 8px" title="Reset View">⌖ Reset</button>
    <span id="graph-zoom-label" style="font-size:11px;color:#94a3b8;align-self:center;padding:0 4px">100%</span>
  `;
  container.appendChild(toolbar);

  const canvas = document.createElement("canvas");
  canvas.width = container.clientWidth || 800;
  canvas.height = container.clientHeight || 560;
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  canvas.style.display = "block";
  canvas.style.cursor = "grab";
  container.appendChild(canvas);

  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  // Viewport transformation state
  let scale = 1.0;
  let panX = 0;
  let panY = 0;

  // Dragging state
  let isPanning = false;
  let startPanX = 0;
  let startPanY = 0;
  let draggedNode = null;
  let hoveredNode = null;
  let selectedNodeId = null;

  const nodeRadius = 20;
  const pos = {};

  // Layout node coordinates
  nodes.forEach((node, idx) => {
    const angle = (idx / Math.max(1, nodes.length)) * 2 * Math.PI;
    const r = Math.min(width, height) * 0.32;
    pos[node.id] = {
      x: width / 2 + r * Math.cos(angle) + (Math.random() - 0.5) * 20,
      y: height / 2 + r * Math.sin(angle) + (Math.random() - 0.5) * 20,
      node: node
    };
    if (node.type === "target") {
      pos[node.id].x = width / 2;
      pos[node.id].y = height / 2;
    }
  });

  function getNodeStyle(type) {
    const t = String(type || "").toLowerCase();
    if (t === "target") return { color: "#3b82f6", icon: "🎯", stroke: "#60a5fa" };
    if (t === "actor") return { color: "#ef4444", icon: "👤", stroke: "#f87171" };
    if (t === "handle" || t === "username") return { color: "#06b6d4", icon: "🏷️", stroke: "#22d3ee" };
    if (t.includes("crypto") || t.includes("btc") || t.includes("xmr") || t.includes("wallet")) return { color: "#f59e0b", icon: "₿", stroke: "#fbbf24" };
    if (t.includes("tls") || t.includes("server") || t.includes("banner") || t.includes("ip")) return { color: "#a855f7", icon: "🖥️", stroke: "#c084fc" };
    return { color: "#10b981", icon: "🔍", stroke: "#34d399" };
  }

  // Basic relaxation layout
  for (let iter = 0; iter < 90; iter++) {
    const keys = Object.keys(pos);
    for (let i = 0; i < keys.length; i++) {
      for (let j = i + 1; j < keys.length; j++) {
        const n1 = pos[keys[i]];
        const n2 = pos[keys[j]];
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        if (dist < 160) {
          const force = (160 - dist) / dist * 0.12;
          n1.x -= dx * force; n1.y -= dy * force;
          n2.x += dx * force; n2.y += dy * force;
        }
      }
    }
    edges.forEach(edge => {
      const sKey = typeof edge.source === 'object' ? edge.source.id : edge.source;
      const tKey = typeof edge.target === 'object' ? edge.target.id : edge.target;
      const p1 = pos[sKey];
      const p2 = pos[tKey];
      if (p1 && p2) {
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (dist - 130) * 0.04;
        p1.x += dx / dist * force; p1.y += dy / dist * force;
        p2.x -= dx / dist * force; p2.y -= dy / dist * force;
      }
    });
    keys.forEach(k => {
      const p = pos[k];
      p.x = Math.max(nodeRadius + 20, Math.min(width - nodeRadius - 20, p.x));
      p.y = Math.max(nodeRadius + 20, Math.min(height - nodeRadius - 20, p.y));
    });
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.translate(panX, panY);
    ctx.scale(scale, scale);

    // 1. Draw Edges
    edges.forEach(edge => {
      const sKey = typeof edge.source === 'object' ? edge.source.id : edge.source;
      const tKey = typeof edge.target === 'object' ? edge.target.id : edge.target;
      const p1 = pos[sKey];
      const p2 = pos[tKey];
      if (p1 && p2) {
        const isConnectedToHover = hoveredNode && (sKey === hoveredNode.id || tKey === hoveredNode.id);
        const isConnectedToSelect = selectedNodeId && (sKey === selectedNodeId || tKey === selectedNodeId);

        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = isConnectedToHover || isConnectedToSelect ? "#38bdf8" : (edge.type === "persona_lead" ? "#f59e0b" : "#334155");
        ctx.lineWidth = isConnectedToHover || isConnectedToSelect ? 2.5 : 1.5;
        if (edge.type === "persona_lead") ctx.setLineDash([5, 5]);
        else ctx.setLineDash([]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label with dark background pill
        if (edge.label) {
          const mx = (p1.x + p2.x) / 2;
          const my = (p1.y + p2.y) / 2;
          ctx.font = "9px Inter, sans-serif";
          ctx.textAlign = "center";
          ctx.fillStyle = isConnectedToHover || isConnectedToSelect ? "#e2e8f0" : "#64748b";
          ctx.fillText(edge.label, mx, my - 3);
        }
      }
    });

    // 2. Draw Nodes
    Object.keys(pos).forEach(k => {
      const p = pos[k];
      const node = p.node;
      const style = getNodeStyle(node.type);
      const isSelected = selectedNodeId === node.id;
      const isHovered = hoveredNode === node;
      const isHighlight = node.highlighted;

      // Glow behind selected/hovered nodes
      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, nodeRadius + 8, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(56, 189, 248, 0.25)";
        ctx.fill();
      }

      // Outer border circle
      ctx.beginPath();
      ctx.arc(p.x, p.y, isSelected || isHovered ? nodeRadius + 3 : nodeRadius, 0, 2 * Math.PI);
      ctx.fillStyle = style.color;
      ctx.fill();
      ctx.strokeStyle = isSelected || isHovered ? "#ffffff" : style.stroke;
      ctx.lineWidth = isSelected || isHovered ? 3 : 2;
      ctx.stroke();

      // Icon inside circle
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#ffffff";
      ctx.fillText(style.icon, p.x, p.y);

      // Label with dark outline for readability
      const labelText = node.label || node.id;
      ctx.font = isSelected || isHovered ? "bold 11px Inter, sans-serif" : "10.5px Inter, sans-serif";
      ctx.textBaseline = "alphabetic";
      ctx.strokeStyle = "#060d19";
      ctx.lineWidth = 3;
      ctx.strokeText(labelText, p.x, p.y + nodeRadius + 14);
      ctx.fillStyle = isSelected || isHovered ? "#38bdf8" : "#f1f5f9";
      ctx.fillText(labelText, p.x, p.y + nodeRadius + 14);
    });

    ctx.restore();
  }

  draw();

  // Helper to map client mouse to canvas coordinates
  function getCanvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    const clientX = (e.clientX - rect.left) * (canvas.width / rect.width);
    const clientY = (e.clientY - rect.top) * (canvas.height / rect.height);
    const x = (clientX - panX) / scale;
    const y = (clientY - panY) / scale;
    return { x, y, clientX, clientY };
  }

  function findNodeUnder(x, y) {
    let found = null;
    Object.keys(pos).forEach(k => {
      const p = pos[k];
      const dx = x - p.x;
      const dy = y - p.y;
      if (Math.sqrt(dx * dx + dy * dy) <= nodeRadius + 4) {
        found = p.node;
      }
    });
    return found;
  }

  // Mouse Interaction: Dragging & Panning
  canvas.addEventListener("mousedown", e => {
    const { x, y, clientX, clientY } = getCanvasCoords(e);
    const hit = findNodeUnder(x, y);

    if (hit) {
      draggedNode = hit;
      canvas.style.cursor = "grabbing";
    } else {
      isPanning = true;
      startPanX = clientX - panX;
      startPanY = clientY - panY;
      canvas.style.cursor = "move";
    }
  });

  canvas.addEventListener("mousemove", e => {
    const { x, y, clientX, clientY } = getCanvasCoords(e);

    if (draggedNode) {
      pos[draggedNode.id].x = x;
      pos[draggedNode.id].y = y;
      draw();
    } else if (isPanning) {
      panX = clientX - startPanX;
      panY = clientY - startPanY;
      draw();
    } else {
      const hit = findNodeUnder(x, y);
      if (hit !== hoveredNode) {
        hoveredNode = hit;
        canvas.style.cursor = hit ? "pointer" : "grab";
        draw();
      }
    }
  });

  window.addEventListener("mouseup", () => {
    draggedNode = null;
    isPanning = false;
    canvas.style.cursor = "grab";
  });

  // Node Selection on Click
  canvas.addEventListener("click", e => {
    const { x, y } = getCanvasCoords(e);
    const hit = findNodeUnder(x, y);

    if (hit) {
      selectedNodeId = hit.id;
      draw();
      if (detailsEl) {
        detailsEl.innerHTML = `
          <div style="background:var(--bg-dark);padding:14px;border-radius:6px;border:1px solid var(--border-line)">
            <span class="badge blue" style="font-size:10px">${esc(hit.type || "node").toUpperCase()}</span>
            <h3 style="margin:8px 0 4px 0;font-size:14px;color:var(--text-main)">${esc(hit.label || hit.id)}</h3>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">ID: <code>${esc(hit.id)}</code></div>
            ${hit.confidence != null ? `<div style="margin-bottom:6px"><span class="badge green">Attribution Confidence: ${Math.round(hit.confidence * 100)}%</span></div>` : ''}
            ${hit.source ? `<div style="font-size:11.5px;color:var(--text-sub)">Provenance: <strong>${esc(hit.source)}</strong></div>` : ''}
          </div>`;
      }
    }
  });

  // Zooming with Mouse Wheel
  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const newScale = Math.min(2.5, Math.max(0.4, scale * zoomFactor));

    const { clientX, clientY } = getCanvasCoords(e);
    panX = clientX - (clientX - panX) * (newScale / scale);
    panY = clientY - (clientY - panY) * (newScale / scale);
    scale = newScale;

    const zoomLbl = document.getElementById("graph-zoom-label");
    if (zoomLbl) zoomLbl.textContent = `${Math.round(scale * 100)}%`;
    draw();
  }, { passive: false });

  // Toolbar Button Handlers
  const btnIn = document.getElementById("graph-btn-zoom-in");
  const btnOut = document.getElementById("graph-btn-zoom-out");
  const btnReset = document.getElementById("graph-btn-reset");
  const zoomLbl = document.getElementById("graph-zoom-label");

  if (btnIn) btnIn.onclick = () => {
    scale = Math.min(2.5, scale * 1.2);
    if (zoomLbl) zoomLbl.textContent = `${Math.round(scale * 100)}%`;
    draw();
  };

  if (btnOut) btnOut.onclick = () => {
    scale = Math.max(0.4, scale / 1.2);
    if (zoomLbl) zoomLbl.textContent = `${Math.round(scale * 100)}%`;
    draw();
  };

  if (btnReset) btnReset.onclick = () => {
    scale = 1.0;
    panX = 0;
    panY = 0;
    if (zoomLbl) zoomLbl.textContent = `100%`;
    draw();
  };
}

async function correlationPage() {
  const invId = new URLSearchParams(location.search).get("id") || "";
  const caseSelect = document.getElementById("graph-case-select");

  if (caseSelect) {
    try {
      const data = await api("/api/investigations");
      const list = data.investigations || (Array.isArray(data) ? data : []);
      caseSelect.innerHTML = `<option value="">Select an Investigation</option>` + list.map(i => {
        const id = i.investigation_id || i.id;
        const sel = id === invId ? 'selected' : '';
        return `<option value="${esc(id)}" ${sel}>${esc(id)} — ${esc(i.target || "Target")}</option>`;
      }).join("");

      caseSelect.addEventListener("change", e => {
        const newId = e.target.value;
        if (newId) window.location.href = `/web/correlation.html?id=${encodeURIComponent(newId)}`;
      });
    } catch(e) { /* ignore */ }
  }

  const filterBtns = document.querySelectorAll(".graph-filter");
  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b => { b.classList.remove("primary"); b.classList.add("ghost"); });
      btn.classList.add("primary");
      btn.classList.remove("ghost");
      const cat = btn.dataset.filter || "all";
      const q = document.getElementById("graph-search-input")?.value?.trim() || "";
      const container = document.getElementById("graph-container");
      const detailsEl = document.getElementById("node-details-container");
      if (container) renderFilteredGraph(container, detailsEl, cat, q);
    });
  });

  const searchInput = document.getElementById("graph-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", e => {
      const q = e.target.value.trim();
      const activeFilter = document.querySelector(".graph-filter.primary")?.dataset?.filter || "all";
      const container = document.getElementById("graph-container");
      const detailsEl = document.getElementById("node-details-container");
      if (container) renderFilteredGraph(container, detailsEl, activeFilter, q);
    });
  }

  if (invId) {
    loadCaseGraph(invId);
  } else {
    try {
      const data = await api("/api/investigations");
      const list = data.investigations || (Array.isArray(data) ? data : []);
      if (list.length > 0) {
        const firstId = list[0].investigation_id || list[0].id;
        if (caseSelect) caseSelect.value = firstId;
        loadCaseGraph(firstId);
      } else {
        const container = document.getElementById("graph-container");
        if (container) {
          container.innerHTML = `
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;min-height:360px;color:var(--text-muted);padding:40px;text-align:center">
              <div style="font-size:36px;margin-bottom:12px">🔍</div>
              <strong style="font-size:14px;color:var(--text-main)">Select an Investigation to View Graph</strong>
              <p style="font-size:12px;margin-top:6px">Choose an investigation from the dropdown above to render its correlation network.</p>
            </div>`;
        }
      }
    } catch(e) {}
  }
}

// ------------------------------------------------------------------
// 7. INVESTIGATIONS LIST PAGE (/web/investigations.html)
// ------------------------------------------------------------------
async function investigationsListPage() {
  const tbody = document.getElementById("inv-tbody");
  const countEl = document.getElementById("inv-count");
  const searchInput = document.getElementById("inv-search-input");
  if (!tbody) return;

  let allInvestigations = [];

  const renderTable = (list) => {
    tbody.innerHTML = list.length
      ? list.map(inv => {
          const id = inv.investigation_id || inv.id || "—";
          const statusCls = (inv.status || "").toLowerCase() === "completed" ? "green"
                          : (inv.status || "").toLowerCase() === "running" ? "blue" : "amber";
          return `<tr>
            <td><code style="font-size:12px;color:var(--cyan)">${esc(id)}</code></td>
            <td><strong style="font-size:12px;color:var(--text-main)">${esc(inv.target || "—")}</strong></td>
            <td><span class="badge ${statusCls}">${esc((inv.status || "UNKNOWN").toUpperCase())}</span></td>
            <td style="font-size:11px;color:var(--text-muted)">${esc(inv.source || inv.initiated_by || "—")}</td>
            <td style="font-size:11px;color:var(--text-muted)">${esc((inv.created_at || "").slice(0,16).replace("T"," "))}</td>
            <td style="font-size:11px;color:var(--text-muted)">${esc((inv.updated_at || "").slice(0,16).replace("T"," "))}</td>
            <td><a href="/web/investigation.html?id=${encodeURIComponent(id)}" class="btn primary sm">Open Workspace →</a></td>
          </tr>`;
        }).join("")
      : `<tr><td colspan="7" class="empty">No investigations found. Create one above to begin.</td></tr>`;
  };

  try {
    const data = await api("/api/investigations");
    allInvestigations = data.investigations || (Array.isArray(data) ? data : []);
    if (countEl) countEl.textContent = `${allInvestigations.length} CASES`;
    renderTable(allInvestigations);
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="7" class="error-state"><div class="error-icon">⚠️</div>${esc(e.message)}</td></tr>`;
  }

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase();
      const filtered = allInvestigations.filter(inv =>
        (inv.investigation_id || inv.id || "").toLowerCase().includes(q) ||
        (inv.target || "").toLowerCase().includes(q) ||
        (inv.status || "").toLowerCase().includes(q)
      );
      renderTable(filtered);
    });
  }

  const newBtn = document.getElementById("btn-new-investigation");
  const newForm = document.getElementById("new-inv-form");
  if (newBtn && newForm) {
    newBtn.addEventListener("click", () => newForm.classList.toggle("hidden"));
  }

  const createBtn = document.getElementById("btn-create-investigation");
  if (createBtn) {
    createBtn.addEventListener("click", async () => {
      const target = document.getElementById("new-inv-target")?.value?.trim();
      const notes = document.getElementById("new-inv-notes")?.value?.trim() || "";
      const mode = document.getElementById("new-inv-mode")?.value || "investigation";
      const errEl = document.getElementById("new-inv-error");

      if (!target) {
        if (errEl) { errEl.textContent = "Target is required."; errEl.classList.remove("hidden"); }
        return;
      }
      if (errEl) errEl.classList.add("hidden");

      createBtn.disabled = true;
      createBtn.textContent = "Creating...";

      try {
        let endpoint = "/api/investigate";
        let payload = { target, target_type: "url", notes };
        if (mode === "crawl") {
          endpoint = "/api/crawl";
          payload = { urls: [target], target, workers: 2 };
        }

        const res = await api(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const newId = res.investigation_id;
        if (newId) window.location.href = `/web/investigation.html?id=${encodeURIComponent(newId)}`;
      } catch(err) {
        createBtn.disabled = false;
        createBtn.textContent = "Create";
        if (errEl) { errEl.textContent = `Error: ${err.message}`; errEl.classList.remove("hidden"); }
      }
    });
  }
}

// ------------------------------------------------------------------
// 8. THREAT ACTORS REGISTRY (/web/actors.html)
// ------------------------------------------------------------------
async function threatActorsPage() {
  const tbody = document.querySelector("#threat-actors-tbody");
  const countEl = document.querySelector("#actor-count-text");
  const searchInput = document.querySelector("#actor-search-input");
  if (!tbody) return;

  try {
    const data = await api("/api/actors");
    let actors = data.actors || [];

    const renderTable = (list) => {
      if (countEl) countEl.textContent = `${list.length} THREAT ACTORS TRACKED`;
      tbody.innerHTML = list.length
        ? list.map(a => {
            const handlesBadge = (a.handles || []).length
              ? a.handles.map(h => `<span class="badge blue" style="margin:2px 2px 2px 0;font-size:10px">${esc(h)}</span>`).join("")
              : `<span style="font-size:11px;color:var(--text-muted)">—</span>`;

            const walletsBadge = (a.wallets || []).length
              ? a.wallets.map(w => `<code style="font-size:10.5px;color:var(--cyan);display:block;margin-bottom:2px">${esc(w)}</code>`).join("")
              : `<span style="font-size:11px;color:var(--text-muted)">—</span>`;

            const invId = a.investigation_id || "—";

            return `<tr>
              <td><code style="font-size:11px;color:var(--blue)">${esc(a.actor_id || "ACT-UNKNOWN")}</code></td>
              <td>
                <strong style="font-size:13px;color:var(--text-main);display:block">${esc(a.display_name || "Unknown Actor")}</strong>
                <span class="badge ${a.confidence > 0.7 ? "green" : "amber"}" style="font-size:9.5px;margin-top:2px">${esc((a.category || "unknown").toUpperCase())} • ${Math.round((a.confidence || 0.5) * 100)}%</span>
              </td>
              <td><div style="max-width:220px;overflow:hidden">${handlesBadge}</div></td>
              <td><div style="max-width:220px;overflow:hidden">${walletsBadge}</div></td>
              <td style="font-size:11px;color:var(--text-muted)">${esc((a.created_at || "").slice(0, 10) || "—")}</td>
              <td>
                <div style="display:flex;gap:4px;flex-wrap:wrap">
                  ${invId !== "—" ? `<a href="/web/investigation.html?id=${encodeURIComponent(invId)}" class="btn primary sm">Open Case →</a>` : ""}
                  ${invId !== "—" ? `<a href="/web/correlation.html?id=${encodeURIComponent(invId)}" class="btn ghost sm">⌘ Graph</a>` : ""}
                  <button class="btn ghost sm" onclick="watchActor('${esc(a.display_name)}', '${esc(invId)}')">+ Watch</button>
                </div>
              </td>
            </tr>`;
          }).join("")
        : `<tr><td colspan="6" class="empty-state">No threat actor profiles registered in database.</td></tr>`;
    };

    renderTable(actors);

    if (searchInput) {
      searchInput.oninput = (e) => {
        const q = e.target.value.toLowerCase().trim();
        if (!q) { renderTable(actors); return; }
        const filtered = actors.filter(a =>
          (a.display_name || "").toLowerCase().includes(q) ||
          (a.actor_id || "").toLowerCase().includes(q) ||
          (a.category || "").toLowerCase().includes(q) ||
          (a.handles || []).some(h => h.toLowerCase().includes(q)) ||
          (a.wallets || []).some(w => w.toLowerCase().includes(q))
        );
        renderTable(filtered);
      };
    }
  } catch(e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="error-state">${esc(e.message)}</td></tr>`;
  }
}

window.watchActor = async function(actorName) {
  if (!actorName) return;
  try {
    await api("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: actorName, interval_minutes: 60 })
    });
    alert(`Threat Actor '${actorName}' added to active surveillance watchlist!`);
  } catch(e) {
    alert(`Could not add to watchlist: ${e.message}`);
  }
};

// ------------------------------------------------------------------
// 9. MONITORING PAGE (/web/monitoring.html)
// ------------------------------------------------------------------
async function monitoringPage() {
  const mList = document.getElementById("monitoring-list");
  const aList = document.getElementById("alerts-list");
  if (!mList && !aList) return;

  const addBtn = document.getElementById("btn-add-watch");
  if (addBtn && !addBtn.dataset.wired) {
    addBtn.dataset.wired = "true";
    addBtn.onclick = async () => {
      const target = prompt("Enter Target to Monitor (Darknet .onion URL, Threat Actor handle, or Domain):");
      if (!target) return;
      const intervalStr = prompt("Enter surveillance interval in minutes (default: 60):", "60");
      const interval = parseInt(intervalStr) || 60;
      try {
        await api("/api/watchlist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target: target.trim(), interval_minutes: interval })
        });
        alert(`Target '${target}' successfully added to continuous surveillance watchlist!`);
        monitoringPage();
      } catch(err) {
        alert(`Failed to add watchlist item: ${err.message}`);
      }
    };
  }

  const invId = new URLSearchParams(location.search).get("id") || "";
  try {
    const md = await api(`/api/monitoring${invId ? `?investigation_id=${encodeURIComponent(invId)}` : ""}`).catch(() => ({ watchlist: [] }));
    const ad = await api(`/api/alerts${invId ? `?investigation_id=${encodeURIComponent(invId)}` : ""}`).catch(() => ({ alerts: [] }));
    const wl = md.watchlist || [];
    const al = ad.alerts || [];

    if (mList) {
      mList.innerHTML = wl.length
        ? wl.map(w => `
          <div style="padding:10px;border-bottom:1px solid var(--border-line);display:flex;justify-content:space-between;align-items:center">
            <div>
              <strong style="font-size:12.5px;color:var(--text-main)">${esc(w.target_url || w.target || "—")}</strong>
              <div style="font-size:11px;color:var(--text-muted)">Interval: ${w.interval_minutes || 60}m • Last: ${esc((w.last_scan_at || "Never").slice(0, 16).replace("T", " "))}</div>
            </div>
            <div style="display:flex;gap:6px;align-items:center">
              ${renderStatus(w.status)}
              <button class="btn ghost sm" onclick="triggerWatchScan('${esc(w.watch_id)}', this)">Scan</button>
            </div>
          </div>`).join("")
        : `<div class="empty">No targets on watchlist. Click '+ Add Watch Target' to add one.</div>`;
    }

    if (aList) {
      aList.innerHTML = al.length
        ? al.map(a => `
          <div style="padding:10px;border-bottom:1px solid var(--border-line)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
              <span class="badge red">${esc(a.severity || "HIGH")}</span>
              <span style="font-size:10px;color:var(--text-muted)">${esc((a.created_at || "").slice(0, 16).replace("T", " "))}</span>
            </div>
            <strong style="font-size:12px;color:var(--text-main)">${esc(a.alert_type || "Alert")}</strong>
            <div style="font-size:11.5px;color:var(--text-sub);margin-top:2px">${esc(a.message || "")}</div>
          </div>`).join("")
        : `<div class="empty">No security trigger alerts recorded.</div>`;
    }
  } catch(e) { /* non-critical */ }
}

// ------------------------------------------------------------------
// 10. EVIDENCE VAULT (/web/findings.html)
// ------------------------------------------------------------------
async function findingsPage() {
  const tbody = document.getElementById("findings-tbody");
  const countEl = document.getElementById("vault-count");
  if (!tbody) return;

  const invId = new URLSearchParams(location.search).get("id") || "";
  try {
    const endpoint = invId
      ? `/api/investigations/${encodeURIComponent(invId)}/findings`
      : "/api/findings?limit=200";
    const data = await api(endpoint);
    const findings = data.findings || (Array.isArray(data) ? data : []);
    if (countEl) countEl.textContent = `${findings.length} ARTIFACTS ${invId ? `[CASE: ${invId}]` : '[GLOBAL]'}`;

    tbody.innerHTML = findings.length
      ? findings.map(f => `<tr>
          <td><code style="font-size:11px;color:var(--cyan)">${esc(f.evidence_id || f.finding_id || "EVD-" + Math.abs(hashCode(f.value || "")))}</code></td>
          <td><a href="/web/investigation.html?id=${encodeURIComponent(f.investigation_id || invId)}" class="badge blue" style="font-size:10px">${esc(f.investigation_id || invId || "—")}</a></td>
          <td><span class="badge ${typeBadgeClass(f.finding_type || f.type)}">${esc(f.finding_type || f.type || "finding")}</span></td>
          <td><strong style="font-size:12px;color:var(--text-main)">${esc(f.value || f.finding_value || "")}</strong></td>
          <td><span class="badge ${parseFloat(f.confidence||0)>0.7?"green":"amber"}">${Math.round((parseFloat(f.confidence)||0.5)*100)}%</span></td>
          <td style="font-size:11px;color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis">${esc(f.source_url || f.source || "Dark Web")}</td>
          <td style="font-size:11px;color:var(--text-muted)">${esc((f.created_at || f.evidence_collected_at || "").slice(0, 16).replace("T", " "))}</td>
        </tr>`).join("")
      : `<tr><td colspan="7" class="empty">No forensic artifacts in evidence vault.</td></tr>`;
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="7" class="error-state">${esc(e.message)}</td></tr>`;
  }
}

// ------------------------------------------------------------------
// 11. REPORTS & DOSSIERS EXPORT (/web/reports.html)
// ------------------------------------------------------------------
async function reportsPage() {
  const invId = new URLSearchParams(location.search).get("id") || "";
  if (invId) {
    const pdf = document.getElementById("export-pdf");
    const html = document.getElementById("export-html");
    const json = document.getElementById("export-json");
    const csv = document.getElementById("export-csv");
    if (pdf) pdf.href = `/api/export/${encodeURIComponent(invId)}/pdf`;
    if (html) html.href = `/api/export/${encodeURIComponent(invId)}/html`;
    if (json) json.href = `/api/export/${encodeURIComponent(invId)}/json`;
    if (csv) csv.href = `/api/export/${encodeURIComponent(invId)}/csv`;
  }

  const reportsList = document.getElementById("reports-list");
  if (reportsList) {
    try {
      const data = await api("/api/investigations");
      const list = data.investigations || (Array.isArray(data) ? data : []);
      reportsList.innerHTML = list.length
        ? `<table class="table"><thead><tr><th>Case ID</th><th>Target</th><th>Status</th><th>PDF Dossier</th><th>Evidence Package</th></tr></thead><tbody>` +
          list.map(i => {
            const id = i.investigation_id || i.id;
            return `<tr>
              <td><code>${esc(id)}</code></td>
              <td><strong>${esc(i.target || "—")}</strong></td>
              <td>${renderStatus(i.status)}</td>
              <td><a href="/api/export/${encodeURIComponent(id)}/pdf" class="btn primary sm">Download PDF</a></td>
              <td><a href="/api/reports/download-package/${encodeURIComponent(id)}" class="btn secondary sm">ZIP Package</a></td>
            </tr>`;
          }).join("") + `</tbody></table>`
        : `<div class="empty">No archived reports available.</div>`;
    } catch(e) {
      reportsList.innerHTML = `<div class="error-state">${esc(e.message)}</div>`;
    }
  }
}

// ------------------------------------------------------------------
// 12. GLOBAL BOOTSTRAP
// ------------------------------------------------------------------
function boot() {
  initShell();
  const p = location.pathname;

  if (p.endsWith("index.html") || p === "/" || p.endsWith("/web/")) dashboard();
  else if (p.includes("investigation.html")) investigationPage();
  else if (p.includes("investigations.html")) investigationsListPage();
  else if (p.includes("osint.html")) osintPage();
  else if (p.includes("crawl.html")) crawlPage();
  else if (p.includes("correlation.html")) correlationPage();
  else if (p.includes("stylometry.html")) stylometryPage();
  else if (p.includes("actors.html")) threatActorsPage();
  else if (p.includes("monitoring.html")) monitoringPage();
  else if (p.includes("findings.html")) findingsPage();
  else if (p.includes("reports.html")) reportsPage();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
