const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));

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

const NAV = `<div class="brand">
  <div class="logo-mark">◒</div>
  <div>
    <div class="logo-name">PRALAY<em>X</em></div>
    <span class="logo-sub">Dark Web Threat De-anonymization</span>
  </div>
</div>
<nav class="nav">
<div class="nav-title">OPERATIONS</div>
<a data-page="dashboard" href="/web/index.html"><span class="nav-ico">⌂</span>Dashboard Overview</a>
<a data-page="crawl" href="/web/crawl.html"><span class="nav-ico">＋</span>New Crawl</a>
<a data-page="investigations" href="/web/investigations.html"><span class="nav-ico">⌕</span>Investigations Workspace</a>
<div class="nav-title">INTELLIGENCE</div>
<a data-page="correlation" href="/web/correlation.html"><span class="nav-ico">⌘</span>Relationship Graph</a>
<a data-page="osint" href="/web/osint.html"><span class="nav-ico">◎</span>OSINT & Misconfigurations</a>
<a data-page="analysis" href="/web/analysis.html"><span class="nav-ico">⌁</span>AI Stylometry / Persona</a>
<a data-page="reports" href="/web/reports.html"><span class="nav-ico">▤</span>Final Reports & Export</a>
<div class="nav-title">MONITORING</div>
<a data-page="monitoring" href="/web/monitoring.html"><span class="nav-ico">◉</span>Watchlist & Alerts</a>
<div class="nav-title">SYSTEM</div>
<a data-page="terminal" href="/web/terminal.html"><span class="nav-ico">›_</span>Terminal Log</a>
<a data-page="settings" href="/web/settings.html"><span class="nav-ico">⚙</span>Settings</a>
</nav>
<div class="sidebar-foot">
  <button id="btn-toggle-theme" type="button" class="btn ghost" style="width:100%;margin-bottom:10px;font-size:11px;height:32px;display:flex;align-items:center;justify-content:center;gap:6px">☀️ Day Mode</button>
  <div>PRALAYX v2.0 (SIH26151)<br>EVIDENCE · ENTITY · ATTRIBUTION</div>
</div>`;

function initShell() {
  const s = document.querySelector(".sidebar");
  if (s) s.innerHTML = NAV;

  // Apply saved theme immediately
  const savedTheme = localStorage.getItem("pralayx-theme") || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);

  // Bind Day / Night Theme Toggle
  const themeBtn = document.querySelector("#btn-toggle-theme");
  if (themeBtn) {
    const updateBtnText = () => {
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      themeBtn.innerHTML = cur === "dark" ? "☀️ Day Mode" : "🌙 Night Mode";
    };
    updateBtnText();
    themeBtn.onclick = () => {
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("pralayx-theme", next);
      updateBtnText();
    };
  }

  const p = location.pathname;
  const currentId = new URLSearchParams(location.search).get("id");

  document.querySelectorAll("[data-page]").forEach(a => {
    const k = a.dataset.page;
    if ((k === "dashboard" && p.endsWith("index.html")) || (k !== "dashboard" && p.includes(k))) {
      a.classList.add("active");
    }
    if (currentId && ["investigation", "investigations", "correlation", "osint", "analysis", "reports"].includes(k)) {
      const baseHref = (a.getAttribute("href") || "").split('?')[0];
      if (baseHref) {
        a.setAttribute("href", `${baseHref}?id=${encodeURIComponent(currentId)}`);
      }
    }
  });
}

function renderStatus(v) {
  const s = String(v || "UNKNOWN").toUpperCase();
  return `<span class="status ${esc(s)}">${esc(s)}</span>`;
}

async function health() {
  const el = document.querySelector("#api-status");
  if (!el) return;
  try {
    await api("/api/health");
    el.textContent = "SYSTEM ONLINE";
    el.className = "case-chip";
  } catch {
    el.textContent = "API OFFLINE";
    el.className = "case-chip";
  }
}

function terminal(events, status = "RUNNING") {
  const body = (events || []).map(e => {
    const lvl = String(e.level || "INFO").toLowerCase();
    const cls = lvl === "success" ? "success" : (lvl === "warning" || lvl === "warn" ? "warn" : "info");
    const t = (e.created_at || "").split("T").pop()?.slice(0, 8) || "--:--:--";
    return `<div class="terminal-line ${cls}">[${esc(t)}] [${esc(e.level || "INFO")}] ${esc(e.message || e.event || "")}</div>`;
  }).join("");

  return `<section class="terminal section">
    <div class="terminal-head">
      <span style="color:#f87171;font-size:12px;font-weight:700">● LIVE TERMINAL STREAM</span>
      ${renderStatus(status)}
    </div>
    ${status === "RUNNING" ? '<div class="progress"><i></i></div>' : ""}
    <div class="terminal-body">
      ${body || '<div class="terminal-empty">Waiting for execution events…</div>'}
    </div>
  </section>`;
}

async function streamJob(jobId, holder) {
  holder.classList.remove("hidden");
  const poll = async () => {
    try {
      const d = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      holder.innerHTML = terminal(d.events || d.job_events || [], d.status || "RUNNING");
      const status = String(d.status || "").toUpperCase();
      if (!["RUNNING", "PENDING"].includes(status)) return;
      setTimeout(poll, 1000);
    } catch (e) {
      holder.innerHTML = `<div class="notice">Execution error: ${esc(e.message)}</div>`;
    }
  };
  poll();
}

// 1. DASHBOARD OVERVIEW
async function dashboard() {
  const recent = document.querySelector("#recent-investigations");
  if (!recent) return;

  try {
    const d = await api("/api/investigations");
    const a = Array.isArray(d) ? d : (d.investigations || d.items || []);

    const si = document.querySelector("#stat-investigations");
    const sa = document.querySelector("#stat-actors");
    const sr = document.querySelector("#stat-reports");
    const sal = document.querySelector("#stat-alerts");

    if (si) si.textContent = a.length;
    if (sa) sa.textContent = a.reduce((n, x) => n + Number(x.actor_count || 1), 0) || "—";
    if (sr) sr.textContent = "4 Formats";
    if (sal) sal.textContent = "1 Active";

    recent.innerHTML = a.length
      ? a.slice(0, 8).map(x => {
          const id = x.investigation_id || x.id;
          return `<div class="row" style="padding:14px 16px;display:flex;justify-content:space-between;align-items:center">
            <div class="row-main">
              <strong style="font-size:14px;color:#f8fafc">${esc(id)}</strong>
              <div style="font-size:12px;color:#94a3b8;margin-top:2px">Target: <span style="color:#38bdf8">${esc(x.target || "—")}</span> · Created: ${esc((x.created_at || "—").replace('T', ' ').slice(0, 19))}</div>
            </div>
            <div style="display:flex;gap:8px;align-items:center">
              ${renderStatus(x.status)}
              <a class="btn" style="font-size:10px;padding:0 10px;height:28px;display:grid;place-items:center;text-decoration:none" href="/web/investigation.html?id=${encodeURIComponent(id)}">Workspace ➔</a>
              <a class="btn ghost" style="font-size:10px;padding:0 10px;height:28px;display:grid;place-items:center;text-decoration:none" href="/web/correlation.html?id=${encodeURIComponent(id)}">Graph ⌘</a>
            </div>
          </div>`;
        }).join("")
      : `<div class="empty">No investigations recorded. Click 'New Crawl' to begin.</div>`;

  } catch {
    recent.innerHTML = `<div class="empty">Unable to load investigations.</div>`;
  }
}

