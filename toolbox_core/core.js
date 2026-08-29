

const _WF_ICONS = {

  play: '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M4 2v10l8-5z"/></svg>',

  stop: '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><rect x="3" y="3" width="8" height="8" rx="1.5"/></svg>',

  settings: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="7" cy="7" r="2.8"/><path d="M7 1v2M7 11v2M13 7h-2M3 7H1M11.3 2.7l-1.4 1.4M4.1 9.9l-1.4 1.4M11.3 11.3l-1.4-1.4M4.1 4.1 2.7 2.7"/></svg>',
  open: '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M1.5 3.5h3.5l1.5-1.5h5a1 1 0 011 1v8a1 1 0 01-1 1h-10a1 1 0 01-1-1v-6.5a1 1 0 011-1z" opacity=".5"/></svg>'
};

const S = {};

const nav = [

  {key:"svn",label:"SVN 记录"},

  {key:"merge",label:"语义合并"},

  {key:"textcheck",label:"文字检测"},

  {key:"workflow",label:"工作流"},

  {key:"translate",label:"翻译"},

  {key:"prefab",label:"修改预制"},

  {key:"assist",label:"辅助功能"},

];

nav.forEach(n => { S[n.key] = {el:null,built:false,logEl:null}; });

const sidebarNav = document.getElementById("sidebar_nav");

const content = document.getElementById("content");

nav.forEach(n=>{

  const btn = document.createElement("button");

  btn.className = "nav-btn";

  btn.innerHTML = `${n.label}<span class="nav-dot" id="nav_dot_${n.key}"></span>`;

  btn.dataset.key = n.key;

  sidebarNav.appendChild(btn);

  S[n.key].navBtn = btn;

});

nav.forEach(n => {

  const panel = document.createElement("div");

  panel.className = "tab-panel";

  panel.id = "tab-" + n.key;

  content.appendChild(panel);

  S[n.key].panel = panel;

});

let config = {};

async function loadConfig() {

  const r = await fetch("/api/config");

  config = await r.json();

}

async function saveConfig(updates) {

  Object.assign(config, updates);

  await fetch("/api/config", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(updates)});

}

const tabMeta = {

  svn:{title:"SVN 记录",sub:"修改摘要、版本对比与导出工具"},

  merge:{title:"语义合并",sub:"精准文件级SVN版本合并 — 无需还原、无需清空本地修改"},

  workflow:{title:"工作流",sub:"自动化 SVN 操作编排"},

  translate:{title:"翻译",sub:"Excel 多语言批量翻译工作台"},

  textcheck:{title:"文字表检测",sub:"Texts.xlsm 翻译质量检查 — 漏翻/占位符/标签/重复ID"},

  prefab:{title:"修改预制",sub:"预制文件批量修改工具"},

  assist:{title:"辅助功能",sub:"一键生成meta等辅助工具"},

};

function switchTab(key) {

  nav.forEach(n => {

    S[n.key].panel.classList.remove("active");

    S[n.key].navBtn.classList.remove("active");

  });

  S[key].panel.classList.add("active");

  S[key].navBtn.classList.add("active");

  const meta = tabMeta[key];

  if (meta) {

    document.getElementById("page_title").textContent = meta.title;

    document.getElementById("page_subtitle").textContent = meta.sub;

  }

  if (!S[key].built) {

    buildTab(key);

  } else if (key === "svn" || key === "merge") {

    const now = new Date();

    const y = now.getFullYear();

    const m = String(now.getMonth() + 1).padStart(2, "0");

    const d = String(now.getDate()).padStart(2, "0");

    const startEl = document.getElementById(key + "_start");

    const endEl = document.getElementById(key + "_end");

    if (startEl) startEl.value = y + "-01-01";

    if (endEl) endEl.value = y + "-" + m + "-" + d;

  }

  // 切换页签时把日志区域滚动到底部
  requestAnimationFrame(scrollLogToBottom);

  // 每次切换左侧页签检测一次更新（已有更新提示则不重复请求）
  triggerUpdateCheck();

}

function buildTab(key) {

  const panel = S[key].panel;

  panel.innerHTML = '<div class="empty-state">加载中…</div>';

  void panel.offsetHeight;

  var tabScripts = {
    merge: "tab-merge.js",
    workflow: "tab-workflow.js",
    translate: "tab-translate.js",
    textcheck: "tab-textcheck.js",
    prefab: "tab-prefab.js",
    assist: "tab-assist.js",
  };

  var tabBuildFn = {svn:"buildSvnTab", merge:"buildMergeTab", workflow:"buildWorkflowTab", translate:"buildTranslateTab", textcheck:"buildTextCheckTab", prefab:"buildPrefabTab", assist:"buildAssistTab"};
  var buildFn = tabBuildFn[key];
  if (typeof window[buildFn] === "function") {
    window[buildFn](panel);
  } else if (tabScripts[key]) {
    var s = document.createElement("script");
    s.src = "/api/static/" + tabScripts[key];
    s.onload = function() {
      if (typeof window[buildFn] === "function") {
        window[buildFn](panel);
      }
      _finishBuildTab(key);
    };
    document.body.appendChild(s);
    return;
  }

  _finishBuildTab(key);

  function _finishBuildTab(k) {
    if (k === "svn" || k === "merge") {
      setTimeout(function(){_initDatePicker(k+"_start");_initDatePicker(k+"_end")}, 0);
    }
    S[k].built = true;
    scrollLogToBottom();
  }
}

const now = new Date();

const cy = now.getFullYear();

const cm = now.getMonth()+1;

const cd = now.getDate();

