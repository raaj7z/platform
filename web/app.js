const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));

async function api(path,opt={}){
 const r=await fetch(path,{
  ...opt,
  headers:{
   "Content-Type":"application/json",
   ...(opt.headers||{})
  }
 });

 let d={};

 try{
  d=await r.json();
 }catch{}

 if(!r.ok){
  const detail=d?.detail;

  if(Array.isArray(detail)){
   const message=detail.map(x=>{
    if(typeof x==="string")return x;
    if(x?.msg)return x.msg;
    return JSON.stringify(x);
   }).join("; ");

   throw Error(message||`HTTP ${r.status}`);
  }

  if(detail&&typeof detail==="object"){
   throw Error(detail.msg||JSON.stringify(detail));
  }

  throw Error(String(detail||`HTTP ${r.status}`));
 }

 return d;
}

const NAV=`<div class="brand"><div class="logo-mark">◒</div><div><div class="logo-name">PRALAY<em>X</em></div><span class="logo-sub">Dark Web Intelligence Platform</span></div></div>
<nav class="nav">
<div class="nav-title">OPERATIONS</div>
<a data-page="dashboard" href="/web/index.html"><span class="nav-ico">⌂</span>Dashboard</a>
<a data-page="crawl" href="/web/crawl.html"><span class="nav-ico">＋</span>New Crawl</a>
<a data-page="investigations" href="/web/investigations.html"><span class="nav-ico">⌕</span>Investigations</a>
<div class="nav-title">INTELLIGENCE</div>
<a data-page="reports" href="/web/reports.html"><span class="nav-ico">▤</span>Reports</a>
<a data-page="osint" href="/web/osint.html"><span class="nav-ico">◎</span>OSINT</a>
<a data-page="analysis" href="/web/analysis.html"><span class="nav-ico">⌁</span>Analysis</a>
<a data-page="correlation" href="/web/correlation.html"><span class="nav-ico">⌘</span>Correlation</a>
<div class="nav-title">MONITORING</div>
<a data-page="monitoring" href="/web/monitoring.html"><span class="nav-ico">◉</span>Watchlist</a>
<a data-page="monitoring" href="/web/monitoring.html#alerts"><span class="nav-ico">♢</span>Alerts</a>
<div class="nav-title">SYSTEM</div>
<a data-page="terminal" href="/web/terminal.html"><span class="nav-ico">›_</span>Terminal</a>
<a data-page="settings" href="/web/settings.html"><span class="nav-ico">⚙</span>Settings</a>
</nav>
<div class="sidebar-foot">PRALAYX v2.0<br><br>EVIDENCE · ENTITY · ATTRIBUTION</div>`;

function initShell(){
 const s=document.querySelector(".sidebar");

 if(s){
  s.innerHTML=NAV;
 }

 const p=location.pathname;

 document.querySelectorAll("[data-page]").forEach(a=>{
  const k=a.dataset.page;

  if(
   (k==="dashboard"&&p.endsWith("index.html"))||
   (k!=="dashboard"&&p.includes(k))
  ){
   a.classList.add("active");
  }
 });
}

function renderStatus(v){
 const s=String(v||"UNKNOWN").toUpperCase();

 return `<span class="status ${esc(s)}">${esc(s)}</span>`;
}

async function health(){
 const el=document.querySelector("#api-status");

 if(!el)return;

 try{
  await api("/api/health");
  el.textContent="SYSTEM ONLINE";
  el.className="case-chip";
 }catch{
  el.textContent="API OFFLINE";
  el.className="case-chip";
 }
}