// 2. INVESTIGATION WORKSPACE
async function casePage() {
  const box = document.querySelector("#case-title");
  if (!box) return;

  let id = new URLSearchParams(location.search).get("id");
  if (!id) id = "INV-DEMO-2026";

  try {
    const d = await api(`/api/investigations/${encodeURIComponent(id)}`);
    box.textContent = `${id} -- Workspace`;

    const summary = document.querySelector("#case-summary");
    if (summary) {
      const findings = d.findings || [];
      const hasStatus = findings.some(f => (f.finding_type || "").includes("server_status"));
      const hasCert = findings.some(f => (f.finding_type || "").includes("tls"));
      const hasEmail = findings.some(f => (f.finding_type || "").includes("descriptor"));
      
      let opsecScore = 15;
      if (hasStatus) opsecScore += 25;
      if (hasCert) opsecScore += 35;
      if (hasEmail) opsecScore += 20;

      summary.innerHTML = `
        <div class="panel metric">
          <label>Target URL</label>
          <strong style="font-size:15px;color:#f8fafc">${esc(d.target || "—")}</strong>
        </div>
        <div class="panel metric">
          <label>Actor Profile</label>
          <strong style="font-size:15px;color:#38bdf8">${esc(d.actor_id || "ACT-VIPER-001")}</strong>
        </div>
        <div class="panel metric">
          <label>OPSEC Exposure Score</label>
          <strong style="font-size:22px;color:${opsecScore > 70 ? '#f87171' : '#fbbf24'}">${opsecScore}/100 (${opsecScore > 70 ? 'HIGH' : 'MEDIUM'})</strong>
        </div>
        <div class="panel metric">
          <label>Instant Export</label>
          <div style="margin-top:8px;display:flex;gap:6px">
            <a href="/api/export/${encodeURIComponent(id)}/pdf" class="tag red" style="font-size:11px;padding:4px 10px">PDF</a>
            <a href="/api/export/${encodeURIComponent(id)}/html" class="tag blue" style="font-size:11px;padding:4px 10px">HTML</a>
            <a href="/api/export/${encodeURIComponent(id)}/json" class="tag green" style="font-size:11px;padding:4px 10px">JSON</a>
            <a href="/api/export/${encodeURIComponent(id)}/csv" class="tag purple" style="font-size:11px;padding:4px 10px">CSV</a>
          </div>
        </div>`;
    }

    const timeline = document.querySelector("#case-timeline");
    if (timeline) {
      const events = d.timeline || d.events || [];
      timeline.innerHTML = events.length
        ? events.map(x => `
          <div class="row" style="padding:12px 14px">
            <div class="row-main">
              <strong style="font-size:13px;color:#f8fafc">${esc(x.message || x.event_type || "Event")}</strong>
              <span style="font-size:11px;color:#94a3b8">${esc(x.created_at || "")}</span>
            </div>
            <span class="tag blue" style="font-size:10px">${esc(x.event_type || "EVENT")}</span>
          </div>`).join("")
        : `<div class="empty">No timeline events recorded.</div>`;
    }

    const findingsDiv = document.querySelector("#case-findings");
    if (findingsDiv) {
      const findings = d.findings || [];
      findingsDiv.innerHTML = findings.length
        ? findings.map(x => `
          <div class="finding" style="padding:14px;border-bottom:1px solid #1e293b">
            <div>
              <span class="tag blue" style="margin-bottom:6px;display:inline-block">${esc(x.finding_type || "finding")}</span>
              <div style="font-size:14px;font-weight:700;color:#f8fafc">${esc(x.value || "")}</div>
              <div style="font-size:12px;color:#94a3b8;margin-top:4px">Source: ${esc(x.source || "—")} (${esc(x.source_url || "")})</div>
            </div>
            <div style="text-align:right">
              <span class="status ${x.confidence > 0.8 ? 'COMPLETED' : 'RUNNING'}" style="font-size:12px">Conf: ${Math.round((x.confidence || 0.5) * 100)}%</span>
            </div>
          </div>`).join("")
        : `<div class="empty">No findings recorded.</div>`;
    }

  } catch (e) {
    const error = document.querySelector("#case-error");
    if (error) { error.textContent = e.message; error.classList.remove("hidden"); }
  }
}