function _getSvnUrlInputUrl() {
  /* SVN 地址输入框显示本地路径，真实 URL 存 dataset.url；兼容直接填 URL */
  const el = document.getElementById("svn_url");
  if (!el) return "";
  const u = el.dataset.url || "";
  if (u) return u;
  const v = el.value.trim();
  return isSvnUrl(v) ? v : "";
}
async function _ensureSvnUrlInputUrl() {
  /* 查询前确保拿到 URL：本地路径未反查时先调 detect */
  let url = _getSvnUrlInputUrl();
  if (url) return url;
  const v = document.getElementById("svn_url")?.value.trim() || "";
  if (!v) return "";
  if (isSvnUrl(v)) return v;
  try {
    const r = await fetch("/api/svn/detect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path: v})});
    const d = await r.json();
    if (d.ok) {
      document.getElementById("svn_url").dataset.url = d.url;
      return d.url;
    }
  } catch(_) {}
  return "";
}
function _showLocalForSvnInput(url) {
  /* 把 SVN 地址输入框值换成 URL 对应的本地路径（仅显示），失败保持 URL */
  if (!url || !isSvnUrl(url)) return;
  fetch("/api/svn/resolve-url", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url})})
    .then(r=>r.json()).then(d => {
      if (d.ok && d.path) {
        const el = document.getElementById("svn_url");
        if (el && el.dataset.url === url) el.value = d.path;
      }
    })
    .catch(() => {});
}
function buildSvnTab(panel) {

  const today = `${cy}-${String(cm).padStart(2,"0")}-${String(cd).padStart(2,"0")}`;

  const yearStart = `${cy}-01-01`;

  panel.innerHTML = `

    <div class="workbench svn-layout">

      <div class="svn-main">

        <div class="card">

          <div class="card-title">SVN 地址</div>

          <div class="flex-row">

            <input type="text" id="svn_url" placeholder="输入 SVN 链接（svn:// 或 http(s)://*/svn/*），或拖入本地工作副本自动识别" style="flex:1" autocomplete="off" class="svn-url-drop-target">

            <button class="btn btn-normal" style="flex-shrink:0" data-action="browse-svn-url" title="浏览本地SVN工作副本"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>

            <button class="btn btn-normal" style="flex-shrink:0" data-action="open-svn-url" title="打开文件夹"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>

          </div>

          <div class="svn-url-drop-hint">可将文件/文件夹拖拽到输入框自动识别 SVN 地址</div>

        </div>

        <div class="card">

          <div class="card-title">操作设置</div>

          <div class="form-group">

            <label>模式</label>

            <div class="toggle-group" id="svn_mode_group">

              <button class="toggle-btn active" data-v="summary">修改摘要</button>

              <button class="toggle-btn" data-v="compare">对比 Excel</button>

              <button class="toggle-btn" data-v="export">导出文件</button>

            </div>

          </div>

          <div class="form-group">

            <label>日期范围</label>

            <div class="flex-row" style="align-items:center">

              <input type="text" id="svn_start" value="${yearStart}" placeholder="YYYY-MM-DD 格式，默认当年 1 月 1 日" style="flex:1;min-width:0">

              <span style="color:var(--dim)">—</span>

              <input type="text" id="svn_end" value="${today}" placeholder="YYYY-MM-DD 格式，默认今天" style="flex:1;min-width:0">

            </div>

          </div>

        </div>

      </div>

      <div class="svn-side">

        <div class="card">

          <div class="section-label" style="display:flex;justify-content:space-between;align-items:center">

            <span>过滤与输出</span>

            <button data-action="svn-advanced" title="高级设置" style="border:none;background:transparent;color:var(--dim);font-size:18px;padding:0;cursor:pointer;line-height:1">⚙</button>

          </div>

          <div class="form-group">

            <label>关键词过滤</label>

            <input type="text" id="svn_keyword" placeholder="输入提交信息中的关键字，多个用逗号分隔" autocomplete="off">

          </div>

          <div class="form-group">

            <label>提交者过滤</label>

            <input type="text" id="svn_author" placeholder="SVN提交者账户名，多个用逗号分隔" autocomplete="off">

          </div>

          <div class="form-group">

            <label>输出目录</label>

            <div class="flex-row">

              <input type="text" id="svn_output" placeholder="选择导出文件的保存目录，导出前会清空该目录内容" style="flex:1" autocomplete="off">

              <button class="btn btn-normal" style="flex-shrink:0" data-action="browse-svn-output" id="svn_browse_btn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>

              <button class="btn btn-normal" style="flex-shrink:0" data-action="open-svn-output" title="打开输出文件夹" id="svn_open_btn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>

            </div>

          </div>

        </div>

      </div>

      <div class="action-center">

        <button class="btn btn-primary" data-action="run-svn" data-output="#svn_output">开始执行</button>

      </div>

      <div class="svn-log-wrap">

        <div class="card">

          <div class="card-header compact">

            <span style="font-weight:600">执行日志</span>

            <div style="margin-left:auto;display:flex;gap:8px">

              <button class="btn btn-normal btn-sm" data-action="svn-clear-cache">清除缓存</button>

            </div>

          </div>

          <div class="log" id="svn_log"><div class="log-anchor"></div></div>

        </div>

      </div>

    </div>

  `;

  const svnUrlHistory = getSvnUrlHistory();

  initSuggest("svn_url", svnUrlHistory);

  // 下拉选项显示本地工作副本路径（值仍为 SVN URL）
  fetch("/api/svn/working-copies")
    .then(r=>r.json()).then(d => { if (d.ok && d.paths && d.paths.length) initSuggest("svn_url", d.paths); })
    .catch(()=>{});

  enablePathDrop("svn_url", { mode: "svn" });

  enablePathDrop("svn_output", { mode: "path" });

  const _svnUrlInput = document.getElementById("svn_url");
  const savedUrl = isSvnUrl(config.svn_url_current) ? config.svn_url_current : (svnUrlHistory[0] || "");
  if (savedUrl) {
    _svnUrlInput.value = savedUrl;
    _svnUrlInput.dataset.url = savedUrl;
    _showLocalForSvnInput(savedUrl); // 输入框显示本地路径
  }

  _svnUrlInput.addEventListener("keydown",e=>{
    if (e.key === "Enter") {
      const val = e.target.value.trim();
      if (val && isSvnUrl(val)) {
        saveSvnUrlValue("svn_url", val);
        _svnUrlInput.dataset.url = val;
        _showLocalForSvnInput(val);
      }
    }
  });

  document.getElementById("svn_output").value = config.output_dir || "";

  initSuggest("svn_output", config.output_dir_history||[]);

  _svnUrlInput.addEventListener("change", ()=>{
    const val = _svnUrlInput.value.trim();
    if (!val) return;
    if (isSvnUrl(val)) {
      _svnUrlInput.dataset.url = val;
      _showLocalForSvnInput(val);
    } else {
      // 本地路径 → 反查 SVN 链接
      fetch("/api/svn/detect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path: val})})
        .then(r=>r.json()).then(d => { if (d.ok) _svnUrlInput.dataset.url = d.url; })
        .catch(()=>{});
    }
  });

  _svnUrlInput.addEventListener("blur", async ()=>{
    const val = _svnUrlInput.value.trim();
    if (!val) return;
    if (!isSvnUrl(val)) {
      // 本地路径 → 反查 SVN 链接
      try {
        const r = await fetch("/api/svn/detect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path: val})});
        const d = await r.json();
        if (d.ok) _svnUrlInput.dataset.url = d.url;
      } catch(_) {}
      return;
    }
    saveSvnUrlValue("svn_url", val);
    _svnUrlInput.dataset.url = val;
    _showLocalForSvnInput(val);
  });

  document.getElementById("svn_output").addEventListener("blur", ()=>{

    const val = document.getElementById("svn_output").value.trim();

    if (val) {

      const hist = [val, ...(config.output_dir_history||[]).filter(u=>u!==val)].slice(0,10);

      saveConfig({output_dir: val, output_dir_history: hist});

      config.output_dir = val;

      config.output_dir_history = hist;

      initSuggest("svn_output", hist);

    }

  });

  initSuggest("svn_keyword", config.svn_keyword_history||[]);

  initSuggest("svn_author", config.svn_author_history||[]);

  ["svn_keyword","svn_author"].forEach(id => {

    document.getElementById(id).addEventListener("blur", ()=>{

      const val = document.getElementById(id).value.trim();

      const key = id==="svn_keyword" ? "svn_keyword_history" : "svn_author_history";

      if (val && !(config[key]||[]).includes(val)) {

        saveConfig({[key]: [val, ...(config[key]||[])].slice(0,20)});

        const peerId = id==="svn_keyword" ? "merge_keyword" : "merge_author";

        initSuggest(id, config[key]);

        initSuggest(peerId, config[key]);

      }

    });

  });

  S.svn.logEl = document.getElementById("svn_log");

}

async function runSvn() {

  triggerUpdateCheck();

  const mode = document.querySelector("#svn_mode_group .toggle-btn.active")?.dataset.v || "compare";

  const svn_url = await _ensureSvnUrlInputUrl();

  const body = {

    svn_url,

    mode,

    start_date:document.getElementById("svn_start").value,

    end_date:document.getElementById("svn_end").value,

    keyword:document.getElementById("svn_keyword")?.value||"",

    author:document.getElementById("svn_author")?.value||"",

    output:document.getElementById("svn_output")?.value||""

  };

  if (!isSvnUrl(body.svn_url)) {

    _showToast("请输入有效的 SVN 链接");

    document.getElementById("svn_url").focus();

    return;

  }

  const dateError = _dateRangeError(body.start_date, body.end_date);

  if (dateError) {

    _showToast(dateError);

    document.getElementById("svn_start").focus();

    return;

  }

  const out = body.output;

  const kw = body.keyword;

  const au = body.author;

  const svnHist = isSvnUrl(body.svn_url) ? [body.svn_url, ...getSvnUrlHistory().filter(u=>u!==body.svn_url)].slice(0,20) : getSvnUrlHistory();

  saveConfig({

    output_dir: out,

    output_dir_history: [out, ...(config.output_dir_history||[]).filter(u=>u!==out)].slice(0,10),

    svn_url_current: body.svn_url,

    svn_urls: svnHist,

    svn_keyword_history: kw && !(config.svn_keyword_history||[]).includes(kw) ? [kw, ...(config.svn_keyword_history||[])].slice(0,20) : config.svn_keyword_history,

    svn_author_history: au && !(config.svn_author_history||[]).includes(au) ? [au, ...(config.svn_author_history||[])].slice(0,20) : config.svn_author_history,

  });

  config.svn_url_current = body.svn_url;

  config.svn_urls = svnHist;

  if (kw && !(config.svn_keyword_history||[]).includes(kw)) config.svn_keyword_history = [kw, ...(config.svn_keyword_history||[])].slice(0,20);

  if (au && !(config.svn_author_history||[]).includes(au)) config.svn_author_history = [au, ...(config.svn_author_history||[])].slice(0,20);

  initSuggest("svn_url", config.svn_urls);

  initSuggest("svn_keyword", config.svn_keyword_history||[]);

  initSuggest("svn_author", config.svn_author_history||[]);

  runTask("/api/svn/run", body, document.querySelector("[data-action='run-svn']"), "svn_log");

}

let uploadFilesData = [];

let _wfSortables = [];

let _wfHistoryDd = null;

let _wfExpandedIdx = -1;

document.addEventListener("click", (e) => {

  if (!e.target.closest("#wf_step_type_picker") && !e.target.closest(".wf-add-step-item")) {

    document.querySelectorAll("#wf_step_type_picker").forEach(m => m.remove());

  }

});

document.addEventListener("mousedown", (e) => {

  if (_wfHistoryDd && !e.target.closest(".wf-history-drop") && !e.target.closest(".wf-modal-input")) {

    _wfHistoryDd.remove();

    _wfHistoryDd = null;

  }

});

function escapeHtml(s){

  return (s||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

}

let trLangAdvModal = null;

let _runningCount = 0;

const _esMap = {};

let _tabCount = {svn:0, merge:0, upload:0, textcheck:0, workflow:0, translate:0, prefab:0, assist:0};

let _wfPlayState = {};

function _updateWfDot(wfIdx) {

  const parent = document.querySelector(`.wf-parent[data-idx="${wfIdx}"]`);

  const dot = parent?.querySelector(".wf-status-dot span");

  if (!dot) return;

  const running = Object.keys(_wfPlayState).some(k => k.startsWith("step_" + wfIdx + "_") || k === "update_" + wfIdx);

  dot.style.background = running ? "var(--yellow,#f0c040)" : "var(--green,#4caf50)";

}

function _incRunning() {

  if (_runningCount === 0) {

    const sb = document.getElementById("status_bar");

    if (sb) { sb.classList.add("running"); sb.querySelector("span").textContent = "运行中"; }

  }

  _runningCount++;

}

function _decRunning() {

  _runningCount = Math.max(0, _runningCount - 1);

  if (_runningCount === 0) {

    const sb = document.getElementById("status_bar");

    if (sb) { sb.classList.remove("running"); const sp = sb.querySelector("span"); if (sp) sp.textContent = "系统空闲"; }

  }

}

const _URL_TAB = {

  "/api/svn/run":"svn", "/api/upload/run":"upload",

  "/api/translate/run":"translate", "/api/workflow/run":"workflow",

  "/api/assist/run":"assist",

  "/api/prefab/clear-text":"prefab", "/api/prefab/atlas/copy":"prefab",

  "/api/prefab/atlas/resolve":"prefab", "/api/prefab/atlas/rewrite":"prefab",
  "/api/prefab/font-scan":"prefab", "/api/prefab/font-modify":"prefab",
};





function _setTabDot(tabKey, on) {

  const dot = document.getElementById("nav_dot_" + tabKey);

  if (dot) dot.classList.toggle("active", on);

}

function _initDatePicker(inputId) {

  const input = document.getElementById(inputId);

  if (!input) return;

  let wrap = input.parentElement;

  if (!wrap.classList.contains("dp-wrap")) {

    wrap = document.createElement("div");

    wrap.className = "dp-wrap";

    input.parentElement.insertBefore(wrap, input);

    wrap.appendChild(input);

  }

  input.classList.add("dp-input");

  if (!wrap.querySelector(".dp-trigger")) {

    const btn = document.createElement("button");

    btn.type = "button";

    btn.className = "dp-trigger";

    btn.innerHTML = "&#128197;";

    wrap.appendChild(btn);

  }

  let popup = document.getElementById("dp-" + inputId);

  if (!popup) {

    popup = document.createElement("div");

    popup.id = "dp-" + inputId;

    popup.className = "dp-popup";

    popup.style.display = "none";

    document.body.appendChild(popup);

  }

  let currentYear, currentMonth, selectedDate = null;

  function _dpParse(v) {

    if (!v) return null;

    const m = v.match(/^(\d{4})-(\d{2})-(\d{2})$/);

    return m ? {y:+m[1],m:+m[2]-1,d:+m[3]} : null;

  }

  function _dpStr(y,m,d){return y+"-"+String(m+1).padStart(2,"0")+"-"+String(d).padStart(2,"0")}

  function _dpPosition() {

    const r=input.getBoundingClientRect();

    popup.style.left=Math.max(4,Math.min(r.left,window.innerWidth-244))+"px";

    var bot=r.bottom+4+260;popup.style.top=(bot>window.innerHeight?r.top-264:r.bottom+4)+"px"

  }

  function _dpRender() {

    const fd = new Date(currentYear,currentMonth,1).getDay();

    const dim = new Date(currentYear,currentMonth+1,0).getDate();

    const dip = new Date(currentYear,currentMonth,0).getDate();

    const t=new Date(),ty=t.getFullYear(),tm=t.getMonth(),td=t.getDate();

    let h="<div class=dp-header><button class=dp-prev data-action=prev>\u2039</button><span class=dp-title>"+currentYear+"\u5e74"+(currentMonth+1)+"\u6708</span><button class=dp-next data-action=next>\u203a</button></div><div class=dp-weekdays>"+"\u65e5\u4e00\u4e8c\u4e09\u56db\u4e94\u516d".split("").map(function(w){return"<span>"+w+"</span>"}).join("")+"</div><div class=dp-days>";

    for(let i=fd-1;i>=0;i--){var d=dip-i;h+='<div class="dp-day other-month" data-y="'+(currentMonth===0?currentYear-1:currentYear)+'" data-m="'+(currentMonth===0?11:currentMonth-1)+'" data-d="'+d+'">'+d+"</div>"}

    for(let d=1;d<=dim;d++){var c="dp-day";if(selectedDate&&selectedDate.y===currentYear&&selectedDate.m===currentMonth&&selectedDate.d===d)c+=" selected";if(ty===currentYear&&tm===currentMonth&&td===d)c+=" today";h+='<div class="'+c+'" data-y="'+currentYear+'" data-m="'+currentMonth+'" data-d="'+d+'">'+d+"</div>"}

    var r=(7-(fd+dim)%7)%7;for(let d=1;d<=r;d++){h+='<div class="dp-day other-month" data-y="'+(currentMonth===11?currentYear+1:currentYear)+'" data-m="'+(currentMonth===11?0:currentMonth+1)+'" data-d="'+d+'">'+d+"</div>"}

    h+='</div><div class=dp-footer><button class=dp-today data-action=today>&#20170;&#22825;</button><button class=dp-clear data-action=clear>&#28165;&#38500;</button></div>';

    popup.innerHTML=h;

  }

  function _dpShow(){if(selectedDate){currentYear=selectedDate.y;currentMonth=selectedDate.m}else{var n=new Date();currentYear=n.getFullYear();currentMonth=n.getMonth()}_dpRender();_dpPosition();popup.style.display="block"}

  function _dpSet(y,m,d){selectedDate={y,m,d};currentYear=y;currentMonth=m;input.value=_dpStr(y,m,d);_dpRender()}

  function _dpClear(){selectedDate=null;input.value="";_dpRender()}

  input._dpSet=_dpSet;input._dpClear=_dpClear;

  input.addEventListener("focus",_dpShow);

  input.addEventListener("input",function(){var p=_dpParse(input.value);if(p){selectedDate=p;currentYear=p.y;currentMonth=p.m;_dpRender()}else{selectedDate=null}});

  wrap.querySelector(".dp-trigger").addEventListener("click",function(e){e.preventDefault();_dpShow()});

  popup.addEventListener("click",function(e){

    var t=e.target.closest("[data-action],.dp-day");if(!t)return;

    var a=t.dataset.action;

    if(a==="prev"){currentMonth--;if(currentMonth<0){currentMonth=11;currentYear--}_dpRender();_dpPosition()}

    else if(a==="next"){currentMonth++;if(currentMonth>11){currentMonth=0;currentYear++}_dpRender();_dpPosition()}

    else if(a==="today"){var n=new Date();_dpSet(n.getFullYear(),n.getMonth(),n.getDate())}

    else if(a==="clear"){_dpClear()}

    else if(t.classList.contains("dp-day")){_dpSet(parseInt(t.dataset.y),parseInt(t.dataset.m),parseInt(t.dataset.d))}

  });

  function _dpClose(e){if(!wrap.contains(e.target)&&!popup.contains(e.target))popup.style.display="none"}

  document.addEventListener("click",_dpClose,true);

  var p=_dpParse(input.value);if(p){selectedDate=p;currentYear=p.y;currentMonth=p.m}

}

function _incTabRunning(tabKey) {

  if (_tabCount[tabKey] === 0) _setTabDot(tabKey, true);

  _tabCount[tabKey]++;

}

function _decTabRunning(tabKey) {

  _tabCount[tabKey] = Math.max(0, _tabCount[tabKey] - 1);

  if (_tabCount[tabKey] === 0) _setTabDot(tabKey, false);

}

function _logAppend(el, child) {

  const a = el.querySelector(".log-anchor");

  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 5;

  if (a) el.insertBefore(child, a);

  else el.appendChild(child);

  if (atBottom) el.scrollTop = el.scrollHeight;

}

function _logClear(el) {

  el.innerHTML = '<div class="log-anchor"></div>';

}

let _lastErrorFocusTab = null;

let _lastErrorFocusTime = 0;

function _focusAppOnError(tabKey, logEl) {

  const now = Date.now();

  if (tabKey === _lastErrorFocusTab && now - _lastErrorFocusTime < 3000) return;

  _lastErrorFocusTab = tabKey;

  _lastErrorFocusTime = now;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.focusWindow) {

    window.pywebview.api.focusWindow();

  }

  switchTab(tabKey);

  setTimeout(() => {

    logEl?.scrollIntoView({behavior:"smooth", block:"end"});

    const logContainer = document.getElementById("wf_log");

    if (logContainer) logContainer.scrollTop = logContainer.scrollHeight;

    const mainContent = document.querySelector(".content");

    if (mainContent) mainContent.scrollTop = mainContent.scrollHeight;

  }, 200);

}

async function runTask(url, body, btn, logId, label, onDone) {

  const logEl = document.getElementById(logId);

  if (!url.includes("/workflow/")) logEl?.scrollIntoView({behavior:"smooth", block:"nearest"});

  const tabKey = _URL_TAB[url];

  let _outputPath = "";



  const _logBuf = [];

  let _logTimer = null;

  const MAX_LOG_LINES = 2000;

  let _taskId = "";

  let _finished = false;

  function _done() {

    if (_finished) return;

    _finished = true;

    _decRunning();

    if (tabKey) _decTabRunning(tabKey);

    if (!label && btn && btn.dataset.taskId) {

      btn.dataset.taskId = '';

      btn.classList.remove('stop');

      btn.innerHTML = btn.dataset.orig || '执行';

    }

    if (onDone) onDone(_outputPath, _taskId);

  }

  function _logFlush() {

    if (!_logBuf.length) return;

    const lines = _logBuf.splice(0);

    const frag = document.createDocumentFragment();

    for (const raw of lines) {

      const m = raw.match(/^\[(\d{2}:\d{2}:\d{2})\](?:\[(\w+)\])?\s*(.*)/);

      let tag = "", plainMsg = raw;

      if (m) {

        plainMsg = m[3] || "";

        tag = (m[2] || "").toLowerCase();

      }

      const _m = plainMsg.match(/(?:已生成修改总结|修改总结)[:\s]+(.+?)\\修改总结\.txt/);

      if (_m) _outputPath = _m[1].trim();

      const _pm = plainMsg.match(/\[输出路径\]\s+(.+)/);

      if (_pm) _outputPath = _pm[1].trim();

      let msg = escapeHtml(plainMsg);

      if (m) msg = `<span class="ts">${m[1]}</span> ${msg}`;

      if (label) {

        msg = `<span style="color:var(--accent);font-weight:600">[${escapeHtml(label)}]</span> ${msg}`;

      }

      const isError = tag === "error" || raw.includes("❌");

      const cls = isError ? "error" : ({"warn":"warn","ok":"success","success":"success","info":"info"}[tag] || "");

      const div = document.createElement("div");

      div.className = cls;

      div.innerHTML = msg;

      frag.appendChild(div);

    }

    const hasError = Array.from(frag.children).some(c => c.className === "error");

    _logAppend(logEl, frag);

    // limit log lines to prevent DOM bloat and UI freeze

    while (logEl.children.length - 1 > MAX_LOG_LINES) {

      const first = logEl.firstElementChild;

      if (!first || first.classList.contains("log-anchor")) break;

      first.remove();

    }

    if (hasError) _focusAppOnError(tabKey, logEl);

  }

  function _logStartTimer() {

    if (_logTimer) return;

    _logTimer = setInterval(() => {

      if (_logBuf.length) _logFlush();

    }, 80);

  }

  function _logStopTimer() {

    if (_logTimer) { clearInterval(_logTimer); _logTimer = null; }

  }

  function _logPush(raw) {

    _logBuf.push(raw);

    if (!_logTimer) _logStartTimer();

  }

  _incRunning();

  if (tabKey) _incTabRunning(tabKey);

  _logClear(logEl);

  let d;

  try {

    const r = await fetch(url, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});

    d = await r.json();

    if (!d || typeof d !== "object") throw new Error("服务器返回了无效响应");

    if (!r.ok && !d.error) d.error = "请求失败（HTTP " + r.status + "）";

  } catch (error) {

    const errorMessage = error && error.message ? error.message : "网络请求失败";

    const div = document.createElement("div");

    div.className = "error";

    div.textContent = "❌ 任务启动失败：" + errorMessage;

    _logAppend(logEl, div);

    _showToast("任务启动失败：" + errorMessage);

    _focusAppOnError(tabKey, logEl);

    _done();

    return;

  }

  _taskId = d.task_id || "";

  if (body.wf_idx !== undefined) {

    const sk = body._stateKey || body.wf_idx;

    if (_wfPlayState[sk]) _wfPlayState[sk].taskId = _taskId;

  }

  if (!label && btn && _taskId) {

    if (!btn.dataset.orig) btn.dataset.orig = btn.textContent;

    btn.dataset.taskId = _taskId;

    btn.innerHTML = _WF_ICONS.stop;

    btn.classList.add('stop');

  }

  if (d.error) {

    const div = document.createElement("div");

    div.className = "error";

    div.textContent = "❌ " + d.error;

    _logAppend(logEl, div);

    _showToast(d.error);

    _focusAppOnError(tabKey, logEl);

    _taskId = "";

    _done();

    return;

  }

  if (!_taskId) {

    const div = document.createElement("div");

    div.className = "error";

    div.textContent = "❌ 任务启动失败：服务器未返回任务 ID";

    _logAppend(logEl, div);

    _showToast("任务启动失败：服务器未返回任务 ID");

    _focusAppOnError(tabKey, logEl);

    _done();

    return;

  }

  const esKey = body._stateKey || url;

  const prev = _esMap[esKey];

  if (prev) {

    prev.es.close();

    prev.done();

  }

  const evtSrc = new EventSource("/api/log/stream/" + _taskId);

  _esMap[esKey] = { es: evtSrc, done: _done };

  evtSrc.onmessage = (e) => {

    if (e.data === "[DONE]") {

      _logStopTimer();

      _logFlush();

      evtSrc.close();

      _esMap[esKey] = null;

      _done();

      if (_outputPath) {

        const _hint = document.createElement("div");

        _hint.textContent = "📂 正在打开文件夹: " + _outputPath;

        _hint.style.cssText = "color:var(--accent);font-size:12px";

        _logAppend(logEl, _hint);

        _openFolder(_outputPath);

      }

      return;

    }

    const lines = e.data.split("\n");

    for (const raw of lines) {

      if (!raw.trim()) continue;

      _logPush(raw);

    }

  };

  evtSrc.onerror = () => {

    _logStopTimer();

    _logFlush();

    evtSrc.close();

    _esMap[esKey] = null;

    _done();

    const div = document.createElement("div");

    div.className = "warn";

    div.textContent = "⚠ 日志连接中断";

    _logAppend(logEl, div);

    _focusAppOnError(tabKey, logEl);

  };

}

function _openFolder(path) {

  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_folder) {

    window.pywebview.api.open_folder(path).then(()=>{});

  } else {

    fetch("/api/open/folder", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path})}).then(r=>r.json()).catch(e=>console.warn("打开文件夹失败:", e));

  }

}