function terminal(events,status="RUNNING"){
 const body=(events||[]).map(e=>{
  const lvl=String(e.level||"INFO").toLowerCase();

  const cls=
   lvl==="success"
    ?"success"
    :(lvl==="warning"||lvl==="warn"
      ?"warn"
      :"info");

  const t=
   (e.created_at||"")
    .split("T")
    .pop()
    ?.slice(0,8)||"--:--:--";

  return `<div class="terminal-line ${cls}">[${esc(t)}] [${esc(e.level||"INFO")}] ${esc(e.message||e.event||"")}</div>`;
 }).join("");

 return `<section class="terminal section">
  <div class="terminal-head">
   <span style="color:#ff5d70;font-size:9px">● LIVE TERMINAL</span>
   ${renderStatus(status)}
  </div>
  ${status==="RUNNING"?'<div class="progress"><i></i></div>':""}
  <div class="terminal-body">
   ${body||'<div class="terminal-empty">Waiting for execution events…</div>'}
  </div>
 </section>`;
}

async function streamJob(jobId,holder){
 holder.classList.remove("hidden");

 const poll=async()=>{
  try{
   const d=await api(
    `/api/jobs/${encodeURIComponent(jobId)}`
   );

   holder.innerHTML=terminal(
    d.events||d.job_events||[],
    d.status||"RUNNING"
   );

   const status=String(
    d.status||""
   ).toUpperCase();

   if(
    !["RUNNING","PENDING"].includes(status)
   ){
    return;
   }

   setTimeout(poll,1000);

  }catch(e){
   holder.innerHTML=
    `<div class="notice">Execution error: ${esc(e.message)}</div>`;
  }
 };

 poll();
}

async function dashboard(){
 const recent=document.querySelector(
  "#recent-investigations"
 );

 if(!recent)return;

 try{
  const d=await api("/api/investigations");

  const a=
   Array.isArray(d)
    ?d
    :(d.investigations||d.items||[]);

  const si=document.querySelector(
   "#stat-investigations"
  );

  const sa=document.querySelector(
   "#stat-actors"
  );

  if(si){
   si.textContent=a.length;
  }

  if(sa){
   sa.textContent=
    a.reduce(
     (n,x)=>n+Number(x.actor_count||0),
     0
    )||"—";
  }

  recent.innerHTML=a.length
   ?a.slice(0,6).map(x=>{
     const id=x.id||x.investigation_id;

     return `<div class="row">
      <div class="row-main">
       <strong>${esc(id)}</strong>
       <span>${esc(x.target||"—")}</span>
      </div>
      ${renderStatus(x.status)}
      <a class="tag" href="/web/investigation.html?id=${encodeURIComponent(id)}">VIEW</a>
     </div>`;
    }).join("")
   :`<div class="empty">No investigations recorded.</div>`;

 }catch{
  recent.innerHTML=
   `<div class="empty">Unable to load investigations.</div>`;
 }
}

async function investigations(){
 const box=document.querySelector(
  "#investigation-list"
 );

 if(!box)return;

 try{
  const d=await api("/api/investigations");

  const a=
   Array.isArray(d)
    ?d
    :(d.investigations||d.items||[]);

  box.innerHTML=
   `<div class="panel-pad">
    <table class="table">
     <thead>
      <tr>
       <th>ID</th>
       <th>Target</th>
       <th>Actor</th>
       <th>Status</th>
       <th>Updated</th>
      </tr>
     </thead>
     <tbody>
      ${
       a.map(x=>{
        const id=x.id||x.investigation_id;

        return `<tr>
         <td>
          <a href="/web/investigation.html?id=${encodeURIComponent(id)}">
           ${esc(id)}
          </a>
         </td>
         <td>${esc(x.target||"—")}</td>
         <td>${esc(x.actor_id||"—")}</td>
         <td>${renderStatus(x.status)}</td>
         <td>${esc(x.updated_at||x.created_at||"—")}</td>
        </tr>`;
       }).join("")
      }
     </tbody>
    </table>
   </div>`;

 }catch{
  box.innerHTML=
   `<div class="empty">Unable to load investigations.</div>`;
 }
}