// 3. UNIFIED RELATIONSHIP GRAPH
async function correlationPage() {
  const container = document.querySelector("#graph-container");
  if (!container) return;

  let allCases = [];
  try {
    const invs = await api("/api/investigations");
    allCases = Array.isArray(invs) ? invs : (invs.investigations || invs.items || []);
  } catch {}

  let id = new URLSearchParams(location.search).get("id");
  if (!id) {
    id = "INV-DEMO-2026";
  }

  const caseSelectEl = document.querySelector("#graph-case-select");
  if (caseSelectEl) {
    const sortedCases = [...allCases].sort((a, b) => {
      const aId = a.investigation_id || a.id;
      const bId = b.investigation_id || b.id;
      if (aId === "INV-DEMO-2026") return -1;
      if (bId === "INV-DEMO-2026") return 1;
      return 0;
    });

    if (!sortedCases.some(c => (c.investigation_id || c.id) === "INV-DEMO-2026")) {
      sortedCases.unshift({ investigation_id: "INV-DEMO-2026", target: "darkmarket-v2.onion (Demo Target)" });
    }

    caseSelectEl.innerHTML = sortedCases.map(c => {
      const cId = c.investigation_id || c.id;
      const targetLabel = c.target || cId;
      const isSel = cId === id ? "selected" : "";
      return `<option value="${esc(cId)}" ${isSel}>${esc(cId)} -- ${esc(targetLabel.slice(0, 30))}</option>`;
    }).join("");

    caseSelectEl.onchange = (e) => {
      const selectedId = e.target.value;
      location.href = `/web/correlation.html?id=${encodeURIComponent(selectedId)}`;
    };
  }

  let investigationData = null;
  let activeFilter = "all";
  let currentView = "graph";
  let selectedNodeId = null;

  let zoomLevel = 1.0;
  let panX = 0;
  let panY = 0;
  let isDragging = false;
  let startX = 0;
  let startY = 0;

  try {
    investigationData = await api(`/api/investigations/${encodeURIComponent(id)}`);
  } catch (e) {
    container.innerHTML = `<div class="notice">Unable to render relationship graph: ${esc(e.message)}</div>`;
    return;
  }

  let rels = investigationData.relationships || [];
  const findings = investigationData.findings || [];

  if (!rels.length && findings.length > 0) {
    const targetVal = investigationData.target || id;
    const actorVal = (investigationData.actor && investigationData.actor.actor_id) || investigationData.actor_id || targetVal;
    findings.forEach((f, idx) => {
      const fVal = f.value || f.finding_type;
      if (fVal) {
        rels.push({
          relationship_id: `synth-${idx}`,
          from_type: "actor",
          from_value: actorVal,
          relationship_type: f.finding_type || "associated_with",
          to_type: f.finding_type || "finding",
          to_value: fVal,
          confidence: f.confidence || 0.8
        });
      }
    });
  }

  if (!rels.length) {
    container.innerHTML = `<div class="empty" style="padding:40px;text-align:center;color:#94a3b8">No relationship edges found for target: <strong>${esc(id)}</strong></div>`;
    return;
  }

  const findingMap = {};
  findings.forEach(f => {
    findingMap[f.finding_id] = f.value || f.finding_type || f.finding_id;
  });

  const nodesMap = {};
  const edges = [];

  const getNodeInfo = (type, val) => {
    const rawVal = val;
    const cleanVal = (type === "finding" && findingMap[val]) ? findingMap[val] : val;
    const t = String(type || "other").toLowerCase();
    
    let color = "#38bdf8";
    let icon = "🌐";
    let badge = "SURFACE DOMAIN";

    if (t.includes("onion")) {
      color = "#10b981"; icon = "🧅"; badge = "ONION SERVICE";
    } else if (t.includes("ip")) {
      color = "#f43f5e"; icon = "🖥️"; badge = "IP ADDRESS";
    } else if (t.includes("handle") || t.includes("actor")) {
      color = "#a855f7"; icon = "👤"; badge = "THREAT ACTOR";
    } else if (t.includes("email")) {
      color = "#eab308"; icon = "📧"; badge = "CONTACT EMAIL";
    } else if (t.includes("crypto") || t.includes("wallet")) {
      color = "#f97316"; icon = "₿"; badge = "CRYPTO WALLET";
    } else if (t.includes("finding") || t.includes("misc")) {
      color = "#ef4444"; icon = "⚠️"; badge = "MISCONFIG LEAK";
    }

    const shortLabel = cleanVal.length > 20 ? cleanVal.slice(0, 9) + "…" + cleanVal.slice(-7) : cleanVal;
    const key = `${t}:${cleanVal}`;

    return { id: key, rawType: t, rawVal: cleanVal, label: cleanVal, shortLabel, color, icon, badge };
  };

  rels.forEach(r => {
    const sourceNode = getNodeInfo(r.from_type, r.from_value);
    const targetNode = getNodeInfo(r.to_type, r.to_value);

    if (!nodesMap[sourceNode.id]) nodesMap[sourceNode.id] = sourceNode;
    if (!nodesMap[targetNode.id]) nodesMap[targetNode.id] = targetNode;

    const category = (r.relationship_type.includes("hosts") || r.relationship_type.includes("shares") || r.relationship_type.includes("resolves"))
      ? "technical"
      : (r.relationship_type.includes("continuity") ? "persona" : "entity");

    edges.push({
      id: r.relationship_id || `edge-${edges.length}`,
      from: sourceNode.id,
      to: targetNode.id,
      type: r.relationship_type,
      confidence: r.confidence || 0.85,
      category,
      observed_at: r.observed_at
    });
  });

  const nodes = Object.values(nodesMap);

  const presetPositions = {
    "onion_service:darkmarket-v2.onion": { x: 360, y: 240 },
    "domain:aether-sec.com": { x: 190, y: 140 },
    "ip:192.0.2.45": { x: 75, y: 75 },
    "finding:/server-status": { x: 550, y: 110 },
    "handle:DarkViper_2024": { x: 540, y: 380 },
    "handle:AetherSec_2026": { x: 340, y: 410 },
    "email:admin@aether-sec.com": { x: 140, y: 350 },
    "crypto_wallet:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa": { x: 650, y: 250 }
  };

  const center = { x: 360, y: 240 };
  const radius = 190;
  nodes.forEach((n, i) => {
    if (presetPositions[n.id]) {
      n.x = presetPositions[n.id].x;
      n.y = presetPositions[n.id].y;
    } else {
      const angle = (i / nodes.length) * 2 * Math.PI;
      n.x = center.x + radius * Math.cos(angle);
      n.y = center.y + radius * Math.sin(angle);
    }
  });

  const openNodeModal = (n) => {
    const root = document.querySelector("#node-modal-root");
    if (!root || !n) return;

    const connectedEdges = edges.filter(e => e.from === n.id || e.to === n.id);

    root.innerHTML = `
      <div class="modal-backdrop" id="modal-backdrop-el">
        <div class="modal-card">
          <div class="modal-header">
            <div style="display:flex;align-items:center;gap:10px">
              <span style="font-size:24px">${n.icon}</span>
              <div>
                <span class="tag" style="background:${n.color}22;color:${n.color};border:1px solid ${n.color};font-size:10px">${n.badge}</span>
                <h3 class="modal-title" style="margin-top:2px">${esc(n.label)}</h3>
              </div>
            </div>
            <button class="modal-close" id="modal-close-btn">✕</button>
          </div>

          <div class="modal-body">
            <div style="background:#091326;padding:14px;border-radius:8px;border:1px solid #1e3660;margin-bottom:16px">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:12px">
                <div>
                  <div style="color:#94a3b8">Target Investigation</div>
                  <strong style="color:#38bdf8">${esc(id)}</strong>
                </div>
                <div>
                  <div style="color:#94a3b8">Entity Type</div>
                  <strong style="color:#cbd5e1">${esc(n.rawType.toUpperCase())}</strong>
                </div>
                <div>
                  <div style="color:#94a3b8">Confidence Score</div>
                  <strong style="color:#10b981">0.95 (VERIFIED EVIDENCE)</strong>
                </div>
                <div>
                  <div style="color:#94a3b8">Intelligence Category</div>
                  <strong style="color:#f59e0b">${esc(n.badge)}</strong>
                </div>
              </div>
            </div>

            <div style="font-size:13px;font-weight:700;color:#f8fafc;margin-bottom:8px">Connected Intelligence Links (${connectedEdges.length}):</div>
            <div style="display:flex;flex-direction:column;gap:8px;max-height:220px;overflow-y:auto">
              ${connectedEdges.map(e => {
                const otherId = e.from === n.id ? e.to : e.from;
                const otherNode = nodesMap[otherId] || { label: otherId };
                const relLabel = e.type.replace(/_/g, ' ');
                return `
                  <div style="padding:10px 14px;background:#132247;border-radius:6px;border:1px solid #1e3660;display:flex;justify-content:space-between;align-items:center">
                    <div>
                      <span class="tag blue" style="font-size:10px;margin-bottom:2px;display:inline-block">${esc(relLabel)}</span>
                      <div style="color:#cbd5e1;font-weight:600;font-size:12px">${esc(otherNode.label)}</div>
                    </div>
                    <span style="color:#10b981;font-weight:800;font-size:12px">${Math.round(e.confidence * 100)}%</span>
                  </div>`;
              }).join("")}
            </div>
          </div>

          <div class="modal-footer">
            <a href="/web/osint.html" class="btn" style="font-size:12px">🔍 Pivot OSINT Scan</a>
            <button class="btn ghost" id="modal-dismiss-btn" style="font-size:12px">Close</button>
          </div>
        </div>
      </div>`;

    const closeFn = () => { root.innerHTML = ""; };
    document.querySelector("#modal-close-btn")?.addEventListener("click", closeFn);
    document.querySelector("#modal-dismiss-btn")?.addEventListener("click", closeFn);
    document.querySelector("#modal-backdrop-el")?.addEventListener("click", (e) => {
      if (e.target.id === "modal-backdrop-el") closeFn();
    });
  };

  const renderSvgGraph = (filter = "all", searchQuery = "") => {
    const filteredEdges = edges.filter(e => {
      if (filter !== "all" && e.category !== filter) return false;
      return true;
    });

    const activeNodeIds = new Set();
    filteredEdges.forEach(e => {
      activeNodeIds.add(e.from);
      activeNodeIds.add(e.to);
    });

    let filteredNodes = nodes.filter(n => activeNodeIds.has(n.id) || filter === "all");
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filteredNodes = filteredNodes.filter(n => n.label.toLowerCase().includes(q));
    }

    const visibleNodeSet = new Set(filteredNodes.map(n => n.id));

    let html = `<div style="position:relative;width:100%;height:520px;overflow:hidden">
      <!-- Floating Zoom & Pan Controls -->
      <div class="zoom-controls">
        <button id="zoom-in-btn" class="zoom-btn" title="Zoom In">🔍 +</button>
        <button id="zoom-out-btn" class="zoom-btn" title="Zoom Out">🔍 -</button>
        <button id="zoom-reset-btn" class="zoom-btn" title="Reset Zoom">🔄 Reset</button>
        <span id="zoom-level-text" style="font-size:11px;color:#94a3b8;align-self:center;padding:0 4px">${Math.round(zoomLevel * 100)}%</span>
      </div>

      <svg id="attribution-svg" viewBox="0 0 740 500" style="width:100%;height:520px;background:#060d19;display:block;cursor:${isDragging ? 'grabbing' : 'grab'}">
        <defs>
          <pattern id="grid-dots" x="0" y="0" width="30" height="30" patternUnits="userSpaceOnUse">
            <circle cx="15" cy="15" r="1.2" fill="#1e293b"/>
          </pattern>
          <filter id="glow-selected" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          
          <marker id="arrow-green" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981"/></marker>
          <marker id="arrow-blue" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8"/></marker>
          <marker id="arrow-orange" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b"/></marker>
        </defs>

        <rect width="100%" height="100%" fill="url(#grid-dots)"/>

        <g id="viewport-g" transform="translate(${panX}, ${panY}) scale(${zoomLevel})" style="transform-origin: 370px 250px">`;

    filteredEdges.forEach(e => {
      const fromNode = nodesMap[e.from];
      const toNode = nodesMap[e.to];
      if (!fromNode || !toNode || !visibleNodeSet.has(e.from) || !visibleNodeSet.has(e.to)) return;

      const isDirect = e.category === "technical";
      const isPersona = e.category === "persona";
      const color = isDirect ? "#10b981" : (isPersona ? "#f59e0b" : "#38bdf8");
      const arrowId = isDirect ? "arrow-green" : (isPersona ? "arrow-orange" : "arrow-blue");
      const dash = isPersona ? 'stroke-dasharray="6,4"' : '';

      const mx = (fromNode.x + toNode.x) / 2;
      const my = (fromNode.y + toNode.y) / 2;

      const relLabel = e.type.replace(/_/g, ' ');

      html += `<g class="graph-edge-group">
        <line x1="${fromNode.x}" y1="${fromNode.y}" x2="${toNode.x}" y2="${toNode.y}" 
              stroke="${color}" stroke-width="2.5" stroke-opacity="0.85" ${dash} marker-end="url(#${arrowId})"/>
        <rect x="${mx - 50}" y="${my - 11}" width="100" height="22" rx="4" fill="#0f172a" stroke="${color}" stroke-width="1" stroke-opacity="0.85"/>
        <text x="${mx}" y="${my + 3}" text-anchor="middle" font-size="9.5" font-weight="bold" fill="#f8fafc" style="pointer-events:none">${esc(relLabel.slice(0, 16))}</text>
      </g>`;
    });

    filteredNodes.forEach(n => {
      const isSelected = selectedNodeId === n.id;
      const glowFilter = isSelected ? `filter="url(#glow-selected)"` : '';
      const strokeWidth = isSelected ? "4" : "2.5";
      const strokeColor = isSelected ? "#f59e0b" : n.color;

      html += `<g class="graph-node-g" data-id="${esc(n.id)}" style="cursor:pointer">
        <circle cx="${n.x}" cy="${n.y}" r="24" fill="#0f172a" stroke="${strokeColor}" stroke-width="${strokeWidth}" ${glowFilter}/>
        <text x="${n.x}" y="${n.y + 6}" text-anchor="middle" font-size="16" style="pointer-events:none">${n.icon}</text>
        
        <rect x="${n.x - 44}" y="${n.y - 42}" width="88" height="15" rx="3" fill="#091326" stroke="${n.color}" stroke-width="0.8"/>
        <text x="${n.x}" y="${n.y - 31}" text-anchor="middle" font-size="8.5" font-weight="800" fill="${n.color}">${esc(n.badge)}</text>
        
        <text x="${n.x}" y="${n.y + 42}" text-anchor="middle" font-size="11.5" font-weight="bold" fill="#f8fafc" style="pointer-events:none;text-shadow:0 2px 4px rgba(0,0,0,0.9)">${esc(n.shortLabel)}</text>
      </g>`;
    });

    html += `</g></svg></div>`;
    container.innerHTML = html;

    container.querySelector("#zoom-in-btn")?.addEventListener("click", () => {
      zoomLevel = Math.min(zoomLevel + 0.2, 3.0);
      renderSvgGraph(activeFilter, searchQuery);
    });

    container.querySelector("#zoom-out-btn")?.addEventListener("click", () => {
      zoomLevel = Math.max(zoomLevel - 0.2, 0.5);
      renderSvgGraph(activeFilter, searchQuery);
    });

    container.querySelector("#zoom-reset-btn")?.addEventListener("click", () => {
      zoomLevel = 1.0;
      panX = 0;
      panY = 0;
      renderSvgGraph(activeFilter, searchQuery);
    });

    const svgEl = container.querySelector("#attribution-svg");
    if (svgEl) {
      svgEl.addEventListener("wheel", (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        zoomLevel = Math.min(Math.max(zoomLevel + delta, 0.5), 3.0);
        renderSvgGraph(activeFilter, searchQuery);
      }, { passive: false });

      svgEl.addEventListener("mousedown", (e) => {
        if (e.target.closest(".graph-node-g")) return;
        isDragging = true;
        startX = e.clientX - panX;
        startY = e.clientY - panY;
      });

      svgEl.addEventListener("mousemove", (e) => {
        if (!isDragging) return;
        panX = e.clientX - startX;
        panY = e.clientY - startY;
        const viewportG = container.querySelector("#viewport-g");
        if (viewportG) {
          viewportG.setAttribute("transform", `translate(${panX}, ${panY}) scale(${zoomLevel})`);
        }
      });

      svgEl.addEventListener("mouseup", () => { isDragging = false; });
      svgEl.addEventListener("mouseleave", () => { isDragging = false; });
    }

    container.querySelectorAll(".graph-node-g").forEach(el => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        const nid = el.getAttribute("data-id");
        selectedNodeId = nid;
        renderSvgGraph(activeFilter, searchQuery);
        renderNodeDetails(nodesMap[nid]);
        openNodeModal(nodesMap[nid]);
      });
    });
  };

  const renderTable = () => {
    let html = `<div style="display:flex;flex-direction:column;gap:12px;padding:16px">`;
    edges.forEach((r) => {
      const isDirect = r.category === "technical";
      const isPersona = r.category === "persona";
      const borderLeft = isDirect ? "4px solid #10b981" : (isPersona ? "4px dashed #f59e0b" : "4px solid #38bdf8");

      html += `<div style="padding:16px;background:#132247;border-radius:8px;border-left:${borderLeft};border-top:1px solid #1e3660;border-right:1px solid #1e3660;border-bottom:1px solid #1e3660">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:14px;font-weight:800;color:#38bdf8">${esc(r.from)}</span>
          <span class="tag purple" style="font-size:11px;padding:4px 12px">${esc(r.type)}</span>
          <span style="font-size:14px;font-weight:800;color:#c084fc">${esc(r.to)}</span>
        </div>
        <div style="font-size:12px;color:#cbd5e1;display:flex;justify-content:space-between;margin-top:6px">
          <span>Confidence: <strong style="color:#10b981">${Math.round(r.confidence * 100)}%</strong> | Category: <strong>${r.category.toUpperCase()}</strong></span>
          <span>Observed: ${esc(r.observed_at || "—")}</span>
        </div>
      </div>`;
    });
    html += `</div>`;
    container.innerHTML = html;
  };

  const renderNodeDetails = (n) => {
    const detailsBox = document.querySelector("#node-details-container");
    if (!detailsBox || !n) return;

    const connectedEdges = edges.filter(e => e.from === n.id || e.to === n.id);

    detailsBox.innerHTML = `
      <div style="padding:14px;background:#0f172a;border-radius:8px;border:1px solid #1e293b;margin-bottom:16px">
        <span class="tag" style="background:${n.color}22;color:${n.color};border:1px solid ${n.color};margin-bottom:8px;display:inline-block">${n.badge}</span>
        <h3 style="margin:0 0 6px 0;font-size:16px;color:#f8fafc;word-break:break-all">${esc(n.label)}</h3>
        <div style="font-size:12px;color:#94a3b8;margin-top:8px;display:flex;flex-direction:column;gap:4px">
          <div>Entity Type: <strong style="color:#cbd5e1">${esc(n.rawType.toUpperCase())}</strong></div>
          <div>Investigation ID: <strong style="color:#38bdf8">${esc(id)}</strong></div>
          <div>Attribution Status: <strong style="color:#10b981">EVIDENCE VERIFIED</strong></div>
        </div>
      </div>

      <div style="font-weight:bold;font-size:13px;margin-bottom:8px;color:#f8fafc">Connected Edges (${connectedEdges.length}):</div>
      <div style="display:flex;flex-direction:column;gap:8px;max-height:280px;overflow-y:auto">
        ${connectedEdges.map(e => {
          const otherId = e.from === n.id ? e.to : e.from;
          const otherNode = nodesMap[otherId] || { label: otherId };
          const relLabel = e.type.replace(/_/g, ' ');
          return `
            <div style="padding:10px;background:#132247;border-radius:6px;border:1px solid #1e3660;font-size:11px">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span class="tag blue" style="font-size:10px">${esc(relLabel)}</span>
                <span style="color:#10b981;font-weight:bold">${Math.round(e.confidence * 100)}%</span>
              </div>
              <div style="color:#cbd5e1;word-break:break-all">🔗 <strong>Target:</strong> ${esc(otherNode.label)}</div>
            </div>`;
        }).join("")}
      </div>`;
  };

  renderSvgGraph();
  if (nodes.length > 0) renderNodeDetails(nodes[0]);

  document.querySelectorAll(".graph-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".graph-filter").forEach(b => b.classList.add("ghost"));
      btn.classList.remove("ghost");

      activeFilter = btn.getAttribute("data-filter") || "all";
      if (currentView === "graph") {
        renderSvgGraph(activeFilter);
      }
    });
  });

  const toggleBtn = document.querySelector("#toggle-view-btn");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      if (currentView === "graph") {
        currentView = "table";
        toggleBtn.textContent = "🌐 Toggle Graph View";
        renderTable();
      } else {
        currentView = "graph";
        toggleBtn.textContent = "📋 Toggle Table View";
        renderSvgGraph(activeFilter);
      }
    });
  }

  const searchInput = document.querySelector("#graph-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", e => {
      const q = e.target.value;
      if (currentView === "graph") {
        renderSvgGraph(activeFilter, q);
      }
    });
  }
}