let dirModal = null;

async function browseDir(inputId, callback, initialPath, appendMode) {

  if (window.pywebview && pywebview.api && pywebview.api.browseDir) {

    const path = await pywebview.api.browseDir(initialPath || "");

    if (path) {

      if (appendMode) {

        const inp = document.getElementById(inputId);

        const oldPaths = inp.value.trim().split(",").map(s => s.trim()).filter(Boolean);

        inp.value = oldPaths.includes(path) ? oldPaths.join(", ") : [...oldPaths, path].join(", ");

      } else {

        document.getElementById(inputId).value = path;

      }

      if (typeof window._wfModalAutoSave === "function") window._wfModalAutoSave();

      if (callback) callback();

    }

    return;

  }

  if (!dirModal) {

    dirModal = document.createElement("div");

    dirModal.style.cssText = "position:fixed;top:6.25rem;left:50%;transform:translateX(-50%);width:35rem;max-height:43.75rem;background:var(--panel);border:1px solid rgba(255,255,255,.08);border-radius:1.25rem;z-index:1000;display:none;flex-direction:column;box-shadow:0 1.25rem 3.75rem rgba(0,0,0,.5)";

    dirModal.innerHTML = `

        <div style="padding:1.25rem 1.5rem;border-bottom:1px solid rgba(255,255,255,.05);display:flex;justify-content:space-between;align-items:center">

          <span style="font-weight:600;font-size:1rem">选择目录</span>

          <button class="btn btn-normal btn-sm" data-action="close-dir-modal">✕</button>

        </div>

        <div class="flex-row" style="padding:0.875rem 1.5rem">

          <button class="btn btn-normal btn-sm" id="dir_up">⬆ 上级</button>

          <span id="dir_path" style="color:var(--dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;align-self:center;font-size:0.8125rem"></span>

        </div>

        <div id="dir_drives" style="padding:0.25rem 1rem 0;display:flex;flex-wrap:wrap;gap:4px"></div>

        <div id="dir_list" style="flex:1;overflow:auto;padding:0.5rem 1rem"></div>

        <div class="flex-row" style="padding:0.875rem 1.5rem;border-top:1px solid rgba(255,255,255,.05);justify-content:flex-end">

          <button class="btn btn-normal" data-action="close-dir-modal">取消</button>

          <button class="btn btn-primary" data-action="confirm-dir">选择此目录</button>

        </div>

      `;

    document.body.appendChild(dirModal);

    document.getElementById("dir_up").onclick = () => dirNavigate(dirModal._parent);

    document.getElementById("dir_drives").onclick = (e) => {

      const btn = e.target.closest("[data-drive]");

      if (btn) dirNavigate(btn.dataset.drive);

    };

    document.getElementById("dir_list").onclick = (e) => {

      const item = e.target.closest("[data-path]");

      if (item) {

        document.querySelectorAll("#dir_list [data-path]").forEach(x=>x.style.background="");

        item.style.background = "rgba(94,162,255,.2)";

        dirModal._selected = item.dataset.path;

      }

    };

    document.getElementById("dir_list").ondblclick = (e) => {

      const item = e.target.closest("[data-path]");

      if (item) dirNavigate(item.dataset.path);

    };

  }

  dirModal._targetInput = inputId;

  dirModal._callback = callback;

  dirModal._selected = null;

  const cur = initialPath || document.getElementById(inputId).value.trim() || "C:\\";

  dirNavigate(cur);

  dirModal.style.display = "flex";

}