async function casePage(){
 const box=document.querySelector(
  "#case-title"
 );

 if(!box)return;

 const id=
  new URLSearchParams(
   location.search
  ).get("id");

 if(!id)return;

 try{
  const d=await api(
   `/api/investigations/${encodeURIComponent(id)}`
  );

  box.textContent=id;

  const summary=document.querySelector(
   "#case-summary"
  );

  if(summary){
   summary.innerHTML=`
    <div class="panel metric">
     <label>Target</label>
     <strong style="font-size:14px">
      ${esc(d.target||"—")}
     </strong>
    </div>

    <div class="panel metric">
     <label>Actor</label>
     <strong style="font-size:14px">
      ${esc(d.actor_id||"—")}
     </strong>
    </div>

    <div class="panel metric">
     <label>Status</label>
     <strong style="font-size:13px">
      ${renderStatus(d.status)}
     </strong>
    </div>

    <div class="panel metric">
     <label>Findings</label>
     <strong>
      ${(d.findings||[]).length}
     </strong>
    </div>`;
  }

  const timeline=
   document.querySelector("#case-timeline");

  if(timeline){
   const events=
    d.timeline||d.events||[];

   timeline.innerHTML=events.length
    ?events.map(x=>`
      <div class="row">
       <div class="row-main">
        <strong>
         ${esc(x.message||x.event_type||"Event")}
        </strong>
        <span>
         ${esc(x.created_at||"")}
        </span>
       </div>
      </div>
     `).join("")
    :`<div class="empty">
       No timeline events recorded.
      </div>`;
  }

  const findings=
   document.querySelector("#case-findings");

  if(findings){
   findings.innerHTML=
    (d.findings||[]).length
     ?(d.findings||[]).map(x=>`
       <div class="finding">
        <span class="type">
         ${esc(x.finding_type||x.type||"finding")}
        </span>
        <span class="value">
         ${esc(x.value||"")}
        </span>
        <span class="conf">
         ${esc(x.confidence??"—")}
        </span>
       </div>
      `).join("")
     :`<div class="empty">
        No findings recorded.
       </div>`;
  }

 }catch(e){
  const error=
   document.querySelector("#case-error");

  if(error){
   error.textContent=e.message;
  }
 }
}

function bindCrawl(){
 const form=document.querySelector(
  "#crawl-form"
 );

 if(!form)return;

 form.addEventListener(
  "submit",
  async e=>{
   e.preventDefault();

   const holder=
    document.querySelector("#live-session");

   if(holder){
    holder.classList.remove("hidden");
   }

   try{
    const url=
     document.querySelector("#crawl-url")
      ?.value
      .trim()||"";

    const username=
     document.querySelector("#crawl-username")
      ?.value
      .trim()||null;

    if(!url){
     if(holder){
      holder.innerHTML=
       `<div class="notice">
        Crawler error: target URL is required.
       </div>`;
     }

     return;
    }

    const payload={
     urls:[url],
     target:username,
     workers:3
    };

    const r=await api(
     "/api/crawl",
     {
      method:"POST",
      body:JSON.stringify(payload)
     }
    );

    if(!r.job_id){
     throw Error(
      "Crawler request succeeded but no job ID was returned."
     );
    }

    if(holder){
     streamJob(
      r.job_id,
      holder
     );
    }

   }catch(err){
    if(holder){
     holder.innerHTML=
      `<div class="notice">
       Crawler error: ${esc(err.message)}
      </div>`;
    }
   }
  }
 );
}