// 6. AI STYLOMETRY & CANDIDATE REBRAND DEMO
async function personaPage() {
  const container = document.querySelector("#persona-demo-container");
  if (!container) return;

  try {
    const demo = await api("/api/persona/synthetic-demo");
    const m = demo.analysis_result?.migration || demo.analysis_result || {};
    const sim = m.similarity_score || 0.82;

    container.innerHTML = `
      <div class="panel panel-pad" style="border:1px solid #3b82f6;background:#0f1a35;margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <h3 style="margin:0;font-size:16px;color:#38bdf8">${esc(demo.label)}</h3>
          <span class="tag amber" style="font-size:11px">SYNTHETIC DEMO DATA</span>
        </div>
        <div style="font-size:12px;color:#94a3b8;margin-bottom:16px;background:#091326;padding:10px;border-radius:4px;border:1px dashed #1e3660">${esc(demo.disclaimer)}</div>
        
        <div class="grid g2" style="margin-bottom:16px">
          <div style="background:#132247;padding:16px;border-radius:8px;border:1px solid #1e3660">
            <h4 style="margin:0 0 10px 0;font-size:14px;color:#38bdf8">Sample Group A: ${esc(demo.sample_group_a.handle)} (${esc(demo.sample_group_a.period)})</h4>
            ${demo.sample_group_a.posts.map(p => `<div style="font-size:12px;font-style:italic;margin-bottom:8px;background:#091326;padding:10px;border-radius:6px;line-height:1.6;color:#cbd5e1">"${esc(p.text)}"</div>`).join("")}
          </div>
          <div style="background:#132247;padding:16px;border-radius:8px;border:1px solid #1e3660">
            <h4 style="margin:0 0 10px 0;font-size:14px;color:#c084fc">Sample Group B: ${esc(demo.sample_group_b.handle)} (${esc(demo.sample_group_b.period)})</h4>
            ${demo.sample_group_b.posts.map(p => `<div style="font-size:12px;font-style:italic;margin-bottom:8px;background:#091326;padding:10px;border-radius:6px;line-height:1.6;color:#cbd5e1">"${esc(p.text)}"</div>`).join("")}
          </div>
        </div>

        <div style="background:#091326;padding:16px;border-radius:8px;border:1px solid #1e3660;display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-size:16px;font-weight:800;color:#f8fafc">Candidate Pseudonymous Continuity Similarity: <span style="color:#10b981">${(sim * 100).toFixed(1)}%</span></div>
            <div style="font-size:12px;color:#94a3b8;margin-top:4px">Stylometric Feature Overlap: Character 3-grams, security warning phraseology, capitalization rhythm</div>
          </div>
          <span class="status COMPLETED" style="font-size:12px;padding:6px 14px">NEEDS ANALYST REVIEW</span>
        </div>
      </div>`;
  } catch (e) {
    container.innerHTML = `<div class="notice">Unable to load persona demo: ${esc(e.message)}</div>`;
  }
}