async function dirNavigate(path) {

  const r = await fetch("/api/dir/browse", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path})});

  const d = await r.json();

  document.getElementById("dir_path").textContent = d.current;

  dirModal._parent = d.parent;

  document.getElementById("dir_up").disabled = !d.parent;

  let drivesHtml = "";

  if (d.drives && d.drives.length) {

    drivesHtml = d.drives.map(dd => `<button class="btn btn-normal btn-sm" data-drive="${escapeHtml(dd.path)}" style="font-size:12px;height:28px;min-height:28px;padding:0 10px">${escapeHtml(dd.name)}</button>`).join("");

  }

  document.getElementById("dir_drives").innerHTML = drivesHtml;

  document.getElementById("dir_list").innerHTML = d.dirs.map(dd => `<div data-path="${escapeHtml(dd.path)}" style="padding:0.875rem 1rem;border-radius:0.75rem;cursor:pointer;transition:.15s">📁 ${escapeHtml(dd.name)}</div>`).join("");

}

function confirmDir() {

  const path = dirModal._selected || document.getElementById("dir_path").textContent;

  if (path) {

    const inp = document.getElementById(dirModal._targetInput);

    if (dirModal._oldPaths) {

      // 增量追加模式：合并旧路径，去重

      const allPaths = [...dirModal._oldPaths];

      if (!allPaths.includes(path)) {

        allPaths.push(path);

      }

      inp.value = allPaths.join(", ");

      dirModal._oldPaths = null;

    } else {

      inp.value = path;

    }

    if (dirModal._callback) dirModal._callback();

  }

  closeDirModal();

}

function closeDirModal() {

  dirModal.style.display = "none";

}

function _browseDirAppend(inputId) {

  browseDir(inputId, null, null, true);

}

let advModal = null;

function openAdvSettings() {

  if (!advModal) {

    advModal = document.createElement("div");

    advModal.style.cssText = "position:fixed;top:6.25rem;left:50%;transform:translateX(-50%);width:34rem;max-height:43.75rem;background:var(--panel);border:1px solid rgba(255,255,255,.08);border-radius:1.25rem;z-index:1000;display:none;flex-direction:column;box-shadow:0 1.25rem 3.75rem rgba(0,0,0,.5)";

    advModal.innerHTML = `

        <div style="padding:1.25rem 1.5rem;border-bottom:1px solid rgba(255,255,255,.05);display:flex;justify-content:space-between;align-items:center">

          <span style="font-weight:600;font-size:1rem">⚙ 高级设置</span>

          <button class="btn btn-normal btn-sm" data-action="close-adv-settings">✕</button>

        </div>

        <div style="padding:1.25rem 1.5rem;overflow:auto;flex:1">

          <div style="font-size:0.85rem;font-weight:600;color:var(--accent);margin-bottom:8px">SVN 认证</div>

          <div class="form-group">

            <label>用户名</label>

            <input type="text" id="adv_svn_user" placeholder="SVN提交者的账户名" autocomplete="off" style="width:100%">

          </div>

          <div class="form-group">

            <label>密码</label>

            <input type="password" id="adv_svn_pass" placeholder="输入 SVN 登录密码，加密存储" style="width:100%">

          </div>

          <div style="font-size:0.85rem;font-weight:600;color:var(--accent);margin:16px 0 8px">导出设置</div>

          <div class="form-group">

            <label>排除目录（逗号分隔）</label>

            <input type="text" id="adv_exclude_dirs" placeholder="输入需要排除的文件夹名字，不需要完整路径，逗号分隔" autocomplete="off" style="width:100%">

          </div>

          <div style="font-size:0.85rem;font-weight:600;color:var(--accent);margin:16px 0 8px">文件级配置</div>

          <div class="form-group">

            <label>文件名</label>

            <div style="display:flex;gap:6px;align-items:center">

              <input type="text" id="adv_cmp_file" placeholder="输入文件名加载对应的预设配置" autocomplete="off" style="flex:1;min-width:0">

              <button class="btn btn-normal btn-sm" data-action="adv-save-preset" style="font-size:13px;padding:0 10px">保存</button>

              <button class="btn btn-normal btn-sm" data-action="adv-del-preset" style="font-size:13px;padding:0 10px;color:var(--warn,orange)" id="adv_del_preset_btn">×</button>

            </div>

          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">

            <div class="form-group">

              <label>标题行数</label>

              <input type="number" id="adv_cmp_title_rows" placeholder="Excel 表头占几行，正整数，默认 1" min="1" step="1" style="width:100%">

            </div>

            <div class="form-group">

              <label>对比ID列</label>

              <input type="number" id="adv_cmp_id_col" placeholder="ID 列是第几列，从 1 开始计数，默认 1" min="1" step="1" style="width:100%">

            </div>

          </div>

          <div class="form-group">

            <label>输出列表头（逗号分隔）</label>

            <input type="text" id="adv_cmp_output_cols" placeholder="输入需要保留的列名，逗号分隔，留空导出全部列" autocomplete="off" style="width:100%">

          </div>

        </div>

        <div class="flex-row" style="padding:0.875rem 1.5rem;border-top:1px solid rgba(255,255,255,.05);justify-content:flex-end;gap:8px">

          <button class="btn btn-normal" data-action="close-adv-settings">取消</button>

          <button class="btn btn-primary" data-action="save-adv-settings">保存</button>

        </div>

      `;

    document.body.appendChild(advModal);

    document.getElementById("adv_cmp_file").addEventListener("input", advLoadPresetValues);

  }

  document.getElementById("adv_svn_user").value = config.svn_user || "";

  document.getElementById("adv_svn_pass").value = "";

  document.getElementById("adv_exclude_dirs").value = config.exclude_dirs || "";

  document.getElementById("adv_cmp_title_rows").value = config.cmp_title_rows || "1";

  document.getElementById("adv_cmp_id_col").value = config.cmp_id_col || "1";

  document.getElementById("adv_cmp_output_cols").value = config.cmp_output_cols || "";

  document.getElementById("adv_cmp_file").value = "";

  advRefreshPresetList();

  advModal.style.display = "flex";

}