async function monitoring(){
 const w=document.querySelector(
  "#watchlist"
 );

 const a=document.querySelector(
  "#alerts"
 );

 if(w){
  try{
   const d=await api(
    "/api/watchlist"
   );

   const x=
    Array.isArray(d)
     ?d
     :(d.watchlist||d.items||[]);

   w.innerHTML=x.length
    ?x.map(i=>`
      <div class="row">
       <div class="row-main">
        <strong>
         ${esc(
          i.actor_id||
          i.name||
          i.identifier||
          "Actor"
         )}
        </strong>

        <span>
         Every ${esc(i.interval_minutes||"—")} min
         · Last scan ${esc(i.last_scan_at||"Never")}
        </span>
       </div>

       ${renderStatus(
        i.enabled===false
         ?"PAUSED"
         :"RUNNING"
       )}
      </div>
     `).join("")
    :`<div class="empty">
       No tracked actors.
      </div>`;

  }catch{}
 }

 if(a){
  try{
   const d=await api(
    "/api/alerts"
   );

   const x=
    Array.isArray(d)
     ?d
     :(d.alerts||d.items||[]);

   a.innerHTML=x.length
    ?x.map(i=>`
      <div class="row">
       <div class="row-main">
        <strong>
         ${esc(
          i.title||
          i.alert_type||
          "Alert"
         )}
        </strong>

        <span>
         ${esc(i.message||"")}
        </span>
       </div>

       <span class="tag red">
        ${esc(i.severity||"INFO")}
       </span>
      </div>
     `).join("")
    :`<div class="empty">
       No alerts.
      </div>`;

  }catch{}
 }
}

async function reports(){
 const box=document.querySelector(
  "#report-list"
 );

 if(!box)return;

 try{
  const d=await api(
   "/api/reports"
  );

  const a=
   Array.isArray(d)
    ?d
    :(d.reports||d.items||[]);

  box.innerHTML=a.length
   ?`<div class="panel-pad">
      <table class="table">
       <thead>
        <tr>
         <th>File</th>
         <th>Investigation</th>
         <th>Run</th>
         <th>Format</th>
         <th>Size</th>
         <th>Created</th>
        </tr>
       </thead>

       <tbody>
        ${
         a.map(x=>`
          <tr>
           <td>
            ${esc(
             x.file_name||
             x.name||
             "Report"
            )}
           </td>

           <td>
            ${esc(x.investigation_id||"—")}
           </td>

           <td>
            ${esc(x.run_id||"—")}
           </td>

           <td>
            ${esc(x.format||"—")}
           </td>

           <td>
            ${esc(x.file_size||"—")}
           </td>

           <td>
            ${esc(x.created_at||"—")}
           </td>
          </tr>
         `).join("")
        }
       </tbody>
      </table>
     </div>`
   :`<div class="empty">
      No report artifacts recorded.
     </div>`;

 }catch{
  box.innerHTML=
   `<div class="empty">
    Report history unavailable.
   </div>`;
 }
}

function bindOsint(){
 const f=document.querySelector(
  "#osint-form"
 );

 if(!f)return;

 f.addEventListener(
  "submit",
  async e=>{
   e.preventDefault();

   const holder=
    document.querySelector("#osint-result");

   if(holder){
    holder.classList.remove("hidden");
   }

   try{
    const iid=
     document.querySelector(
      "#osint-investigation"
     )?.value?.trim();

    const target=
     document.querySelector(
      "#osint-target"
     )?.value?.trim();

    const targetType=
     document.querySelector(
      "#osint-type"
     )?.value;

    if(!iid){
     throw Error(
      "Investigation ID is required."
     );
    }

    if(!target){
     throw Error(
      "OSINT target is required."
     );
    }

    const r=await api(
     `/api/investigations/${encodeURIComponent(iid)}/send-to-osint`,
     {
      method:"POST",
      body:JSON.stringify({
       target,
       target_type:targetType
      })
     }
    );

    if(!r.job_id){
     throw Error(
      "OSINT request succeeded but no job ID was returned."
     );
    }

    if(holder){
     streamJob(
      r.job_id,
      holder
     );
    }

   }catch(err){
    if(holder){
     holder.innerHTML=
      `<div class="notice">
       OSINT error: ${esc(err.message)}
      </div>`;
    }
   }
  }
 );
}

document.addEventListener(
 "DOMContentLoaded",
 ()=>{
  initShell();
  health();
  dashboard();
  investigations();
  casePage();
  bindCrawl();
  monitoring();
  reports();
  bindOsint();
 }
);