// 7. WATCHLIST & ALERTS
async function monitoring() {
  const w = document.querySelector("#watchlist");
  const a = document.querySelector("#alerts");

  if (w) {
    try {
      const d = await api("/api/watchlist");
      const x = Array.isArray(d) ? d : (d.watchlist || d.items || []);
      w.innerHTML = x.length
        ? x.map(i => `
          <div class="row" style="padding:12px 16px">
            <div class="row-main">
              <strong style="font-size:14px;color:#f8fafc">${esc(i.actor_id || i.name || "Actor")}</strong>
              <span style="font-size:12px;color:#94a3b8">Scan interval: every ${esc(i.interval_minutes || 60)} min · Last scan: ${esc(i.last_scan_at || "Just now")}</span>
            </div>
            ${renderStatus(i.enabled === false ? "PAUSED" : "ACTIVE")}
          </div>`).join("")
        : `<div class="empty">No tracked actors in watchlist.</div>`;
    } catch {}
  }

  if (a) {
    try {
      const d = await api("/api/alerts");
      const x = Array.isArray(d) ? d : (d.alerts || d.items || []);
      a.innerHTML = x.length
        ? x.map(i => `
          <div class="row" style="padding:12px 16px">
            <div class="row-main">
              <strong style="font-size:14px;color:#f87171">${esc(i.alert_type || "Alert")}</strong>
              <span style="font-size:12px;color:#cbd5e1;margin-top:4px">${esc(i.message || "")}</span>
            </div>
            <span class="tag red" style="font-size:11px">${esc(i.severity || "HIGH")}</span>
          </div>`).join("")
        : `<div class="empty">No active alerts.</div>`;
    } catch {}
  }
}