function advRefreshPresetList() {

  const presets = config.cmp_file_presets || [];

  _suggests["adv_cmp_file"] = { items: ["", ...presets] };

  const delBtn = document.getElementById("adv_del_preset_btn");

  delBtn.style.opacity = presets.length ? "1" : "0.3";

}

function advLoadPresetValues() {

  const name = document.getElementById("adv_cmp_file").value.trim();

  const settings = config.cmp_file_settings || {};

  const vals = settings[name];

  if (vals) {

    document.getElementById("adv_cmp_title_rows").value = vals.cmp_title_rows || "1";

    document.getElementById("adv_cmp_id_col").value = vals.cmp_id_col || "1";

    document.getElementById("adv_cmp_output_cols").value = vals.cmp_output_cols || "";

  } else {

    document.getElementById("adv_cmp_title_rows").value = config.cmp_title_rows || "1";

    document.getElementById("adv_cmp_id_col").value = config.cmp_id_col || "1";

    document.getElementById("adv_cmp_output_cols").value = config.cmp_output_cols || "";

  }

}

function _validateAdvNumbers() {

  const fields = [

    ["adv_cmp_title_rows", "标题行数"],

    ["adv_cmp_id_col", "对比 ID 列"]

  ];

  for (const [id, label] of fields) {

    const input = document.getElementById(id);

    const value = Number(input.value);

    if (!Number.isInteger(value) || value < 1) {

      _showToast(label + "必须是大于等于 1 的整数");

      input.focus();

      return false;

    }

  }

  const outputCols = document.getElementById("adv_cmp_output_cols");

  if (outputCols.value.trim() && !outputCols.value.split(",").some(value => value.trim())) {

    _showToast("请填写有效的输出列表头");

    outputCols.focus();

    return false;

  }

  return true;

}

function saveAdvFilePreset() {

  if (!_validateAdvNumbers()) return;

  const name = document.getElementById("adv_cmp_file").value.trim();

  const cmp_title_rows = document.getElementById("adv_cmp_title_rows").value.trim() || "1";

  const cmp_id_col = document.getElementById("adv_cmp_id_col").value || "1";

  const cmp_output_cols = document.getElementById("adv_cmp_output_cols").value.trim();

  if (name) {

    const payload = {

      cmp_file_presets: [...new Set([name, ...(config.cmp_file_presets || [])])],

      cmp_file_settings: Object.assign({}, config.cmp_file_settings || {}, {

        [name]: { cmp_title_rows, cmp_id_col, cmp_output_cols }

      })

    };

    fetch("/api/config", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})

      .then(r=>r.json()).then(d=>{

        if (d.ok) {

          config.cmp_file_presets = payload.cmp_file_presets;

          config.cmp_file_settings = payload.cmp_file_settings;

          advRefreshPresetList();

        }

      });

  } else {

    const payload = { cmp_title_rows, cmp_id_col, cmp_output_cols };

    fetch("/api/config", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})

      .then(r=>r.json()).then(d=>{

        if (d.ok) {

          config.cmp_title_rows = cmp_title_rows;

          config.cmp_id_col = cmp_id_col;

          config.cmp_output_cols = cmp_output_cols;

        }

      });

  }

}

function delAdvFilePreset() {

  const name = document.getElementById("adv_cmp_file").value.trim();

  if (!name || !(config.cmp_file_presets || []).includes(name)) return;

  const presets = (config.cmp_file_presets || []).filter(n => n !== name);

  const settings = Object.assign({}, config.cmp_file_settings || {});

  delete settings[name];

  const payload = { cmp_file_presets: presets, cmp_file_settings: settings };

  fetch("/api/config", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})

    .then(r=>r.json()).then(d=>{

      if (d.ok) {

        config.cmp_file_presets = presets;

        config.cmp_file_settings = settings;

        document.getElementById("adv_cmp_file").value = "";

        document.getElementById("adv_cmp_title_rows").value = config.cmp_title_rows || "1";

        document.getElementById("adv_cmp_id_col").value = config.cmp_id_col || "1";

        document.getElementById("adv_cmp_output_cols").value = config.cmp_output_cols || "";

        advRefreshPresetList();

      }

    });

}

function closeAdvSettings() {

  advModal.style.display = "none";

}

function saveAdvSettings() {

  if (!_validateAdvNumbers()) return;

  const svn_user = document.getElementById("adv_svn_user").value.trim();

  const svn_pass = document.getElementById("adv_svn_pass").value;

  const exclude_dirs = document.getElementById("adv_exclude_dirs").value.trim();

  const payload = { svn_user, cmp_title_rows: document.getElementById("adv_cmp_title_rows").value.trim() || "1", cmp_id_col: document.getElementById("adv_cmp_id_col").value || "1", cmp_output_cols: document.getElementById("adv_cmp_output_cols").value.trim() };

  if (svn_pass) payload.svn_pass = svn_pass;

  if (exclude_dirs) payload.exclude_dirs = exclude_dirs;

  else payload.exclude_dirs = "";

  document.querySelector("[data-action='save-adv-settings']").textContent = "保存中…";

  fetch("/api/config", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})

    .then(r=>r.json()).then(d=>{

      if (d.ok) {

        config.svn_user = svn_user;

        config.exclude_dirs = exclude_dirs;

        config.cmp_title_rows = payload.cmp_title_rows;

        config.cmp_id_col = payload.cmp_id_col;

        config.cmp_output_cols = payload.cmp_output_cols;

        closeAdvSettings();

      }

    }).finally(()=>{

      document.querySelector("[data-action='save-adv-settings']").textContent = "保存";

    });

}

let _mergeData = {versions:[], checkedRevs:{}, checkedFiles:{}, totalChecked:0, stripPrefix:""};

function _basename(p) {

  p = p.replace(/\/$/, "");

  const idx = p.lastIndexOf("/");

  return idx >= 0 ? p.substring(idx + 1) : p;

}

function _dirname(p) {

  p = p.replace(/\/$/, "");

  const idx = p.lastIndexOf("/");

  return idx >= 0 ? p.substring(0, idx) : "";

}

document.addEventListener("click",e=>{

  const stopBtn = e.target.closest("[data-task-id]");

  if (stopBtn && stopBtn.dataset.taskId) {

    (async () => {

      if (!(await showConfirm({title:"确认停止", message:"确定要停止运行吗？", danger:true}))) return;

      const tid = stopBtn.dataset.taskId;

      // 只发取消请求，不清按钮也不清 data-task-id

      // 让后续的 onerror/[DONE] 自然清理（_done / _mergeDone 等负责恢复按钮和计数器）

      fetch("/api/task/cancel", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task_id: tid})}).catch(()=>{});

    })();

    return;

  }

  const target = e.target.closest("[data-action]");

  if(!target) return;

  const action = target.dataset.action;

  switch(action){

    case "run-svn": runSvn(); break;

    case "run-upload": runUpload(); break;

    case "run-translate": runTranslate(); break;

    case "run-text-check": runTextCheck(); break;

    case "wf-create": wfCreate(); break;

    case "svn-advanced": openAdvSettings(); break;

    case "close-adv-settings": closeAdvSettings(); break;

    case "save-adv-settings": saveAdvSettings(); break;

    case "adv-save-preset": saveAdvFilePreset(); break;

    case "adv-del-preset": delAdvFilePreset(); break;

    case "svn-clear-cache":

      fetch("/api/cache/clear", {method:"POST"}).then(r=>r.json()).then(d=>{

        const el = document.getElementById("svn_log");

        const div = document.createElement("div");

        div.textContent = `${d.ok ? "🗑 已清除" : "⚠ 清除失败"} ${d.count||0} 个缓存文件`;

        el.appendChild(div);

      }); break;

    case "clear-changelist": {

      const tgt = document.getElementById("upload_tgt").value.trim();

      if (!tgt) { _showToast("请先选择目标SVN目录"); break; }

      fetch("/api/svn/clear-changelist", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target_dir:tgt})})

        .then(r=>r.json()).then(d=>{

          if (d.ok) { _showToast("✅ changelist 已清理"); }

          else { _showToast("❌ "+ (d.error||"清理失败")); }

        });

      break;

    }

    case "tr-lang-adv-settings": openTrLangAdvSettings(); break;

    case "tr-lang-close-adv": closeTrLangAdvSettings(); break;

    case "tr-lang-save-adv": saveTrLangAdvSettings(); break;

    case "browse-svn-output": {

      const _so = document.getElementById("svn_output").value.trim();

      browseDir("svn_output", () => {
        const val = document.getElementById("svn_output").value.trim();
        if (!val) return;
        const hist = [val, ...(config.output_dir_history||[]).filter(u=>u!==val)].slice(0,10);
        saveConfig({output_dir: val, output_dir_history: hist});
        config.output_dir = val;
        config.output_dir_history = hist;
        initSuggest("svn_output", hist);
      }, _so || "");

      break;

    }

    case "browse-svn-url": {

      const v = document.getElementById("svn_url").value.trim();

      if (v.startsWith("http")) {

        fetch("/api/svn/find-wc", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:v})})

          .then(r=>r.json()).then(d=>{

            const startPath = (d.ok && d.path) ? d.path : null;

            browseDir("svn_url", onSvnUrlPicked, startPath);

          });

      } else {

        browseDir("svn_url", onSvnUrlPicked);

      }

      break;

    }

    case "open-svn-url": {

      const v = document.getElementById("svn_url").value.trim();

      if (!v) break;

      if (v.startsWith("http")) {

        fetch("/api/svn/open-wc", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:v})})

          .then(r=>r.json()).then(d=>{if(!d.ok) _showToast(d.error||"未找到本地副本");});

      } else {

        _openFolder(v);

      }

      break;

    }

    case "open-svn-output": {

      const _p = document.getElementById("svn_output").value.trim();

      if (_p) _openFolder(_p);

      break;

    }

    case "browse-upload-src": {

      const _us = document.getElementById("upload_src").value.trim();

      browseDir("upload_src", refreshFiles, _us || "");

      break;

    }

    case "browse-merge-source": {

      const _ms0 = document.getElementById("merge_source").value.trim();

      const _msDir = _ms0 ? (_ms0.substring(0, Math.max(_ms0.lastIndexOf("\\"), _ms0.lastIndexOf("/"))) || _ms0) : "";

      browseDir("merge_source", function(){
        const p = document.getElementById("merge_source").value.trim();
        if (!p) return;
        fetch("/api/svn/detect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:p})})
          .then(r=>r.json()).then(d=>{
            if (d.ok) {
              // 输入框显示本地路径，SVN URL 存 dataset.url
              document.getElementById("merge_source").dataset.url = d.url;
              document.getElementById("merge_source").value = p;
              saveSvnUrlValue("merge_source", d.url);
            }
          });
      }, _msDir);

      break;

    }

    case "open-merge-source": {

      const _ms = document.getElementById("merge_source").value.trim();

      if (!_ms) break;

      if (_ms.startsWith("http")) {

        fetch("/api/svn/open-wc", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:_ms})})

          .then(r=>r.json()).then(d=>{if(!d.ok) _showToast(d.error||"未找到本地副本");});

      } else {

        _openFolder(_ms);

      }

      break;

    }

    case "browse-merge-target": {

      const _mt0 = document.getElementById("merge_target").value.trim();

      const _mtDir = _mt0 ? (_mt0.substring(0, Math.max(_mt0.lastIndexOf("\\"), _mt0.lastIndexOf("/"))) || _mt0) : "";

      browseDir("merge_target", function(){
        const val = document.getElementById("merge_target").value.trim();
        if (val && !(config.merge_target_history||[]).includes(val)) {
          saveConfig({merge_target_history:[val, ...(config.merge_target_history||[])].slice(0,20)});
          config.merge_target_history = [val, ...(config.merge_target_history||[])].slice(0,20);
          initSuggest("merge_target", config.merge_target_history);
        }
      }, _mtDir);

      break;

    }

    case "open-merge-target": {

      const _mt = document.getElementById("merge_target").value.trim();

      if (_mt) _openFolder(_mt);

      break;

    }

    case "browse-upload-tgt": {

      const _ut = document.getElementById("upload_tgt").value.trim();

      browseDir("upload_tgt", null, _ut || "");

      break;

    }

    case "refresh-files": refreshFiles(); break;

    case "select-all": selectAllFiles(true); break;

    case "select-none": selectAllFiles(false); break;

    case "browse-tc-file": {

      browseFile("tc_path");

      break;

    }

    case "browse-tc-exclude": {

      browseFile("tc_exclude_path");

      break;

    }

    case "open-tc-exclude": {

      const p = document.getElementById("tc_exclude_path").value.trim();

      if (p) _openFolder(p);

      break;

    }

    case "browse-tr-src": {

      const _ts = document.getElementById("tr_src").value.trim();

      const _tsDir = _ts ? (_ts.substring(0, Math.max(_ts.lastIndexOf("\\"), _ts.lastIndexOf("/"))) || _ts) : "";

      browseFile("tr_src", _tsDir);

      break;

    }

    case "open-tr-src": {

      const _s = document.getElementById("tr_src").value.trim();

      if (_s) _openFolder(_s);

      break;

    }

    case "open-tr-ref": {

      const _r = document.getElementById("tr_ref").value.trim();

      if (_r) _openFolder(_r);

      break;

    }

    case "browse-tr-ref": {

      const _tr = document.getElementById("tr_ref").value.trim();

      const _trDir = _tr ? (_tr.substring(0, Math.max(_tr.lastIndexOf("\\"), _tr.lastIndexOf("/"))) || _tr) : "";

      browseFile("tr_ref", _trDir);

      break;

    }

    case "browse-tr-out": {

      const _to = document.getElementById("tr_out").value.trim();

      browseDir("tr_out", null, _to || "");

      break;

    }

    case "open-tr-out": {

      const _o = document.getElementById("tr_out").value.trim();

      if (_o) _openFolder(_o);

      break;

    }

    case "close-dir-modal": closeDirModal(); break;

    case "confirm-dir": confirmDir(); break;

    case "dismiss-zoom-warn": {

      const w = document.getElementById("zoom_warning");

      w.classList.remove("visible");

      w.dataset.dismissed = "1";

      break;

    }

    case "merge-query": runMergeQuery(); break;

    case "merge-analyze": runMergeAnalysis(); break;

    case "merge-run": runMergeRun(); break;

    case "merge-select-all": if (typeof _selectAllMergeFiles === "function") _selectAllMergeFiles(true); break;

    case "merge-select-invert": {

      const items = document.querySelectorAll("#merge_file_list .merge-file-item");

      items.forEach(el => {

        _toggleMergeFile(el.dataset.path);

      });

      break;

    }

    case "merge-select-clear": if (typeof _selectAllMergeFiles === "function") _selectAllMergeFiles(false); break;

    case "merge-ver-select-all": {

      _mergeData.versions.forEach(v => { _mergeData.checkedRevs[v.rev] = true; });

      renderMergeVersions();

      _updateMergeVersionCount();

      break;

    }

    case "merge-ver-select-invert": {

      _mergeData.versions.forEach(v => { _mergeData.checkedRevs[v.rev] = !_mergeData.checkedRevs[v.rev]; });

      renderMergeVersions();

      _updateMergeVersionCount();

      break;

    }

    case "merge-ver-select-clear": {

      _mergeData.versions.forEach(v => { _mergeData.checkedRevs[v.rev] = false; });

      renderMergeVersions();

      _updateMergeVersionCount();

      break;

    }

    case "assist-browse-meta": {
      var _inp = document.getElementById("assist_meta_path");
      if (!_inp) { _showToast("请先切换到辅助功能页签"); break; }
      browseFile("assist_meta_path", "", "*.meta");
      break;
    }

    case "assist-browse-folder": {
      var _inp2 = document.getElementById("assist_folder_path");
      if (!_inp2) { _showToast("请先切换到辅助功能页签"); break; }
      browseDir("assist_folder_path", function() {
        if (typeof window._assistHandleFolder === "function")
          window._assistHandleFolder(document.getElementById("assist_folder_path").value);
      });
      break;
    }

  }

});

document.addEventListener("change",e=>{

  if(!e.target.matches(".file-item input[type='checkbox']")) return;

  const item = e.target.closest(".file-item");

  const idx = Number(item.dataset.idx);

  uploadFilesData[idx]._sel = e.target.checked;

  item.classList.toggle("selected", e.target.checked);

});

document.addEventListener("click",e=>{

  const item = e.target.closest(".file-item");

  if(!item) return;

  if(e.target.matches("input")) return;

  const idx = Number(item.dataset.idx);

  const file = uploadFilesData[idx];

  file._sel = !file._sel;

  const checkbox = item.querySelector("input[type='checkbox']");

  checkbox.checked = file._sel;

  item.classList.toggle("selected", file._sel);

});

document.addEventListener("click",e=>{

  const navItem = e.target.closest("[data-key]");

  if(navItem){

    const key = navItem.dataset.key;

    if(key && S[key]) switchTab(key);

  }

});

document.addEventListener("click",e=>{

  const toggle = e.target.closest(".toggle-btn");

  if(!toggle) return;

  const group = toggle.closest(".toggle-group");

  if(!group) return;

  group.querySelectorAll(".toggle-btn").forEach(b=>b.classList.remove("active"));

  toggle.classList.add("active");

});

document.addEventListener("click", e => {

  const item = e.target.closest(".merge-version-item");

  if (!item) return;

  if (e.target.closest("input[type='checkbox']")) return;

  if (window.getSelection && window.getSelection().toString()) return;

  const rev = Number(item.dataset.rev);

  const was = _mergeData.checkedRevs[rev];

  _mergeData.checkedRevs[rev] = !was;

  item.classList.toggle("checked", !was);

  const cb = item.querySelector("input[type='checkbox']");

  if (cb) cb.checked = !was;

  _refreshMergeFileList();

  _updateMergeVersionCount();

});

document.addEventListener("change", e => {

  const item = e.target.closest(".merge-version-item input[type='checkbox']");

  if (!item) return;

  const verItem = item.closest(".merge-version-item");

  if (!verItem) return;

  const rev = Number(verItem.dataset.rev);

  _mergeData.checkedRevs[rev] = item.checked;

  verItem.classList.toggle("checked", item.checked);

  _refreshMergeFileList();

  _updateMergeVersionCount();

});

document.addEventListener("change", e => {

  if (!e.target.matches("#merge_file_list .merge-file-item input[type='checkbox']")) return;

  const item = e.target.closest(".merge-file-item");

  if (!item) return;

  if (typeof _toggleMergeFile === "function") _toggleMergeFile(item.dataset.path);

});

document.addEventListener("click", e => {

  const item = e.target.closest(".merge-file-item");

  if (!item) return;

  if (e.target.matches("input")) return;

  if (window.getSelection && window.getSelection().toString()) return;

  if (e.shiftKey && _mergeData.lastFileIdx !== undefined) {

    const items = document.querySelectorAll("#merge_file_list .merge-file-item");

    const curIdx = Number(item.dataset.idx);

    // Determine target state from the clicked item

    const targetState = !_mergeData.checkedFiles[item.dataset.path];

    const start = Math.min(_mergeData.lastFileIdx, curIdx);

    const end = Math.max(_mergeData.lastFileIdx, curIdx);

    for (var i = start; i <= end; i++) {

      var p = items[i].dataset.path;

      var was = _mergeData.checkedFiles[p];

      if (was === targetState) continue;

      _mergeData.checkedFiles[p] = targetState;

      _mergeData.totalChecked += targetState ? 1 : -1;

      items[i].classList.toggle("checked", targetState);

      items[i].querySelector("input[type='checkbox']").checked = targetState;

    }

    _updateMergeFileCount();

  } else {

    if (typeof _toggleMergeFile === "function") _toggleMergeFile(item.dataset.path);

    _mergeData.lastFileIdx = Number(item.dataset.idx);

  }

});

document.addEventListener("input",e=>{

  // wf_name handler removed - workflow name editing now done via settings modal

});

let _suggests = {};

let _activeInputId = null;

let _portal = null;

function isSvnUrl(val) {

  const s = (val || "").trim().toLowerCase();

  return s.startsWith("svn://") || ((s.startsWith("http://") || s.startsWith("https://")) && s.includes("/svn/"));

}

function _dateRangeError(start, end) {

  function isValid(value) {

    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;

    const parts = value.split("-").map(Number);

    const date = new Date(parts[0], parts[1] - 1, parts[2]);

    return date.getFullYear() === parts[0] && date.getMonth() === parts[1] - 1 && date.getDate() === parts[2];

  }

  if (!isValid(start) || !isValid(end)) return "请输入有效日期，格式如 2026-01-01";

  if (start > end) return "开始日期不能晚于结束日期";

  return "";

}

function getSvnUrlHistory() {

  return (config.svn_urls || []).filter(isSvnUrl);

}