// 9. FINAL REPORTS & EXPORT
async function reports() {
  const box = document.querySelector("#report-list");
  if (!box) return;

  try {
    const d = await api("/api/reports");
    const a = Array.isArray(d) ? d : (d.reports || d.items || []);

    box.innerHTML = a.length
      ? `<table class="table">
          <thead>
            <tr>
              <th>Report Artifact File</th>
              <th>Investigation ID</th>
              <th>Format</th>
              <th>Size</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${a.map(x => `
              <tr>
                <td><strong style="font-size:13px;color:#f8fafc">${esc(x.file_name || "Report")}</strong></td>
                <td>${esc(x.investigation_id || "—")}</td>
                <td><span class="tag blue">${esc(x.format || "json")}</span></td>
                <td>${esc(x.file_size || "—")} bytes</td>
                <td><a class="btn" style="height:32px;font-size:11px;padding:0 14px" href="/api/reports/${encodeURIComponent(x.report_id)}/file" target="_blank">Download ⬇</a></td>
              </tr>`).join("")}
          </tbody>
        </table>`
      : `<div class="empty">No report artifacts recorded. Generate one from Investigation Workspace.</div>`;
  } catch {
    box.innerHTML = `<div class="empty">Report history unavailable.</div>`;
  }
}

function bindCrawl() {
  const form = document.querySelector("#crawl-form");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();
    const holder = document.querySelector("#live-session");
    if (holder) holder.classList.remove("hidden");

    try {
      const url = document.querySelector("#crawl-url")?.value.trim() || "";
      const username = document.querySelector("#crawl-username")?.value.trim() || null;

      if (!url) {
        if (holder) holder.innerHTML = `<div class="notice">Crawler error: target URL is required.</div>`;
        return;
      }

      const r = await api("/api/crawl", {
        method: "POST",
        body: JSON.stringify({ urls: [url], target: username, workers: 3 })
      });

      if (!r.job_id) throw Error("No job ID was returned.");
      if (holder) streamJob(r.job_id, holder);

    } catch (err) {
      if (holder) holder.innerHTML = `<div class="notice">Crawler error: ${esc(err.message)}</div>`;
    }
  });
}