function saveSvnUrlValue(inputId, val) {

  if (!isSvnUrl(val)) return;

  const key = inputId === "merge_source" ? "merge_source_current" : "svn_url_current";

  const hist = [val, ...getSvnUrlHistory().filter(u => u !== val)].slice(0, 20);

  config[key] = val;

  config.svn_urls = hist;

  saveConfig({[key]: val, svn_urls: hist});

  ["svn_url", "merge_source"].forEach(id => {

    if (document.getElementById(id)) initSuggest(id, hist);

  });

}

function _getPortal() {

  if (!_portal) {

    _portal = document.createElement("div");

    _portal.className = "suggest-drop";

    document.body.appendChild(_portal);

  }

  return _portal;

}

function initSuggest(inputId, items) {

  _suggests[inputId] = { items: items || [] };

}

function _showSuggest(inputId, showAll) {

  const s = _suggests[inputId];

  if (!s) return;

  const inp = document.getElementById(inputId);

  if (!inp) return;

  const val = inp.value.toLowerCase();

  const visible = s.items.map((u,i) => {
    const isObj = u && typeof u === 'object';
    return {val: isObj ? u.val : u, label: isObj ? u.label : u, idx:i};
  }).filter(x => showAll || !val || String(x.label || x.val).toLowerCase().includes(val));

  const portal = _getPortal();

  portal.innerHTML = visible.length

    ? visible.map(x => {

        const label = x.label || x.val || "⊙ 全局默认";

        const dim = !x.val ? ' style="color:var(--dim)"' : '';

        return `<div class="s-item" data-idx="${x.idx}" data-val="${escapeHtml(x.val)}"${dim}><span class="s-label">${escapeHtml(label)}</span><button class="s-del" data-del-idx="${x.idx}" title="删除">×</button></div>`;

      }).join("")

    : '<div class="s-item" style="color:var(--dim);cursor:default">无匹配记录</div>';

  const rect = inp.getBoundingClientRect();

  portal.style.top = (rect.bottom + 4) + "px";

  portal.style.left = rect.left + "px";

  portal.style.minWidth = rect.width + "px";

  portal.classList.add("show");

  _activeInputId = inputId;

  s.selIdx = -1;

}

function _hideSuggest() {

  if (_portal) _portal.classList.remove("show");

  _activeInputId = null;

}

function _selectSuggest(val) {

  if (_activeInputId) {

    const inp = document.getElementById(_activeInputId);

    inp.value = val;

    inp.dispatchEvent(new Event("input", {bubbles:true}));

    if (_activeInputId === "svn_url" || _activeInputId === "merge_source") {

      saveSvnUrlValue(_activeInputId, val);

      return _hideSuggest();

    }

    const _configMap = {svn_keyword:"svn_keyword_history",svn_author:"svn_author_history",svn_output:"output_dir_history",upload_src:"src_dir_history",upload_tgt:"tgt_dir_history",tr_src:"tr_src_history",tr_ref:"tr_ref_history",tr_out:"tr_out_dir",merge_target:"merge_target_history",merge_author:"svn_author_history",merge_keyword:"svn_keyword_history"};

    const ck = _configMap[_activeInputId];

    if (ck && config[ck]) {

      const updated = [val, ...config[ck].filter(v=>v!==val)].slice(0,20);

      saveConfig({[ck]: updated});

      config[ck] = updated;

      initSuggest(_activeInputId, updated);

    }

  }

  _hideSuggest();

}

document.addEventListener("focusin", e => {

  const inp = e.target.closest("input[autocomplete='off']");

  if (inp && inp.id && _suggests[inp.id]) _showSuggest(inp.id, true);

});

document.addEventListener("input", e => {

  const inp = e.target.closest("input[autocomplete='off']");

  if (inp && inp.id && _suggests[inp.id]) _showSuggest(inp.id);

});

document.addEventListener("click", e => {

  const del = e.target.closest("[data-del-idx]");

  if (del && _activeInputId) {

    e.stopPropagation();

    const idx = Number(del.dataset.delIdx);

    const s = _suggests[_activeInputId];

    if (s && idx >= 0 && idx < s.items.length) {

      const removed = s.items[idx];

      s.items.splice(idx, 1);

      const map = {svn_url:["svn_urls",20], merge_source:["svn_urls",20], svn_output:["output_dir_history",10], upload_src:["src_dir_history",20], upload_tgt:["tgt_dir_history",20], tr_src:["tr_src_history",20], tr_ref:["tr_ref_history",20], tr_out:["tr_out_dir",20], adv_cmp_file:["cmp_file_presets",20], merge_target:["merge_target_history",20], merge_author:["svn_author_history",20], merge_keyword:["svn_keyword_history",20]};

      const mk = map[_activeInputId];

      if (mk) {

        const hist = (config[mk[0]]||[]).filter(v=>v!==removed);

        saveConfig({[mk[0]]: hist});

        config[mk[0]] = hist;

      }

      _showSuggest(_activeInputId, true);

    }

    return;

  }

  const item = e.target.closest(".suggest-drop .s-item");

  if (item && item.dataset.val !== undefined) {

    _selectSuggest(item.dataset.val);

    return;

  }

  if (!e.target.closest(".suggest-drop") && !e.target.closest("input[autocomplete='off']")) {

    _hideSuggest();

  }

});

document.addEventListener("keydown", e => {

  if (!_activeInputId || !_portal || !_portal.classList.contains("show")) return;

  const s = _suggests[_activeInputId];

  if (!s) return;

  const items = _portal.querySelectorAll(".s-item:not([style*='cursor:default'])");

  if (e.key === "ArrowDown") {

    e.preventDefault();

    s.selIdx = Math.min((s.selIdx||-1) + 1, items.length - 1);

    items.forEach((el,i) => el.classList.toggle("sel", i === s.selIdx));

  } else if (e.key === "ArrowUp") {

    e.preventDefault();

    s.selIdx = Math.max((s.selIdx||0) - 1, 0);

    items.forEach((el,i) => el.classList.toggle("sel", i === s.selIdx));

  } else if (e.key === "Enter") {

    if (s.selIdx >= 0 && items[s.selIdx]) {

      e.preventDefault();

      _selectSuggest(items[s.selIdx].dataset.val);

    }

  } else if (e.key === "Escape") {

    _hideSuggest();

  }

});

function _initDirHistory(inputId, configKey, callback){

  const input = document.getElementById(inputId);

  if (!input) return;

  input.addEventListener("blur", async ()=>{

    const val = input.value.trim();

    if (!val) return;

    const r = await fetch("/api/path/verify", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:val})});

    const d = await r.json();

    if (!d.ok) return;

    const hist = config[configKey]||[];

    const updated = [val, ...hist.filter(v=>v!==val)].slice(0,20);

    saveConfig({[configKey]: updated});

    config[configKey] = updated;

    initSuggest(inputId, updated);

    if (callback) callback();

  });

}

let _lastDropTargetId = null;

function enablePathDrop(inputId, opts){

  opts = opts || {};

  const input = document.getElementById(inputId);

  if(!input) return;

  input.addEventListener("dragover", e=>{

    e.preventDefault();

    e.stopPropagation();

    input.classList.add("drag-over");

    _lastDropTargetId = inputId;

  });

  input.addEventListener("dragleave", ()=>{

    input.classList.remove("drag-over");

  });

  input.addEventListener("drop", e=>{

    e.preventDefault();

    input.classList.remove("drag-over");

    _lastDropTargetId = inputId;

  });

}

document.addEventListener("dragend", ()=>{

  document.querySelectorAll(".drag-over").forEach(el=>el.classList.remove("drag-over"));

});

function onSvnUrlPicked() {

  const input = document.getElementById("svn_url");

  const path = input.value.trim();

  if (!path) return;

  fetch("/api/svn/detect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path})})

    .then(r=>r.json()).then(d=>{

      if (d.ok) {

        // 输入框显示本地路径，SVN URL 存 dataset.url
        input.dataset.url = d.url;

        input.value = path;

        const svnHist = [d.url, ...getSvnUrlHistory().filter(u=>u!==d.url)].slice(0,20);

        saveConfig({

          svn_url_current: d.url,

          svn_urls: svnHist,

          output_dir_history: [path, ...(config.output_dir_history||[]).filter(v=>v!==path)].slice(0,10)

        });

        config.svn_url_current = d.url;

        config.svn_urls = svnHist;

        config.output_dir_history = [path, ...(config.output_dir_history||[]).filter(v=>v!==path)].slice(0,10);

        initSuggest("svn_url", config.svn_urls);

      } else {

        _showToast(d.error || "该文件夹不是 SVN 工作副本");

      }

    }).catch(()=>_showToast("无法检测 SVN 仓库"));

}

let _activeToast = null;

function _showToast(msg) {

  if (_activeToast) return;

  const t = document.createElement("div");

  _activeToast = t;

  Object.assign(t.style, {

    position:"fixed",top:"20%",left:"50%",transform:"translateX(-50%)",

    maxWidth:"calc(100vw - 48px)",background:"rgba(0,0,0,.85)",color:"#fff",

    padding:"10px 24px",borderRadius:"8px",fontSize:"13px",zIndex:"9999",

    textAlign:"center",overflowWrap:"anywhere",pointerEvents:"none",transition:"opacity .3s"

  });

  t.textContent = msg;

  document.body.appendChild(t);

  setTimeout(()=>{

    t.style.opacity = "0";

    setTimeout(()=>{

      t.remove();

      if (_activeToast === t) _activeToast = null;

    },300);

  },2000);

}

function showConfirm({title="确认", message="", confirmText="确定", cancelText="取消", danger=false, html=false}={}){

  return new Promise(resolve => {

    const overlay = document.getElementById("confirm_overlay");

    const titleEl = document.getElementById("confirm_title");

    const msgEl = document.getElementById("confirm_msg");

    const okBtn = document.getElementById("confirm_ok_btn");

    const cancelBtn = document.getElementById("confirm_cancel_btn");

    titleEl.textContent = title;

    if (html) msgEl.innerHTML = message; else msgEl.textContent = message;

    okBtn.textContent = confirmText;

    cancelBtn.textContent = cancelText;

    if (cancelText) {

      cancelBtn.style.display = "";

    } else {

      cancelBtn.style.display = "none";

    }

    if (danger) {

      okBtn.className = "btn btn-danger";

    } else {

      okBtn.className = "btn btn-primary";

    }

    const cleanup = () => {

      overlay.classList.remove("show");

      okBtn.removeEventListener("click", onOk);

      cancelBtn.removeEventListener("click", onCancel);

      overlay.removeEventListener("click", onOverlay);

    };

    const onOk = () => { cleanup(); resolve(true); };

    const onCancel = () => { cleanup(); resolve(false); };

    const onOverlay = (e) => { if (e.target === overlay) { cleanup(); resolve(false); } };

    okBtn.addEventListener("click", onOk);

    cancelBtn.addEventListener("click", onCancel);

    overlay.addEventListener("click", onOverlay);

    overlay.classList.add("show");

    okBtn.focus();

  });

}

function showAlert(message, title="提示"){

  return showConfirm({title, message, confirmText:"确定", cancelText:""});

}

async function browseFile(inputId, initialDir, filter) {

  if (window.pywebview && pywebview.api && pywebview.api.browseFile) {

    try {

      const path = await pywebview.api.browseFile(filter || initialDir || "");

      if (path) {

        document.getElementById(inputId).value = path;

        if (typeof window._wfModalAutoSave === "function") window._wfModalAutoSave();

      }

    } catch (e) {

      _showToast("pywebview error: " + e.message);

    }

  } else {

    const input = document.createElement("input");

    input.type = "file";

    input.accept = filter || ".xlsx,.xls,.xlsm";

    input.onchange = () => {

      if (input.files[0]) {

        document.getElementById(inputId).value = input.files[0].path || input.files[0].name;

      }

    };

    input.click();

  }

}

function getBrowserZoom() {

  if (window.visualViewport && window.visualViewport.scale) {

    return window.visualViewport.scale;

  }

  if (window.outerWidth && window.innerWidth) {

    return Math.round(window.outerWidth / window.innerWidth * 100) / 100;

  }

  return 1;

}

function checkZoom() {

  const scale = getBrowserZoom();

  const warn = document.getElementById("zoom_warning");

  if (!warn || warn.dataset.dismissed === "1") return;

  if (Math.abs(scale - 1) > 0.02) {

    warn.classList.add("visible");

  } else {

    warn.classList.remove("visible");

  }

}

function _showUpdateBar(data) {

  const bar = document.getElementById("update_bar");

  const text = document.getElementById("update_text");

  const dismiss = document.getElementById("update_dismiss");

  if (!bar || !text || !dismiss) return;

  text.textContent = `📦 新版本 ${data.latest} 可用`;

  if (data.force) {

    dismiss.style.display = "none";

  }

  bar.classList.add("visible");

}

function triggerUpdateCheck() {

  const bar = document.getElementById("update_bar");

  if (!bar || bar.classList.contains("visible")) return;

  fetch("/api/update/check").then(r=>r.json()).then(data=>{

    if (data.available) {

      _showUpdateBar(data);

    }

  }).catch(()=>{});

}

function checkUpdate() {

  const bar = document.getElementById("update_bar");

  const text = document.getElementById("update_text");

  const btn = document.getElementById("update_btn");

  const dismiss = document.getElementById("update_dismiss");

  if (!bar) return;

  fetch("/api/update/check").then(r=>r.json()).then(data=>{

    if (data.available) {

      _showUpdateBar(data);

    }

  }).catch(()=>{});

  btn.onclick = ()=>{

    btn.disabled = true;

    btn.textContent = "更新中...";

    fetch("/api/update/apply", {method:"POST"}).then(r=>r.json()).then(data=>{

      if (data.ok) {

        text.textContent = "更新已启动，正在重启...";

      } else {

        btn.disabled = false;

        btn.textContent = "一键更新";

        text.textContent = "更新失败: " + (data.error || "未知错误");

      }

    }).catch(()=>{

      btn.disabled = false;

      btn.textContent = "一键更新";

      text.textContent = "网络错误，请稍后重试";

    });

  };

  dismiss.onclick = ()=>{

    bar.classList.remove("visible");

  };

}

function scrollLogToBottom() {
  var k = document.querySelector(".nav-btn.active");
  if (!k) return;
  k = k.dataset.key;
  var e;
  if (k === "workflow") {
    var s = document.querySelectorAll("#wf_log .wf-log-body");
    for (var i = 0; i < s.length; i++) { if (s[i].scrollHeight > s[i].clientHeight) s[i].scrollTop = s[i].scrollHeight; }
    return;
  } else {
    var m = {svn:"svn_log",merge:"merge_log",upload:"upload_log",workflow:"wf_log",translate:"tr_log",textcheck:"tc_log",prefab:"prefab_log",assist:"assist_log"}[k];
    if (m) e = document.getElementById(m);
  }
  if (e && e.scrollHeight > e.clientHeight) e.scrollTop = e.scrollHeight;
}

function _afterPaint() {

  return new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

}

function _waitForPywebviewApi(timeoutMs) {

  if (window.pywebview && window.pywebview.api && window.pywebview.api.app_ready) {

    return Promise.resolve(true);

  }

  return new Promise(resolve => {

    let done = false;

    const finish = ok => {

      if (done) return;

      done = true;

      window.removeEventListener("pywebviewready", onReady);

      resolve(ok);

    };

    const onReady = () => finish(!!(window.pywebview && window.pywebview.api && window.pywebview.api.app_ready));

    window.addEventListener("pywebviewready", onReady, {once:true});

    setTimeout(() => finish(!!(window.pywebview && window.pywebview.api && window.pywebview.api.app_ready)), timeoutMs);

  });

}

window.addEventListener("DOMContentLoaded", async () => {

  await loadConfig();

  switchTab("svn");

  fetch("/api/version").then(r => r.json()).then(d => {
    const el = document.getElementById("app_version");
    if (el && d.version) el.textContent = d.version;
  }).catch(() => {});

  setTimeout(checkZoom, 300);

  await _afterPaint();

  try {

    if (await _waitForPywebviewApi(500)) {

      window.pywebview.api.app_ready().catch(e => console.warn("[Splash] app_ready failed", e));

    }

  } catch(e) {

    console.warn("[Splash] app_ready not available", e);

  }

});

// 界面完全打开后再检查更新（避免阻塞启动）
(function() {
  function onAppReady() { setTimeout(checkUpdate, 1000); }
  if (document.body.classList.contains("app-ready")) {
    onAppReady();
  } else {
    new MutationObserver(function(mutations, obs) {
      if (document.body.classList.contains("app-ready")) {
        obs.disconnect();
        onAppReady();
      }
    }).observe(document.body, {attributes: true, attributeFilter: ["class"]});
  }
})();

document.getElementById("close_btn")?.addEventListener("click", ()=>{

  const closeViaHttp = () => fetch("/api/close", {method:"POST"});

  if (window.pywebview?.api?.hide_window) {

    window.pywebview.api.hide_window().then(ok => {

      if (!ok) closeViaHttp();

    }).catch(closeViaHttp);

  } else {

    closeViaHttp();

  }

});

document.getElementById("help_btn")?.addEventListener("click", ()=>{
  fetch("/api/open-help", {method:"POST"}).then(r=>r.json()).then(d=>{
    if (d.error) _showToast(d.error);
  }).catch(e=>_showToast("打开说明失败: " + e.message));
});




const RESIZE_EDGE = 8;

let _resizeState = null;



function _setEdgeCursor(cursor) {

  document.body.style.cursor = cursor;

  document.querySelectorAll('.drag-bar').forEach(el => el.style.cursor = cursor);

}



function _hasVScrollbar(el) {

  return el && el.scrollHeight > el.clientHeight;

}



function getEdge(mx, my) {

  const vw = window.innerWidth;

  const vh = window.innerHeight;

  const l = mx < RESIZE_EDGE;

  const r = mx > vw - RESIZE_EDGE;

  const t = my < RESIZE_EDGE;

  const b = my > vh - RESIZE_EDGE;

  const CORNER = 4;

  if (t && l && mx < CORNER && my < CORNER) return 'top-left';

  if (t && r && mx > vw - CORNER && my < CORNER) return 'top-right';

  if (b && l && mx < CORNER && my > vh - CORNER) return 'bottom-left';

  if (b && r && mx > vw - CORNER && my > vh - CORNER) return 'bottom-right';

  if (r) {

    const content = document.querySelector('.content');

    if (_hasVScrollbar(content)) {

      const sbw = content.offsetWidth - content.clientWidth;

      const cr = content.getBoundingClientRect();

      if (mx > cr.right - sbw) {

        return null;

      }

    }

  }

  if (l) return 'left';

  if (r) return 'right';

  if (t) return 'top';

  if (b) return 'bottom';

  return null;

}



const _cursorMap = {

  'left':'ew-resize','right':'ew-resize',

  'top':'ns-resize','bottom':'ns-resize',

  'top-left':'nwse-resize','bottom-right':'nwse-resize',

  'top-right':'nesw-resize','bottom-left':'nesw-resize',

};



let _dragState = null;

let _resizeTick = 0;



document.addEventListener('mousemove', function(e) {

  if (_resizeState || _dragState) {

    e.preventDefault();

    const now = Date.now();

    if (now - _resizeTick < 25) return;

    _resizeTick = now;

    if (window.pywebview && window.pywebview.api) {

      const p = _resizeState ? window.pywebview.api.resize() : window.pywebview.api.move();

      p.then(function(active) {

        if (!active) {

          _resizeState = null;

          _dragState = null;

          _setEdgeCursor('');

        }

      });

    }

    return;

  }

  const edge = getEdge(e.clientX, e.clientY);

  _setEdgeCursor(edge ? _cursorMap[edge] : '');

});



document.addEventListener('mousedown', function(e) {

  if (e.target.closest('.topbar') && !e.target.closest('button') && !e.target.closest('.topbar-right')) {

    const edge = getEdge(e.clientX, e.clientY);

    if (!edge) {

      e.preventDefault();

      if (window.pywebview && window.pywebview.api) {

        window.pywebview.api.start_resize('move');

        _dragState = true;

      }

      return;

    }

  }

  const edge = getEdge(e.clientX, e.clientY);

  if (!edge) return;

  e.preventDefault();

  if (window.pywebview && window.pywebview.api) {

    window.pywebview.api.start_resize(edge);

    _resizeState = true;

  }

});



document.addEventListener('mouseup', function(e) {

  if (_resizeState) {

    _resizeState = null;

    _setEdgeCursor('');

    if (window.pywebview && window.pywebview.api) {

      window.pywebview.api.stop_resize();

    }

  }

  if (_dragState) {

    _dragState = null;

    if (window.pywebview && window.pywebview.api) {

      window.pywebview.api.stop_resize();

    }

  }

});



document.addEventListener('mouseleave', function() {

  if (_resizeState || _dragState) {

    _resizeState = null;

    _dragState = null;

    _setEdgeCursor('');

    if (window.pywebview && window.pywebview.api) {

      window.pywebview.api.stop_resize();

    }

  }

});