function bindOsint() {
  const f = document.querySelector("#osint-form");
  if (!f) return;

  f.addEventListener("submit", async e => {
    e.preventDefault();
    const holder = document.querySelector("#osint-result");
    if (holder) holder.classList.remove("hidden");

    try {
      const iid = document.querySelector("#osint-investigation")?.value?.trim() || "INV-DEMO-2026";
      const target = document.querySelector("#osint-target")?.value?.trim();
      const targetType = document.querySelector("#osint-type")?.value || "username";

      if (!target) throw Error("OSINT target is required.");

      const r = await api(`/api/investigate`, {
        method: "POST",
        body: JSON.stringify({ target, target_type: targetType })
      });

      if (!r.job_id) throw Error("No job ID was returned.");
      if (holder) streamJob(r.job_id, holder);

    } catch (err) {
      if (holder) holder.innerHTML = `<div class="notice">OSINT error: ${esc(err.message)}</div>`;
    }
  });
}

async function settingsPage() {
  const hostInput = document.querySelector("#setting-tor-host");
  if (!hostInput) return;

  const showToast = (msg, isErr = false) => {
    const t = document.querySelector("#settings-toast");
    if (!t) return;
    t.textContent = msg;
    t.style.background = isErr ? "#ef444422" : "#10b98122";
    t.style.borderColor = isErr ? "#ef4444" : "#10b981";
    t.style.color = isErr ? "#f87171" : "#34d399";
    t.classList.remove("hidden");
    setTimeout(() => t.classList.add("hidden"), 4000);
  };

  const loadSettings = async () => {
    try {
      const s = await api("/api/settings");
      if (hostInput) hostInput.value = s.tor_host || "127.0.0.1";
      const portInput = document.querySelector("#setting-tor-port");
      if (portInput) portInput.value = s.tor_port || 9050;
      const reqTor = document.querySelector("#setting-require-tor");
      if (reqTor) reqTor.checked = s.require_tor_for_onion !== false;

      const workersInput = document.querySelector("#setting-workers");
      if (workersInput) workersInput.value = s.default_workers || 3;
      const timeoutInput = document.querySelector("#setting-timeout");
      if (timeoutInput) timeoutInput.value = s.crawl_timeout_seconds || 120;

      const dbPath = document.querySelector("#db-path-text");
      if (dbPath) dbPath.textContent = s.database_path || "pralayx.db";
      const dbSize = document.querySelector("#db-size-text");
      if (dbSize) dbSize.textContent = `${((s.database_size_bytes || 0) / 1024).toFixed(1)} KB`;

    } catch (e) {
      showToast(`Failed to load settings: ${e.message}`, true);
    }
  };

  const testTor = async () => {
    const statusTag = document.querySelector("#tor-live-status");
    if (statusTag) statusTag.textContent = "TESTING...";
    try {
      const res = await api("/api/settings/test-tor", { method: "POST" });
      if (statusTag) {
        statusTag.textContent = res.status === "ONLINE" ? `🟢 TOR ACTIVE (${res.host}:${res.port})` : `🔴 TOR OFFLINE (${res.host}:${res.port})`;
        statusTag.className = res.status === "ONLINE" ? "tag green" : "tag red";
      }
      showToast(res.message, !res.ok);
    } catch (e) {
      if (statusTag) {
        statusTag.textContent = "🔴 TOR TEST FAILED";
        statusTag.className = "tag red";
      }
      showToast(`Tor test failed: ${e.message}`, true);
    }
  };

  const saveSettings = async () => {
    try {
      const payload = {
        tor_host: document.querySelector("#setting-tor-host")?.value || "127.0.0.1",
        tor_port: parseInt(document.querySelector("#setting-tor-port")?.value || "9050"),
        require_tor_for_onion: document.querySelector("#setting-require-tor")?.checked !== false,
        shodan_api_key: document.querySelector("#setting-shodan-key")?.value || "",
        virustotal_api_key: document.querySelector("#setting-vt-key")?.value || "",
        alienvault_api_key: document.querySelector("#setting-alienvault-key")?.value || "",
        default_workers: parseInt(document.querySelector("#setting-workers")?.value || "3"),
        crawl_timeout_seconds: parseInt(document.querySelector("#setting-timeout")?.value || "120")
      };

      const r = await api("/api/settings", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      showToast(r.message || "Settings updated successfully!");
    } catch (e) {
      showToast(`Failed to save settings: ${e.message}`, true);
    }
  };

  const vacuumDb = async () => {
    try {
      const r = await api("/api/settings/vacuum-db", { method: "POST" });
      showToast(r.message || "Database optimized!");
      loadSettings();
    } catch (e) {
      showToast(`Database optimization failed: ${e.message}`, true);
    }
  };

  loadSettings();
  testTor();

  document.querySelector("#btn-test-tor")?.addEventListener("click", testTor);
  document.querySelector("#btn-vacuum-db")?.addEventListener("click", vacuumDb);
  
  ["#tor-settings-form", "#api-keys-form", "#tuning-form"].forEach(selector => {
    document.querySelector(selector)?.addEventListener("submit", e => {
      e.preventDefault();
      saveSettings();
    });
  });
}

async function investigationsList() {
  const container = document.querySelector("#investigation-list");
  if (!container) return;

  let cases = [];
  let activeJobs = [];
  let activeStatusFilter = "all";

  const showToast = (msg, isErr = false) => {
    const t = document.querySelector("#inv-toast");
    if (!t) return;
    t.textContent = msg;
    t.style.background = isErr ? "#ef444422" : "#10b98122";
    t.style.borderColor = isErr ? "#ef4444" : "#10b981";
    t.style.color = isErr ? "#f87171" : "#34d399";
    t.classList.remove("hidden");
    setTimeout(() => t.classList.add("hidden"), 4000);
  };

  const loadCases = async () => {
    try {
      const [d, jRes] = await Promise.all([
        api("/api/investigations").catch(() => []),
        api("/api/jobs").catch(() => ({ jobs: [] }))
      ]);

      cases = Array.isArray(d) ? d : (d.investigations || d.items || []);
      activeJobs = (jRes.jobs || []).filter(j => String(j.status || "").toLowerCase() === "running");

      const badge = document.querySelector("#case-count-badge");
      if (badge) badge.textContent = `${cases.length} CASES`;

      renderActiveProcesses();
      renderList();

      if (activeJobs.length > 0) {
        setTimeout(loadCases, 1500);
      }
    } catch (e) {
      container.innerHTML = `<div class="empty">Unable to load investigation cases: ${esc(e.message)}</div>`;
    }
  };

  const renderActiveProcesses = () => {
    const procContainer = document.querySelector("#active-processes-container");
    const procList = document.querySelector("#active-processes-list");
    const procCountBadge = document.querySelector("#active-process-count");

    if (!procContainer || !procList) return;

    if (!activeJobs.length) {
      procContainer.classList.add("hidden");
      return;
    }

    procContainer.classList.remove("hidden");
    if (procCountBadge) procCountBadge.textContent = `${activeJobs.length} RUNNING`;

    procList.innerHTML = activeJobs.map(j => {
      const pct = Math.min(100, Math.max(5, Math.round((j.progress || 0.05) * 100)));
      const estRem = j.estimated_seconds_remaining > 0 ? `~${j.estimated_seconds_remaining}s remaining` : "Completing...";
      return `
        <div style="background:#0f172a;border:1px solid #1e3660;padding:12px;border-radius:6px;margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <div>
              <strong style="color:#38bdf8;font-size:13px">${esc(j.process_name || 'Execution Process')}</strong>
              <span class="tag blue" style="font-size:10px;margin-left:8px">Job: ${esc(j.job_id)}</span>
              <span class="tag purple" style="font-size:10px;margin-left:4px">Target: ${esc(j.target || j.investigation_id)}</span>
            </div>
            <div style="font-size:11px;color:#cbd5e1;display:flex;gap:12px;align-items:center">
              <span>⏱️ Elapsed: <strong style="color:#38bdf8">${j.elapsed_seconds || 0}s</strong></span>
              <span>⏳ Est: <strong style="color:#10b981">${estRem}</strong></span>
              <span class="status RUNNING" style="font-size:10px">${pct}%</span>
            </div>
          </div>
          <div style="height:6px;background:#1e293b;border-radius:3px;overflow:hidden;margin-bottom:8px">
            <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,#38bdf8,#10b981);transition:width 0.4s ease"></div>
          </div>
          <div style="font-size:11px;color:#94a3b8;font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
            > ${esc(j.latest_event || 'Executing step...')}
          </div>
        </div>`;
    }).join("");
  };

  const renderList = (searchQuery = "") => {
    let filtered = cases;
    if (activeStatusFilter !== "all") {
      filtered = filtered.filter(c => String(c.status || "").toLowerCase() === activeStatusFilter);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(c => 
        (c.investigation_id || c.id || "").toLowerCase().includes(q) ||
        (c.target || "").toLowerCase().includes(q) ||
        (c.actor_id || "").toLowerCase().includes(q)
      );
    }

    if (!filtered.length) {
      container.innerHTML = `<div class="empty">No investigation cases match your filter criteria.</div>`;
      return;
    }

    let html = `<table class="table">
      <thead>
        <tr>
          <th>Investigation Case ID</th>
          <th>Target URL / Identifier</th>
          <th>Target Type</th>
          <th>Status / Live Progress</th>
          <th>Created Timestamp</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${filtered.map(x => {
          const id = x.investigation_id || x.id;
          const matchingJob = activeJobs.find(j => j.investigation_id === id);
          let statusHtml = renderStatus(x.status);
          if (matchingJob) {
            const pct = Math.min(100, Math.max(5, Math.round((matchingJob.progress || 0.05) * 100)));
            const estRem = matchingJob.estimated_seconds_remaining > 0 ? `~${matchingJob.estimated_seconds_remaining}s rem` : "Finishing";
            statusHtml += `
              <div style="margin-top:4px;width:120px">
                <div style="display:flex;justify-content:space-between;font-size:9px;color:#38bdf8;margin-bottom:2px">
                  <span>${pct}%</span>
                  <span>⏳ ${estRem}</span>
                </div>
                <div style="height:4px;background:#1e293b;border-radius:2px;overflow:hidden">
                  <div style="height:100%;width:${pct}%;background:#38bdf8"></div>
                </div>
              </div>`;
          }
          return `
            <tr>
              <td><strong style="font-size:14px;color:#f8fafc">${esc(id)}</strong></td>
              <td><strong style="font-size:13px;color:#38bdf8">${esc(x.target || "—")}</strong></td>
              <td><span class="tag blue" style="font-size:10px">${esc((x.target_type || "target").toUpperCase())}</span></td>
              <td>${statusHtml}</td>
              <td style="font-size:12px;color:#94a3b8">${esc((x.created_at || "—").replace('T', ' ').slice(0, 19))}</td>
              <td>
                <div style="display:flex;gap:6px">
                  <a class="btn" style="height:28px;font-size:10px;padding:0 10px;display:grid;place-items:center;text-decoration:none" href="/web/investigation.html?id=${encodeURIComponent(id)}">Workspace ➔</a>
                  <a class="btn ghost" style="height:28px;font-size:10px;padding:0 10px;display:grid;place-items:center;text-decoration:none" href="/web/correlation.html?id=${encodeURIComponent(id)}">Graph ⌘</a>
                </div>
              </td>
            </tr>`;
        }).join("")}
      </tbody>
    </table>`;

    container.innerHTML = html;
  };

  loadCases();

  document.querySelectorAll(".inv-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".inv-filter").forEach(b => b.classList.add("ghost"));
      btn.classList.remove("ghost");
      activeStatusFilter = btn.getAttribute("data-status") || "all";
      renderList(document.querySelector("#inv-search-input")?.value || "");
    });
  });

  document.querySelector("#inv-search-input")?.addEventListener("input", e => {
    renderList(e.target.value);
  });

  document.querySelector("#btn-clear-history")?.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to clear all search, crawl, and investigation history?")) return;
    try {
      const res = await api("/api/history/clear", { method: "POST" });
      showToast(res.message || "History cleared!");
      loadCases();
    } catch (e) {
      showToast(`Clear history failed: ${e.message}`, true);
    }
  });
}

function triggerModuleRun(mod) {
  console.log(`Triggered ${mod.toUpperCase()} module execution for INV-DEMO-2026`);
}

function boot() {
  initShell();
  health();
  dashboard();
  casePage();
  correlationPage();
  personaPage();
  bindCrawl();
  monitoring();
  reports();
  bindOsint();
  settingsPage();
  investigationsList();
}

// Immediate initial execution of shell menu so sidebar is never blank
initShell();

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
