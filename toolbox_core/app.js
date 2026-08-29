
const _WF_ICONS = {
  play: '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M4 2v10l8-5z"/></svg>',
  stop: '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><rect x="3" y="3" width="8" height="8" rx="1.5"/></svg>',
  settings: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="7" cy="7" r="2.8"/><path d="M7 1v2M7 11v2M13 7h-2M3 7H1M11.3 2.7l-1.4 1.4M4.1 9.9l-1.4 1.4M11.3 11.3l-1.4-1.4M4.1 4.1 2.7 2.7"/></svg>'
};
const S = {};
const nav = [
  {key:"svn",label:"SVN 记录"},
  {key:"merge",label:"语义合并"},
  {key:"upload",label:"复制合并"},
  {key:"textcheck",label:"文字检测"},
  {key:"workflow",label:"工作流"},
  {key:"translate",label:"翻译"},
  {key:"prefab",label:"修改预制"},
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
  upload:{title:"复制合并",sub:"批量文件复制上传到 SVN 工作目录"},
  workflow:{title:"工作流",sub:"自动化 SVN 操作编排"},
  translate:{title:"翻译",sub:"Excel 多语言批量翻译工作台"},
  textcheck:{title:"文字表检测",sub:"Texts.xlsm 翻译质量检查 — 漏翻/占位符/标签/重复ID"},
  prefab:{title:"修改预制",sub:"预制文件批量修改工具"},
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
  } else if (key === "upload") {
    const src = document.getElementById("upload_src");
    if (src && src.value.trim()) refreshFiles();
  }
}
function buildTab(key) {
  const panel = S[key].panel;
  panel.innerHTML = '<div class="empty-state">加载中…</div>';
  void panel.offsetHeight;
  switch(key) {
    case "svn": buildSvnTab(panel); break;
    case "merge": buildMergeTab(panel); break;
    case "upload": buildUploadTab(panel); break;
    case "workflow": buildWorkflowTab(panel); break;
    case "translate": buildTranslateTab(panel); break;
    case "textcheck": buildTextCheckTab(panel); break;
    case "prefab": buildPrefabTab(panel); break;
  }
  if (key === "svn" || key === "merge") {
    setTimeout(function(){_initDatePicker(key+"_start");_initDatePicker(key+"_end")}, 0);
  }
  S[key].built = true;
}
const now = new Date();
const cy = now.getFullYear();
const cm = now.getMonth()+1;
const cd = now.getDate();
function buildSvnTab(panel) {
  const today = `${cy}-${String(cm).padStart(2,"0")}-${String(cd).padStart(2,"0")}`;
  const yearStart = `${cy}-01-01`;
  panel.innerHTML = `
    <div class="workbench svn-layout">
      <div class="svn-main">
        <div class="card">
          <div class="card-title">SVN 地址</div>
          <div class="flex-row">
            <input type="text" id="svn_url" placeholder="输入 SVN 仓库 URL" style="flex:1" autocomplete="off" class="svn-url-drop-target">
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
              <input type="text" id="svn_start" value="${yearStart}" placeholder="YYYY-MM-DD" style="flex:1;min-width:0">
              <span style="color:var(--dim)">—</span>
              <input type="text" id="svn_end" value="${today}" placeholder="YYYY-MM-DD" style="flex:1;min-width:0">
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
            <input type="text" id="svn_keyword" placeholder="按SVN提交备注过滤（逗号分隔多个）" autocomplete="off">
          </div>
          <div class="form-group">
            <label>提交者过滤</label>
            <input type="text" id="svn_author" placeholder="按作者过滤" autocomplete="off">
          </div>
          <div class="form-group">
            <label>输出目录</label>
            <div class="flex-row">
              <input type="text" id="svn_output" placeholder="选择输出目录" style="flex:1" autocomplete="off">
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
  initSuggest("svn_url", config.svn_urls||[]);
  enablePathDrop("svn_url", { mode: "svn" });
  enablePathDrop("svn_output", { mode: "path" });
  if (config.svn_urls?.length) document.getElementById("svn_url").value = config.svn_urls[0];
  document.getElementById("svn_url").addEventListener("keydown",e=>{
    if (e.key === "Enter") {
      const val = e.target.value.trim();
      if (val && val.startsWith("http")) {
        saveConfig({svn_urls: [val, ...(config.svn_urls||[]).filter(u=>u!==val)].slice(0,20)});
        config.svn_urls = [val, ...(config.svn_urls||[]).filter(u=>u!==val)].slice(0,20);
        initSuggest("svn_url", config.svn_urls);
      }
    }
  });
  document.getElementById("svn_output").value = config.output_dir || "";
  initSuggest("svn_output", config.output_dir_history||[]);
  document.getElementById("svn_url").addEventListener("blur", ()=>{
    const val = document.getElementById("svn_url").value.trim();
    if (val && val.startsWith("http") && !config.svn_urls.includes(val)) {
      saveConfig({svn_urls: [val, ...(config.svn_urls||[])].slice(0,20)});
      config.svn_urls = [val, ...(config.svn_urls||[])].slice(0,20);
      initSuggest("svn_url", config.svn_urls);
    }
  });
  document.getElementById("svn_output").addEventListener("blur", ()=>{
    const val = document.getElementById("svn_output").value.trim();
    if (val && !config.output_dir_history.includes(val)) {
      saveConfig({output_dir_history: [val, ...(config.output_dir_history||[])].slice(0,10)});
      config.output_dir_history = [val, ...(config.output_dir_history||[])].slice(0,10);
      initSuggest("svn_output", config.output_dir_history);
    }
  });
  initSuggest("svn_keyword", config.svn_keyword_history||[], true);
  initSuggest("svn_author", config.svn_author_history||[], true);
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
function runSvn() {
  triggerUpdateCheck();
  const mode = document.querySelector("#svn_mode_group .toggle-btn.active")?.dataset.v || "compare";
  const body = {
    svn_url:document.getElementById("svn_url").value.trim(),
    mode,
    start_date:document.getElementById("svn_start").value,
    end_date:document.getElementById("svn_end").value,
    keyword:document.getElementById("svn_keyword")?.value||"",
    author:document.getElementById("svn_author")?.value||"",
    output:document.getElementById("svn_output")?.value||""
  };
  const out = body.output;
  const kw = body.keyword;
  const au = body.author;
  saveConfig({
    output_dir: out,
    output_dir_history: [out, ...(config.output_dir_history||[]).filter(u=>u!==out)].slice(0,10),
    svn_urls: [body.svn_url, ...(config.svn_urls||[]).filter(u=>u!==body.svn_url)].slice(0,20),
    svn_keyword_history: kw && !(config.svn_keyword_history||[]).includes(kw) ? [kw, ...(config.svn_keyword_history||[])].slice(0,20) : config.svn_keyword_history,
    svn_author_history: au && !(config.svn_author_history||[]).includes(au) ? [au, ...(config.svn_author_history||[])].slice(0,20) : config.svn_author_history,
  });
  config.svn_urls = [body.svn_url, ...(config.svn_urls||[]).filter(u=>u!==body.svn_url)].slice(0,20);
  if (kw && !(config.svn_keyword_history||[]).includes(kw)) config.svn_keyword_history = [kw, ...(config.svn_keyword_history||[])].slice(0,20);
  if (au && !(config.svn_author_history||[]).includes(au)) config.svn_author_history = [au, ...(config.svn_author_history||[])].slice(0,20);
  initSuggest("svn_url", config.svn_urls);
  initSuggest("svn_keyword", config.svn_keyword_history||[], true);
  initSuggest("svn_author", config.svn_author_history||[], true);
  runTask("/api/svn/run", body, document.querySelector("[data-action='run-svn']"), "svn_log");
}
function buildUploadTab(panel) {
  panel.innerHTML = `
    <div class="workbench upload-layout">
      <div class="upload-main">
        <div class="card">
          <div class="card-title">源目录</div>
          <div class="flex-row">
            <input type="text" id="upload_src" placeholder="选择源目录" style="flex:1" autocomplete="off">
            <button class="btn btn-normal" data-action="browse-upload-src"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
            <button class="btn btn-normal" data-action="refresh-files" title="刷新文件列表"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0115.4-5.6L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 01-15.4 5.6L3 16"/></svg></button>
          </div>
        </div>
      </div>
      <div class="upload-side">
        <div class="card">
          <div class="section-label">目标设置</div>
          <div class="form-group">
            <label>SVN 目标目录</label>
            <div class="flex-row">
              <input type="text" id="upload_tgt" placeholder="选择目标 SVN 工作目录" style="flex:1" autocomplete="off">
              <button class="btn btn-normal" data-action="browse-upload-tgt"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
            </div>
          </div>
        </div>
      </div>
      <div class="upload-files-wrap">
        <div class="card">
          <div class="card-header compact">
            <div class="card-title">文件列表</div>
            <div class="flex-row">
              <button class="btn btn-normal btn-sm" data-action="select-all">全选</button>
              <button class="btn btn-normal btn-sm" data-action="select-none">取消全选</button>
            </div>
          </div>
          <div class="file-list" id="upload_files"></div>
        </div>
      </div>
      <div class="action-center">
        <button class="btn btn-primary" data-action="run-upload">上传到 SVN</button>
      </div>
      <div class="upload-log-wrap">
        <div class="card">
          <div class="card-header compact">
            <span style="font-weight:600">执行日志</span>
            <button class="btn btn-normal btn-sm" data-action="clear-changelist">清理changelist</button>
          </div>
          <div class="log" id="upload_log"><div class="log-anchor"></div></div>
        </div>
      </div>
    </div>
  `;
  if (config.src_dir_history?.length) document.getElementById("upload_src").value = config.src_dir_history[0];
  if (config.tgt_dir_history?.length) document.getElementById("upload_tgt").value = config.tgt_dir_history[0];
  initSuggest("upload_src", config.src_dir_history||[]);
  initSuggest("upload_tgt", config.tgt_dir_history||[]);
  S.upload.logEl = document.getElementById("upload_log");
  enablePathDrop("upload_src", { mode: "path", callback: refreshFiles });
  enablePathDrop("upload_tgt", { mode: "path" });
  let _srcTimer;
  document.getElementById("upload_src").addEventListener("input", ()=>{
    clearTimeout(_srcTimer);
    _srcTimer = setTimeout(refreshFiles, 300);
  });
  _initDirHistory("upload_src", "src_dir_history", refreshFiles);
  _initDirHistory("upload_tgt", "tgt_dir_history");
  const _src = document.getElementById("upload_src").value.trim();
  if (_src) refreshFiles();
}
let uploadFilesData = [];
async function refreshFiles() {
  const src = document.getElementById("upload_src").value.trim();
  if (!src) return;
  const r = await fetch("/api/files/list", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:src})});
  const d = await r.json();
  if (d.error) { await showAlert(d.error); return; }
  uploadFilesData = d.entries;
  renderFileList();
}
function renderFileList(){
  const container = document.getElementById("upload_files");
  container.innerHTML = uploadFilesData.map((f,i)=>`
    <div class="file-item ${f._sel ? 'selected':''}" data-idx="${i}">
      <input type="checkbox" ${f._sel ? 'checked':''}>
      <div style="flex:1">${f.is_dir ? '📁':'📄'} ${f.name}</div>
      <div style="color:var(--dim);font-size:0.8125rem">${f.size} ${f.date}</div>
    </div>
  `).join("");
}
function selectAllFiles(v) { uploadFilesData.forEach(f => f._sel = v); renderFileList(); }
function runUpload() {
  triggerUpdateCheck();
  const src = document.getElementById("upload_src").value.trim();
  const tgt = document.getElementById("upload_tgt").value.trim();
  const files = uploadFilesData.filter(f => f._sel).map(f => ({name:f.name,path:f.path,is_dir:f.is_dir}));
  saveConfig({tgt_dir_history: [tgt, ...(config.tgt_dir_history||[]).filter(u=>u!==tgt)].slice(0,20)});
  runTask("/api/upload/run", {src_dir:src, tgt_dir:tgt, files}, document.querySelector("[data-action='run-upload']"), "upload_log");
}
function buildWorkflowTab(panel) {
  const wfs = config.workflows || [];
  const typeCn = {export_text:"导出文字表",merge_table:"合并文字表",merge_translation:"合并翻译",export_error_code:"导出错误码",unlock_svn:"解锁SVN",open_tables:"打开表格",revert_svn:"SVN回退",copy_files:"整合文字表"};
  const typeIcon = {export_text:"📄",merge_table:"🔗",merge_translation:"🌐",export_error_code:"⚠",unlock_svn:"🔓",open_tables:"📂",revert_svn:"↩",copy_files:"📋"};
  const isEmpty = !wfs.length;
  panel.innerHTML = `
    <div class="wf-layout">
      <div class="card">
        <div class="card-title">工作流列表</div>
        <div class="wf-tree" id="wf_tree">
          ${isEmpty ? '<div class="empty-state" style="padding:32px 16px;color:var(--dim)">暂无工作流，点击"新建"创建</div>'
          : wfs.map((wf, i) => `
            <div class="wf-parent" data-idx="${i}">
              <div class="wf-parent-header">
                <span class="wf-arrow">▶</span>
                <input type="checkbox" class="wf-parent-check">
                <span class="wf-parent-name">${escapeHtml(wf.name)}&nbsp;&nbsp;<span style="color:var(--dim);font-weight:400">${(wf.steps||[]).filter(Boolean).length}步骤</span><span class="wf-edit-icon"><svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 1.5L10.5 3.5"/><path d="M2 10L3.5 6.5L8.5 1.5L10.5 3.5L5.5 8.5L2 10Z"/></svg></span></span>
                <span class="wf-status-dot" data-idx="${i}"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green,#4caf50);margin:0 4px"></span></span>
                <button class="wf-copy-btn" title="复制工作流"><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="3.5" y="1.5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.2"/><path d="M10 4H11V11.5C11 12.328 10.328 13 9.5 13H3.5C2.672 13 2 12.328 2 11.5V5C2 4.172 2.672 3.5 3.5 3.5H4" stroke="currentColor" stroke-width="1.2"/></svg></button>
              </div>
              <button class="wf-del-btn" title="删除工作流">✕</button>
              <div class="wf-children">
                ${(wf.steps||[]).filter(Boolean).map((s, j) => `
                  <div class="wf-child" data-step="${j}">
                    <input type="checkbox" class="wf-child-check">
                    <span class="wf-child-type ${s.type}">${typeIcon[s.type]||''} ${typeCn[s.type]||s.type}</span>
                    <span class="wf-child-name">${escapeHtml(s.name)}</span>
                    <button class="wf-step-play-btn" title="执行本步骤">${_WF_ICONS.play}</button>
                    <button class="wf-settings-btn" title="步骤设置">${_WF_ICONS.settings}</button>
                    <button class="wf-child-del-btn" title="删除步骤">✕</button>
                  </div>
                `).join('')}
                <div class="wf-add-step-item">
                  <span style="font-size:16px;font-weight:600;line-height:1">+</span>
                  <span>添加步骤</span>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
        <div class="wf-toolbar">
          <button class="btn btn-normal" data-action="wf-create">+ 新建</button>
        </div>
      </div>
      <div class="wf-log-wrap">
        <div class="card">
          <div class="card-header compact">
            <span style="font-weight:600">执行日志</span>
          </div>
          <div class="log" id="wf_log"><div class="log-anchor"></div></div>
        </div>
      </div>
    </div>
    <div class="wf-modal-overlay" id="wf_modal_overlay">
      <div class="wf-modal">
        <div class="wf-modal-header">
          <h3>步骤设置 · <span id="wf_modal_title">-</span></h3>
          <button class="wf-modal-close" id="wf_modal_close">✕</button>
        </div>
        <div class="wf-modal-body" id="wf_modal_body"></div>
        <div style="margin-top:16px;display:flex;gap:8px;justify-content:flex-end">
          <button class="btn btn-normal" id="wf_modal_cancel">取消</button>
          <button class="btn btn-primary" id="wf_modal_save">保存</button>
        </div>
      </div>
    </div>
  `;
  let expandedIdx = _wfExpandedIdx;
  const parents = panel.querySelectorAll(".wf-parent");
  if (expandedIdx >= 0 && expandedIdx < parents.length) {
    parents[expandedIdx].classList.add("expanded");
  }
  parents.forEach((el, i) => {
    const header = el.querySelector(".wf-parent-header");
    header.addEventListener("click", (e) => {
      if (e.target.closest(".wf-parent-check,.wf-copy-btn")) return;
      if (expandedIdx === i) {
        el.classList.remove("expanded");
        expandedIdx = -1;
      } else {
        parents.forEach(p => p.classList.remove("expanded"));
        el.classList.add("expanded");
        expandedIdx = i;
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            el.scrollIntoView({behavior: "smooth", block: "nearest"});
          });
        });
      }
    });
    const parentCheck = el.querySelector(".wf-parent-check");
    const childChecks = el.querySelectorAll(".wf-child-check");
    parentCheck.addEventListener("change", () => {
      childChecks.forEach(c => c.checked = parentCheck.checked);
    });
    childChecks.forEach(c => {
      c.addEventListener("change", () => {
        const allChecked = [...childChecks].every(cc => cc.checked);
        const noneChecked = [...childChecks].every(cc => !cc.checked);
        parentCheck.checked = allChecked;
        parentCheck.indeterminate = !allChecked && !noneChecked;
      });
    });
    // 父级批量执行已移除，请使用每个步骤独立的 ▶ 按钮
    const copyBtn = el.querySelector(".wf-copy-btn");
    copyBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const wfIdx = Number(el.dataset.idx);
      const orig = JSON.parse(JSON.stringify(config.workflows[wfIdx]));
      orig.name = (orig.name||"工作流") + " (副本)";
      const steps = orig.steps || [];
      const prefixes = _wfDetectPrefixes(steps);
      if (!prefixes.length) {
        config.workflows.splice(wfIdx+1, 0, orig);
        saveConfig({workflows:config.workflows});
        _wfRebuild();
        return;
      }
      _wfShowPrefixModal(prefixes, (map) => {
        if (!map) return;
        if (Object.keys(map).length) {
          Object.entries(map).forEach(([oldP, newP]) => {
            orig.steps = _wfReplacePrefixes(orig.steps, oldP, newP);
          });
        }
        config.workflows.splice(wfIdx+1, 0, orig);
        saveConfig({workflows:config.workflows});
        _wfRebuild();
      });
    });
    const addItem = el.querySelector(".wf-add-step-item");
    addItem.addEventListener("mousedown", (e) => e.stopPropagation());
    addItem.addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll("#wf_step_type_picker").forEach(m => m.remove());
      const menu = document.createElement("div");
      menu.id = "wf_step_type_picker";
      menu.style.cssText = "position:fixed;z-index:10000;background:#1c1e26;border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:4px 0;box-shadow:0 4px 24px rgba(0,0,0,.5)";
      const itemCount = Object.keys(typeCn).length;
      const estMenuH = itemCount * 30 + 8;
      const rect = addItem.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;
      if (spaceBelow >= estMenuH + 4 || spaceBelow >= spaceAbove) {
        menu.style.left = rect.left + "px";
        menu.style.top = (rect.bottom + 4) + "px";
      } else {
        menu.style.left = rect.left + "px";
        menu.style.top = (rect.top - 4 - estMenuH) + "px";
      }
      Object.entries(typeCn).forEach(([k,v]) => {
        const opt = document.createElement("div");
        opt.style.cssText = "padding:6px 16px;cursor:pointer;white-space:nowrap;font-size:13px;color:var(--text,#e0e0e0)";
        opt.textContent = `${typeIcon[k]||''} ${v}`;
        opt.addEventListener("mouseenter", () => opt.style.background = "rgba(255,255,255,.06)");
        opt.addEventListener("mouseleave", () => opt.style.background = "");
        opt.addEventListener("click", (ev) => {
          ev.stopPropagation();
          menu.remove();
          const wfIdx = Number(el.dataset.idx);
          const wf = config.workflows[wfIdx];
          if (!wf) return;
          const step = {type: k, name: ""};
          if (k === "revert_svn") {
            step.exclude_paths = ["Assets/Code_Lua/test/test.lua", "Assets/StreamingAssets/LocalVersion.xml", "InstallClient.bat"];
          }
          const autoName = _wfAutoName(step);
          if (autoName) step.name = autoName;
          wf.steps.push(step);
          const stepIdx = wf.steps.length - 1;
          saveConfig({workflows:config.workflows});
          _wfRebuild();
          const parentEl = document.querySelector(`.wf-parent[data-idx="${wfIdx}"]`);
          if (parentEl) {
            document.querySelectorAll(".wf-parent.expanded").forEach(p => p.classList.remove("expanded"));
            parentEl.classList.add("expanded");
          }
          setTimeout(() => {
            const step = config.workflows[wfIdx]?.steps?.[stepIdx];
            if (!step) return;
            document.getElementById("wf_modal_title").textContent = typeCn[step.type] || step.type;
            document.getElementById("wf_modal_body").innerHTML = _wfModalFields(step.type, step);
            document.getElementById("wf_modal_overlay").dataset.modalCtx = JSON.stringify({ wfIdx, stepIdx });
            document.getElementById("wf_modal_overlay").classList.add("show");
            setTimeout(() => {
              document.getElementById("wf_modal_body").querySelectorAll("[id^=wf_m_]").forEach(inp => {
                if (inp.id) enablePathDrop(inp.id);
              });
            }, 50);
          }, 50);
        });
        menu.appendChild(opt);
      });
      document.body.appendChild(menu);
    });
    const delBtn = el.querySelector(".wf-del-btn");
    delBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const wfIdx = Number(el.dataset.idx);
      const name = config.workflows[wfIdx]?.name || "未命名";
      const ok = await showConfirm({title:"删除工作流", message:`确定删除工作流「${name}」？`, confirmText:"删除", danger:true});
      if (!ok) return;
      config.workflows.splice(wfIdx, 1);
      saveConfig({workflows:config.workflows});
      _wfRebuild();
    });
    const nameSpan = el.querySelector(".wf-parent-name");
    nameSpan.addEventListener("click", (e) => {
      e.stopPropagation();
      if (nameSpan.querySelector("input")) return;
      const wfIdx = Number(el.dataset.idx);
      const currentName = config.workflows[wfIdx]?.name || "";
      const input = document.createElement("input");
      input.className = "wf-name-input";
      input.value = currentName;
      nameSpan.textContent = "";
      nameSpan.appendChild(input);
      input.focus();
      input.select();
      const finish = (save) => {
        const val = input.value.trim();
        if (save && val && config.workflows[wfIdx]) {
          config.workflows[wfIdx].name = val;
          saveConfig({workflows:config.workflows});
        }
        if (config.workflows[wfIdx]) {
          nameSpan.innerHTML = `${escapeHtml(config.workflows[wfIdx].name)}&nbsp;&nbsp;<span style="color:var(--dim);font-weight:400">${(config.workflows[wfIdx].steps||[]).length}步骤</span><span class="wf-edit-icon"><svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 1.5L10.5 3.5"/><path d="M2 10L3.5 6.5L8.5 1.5L10.5 3.5L5.5 8.5L2 10Z"/></svg></span>`;
        }
      };
      input.addEventListener("blur", () => finish(true));
      input.addEventListener("keydown", (ke) => {
        if (ke.key === "Enter") { ke.preventDefault(); input.blur(); }
        if (ke.key === "Escape") { ke.preventDefault(); finish(false); }
      });
    });
  });

  const overlay = document.getElementById("wf_modal_overlay");
  const modalBody = document.getElementById("wf_modal_body");
  const modalTitle = document.getElementById("wf_modal_title");
  let _modalCtx = null;
  let _wfSaving = false;

  function _wfModalDoSave() {
    if (_wfSaving) return;
    const ctx = _modalCtx || (overlay.dataset.modalCtx ? JSON.parse(overlay.dataset.modalCtx) : null);
    if (!ctx) return;
    _wfSaving = true;
    const { wfIdx, stepIdx } = ctx;
    const step = config.workflows[wfIdx]?.steps?.[stepIdx];
    if (!step) { _wfSaving = false; return; }
    modalBody.querySelectorAll(".wf-modal-input").forEach(inp => {
      const key = inp.dataset.key;
      if (!key) return;
      const arrKeys = ["tools","dirs","file_paths","update_dirs","exclude_paths","upload_svn_dir","revert_paths"];
      if (arrKeys.includes(key)) {
        step[key] = inp.value.split(",").map(s => s.trim()).filter(Boolean);
      } else {
        step[key] = inp.value;
      }
    });
    modalBody.querySelectorAll("input[type=checkbox][data-key]").forEach(inp => {
      step[inp.dataset.key] = inp.checked;
    });
    const autoName = _wfAutoName(step);
    if (autoName) step.name = autoName;
    saveConfig({workflows:config.workflows});
    overlay.classList.remove("show");
    _modalCtx = null;
    _wfSaving = false;
    const childEl = document.querySelector(`.wf-parent[data-idx="${wfIdx}"] .wf-child[data-step="${stepIdx}"] .wf-child-name`);
    if (childEl) childEl.textContent = step.name;
    _showToast("步骤设置已保存");
  }

  function _wfModalAutoSave() {
    if (_wfSaving) return;
    const ctx = _modalCtx || (overlay.dataset.modalCtx ? JSON.parse(overlay.dataset.modalCtx) : null);
    if (!ctx) return;
    _wfSaving = true;
    const { wfIdx, stepIdx } = ctx;
    const step = config.workflows[wfIdx]?.steps?.[stepIdx];
    if (!step) { _wfSaving = false; return; }
    modalBody.querySelectorAll(".wf-modal-input").forEach(inp => {
      const key = inp.dataset.key;
      if (!key) return;
      const arrKeys = ["tools","dirs","file_paths","update_dirs","exclude_paths","upload_svn_dir","revert_paths"];
      if (arrKeys.includes(key)) {
        step[key] = inp.value.split(",").map(s => s.trim()).filter(Boolean);
      } else {
        step[key] = inp.value;
      }
    });
    modalBody.querySelectorAll("input[type=checkbox][data-key]").forEach(inp => {
      step[inp.dataset.key] = inp.checked;
    });
    const autoName = _wfAutoName(step);
    if (autoName) step.name = autoName;
    saveConfig({workflows:config.workflows});
    _wfSaving = false;
    const childEl = document.querySelector(`.wf-parent[data-idx="${wfIdx}"] .wf-child[data-step="${stepIdx}"] .wf-child-name`);
    if (childEl) childEl.textContent = step.name;
  }
  window._wfModalAutoSave = _wfModalAutoSave;

  function _wfModalFields(type, step) {
    const v = (key) => escapeHtml(Array.isArray(step[key]) ? step[key].join(", ") : step[key]||"");
    const _fb = (label, dataKey, id, browseType, append) => `
      <div class="form-group"><label>${label}</label>
        <div class="flex-row"><input type="text" class="wf-modal-input" id="${id}" data-key="${dataKey}" value="${v(dataKey)}" style="flex:1" placeholder="${browseType==='dir'?'选择目录':'选择文件'}">
        <button class="btn btn-normal btn-sm" onclick="(function(t,i,a){if(a){_browseDirAppend(i)}else{var v=document.getElementById(i).value.trim(),d=v.substring(0,v.lastIndexOf('\\\\'));if(!d)d=v;if(t==='file')browseFile(i,d||'');else browseDir(i,null,d||'');}})('${browseType.replace(/'/g,"\\'")}','${id}',${!!append})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button></div></div>`;
    const m = {
      export_text: `
        ${_fb("主文件路径","input_file","wf_m_input_file","file")}
        ${_fb("上传SVN目录","upload_svn_dir","wf_m_upload_svn_dir","dir", true)}`,
      upload_svn: `
        <div class="form-group"><label>源目录（逗号分隔）</label><input type="text" class="wf-modal-input" id="wf_m_dirs" data-key="dirs" value="${v("dirs")}" placeholder="多个目录用,分隔"></div>`,
      merge_table: `
        ${_fb("输入文件","input_dir","wf_m_input_dir","file")}
        ${_fb("输出文件","target_dir","wf_m_target_dir","file")}
        <div class="form-group"><label>标题行</label><input type="number" class="wf-modal-input" id="wf_m_title_rows" data-key="title_rows" value="${v("title_rows")||"1"}" min="1" step="1"></div>
        <div class="form-group"><label>ID列</label><input type="number" class="wf-modal-input" id="wf_m_id_col" data-key="id_col" value="${v("id_col")||"1"}" min="1" step="1"></div>`,
      merge_translation: `
        ${_fb("翻译文件","input_file","wf_m_tr_input","file")}
        ${_fb("目标文件","original_file","wf_m_orig_file","file")}`,
      export_error_code: `
        ${_fb("根目录","root_dir","wf_m_root_dir","dir")}
        <div class="form-group"><label>语言代码</label><input type="text" class="wf-modal-input" id="wf_m_ec_lang" data-key="lang_codes" value="${v("lang_codes")}"></div>
        ${_fb("上传SVN目录","upload_svn_dir","wf_m_upload_svn_dir_ec","dir", true)}`,
      lock_svn: `
        ${_fb("目标文件路径","target_path","wf_m_target_path","file")}
        <div class="form-group"><label>更新目录（逗号分隔）</label><input type="text" class="wf-modal-input" id="wf_m_update_dirs" data-key="update_dirs" value="${v("update_dirs")}" placeholder="多个目录用,分隔"></div>
        <div class="form-group"><label>锁定消息</label><input type="text" class="wf-modal-input" id="wf_m_lock_msg" data-key="lock_msg" value="${v("lock_msg")}"></div>`,
      unlock_svn: `
        ${_fb("目标文件路径","target_path","wf_m_target_path","file")}
        <div class="form-group"><label>更新目录（逗号分隔）</label><input type="text" class="wf-modal-input" id="wf_m_update_dirs" data-key="update_dirs" value="${v("update_dirs")}" placeholder="多个目录用,分隔"></div>
        <div class="form-group"><label>解锁消息</label><input type="text" class="wf-modal-input" id="wf_m_lock_msg" data-key="lock_msg" value="${v("lock_msg")}"></div>`,
      open_tables: `
        <div class="form-group"><label>文件路径（逗号分隔）</label><input type="text" class="wf-modal-input" id="wf_m_file_paths" data-key="file_paths" value="${v("file_paths")}" placeholder="多个文件用,分隔"></div>`,
      revert_svn: `
        <div class="form-group"><label>回退路径（逗号分隔）</label>
          <div class="flex-row"><input type="text" class="wf-modal-input" id="wf_m_rv_paths" data-key="revert_paths" value="${v("revert_paths")}" style="flex:1" placeholder="多个路径用,分隔">
          <button class="btn btn-normal btn-sm" onclick="browseDir('wf_m_rv_paths',null,null,true)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button></div></div>
        <div class="form-group"><label>排除路径（逗号分隔）</label>
          <input type="text" class="wf-modal-input" id="wf_m_rv_exclude" data-key="exclude_paths" value="${v("exclude_paths")}" placeholder="多个路径用,分隔">
        </div>
        <label class="wf-rv-check"><input type="checkbox" data-key="delete_unversioned" ${step.delete_unversioned?'checked':''}> 永久删除未版本控制的文件</label>`,
      copy_files: `
        ${_fb("源目录","src_dir","wf_m_cf_src","dir")}
        ${_fb("目标目录","tgt_dir","wf_m_cf_tgt","dir")}`,
    };
    return m[type] || '<div class="form-group"><span style="color:var(--dim)">无可用设置</span></div>';
  }

  function _wfHistoryPool(key) {
    if (["input_file","original_file","target_path","root_dir","target_dir"].includes(key)) return "wf_history_paths";
    if (["sheet_name","lock_msg"].includes(key)) return "wf_history_msgs";
    return "wf_history_texts";
  }
  function _wfHistorySave(pool, val) {
    if (!val.trim()) return;
    const key = "_" + pool;
    const arr = config[key] || [];
    const updated = [val, ...arr.filter(v => v !== val)].slice(0, 30);
    config[key] = updated;
    saveConfig({[key]: updated});
  }
  function _wfHistoryShow(inp, pool) {
    const key = "_" + pool;
    const items = config[key] || [];
    if (!items.length) return;
    if (_wfHistoryDd) _wfHistoryDd.remove();
    const dd = document.createElement("div");
    dd.className = "wf-history-drop";
    items.forEach((v, i) => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;padding:4px 12px;font-size:13px;color:var(--text);cursor:pointer;word-break:break-all;line-height:1.4";
      row.addEventListener("mouseenter", () => row.style.background = "rgba(94,162,255,.1)");
      row.addEventListener("mouseleave", () => row.style.background = "");
      const label = document.createElement("span");
      label.style.cssText = "flex:1;min-width:0;word-break:break-all;line-height:1.4";
      label.textContent = v;
      row.appendChild(label);
      const del = document.createElement("span");
      del.textContent = "×";
      del.style.cssText = "cursor:pointer;color:var(--dim);font-size:14px;line-height:1;padding:0 2px 0 8px;flex-shrink:0";
      del.addEventListener("mouseenter", () => del.style.color = "var(--danger)");
      del.addEventListener("mouseleave", () => del.style.color = "var(--dim)");
      del.addEventListener("mousedown", (dEv) => {
        dEv.stopPropagation();
        dEv.preventDefault();
        const hist = (config[key]||[]).filter((_, idx) => idx !== i);
        config[key] = hist;
        saveConfig({[key]: hist});
        dd.remove();
        _wfHistoryDd = null;
        inp.focus();
        setTimeout(() => _wfHistoryShow(inp, pool), 50);
      });
      row.appendChild(del);
      row.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        inp.value = v;
        inp.dispatchEvent(new Event("input", {bubbles: true}));
        dd.remove();
        _wfHistoryDd = null;
        inp.focus();
      });
      dd.appendChild(row);
    });
    const rect = inp.getBoundingClientRect();
    dd.style.left = rect.left + "px";
    dd.style.top = (rect.bottom + 4) + "px";
    dd.style.minWidth = Math.max(rect.width, 160) + "px";
    dd.classList.add("show");
    document.body.appendChild(dd);
    _wfHistoryDd = dd;
  }

  let _wfCfEntries = [];
  let _wfCfLastSrcDir = "";

  window._wfCfRefresh = async function() {
    const src = document.querySelector("#wf_m_cf_src")?.value?.trim();
    if (!src) return;
    if (_modalCtx) {
      const wf = config.workflows[_modalCtx.wfIdx];
      if (wf) wf.steps[_modalCtx.stepIdx].src_dir = src;
    }
    const prevSrc = _wfCfLastSrcDir || "";
    _wfCfLastSrcDir = src;
    const r = await fetch("/api/files/list", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:src})});
    const d = await r.json();
    if (d.error) { await showAlert(d.error); return; }
    _wfCfEntries = d.entries || [];
    if (prevSrc && prevSrc !== src) {
      _wfCfEntries.forEach(f => f._sel = false);
    } else {
      const savedFiles = (_modalCtx && config.workflows[_modalCtx.wfIdx]?.steps?.[_modalCtx.stepIdx]?.selected_files) || [];
      _wfCfEntries.forEach(f => {
        f._sel = savedFiles.some(sf => sf.path === f.path);
      });
    }
    _wfCfRender();
  };

  function _wfCfRender() {
    const container = document.getElementById("wf_cf_file_list");
    if (!container) return;
    if (!_wfCfEntries.length) {
      container.innerHTML = '<div class="empty-state" style="padding:16px;color:var(--dim);text-align:center">目录为空</div>';
      _wfCfUpdateCount();
      return;
    }
    container.innerHTML = _wfCfEntries.map((f, i) =>
      `<div class="file-item ${f._sel?'selected':''}" data-idx="${i}">
        <input type="checkbox" ${f._sel?'checked':''}>
        <div style="flex:1">${f.is_dir?'📁':'📄'} ${escapeHtml(f.name)}</div>
        <div style="color:var(--dim);font-size:0.8125rem">${f.size} ${f.date||''}</div>
      </div>`
    ).join("");
    _wfCfUpdateCount();
  }

  function _wfCfToggle(i) {
    if (i < 0 || i >= _wfCfEntries.length) return;
    _wfCfEntries[i]._sel = !_wfCfEntries[i]._sel;
    _wfCfRender();
  }

  window._wfCfSelAll = function() { _wfCfEntries.forEach(f => f._sel = true); _wfCfRender(); };
  window._wfCfSelNone = function() { _wfCfEntries.forEach(f => f._sel = false); _wfCfRender(); };
  window._wfCfSelInv = function() { _wfCfEntries.forEach(f => f._sel = !f._sel); _wfCfRender(); };

  function _wfCfUpdateCount() {
    const cnt = document.getElementById("wf_cf_count");
    if (!cnt) return;
    cnt.textContent = `已选 ${_wfCfEntries.filter(f=>f._sel).length} 个文件`;
  }

  function _wfModalAfterOpen() {
    modalBody.querySelectorAll("[id^=wf_m_]").forEach(inp => {
      if (inp.id) enablePathDrop(inp.id);
    });
    modalBody.querySelectorAll(".wf-modal-input").forEach(inp => {
      const key = inp.dataset.key;
      if (!key) return;
      const pool = _wfHistoryPool(key);
      inp.addEventListener("focus", () => {
        _wfHistoryShow(inp, pool);
      });
      inp.addEventListener("blur", () => {
        setTimeout(() => { if (_wfHistoryDd && !_wfHistoryDd.matches(":hover")) { _wfHistoryDd.remove(); _wfHistoryDd = null; } }, 150);
        _wfHistorySave(pool, inp.value);
      });
    });
    const step = _modalCtx ? config.workflows[_modalCtx.wfIdx]?.steps?.[_modalCtx.stepIdx] : null;
  }

  document.getElementById("wf_modal_close").addEventListener("click", () => { overlay.classList.remove("show"); _modalCtx = null; delete overlay.dataset.modalCtx; if (_wfHistoryDd) { _wfHistoryDd.remove(); _wfHistoryDd = null; } });
  document.getElementById("wf_modal_cancel").addEventListener("click", () => { overlay.classList.remove("show"); _modalCtx = null; delete overlay.dataset.modalCtx; if (_wfHistoryDd) { _wfHistoryDd.remove(); _wfHistoryDd = null; } });
  overlay.addEventListener("click", (e) => { if (e.target === overlay) { overlay.classList.remove("show"); _modalCtx = null; delete overlay.dataset.modalCtx; if (_wfHistoryDd) { _wfHistoryDd.remove(); _wfHistoryDd = null; } } });
  document.getElementById("wf_modal_save").addEventListener("click", _wfModalDoSave);

  panel.querySelectorAll("button,input").forEach(el => {
    el.addEventListener("mousedown", (e) => e.stopPropagation());
  });
  function _wfModalOpen(wfIdx, stepIdx) {
    const step = config.workflows[wfIdx]?.steps?.[stepIdx];
    if (!step) return;
    modalTitle.textContent = typeCn[step.type] || step.type;
    modalBody.innerHTML = _wfModalFields(step.type, step);
    overlay.dataset.modalCtx = JSON.stringify({ wfIdx, stepIdx });
    _modalCtx = { wfIdx, stepIdx };
    overlay.classList.add("show");
    setTimeout(() => _wfModalAfterOpen(), 50);
  }
  panel.querySelectorAll(".wf-settings-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const child = btn.closest(".wf-child");
      const parent = btn.closest(".wf-parent");
      if (!child || !parent) return;
      const wfIdx = Number(parent.dataset.idx);
      const stepIdx = [...parent.querySelector(".wf-children").children].indexOf(child);
      _wfModalOpen(wfIdx, stepIdx);
    });
  });
  panel.querySelectorAll(".wf-child-del-btn").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const child = btn.closest(".wf-child");
      const parent = btn.closest(".wf-parent");
      if (!child || !parent) return;
      const wfIdx = Number(parent.dataset.idx);
      const stepIdx = [...parent.querySelector(".wf-children").children].indexOf(child);
      const step = config.workflows[wfIdx]?.steps?.[stepIdx];
      if (!step) return;
      const ok = await showConfirm({title:"删除步骤", message:`确定删除步骤「${step.name}」？`, confirmText:"删除", danger:true});
      if (!ok) return;
      config.workflows[wfIdx].steps.splice(stepIdx, 1);
      saveConfig({workflows:config.workflows});
      _wfRebuild();
    });
  });
  panel.querySelectorAll(".wf-step-play-btn").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      triggerUpdateCheck();
      const child = btn.closest(".wf-child");
      const parent = btn.closest(".wf-parent");
      if (!child || !parent) return;
      const wfIdx = Number(parent.dataset.idx);
      const stepIdx = [...parent.querySelector(".wf-children").children].indexOf(child);
      const step = config.workflows[wfIdx]?.steps?.[stepIdx];
      if (!step) return;
      const stateKey = "step_" + wfIdx + "_" + stepIdx;
      const state = _wfPlayState[stateKey];
      if (state) {
        if (!(await showConfirm({title:"确认", message:"确定要结束本步骤吗？"}))) return;
        fetch("/api/task/cancel", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task_id: state.taskId})}).catch(()=>{});
        delete _wfPlayState[stateKey];
        btn.innerHTML = _WF_ICONS.play;
        btn.classList.remove("stop");
        btn.title = "执行本步骤";
        return;
      }
      const wfName = config.workflows[wfIdx]?.name || "工作流";
      const logContainer = document.getElementById("wf_log");

      // 清理已完成的工作流日志
      logContainer.querySelectorAll(".wf-log-section").forEach(sec => {
        const bodyEl = sec.querySelector(".wf-log-body");
        if (bodyEl?.id) {
          let done = false;
          let m = bodyEl.id.match(/^wf_log_step_(\d+)_(\d+)_/);
          if (m) { done = !_wfPlayState["step_" + m[1] + "_" + m[2]]; }
          else {
            m = bodyEl.id.match(/^wf_log_(\d+)_/);
            if (m) { done = !_wfPlayState[Number(m[1])]; }
          }
          if (done) sec.remove();
        }
      });

      const bodyId = "wf_log_step_" + wfIdx + "_" + stepIdx + "_" + Date.now();
      const section = document.createElement("div");
      section.className = "wf-log-section";
      section.innerHTML = `<div class="wf-log-section-header">${escapeHtml(wfName)} > ${escapeHtml(step.name||"步骤"+(stepIdx+1))}</div><div class="wf-log-body" id="${bodyId}"></div>`;
      logContainer.appendChild(section);
      btn.innerHTML = _WF_ICONS.stop;
      btn.classList.add("stop");
      btn.title = "点击停止本步骤";
      _wfPlayState[stateKey] = {taskId: ""};
      _updateWfDot(wfIdx);
      runTask("/api/workflow/run", {wf_idx: wfIdx, step_indices: [stepIdx], _stateKey: stateKey}, null, bodyId, wfName, () => {
        if (_wfPlayState[stateKey]) {
          delete _wfPlayState[stateKey];
          btn.innerHTML = _WF_ICONS.play;
          btn.classList.remove("stop");
          btn.title = "执行本步骤";
        }
        _updateWfDot(wfIdx);
      });
    });
  });

  const sortableOptions = {
    animation: 150,
    delay: 300,
    delayOnTouchOnly: false,
    touchStartThreshold: 5,
    ghostClass: "wf-dragging",
    chosenClass: "wf-drag-ghost",
    direction: "vertical",
  };

  _wfSortables = [];
  _wfSortables.push(Sortable.create(document.getElementById("wf_tree"), {
    ...sortableOptions,
    onStart(evt) {
      const el = evt.item;
      if (el.classList.contains("wf-parent") && el.classList.contains("expanded")) {
        el.classList.remove("expanded");
      }
    },
    onEnd() {
      const newOrder = [...document.querySelectorAll("#wf_tree > .wf-parent")].map(el => Number(el.dataset.idx));
      config.workflows = newOrder.map(i => config.workflows[i]);
      saveConfig({workflows:config.workflows});
      document.querySelectorAll("#wf_tree > .wf-parent").forEach((el, i) => { el.dataset.idx = i; });
    },
  }));

  document.querySelectorAll("#wf_tree .wf-children").forEach((container) => {
    _wfSortables.push(Sortable.create(container, {
      ...sortableOptions,
      group: "wf-children",
      filter: ".wf-add-step-item",
      onEnd() {
          const parent = container.closest(".wf-parent");
          const wfIdx = Number(parent.dataset.idx);
          const wf = config.workflows[wfIdx];
          if (!wf) return;
          const stepEls = [...container.children].filter(el => el.classList.contains("wf-child"));
          const newSteps = stepEls.map(el => wf.steps[Number(el.dataset.step)]);
          wf.steps = newSteps;
          saveConfig({workflows:config.workflows});
          stepEls.forEach((el, j) => { el.dataset.step = j; });
        },
    }));
  });

  S.workflow.logEl = document.getElementById("wf_log");
}
let _wfSortables = [];
let _wfHistoryDd = null;
let _wfExpandedIdx = -1;
function _wfDetectPrefixes(steps) {
  const prefixes = new Set();
  const SKIP_KEYS = new Set(["name","type","lock_msg","lang_codes","merge_mode"]);
  function walk(v) {
    if (typeof v === "string" && /^[A-Za-z]:\\/.test(v)) {
      const m = v.match(/^(.+?)\\(?:gameData|Client)(?:\\|$)/i);
      if (m) prefixes.add(m[1]);
    } else if (Array.isArray(v)) {
      v.forEach(walk);
    } else if (v && typeof v === "object") {
      for (const [key, val] of Object.entries(v)) {
        if (!SKIP_KEYS.has(key)) walk(val);
      }
    }
  }
  (steps||[]).forEach(walk);
  return [...prefixes].sort();
}
function _wfReplacePrefixes(obj, oldP, newP) {
  if (typeof obj === "string") {
    if (obj === oldP || obj.startsWith(oldP + "\\")) return newP + obj.substring(oldP.length);
    return obj;
  }
  if (Array.isArray(obj)) return obj.map(v => _wfReplacePrefixes(v, oldP, newP));
  if (obj && typeof obj === "object") {
    const r = {};
    for (const [k, v] of Object.entries(obj)) r[k] = _wfReplacePrefixes(v, oldP, newP);
    return r;
  }
  return obj;
}
function _wfShowPrefixModal(prefixes, onConfirm) {
  const overlay = document.createElement("div");
  overlay.className = "wf-modal-overlay";
  overlay.style.display = "flex";
  overlay.innerHTML = `<div class="wf-modal" style="max-width:560px">
    <div class="wf-modal-header"><h3>路径前缀替换</h3><button class="wf-modal-close" id="_pfx_close">✕</button></div>
    <div class="wf-modal-body" style="font-size:13px">
      <p style="color:var(--dim);margin-bottom:12px">检测到以下路径前缀，输入替换内容后复制（留空则不替换该前缀）：</p>
      ${prefixes.map(p => `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <code style="flex-shrink:0;background:rgba(255,255,255,.04);padding:4px 8px;border-radius:4px;font-size:12px">${escapeHtml(p)}</code>
        <span style="color:var(--dim)">→</span>
        <input class="_pfx_input" data-old="${escapeHtml(p)}" type="text" placeholder="新路径（留空不替换）" style="flex:1;padding:6px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.12);background:#090b10;color:#e0e0e0;font-size:13px">
      </div>`).join("")}
    </div>
    <div style="margin-top:16px;display:flex;gap:8px;justify-content:flex-end">
      <button class="btn btn-normal" id="_pfx_cancel">取消</button>
      <button class="btn btn-primary" id="_pfx_confirm">确定</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  document.getElementById("_pfx_close").onclick = () => { overlay.remove(); onConfirm(null); };
  document.getElementById("_pfx_cancel").onclick = () => { overlay.remove(); onConfirm(null); };
  document.getElementById("_pfx_confirm").onclick = () => {
    const map = {};
    overlay.querySelectorAll("._pfx_input").forEach(inp => {
      const v = inp.value.trim();
      if (v) map[inp.dataset.old] = v;
    });
    overlay.remove();
    onConfirm(map);
  };
}
function _wfRebuild() {
  _wfSortables.forEach(s => s.destroy());
  _wfSortables = [];
  const ep = document.querySelector("#wf_tree .wf-parent.expanded");
  _wfExpandedIdx = ep ? Number(ep.dataset.idx) : -1;
  buildWorkflowTab(S.workflow.panel);
}
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
function wfCreate() {
  config.workflows = config.workflows || [];
  config.workflows.push({name:"新工作流",steps:[]});
  saveConfig({workflows:config.workflows});
  _wfRebuild();
}
function escapeHtml(s){
  return (s||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function _wfAutoName(step) {
  if (!step || !step.type) return "";
  const t = step.type;
  if (t === "open_tables") {
    const paths = step.file_paths || [];
    return paths.map(p => { const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")); return i >= 0 ? p.substring(i+1) : p; }).filter(Boolean).join(",");
  }
  if (t === "lock_svn") {
    const p = step.target_path || "";
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.substring(i+1) : p;
  }
  if (t === "unlock_svn") {
    const p = step.target_path || "";
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.substring(i+1) : p;
  }
  if (t === "export_text") {
    const p = step.input_file || "";
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.substring(i+1) : p;
  }
  if (t === "upload_svn") {
    const dirs = step.dirs || [];
    return dirs.map(d => { const s = d.replace(/[\/\\]$/,""); const i = Math.max(s.lastIndexOf("\\"), s.lastIndexOf("/")); return i >= 0 ? s.substring(i+1) : s; }).filter(Boolean).join(",");
  }
  if (t === "merge_translation") {
    const p = step.original_file || "";
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.substring(i+1) : p;
  }
  if (t === "export_error_code") {
    return step.lang_codes || "";
  }
  if (t === "merge_table") {
    const p = step.input_dir || "";
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    const dir = i >= 0 ? p.substring(0, i) : p;
    const j = Math.max(dir.lastIndexOf("\\"), dir.lastIndexOf("/"));
    return j >= 0 ? dir.substring(j+1) : dir;
  }
  if (t === "revert_svn") {
    const paths = Array.isArray(step.revert_paths) ? step.revert_paths : (step.target_path || "").split(",");
    return paths.map(p => { const s = p.trim().replace(/[\/\\]$/,""); const i = Math.max(s.lastIndexOf("\\"), s.lastIndexOf("/")); return i >= 0 ? s.substring(i+1) : s; }).filter(Boolean).join(",");
  }
  if (t === "copy_files") {
    const p = step.src_dir || "";
    const s = p.replace(/[\/\\]$/,"");
    const i = Math.max(s.lastIndexOf("\\"), s.lastIndexOf("/"));
    return i >= 0 ? s.substring(i+1) : s;
  }
  return "";
}
function buildTextCheckTab(panel) {
  const defaultPath = "F:\\D3_KR2_DEV\\gameData\\Text\\Texts.xlsm";
  panel.innerHTML = `
    <div class="workbench" style="display:flex;flex-direction:column;gap:12px">
      <div class="card">
        <div class="card-title">文字表检测</div>
        <div class="form-group">
          <label>检测文件路径</label>
          <div class="flex-row">
            <input type="text" id="tc_path" value="${escapeHtml(config.tc_path||defaultPath)}" style="flex:1" autocomplete="off">
            <button class="btn btn-normal" data-action="browse-tc-file"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
          </div>
          <div style="font-size:12px;color:var(--dim);margin-top:4px">检测内容：空值、漏翻、占位符不一致、颜色/代码标签丢失、全局重复ID</div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">检测语言</div>
        <div class="check-group" id="tc_tgt_langs"></div>
      </div>
      <div class="card">
        <div class="card-title">排除ID配置</div>
        <div class="form-group">
          <div class="flex-row">
            <input type="text" id="tc_exclude_path" style="flex:1" readonly>
            <button class="btn btn-normal" data-action="browse-tc-exclude" title="浏览配置文件"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
            <button class="btn btn-normal" data-action="open-tc-exclude" title="打开配置文件"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
          </div>
          <div style="font-size:12px;color:var(--dim);margin-top:4px">一行一个 ID，以 # 开头的行为注释</div>
        </div>
      </div>
      <div class="action-center">
        <button class="btn btn-primary" data-action="run-text-check" style="min-width:200px">开始检测</button>
      </div>
      <div class="log-wrap" style="flex:1;min-height:200px">
        <div class="card-header compact" style="padding:0 0 4px 0"><span style="font-weight:600">执行日志</span></div>
        <div class="log" id="tc_log"><div class="log-anchor"></div></div>
      </div>
    </div>`;
  const saved = config.tc_path || defaultPath;
  document.getElementById("tc_path").value = saved;
  enablePathDrop("tc_path", {mode:"file"});
  fetch("/api/translate/lang-id-map").then(r=>r.json()).then(d => {
    const data = d.data || {};
    const names = Object.keys(data).sort();
    const cg = document.getElementById("tc_tgt_langs");
    cg.innerHTML = names.map(n => {
      return `<label><input type="checkbox" value="${escapeHtml(n)}"> ${escapeHtml(n)}</label>`;
    }).join("");
  });
  fetch("/api/text-check/exclude-config").then(r=>r.json()).then(d => {
    if (d.path) document.getElementById("tc_exclude_path").value = d.path;
  });
}
async function runTextCheck() {
  triggerUpdateCheck();
  const filePath = document.getElementById("tc_path").value.trim();
  if (!filePath) { _showToast("请输入检测文件路径"); return; }
  const logEl = document.getElementById("tc_log");
  _logClear(logEl);
  const btn = document.querySelector("[data-action='run-text-check']");
  btn.dataset.orig = btn.dataset.orig || btn.textContent;
  _incRunning();
  try {
    saveConfig({tc_path: filePath});
    const checkedLangs = [];
    document.querySelectorAll("#tc_tgt_langs input:checked").forEach(cb => checkedLangs.push(cb.value));
    if (!checkedLangs.length) { _showToast("请勾选至少一个检测语言"); btn.innerHTML=btn.dataset.orig; _decRunning(); return; }
    const body = {file_path: filePath, target_langs: checkedLangs};
    const r = await fetch("/api/text-check/run", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d = await r.json();
    if (d.error) { _showToast(d.error); btn.innerHTML=btn.dataset.orig; _decRunning(); return; }
    btn.dataset.taskId = d.task_id;
    btn.innerHTML = _WF_ICONS.stop;
    btn.classList.add("stop");
    if (window._esTc) window._esTc.close();
    const evtSrc = new EventSource("/api/log/stream/" + d.task_id);
    window._esTc = evtSrc;
    let tcOutputPath = "";
    const _tcDone = () => {
      if (!btn.dataset.taskId) return;
      btn.dataset.taskId = '';
      btn.classList.remove("stop");
      btn.innerHTML = btn.dataset.orig;
      _decRunning();
    };
    evtSrc.onmessage = (e) => {
      if (e.data === "[DONE]") {
        evtSrc.close();
        window._esTc = null;
        _tcDone();
        if (tcOutputPath) {
          fetch("/api/open/folder", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:tcOutputPath})}).catch(function(){});
          _openFolder(tcOutputPath);
        }
        return;
      }
      for (const raw of e.data.split("\n")) {
        if (!raw.trim()) continue;
        if (raw.startsWith("[输出路径] ")) {
          tcOutputPath = raw.slice(7).trim();
        }
        const div = document.createElement("div");
        div.textContent = raw;
        _logAppend(logEl, div);
        if (/\[error\]/.test(raw)) _focusAppOnError("textcheck", logEl);
      }
    };
  } catch (err) {
    if (btn.dataset.taskId) { btn.dataset.taskId = ''; btn.classList.remove("stop"); btn.innerHTML = btn.dataset.orig; }
    const div = document.createElement("div");
    div.className = "error";
    div.textContent = "❌ 请求失败: " + err.message;
    _logAppend(logEl, div);
    _decRunning();
  }
}
function buildTranslateTab(panel) {
  const api_url = config.tr_api_url||"https://api.openai.com/v1/chat/completions";
  const model = config.tr_model||"gpt-4o-mini";
  const src_lang = config.tr_src_lang||"zh";
  const out = config.tr_out_dir||"";
  const prompt = config.tr_prompt||"你是一位专业的游戏本地化翻译专家。请将以下文本从{src_lang}翻译为{tgt_lang}。\n\n## 核心规则\n1. 术语一致性：游戏专有名词（技能名、道具名、地名、角色名、系统术语）保持统一。\n2. 格式保护：所有格式占位符、标签、转义序列必须原样保留，不可修改或删除。\n3. 长短控制：英文→中文控制在原文60%-100%字符数；中文→英文自然地道。\n4. 风格统一：遵循目标语言的游戏本地化惯例。\n\n## 格式保护规则（必须原样保留）\n- XML/HTML标签：如 <Item size=25 style=1 cfgid={0}>\n- 格式占位符：{0}, {1}, %s, %d, %f\n- 语言标记：::SC::, ::EN::, ::TH::\n- 转义序列：\\n, \\t\n- 颜色/富文本标签：[c], [/c], [color=red]\n\n## 输出格式\n严格按照以下格式返回：\n编号|翻译1|翻译2|翻译3...\n每行一条，不要包含任何额外说明、解释或空行。";
  panel.innerHTML = `
    <div class="translate-layout tr-layout">
      <div class="tr-main">
        <div class="card">
          <div class="card-title">翻译文件</div>
          <div class="form-group">
            <label>文件路径</label>
            <div class="flex-row">
              <input type="text" id="tr_src" placeholder="选择要翻译的 Excel 文件" style="flex:1" autocomplete="off">
              <button class="btn btn-normal" data-action="browse-tr-src"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-tr-src" title="打开文件所在目录"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
          <div class="form-group">
            <label>参考文件</label>
            <div class="flex-row">
              <input type="text" id="tr_ref" placeholder="参考翻译文件（可选）" style="flex:1" autocomplete="off">
              <button class="btn btn-normal" data-action="browse-tr-ref"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-tr-ref" title="打开文件所在目录"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-title">语言列设置</div>
          <div class="form-group">
            <label>源语言列</label>
            <div class="flex-row">
              <input type="text" id="tr_src_lang" value="${escapeHtml(src_lang)}" placeholder="如: 中文" style="width:6.25rem">
              <button class="btn btn-normal btn-sm" data-action="tr-lang-adv-settings" title="语言ID高级设置" style="font-size:16px;padding:0 8px;line-height:1">⚙</button>
            </div>
          </div>
          <div class="form-group">
            <label>目标语言</label>
            <div class="check-group" id="tr_tgt_langs"></div>
          </div>
        </div>
        <div class="action-center">
          <button class="btn btn-primary" data-action="run-translate" data-output="#tr_out">开始翻译</button>
        </div>
      </div>
      <div class="tr-side">
        <div class="card">
          <div class="section-label">API 设置</div>
          <div class="form-group">
            <label>API URL</label>
            <input type="text" id="tr_api_url" value="${escapeHtml(api_url)}">
          </div>
          <div class="form-group">
            <label>API Key</label>
            <input type="password" id="tr_api_key" placeholder="输入 API Key">
          </div>
          <div class="form-group">
            <label>模型</label>
            <input type="text" id="tr_model" value="${escapeHtml(model)}">
          </div>
        </div>
        <div class="card">
          <div class="section-label">输出设置</div>
          <div class="form-group">
            <label>输出目录</label>
            <div class="flex-row">
              <input type="text" id="tr_out" value="${escapeHtml(out)}" style="flex:1">
              <button class="btn btn-normal" data-action="browse-tr-out"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-tr-out" title="打开输出目录"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
          <div class="form-group">
            <label>翻译 Prompt</label>
            <textarea id="tr_prompt">${escapeHtml(prompt)}</textarea>
          </div>
          <div class="form-group">
            <label>批处理量</label>
            <input type="number" id="tr_batch" value="${config.tr_batch_size||20}">
          </div>
        </div>
      </div>
      <div class="tr-log-wrap">
        <div class="card">
          <div class="card-header compact">
            <span style="font-weight:600">执行日志</span>
          </div>
          <div class="log" id="tr_log"><div class="log-anchor"></div></div>
        </div>
      </div>
    </div>
  `;
  if (config.tr_src_history?.length) document.getElementById("tr_src").value = config.tr_src_history[0];
  if (config.tr_ref_history?.length) document.getElementById("tr_ref").value = config.tr_ref_history[0];
  if (config.tr_api_key) document.getElementById("tr_api_key").value = config.tr_api_key;
  initSuggest("tr_src", config.tr_src_history||[]);
  initSuggest("tr_ref", config.tr_ref_history||[]);
  S.translate.logEl = document.getElementById("tr_log");
  enablePathDrop("tr_src", { mode: "path" });
  enablePathDrop("tr_ref", { mode: "path" });
  enablePathDrop("tr_out", { mode: "path" });
  _initDirHistory("tr_src", "tr_src_history");
  _initDirHistory("tr_ref", "tr_ref_history");
  _initDirHistory("tr_out", "tr_out_dir");
  // 从高级设置加载语言列表，填充复选框
  fetch("/api/translate/lang-id-map").then(r=>r.json()).then(d => {
    const data = d.data || {};
    const names = Object.keys(data).sort();
    const cg = document.getElementById("tr_tgt_langs");
    cg.innerHTML = names.map(n => {
      return `<label><input type="checkbox" value="${escapeHtml(n)}"> ${escapeHtml(n)}</label>`;
    }).join("");
  });
}
function runTranslate() {
  triggerUpdateCheck();
  const tgtLangs = [];
  document.querySelectorAll("#tr_tgt_langs input:checked").forEach(cb=>tgtLangs.push(cb.value));
  const apiKey = document.getElementById("tr_api_key").value.trim();
  const body = {
    src_path:document.getElementById("tr_src").value.trim(),
    ref_path:document.getElementById("tr_ref").value.trim(),
    api_url:document.getElementById("tr_api_url").value.trim(),
    api_key:apiKey,
    model:document.getElementById("tr_model").value.trim(),
    src_lang:document.getElementById("tr_src_lang").value.trim(),
    tgt_langs:tgtLangs,
    out_dir:document.getElementById("tr_out").value.trim(),
    prompt:document.getElementById("tr_prompt").value.trim(),
    batch_size:parseInt(document.getElementById("tr_batch").value)||20
  };
  saveConfig({tr_api_url:body.api_url,tr_model:body.model,tr_src_lang:body.src_lang,tr_out_dir:body.out_dir,tr_prompt:body.prompt,tr_batch_size:body.batch_size,api_key:apiKey});
  runTask("/api/translate/run", body, document.querySelector("[data-action='run-translate']"), "tr_log");
}
let trLangAdvModal = null;
function openTrLangAdvSettings() {
  if (!trLangAdvModal) {
    trLangAdvModal = document.createElement("div");
    trLangAdvModal.id = "tr_lang_adv_modal";
    trLangAdvModal.style.cssText = "position:fixed;top:4rem;left:50%;transform:translateX(-50%);width:36rem;max-height:44rem;background:var(--panel);border:1px solid rgba(255,255,255,.08);border-radius:1.25rem;z-index:1000;display:none;flex-direction:column;box-shadow:0 1.25rem 3.75rem rgba(0,0,0,.5)";
    trLangAdvModal.innerHTML = `
      <div style="padding:1.25rem 1.5rem;border-bottom:1px solid rgba(255,255,255,.05);display:flex;justify-content:space-between;align-items:center">
        <span style="font-weight:600;font-size:1rem">语言ID高级设置</span>
        <button class="btn btn-normal btn-sm" data-action="tr-lang-close-adv">✕</button>
      </div>
      <div style="padding:0.75rem 1.5rem;font-size:0.8rem;color:var(--dim)">配置每个语言对应的Excel表头ID，用于自动匹配语言列。例如：中文 → SC, ::SC::, CHS</div>
      <div style="padding:0 1.5rem;overflow:auto;flex:1">
        <table style="width:100%;border-collapse:collapse;font-size:0.85rem" id="tr_lang_adv_table">
          <thead>
            <tr style="border-bottom:1px solid rgba(255,255,255,.08)">
              <th style="text-align:left;padding:0.5rem;color:var(--sub)">语言名称</th>
              <th style="text-align:left;padding:0.5rem;color:var(--sub)">匹配ID（逗号分隔）</th>
              <th style="width:3rem"></th>
            </tr>
          </thead>
          <tbody id="tr_lang_adv_body"></tbody>
        </table>
        <div style="text-align:center;padding:0.75rem 0">
          <button class="btn btn-normal btn-sm" data-action="tr-lang-add-row" style="font-size:13px">+ 新增语言</button>
        </div>
      </div>
      <div class="flex-row" style="padding:0.875rem 1.5rem;border-top:1px solid rgba(255,255,255,.05);justify-content:flex-end;gap:8px">
        <button class="btn btn-normal" data-action="tr-lang-close-adv">取消</button>
        <button class="btn btn-primary" data-action="tr-lang-save-adv">保存</button>
      </div>
    `;
    document.body.appendChild(trLangAdvModal);
    trLangAdvModal.addEventListener("click", e => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;
      const a = btn.dataset.action;
      if (a === "tr-lang-add-row") {
        const tbody = document.getElementById("tr_lang_adv_body");
        const row = document.createElement("tr");
        row.style.borderBottom = "1px solid rgba(255,255,255,.05)";
        row.innerHTML = `
          <td style="padding:0.375rem"><input type="text" class="tr-lang-name" placeholder="如: 中文" style="width:6rem;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:0.3rem 0.5rem;color:var(--text);font-size:0.8rem"></td>
          <td style="padding:0.375rem"><input type="text" class="tr-lang-ids" placeholder="如: SC, ::SC::" style="width:100%;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:0.3rem 0.5rem;color:var(--text);font-size:0.8rem"></td>
          <td style="padding:0.375rem;text-align:center"><button class="btn btn-normal btn-sm" style="font-size:12px;padding:0 6px;color:var(--danger)" data-action="tr-lang-del-row">✕</button></td>
        `;
        tbody.appendChild(row);
      } else if (a === "tr-lang-del-row") {
        const tr = btn.closest("tr");
        if (tr) tr.remove();
      }
    });
  }
  fetch("/api/translate/lang-id-map").then(r=>r.json()).then(d => {
    const data = d.data || {};
    const tbody = document.getElementById("tr_lang_adv_body");
    tbody.innerHTML = "";
    Object.keys(data).sort().forEach(lang => {
      const ids = (data[lang] || []).join(", ");
      const row = document.createElement("tr");
      row.style.borderBottom = "1px solid rgba(255,255,255,.05)";
      row.innerHTML = `
        <td style="padding:0.375rem"><input type="text" class="tr-lang-name" value="${escapeHtml(lang)}" style="width:6rem;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:0.3rem 0.5rem;color:var(--text);font-size:0.8rem"></td>
        <td style="padding:0.375rem"><input type="text" class="tr-lang-ids" value="${escapeHtml(ids)}" style="width:100%;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:0.3rem 0.5rem;color:var(--text);font-size:0.8rem"></td>
        <td style="padding:0.375rem;text-align:center"><button class="btn btn-normal btn-sm" style="font-size:12px;padding:0 6px;color:var(--danger)" data-action="tr-lang-del-row">✕</button></td>
      `;
      tbody.appendChild(row);
    });
  });
  trLangAdvModal.style.display = "flex";
  // 添加关闭点击外部支持
  const overlay = document.getElementById("tr_lang_adv_overlay");
  if (!overlay) {
    const o = document.createElement("div");
    o.id = "tr_lang_adv_overlay";
    o.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.3);z-index:999;display:none";
    o.addEventListener("click", function() { closeTrLangAdvSettings(); });
    document.body.appendChild(o);
  }
  document.getElementById("tr_lang_adv_overlay").style.display = "block";
}
function closeTrLangAdvSettings() {
  if (trLangAdvModal) trLangAdvModal.style.display = "none";
  const o = document.getElementById("tr_lang_adv_overlay");
  if (o) o.style.display = "none";
}
function saveTrLangAdvSettings() {
  const rows = document.querySelectorAll("#tr_lang_adv_body tr");
  const data = {};
  rows.forEach(tr => {
    const nameInput = tr.querySelector(".tr-lang-name");
    const idsInput = tr.querySelector(".tr-lang-ids");
    if (!nameInput || !idsInput) return;
    const name = nameInput.value.trim();
    const idsText = idsInput.value.trim();
    if (!name || !idsText) return;
    const ids = idsText.split(",").map(s => s.trim()).filter(Boolean);
    if (ids.length) data[name] = ids;
  });
  const btn = document.querySelector("[data-action='tr-lang-save-adv']");
  const orig = btn.textContent;
  btn.textContent = "保存中...";
  btn.disabled = true;
  fetch("/api/translate/lang-id-map", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({lang_id_map: data})
  }).then(r=>r.json()).then(d => {
    if (d.ok) {
      closeTrLangAdvSettings();
    }
  }).finally(() => {
    btn.textContent = orig;
    btn.disabled = false;
  });
}
let _runningCount = 0;
const _esMap = {};
let _tabCount = {svn:0, merge:0, upload:0, textcheck:0, workflow:0, translate:0};
let _wfPlayState = {};
function _updateWfDot(wfIdx) {
  const dot = document.querySelector(`.wf-status-dot[data-idx="${wfIdx}"] span`);
  if (!dot) return;
  const running = Object.keys(_wfPlayState).some(k => k.startsWith("step_" + wfIdx + "_"));
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
};
function buildPrefabTab(panel) {
  panel.innerHTML = `
    <div class="workbench" style="display:flex;flex-direction:column;gap:12px">
      <div class="form-group" style="flex-direction:row;align-items:center;gap:12px">
        <label style="white-space:nowrap">操作模式</label>
        <div class="cd-wrap">
          <div class="cd-trigger" id="prefab_mode_trigger" data-value="clear-text"><span>一键清理文字</span><span class="cd-arrow"></span></div>
          <div class="cd-menu" id="prefab_mode_menu">
            <div class="cd-item selected" data-value="clear-text">一键清理文字</div>
          </div>
        </div>
      </div>
      <div class="flex-row" style="gap:8px">
        <button class="btn btn-normal" data-action="browse-prefab-files" title="选择预制文件">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          选择文件
        </button>
        <button class="btn btn-normal" data-action="browse-prefab-dir" title="选择文件夹（递归扫描 .prefab）">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>
          选择文件夹
        </button>
      </div>
      <div class="card" id="prefab_dropzone" style="border:2px dashed var(--line);border-radius:var(--radius);padding:40px 20px;text-align:center;cursor:pointer;transition:border-color .2s,background .2s;position:relative">
        <input type="text" id="prefab_drop_input" style="position:absolute;inset:0;width:100%;height:100%;background:transparent;border:none;outline:none;color:transparent;caret-color:transparent;font-size:1px;cursor:pointer" autocomplete="off">
        <div style="font-size:40px;color:var(--dim);margin-bottom:12px;pointer-events:none">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:48px;height:48px">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </div>
        <div style="font-size:15px;color:var(--sub);margin-bottom:4px;pointer-events:none">将文件或文件夹拖拽到此处</div>
        <div style="font-size:12px;color:var(--dim);pointer-events:none">或使用上方按钮选择</div>
        <div id="prefab_summary" style="margin-top:12px;font-size:13px;color:var(--accent);display:none"></div>
      </div>
      <div class="log-wrap" style="flex:1;min-height:200px">
        <div class="card-header compact" style="padding:0 0 4px 0"><span style="font-weight:600">执行日志</span></div>
        <div class="log" id="prefab_log"><div class="log-anchor"></div></div>
      </div>
    </div>`;

  // 拖拽通过 pywebview _dnd_state 获取完整路径
  enablePathDrop("prefab_drop_input", {mode:"path"});
  var inputEl = document.getElementById("prefab_drop_input");
  var dz = document.getElementById("prefab_dropzone");
  if (inputEl && dz) {
    inputEl.addEventListener("dragover", function(e) { e.preventDefault(); dz.style.borderColor = "var(--accent)"; dz.style.background = "rgba(94,162,255,.08)"; });
    inputEl.addEventListener("dragleave", function() { dz.style.borderColor = ""; dz.style.background = ""; });
    inputEl.addEventListener("drop", function(e) {
      e.preventDefault();
      dz.style.borderColor = ""; dz.style.background = "";
      console.log("drop, files="+(e.dataTransfer?e.dataTransfer.files.length:0));
      // 通过 WebView2 原生 API 传递文件到 _dnd_state
      try {
        if (window.chrome && chrome.webview && chrome.webview.postMessageWithAdditionalObjects && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
          chrome.webview.postMessageWithAdditionalObjects("FilesDropped", e.dataTransfer.files);
          console.log("sent FilesDropped");
          // 重试读取 _dnd_state（最多 15 次，每次 200ms）
          var retries = 0;
          function tryConsume() {
            fetch("/api/prefab/consume-dropped", {method:"POST"}).then(function(r){return r.json();}).then(function(d){
              console.log("consume:", d.count, d.paths);
              if (d.count > 0) { startPrefabClear(d.paths); }
              else if (retries < 15) { retries++; setTimeout(tryConsume, 200); }
              else { _showToast("获取路径超时，请使用上方按钮"); }
            });
          }
          setTimeout(tryConsume, 200);
        } else {
          _showToast("请使用上方的「选择文件」或「选择文件夹」按钮");
        }
      } catch(ex) { console.log("error:", ex); _showToast("拖拽路径获取失败"); }
    });
  }

  // Browse file button
  var browseBtn = panel.querySelector("[data-action='browse-prefab-files']");
  if (browseBtn) {
    browseBtn.addEventListener("click", async function() {
      var path = null;
      if (window.pywebview && pywebview.api && pywebview.api.browseFile) {
        path = await pywebview.api.browseFile("*.prefab");
      }
      if (!path) return;
      startPrefabClear([path]);
    });
  }

  // Browse dir button
  var browseDirBtn = panel.querySelector("[data-action='browse-prefab-dir']");
  if (browseDirBtn) {
    browseDirBtn.addEventListener("click", async function() {
      var path = null;
      if (window.pywebview && pywebview.api && pywebview.api.browseDir) {
        path = await pywebview.api.browseDir("");
      }
      if (!path) return;
      startPrefabClear([path]);
    });
  }

  // 自绘下拉菜单初始化
  _initCustomDropdown("prefab_mode");

  function _initCustomDropdown(id) {
    var trigger = document.getElementById(id + "_trigger");
    var menu = document.getElementById(id + "_menu");
    var items = menu ? menu.querySelectorAll(".cd-item") : [];
    if (!trigger || !menu) return;
    trigger.addEventListener("click", function(e) {
      e.stopPropagation();
      var isOpen = menu.classList.contains("show");
      document.querySelectorAll(".cd-menu.show").forEach(function(m){m.classList.remove("show");});
      document.querySelectorAll(".cd-trigger.open").forEach(function(t){t.classList.remove("open");});
      if (!isOpen) { menu.classList.add("show"); trigger.classList.add("open"); }
    });
    items.forEach(function(item) {
      item.addEventListener("click", function(e) {
        e.stopPropagation();
        var v = this.dataset.value;
        var txt = this.textContent;
        trigger.dataset.value = v;
        trigger.querySelector("span").textContent = txt;
        items.forEach(function(x){x.classList.remove("selected");});
        this.classList.add("selected");
        menu.classList.remove("show");
        trigger.classList.remove("open");
      });
    });
    document.addEventListener("click", function() {
      menu.classList.remove("show");
      trigger.classList.remove("open");
    });
  }
}

function startPrefabClear(paths) {
  console.log("startPrefabClear:", JSON.stringify(paths));
  var summary = document.getElementById("prefab_summary");
  summary.textContent = "正在扫描 " + paths.length + " 个路径...";
  summary.style.display = "block";
  console.log("scan request:", JSON.stringify({paths: paths}));
  fetch("/api/prefab/scan", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({paths: paths})
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) { summary.style.display="none"; _showToast(d.error); return; }
    if (d.count === 0) { summary.style.display="none"; _showToast("未找到 .prefab 文件"); return; }
    summary.textContent = "已扫描 " + d.count + " 个 .prefab 文件，正在清理...";
    runTask("/api/prefab/clear-text", {files: d.files}, null, "prefab_log", null, function() {
      var s = document.getElementById("prefab_summary");
      if (s) { s.textContent = "清理完成"; setTimeout(function(){s.style.display="none";}, 3000); }
    });
  }).catch(function(err) {
    summary.style.display="none";
    _showToast("扫描失败: " + err.message);
  });
}

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
  function _logFlush() {
    if (!_logBuf.length) return;
    const lines = _logBuf.splice(0);
    const frag = document.createDocumentFragment();
    for (const raw of lines) {
      const m = raw.match(/^\[(\d{2}:\d{2}:\d{2})\](?:\[(\w+)\])?\s*(.*)/);
      let tag = "", msg = raw;
      if (m) {
        msg = m[3] || "";
        tag = (m[2] || "").toLowerCase();
        msg = `<span class="ts">${m[1]}</span> ${msg}`;
      }
      if (label) {
        msg = `<span style="color:var(--accent);font-weight:600">[${escapeHtml(label)}]</span> ${msg}`;
      }
      const isError = tag === "error" || raw.includes("❌");
      const cls = isError ? "error" : ({"warn":"warn","ok":"success","success":"success","info":"info"}[tag] || "");
      const div = document.createElement("div");
      div.className = cls;
      div.innerHTML = msg;
      const _m = msg.match(/(?:已生成修改总结|修改总结)[:\s]+(.+?)\\修改总结\.txt/);
      if (_m) _outputPath = _m[1].trim();
      const _pm = msg.match(/\[输出路径\]\s+(.+)/);
      if (_pm) _outputPath = _pm[1].trim();
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
  const r = await fetch(url, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const d = await r.json();
  if (body.wf_idx !== undefined) {
    const sk = body._stateKey || body.wf_idx;
    if (_wfPlayState[sk]) _wfPlayState[sk].taskId = d.task_id;
  }
  if (!label && btn && d.task_id) {
    if (!btn.dataset.orig) btn.dataset.orig = btn.textContent;
    btn.dataset.taskId = d.task_id;
    btn.innerHTML = _WF_ICONS.stop;
    btn.classList.add('stop');
  }

  function _done() {
    _decRunning();
    if (tabKey) { _tabCount[tabKey] = Math.max(0, _tabCount[tabKey] - 1); if (_tabCount[tabKey] === 0) _setTabDot(tabKey, false); }
    if (label) {
      if (onDone) onDone();
    } else if (btn && btn.dataset.taskId) {
      btn.dataset.taskId = '';
      btn.classList.remove('stop');
      btn.innerHTML = btn.dataset.orig || '执行';
    } else if (onDone) {
      onDone();
    }
  }

  if (d.error) {
    logEl.innerHTML = '<span class="error">❌ '+escapeHtml(d.error)+'</span>';
    _focusAppOnError(tabKey, logEl);
    _done();
    return;
  }
  const esKey = body._stateKey || url;
  if (_esMap[esKey]) _esMap[esKey].close();
  const evtSrc = new EventSource("/api/log/stream/" + d.task_id);
  _esMap[esKey] = evtSrc;
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
    logEl.innerHTML += "\n⚠ 日志连接中断\n";
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
            <input type="text" id="adv_svn_user" placeholder="SVN 用户名" autocomplete="off" style="width:100%">
          </div>
          <div class="form-group">
            <label>密码</label>
            <input type="password" id="adv_svn_pass" placeholder="SVN 密码" style="width:100%">
          </div>
          <div style="font-size:0.85rem;font-weight:600;color:var(--accent);margin:16px 0 8px">导出设置</div>
          <div class="form-group">
            <label>排除目录（逗号分隔）</label>
            <input type="text" id="adv_exclude_dirs" placeholder="BinData, GenerateData, Language" autocomplete="off" style="width:100%">
          </div>
          <div style="font-size:0.85rem;font-weight:600;color:var(--accent);margin:16px 0 8px">文件级配置</div>
          <div class="form-group">
            <label>文件名</label>
            <div style="display:flex;gap:6px;align-items:center">
              <input type="text" id="adv_cmp_file" placeholder="选择或输入文件名" autocomplete="off" style="flex:1;min-width:0">
              <button class="btn btn-normal btn-sm" data-action="adv-save-preset" style="font-size:13px;padding:0 10px">保存</button>
              <button class="btn btn-normal btn-sm" data-action="adv-del-preset" style="font-size:13px;padding:0 10px;color:var(--warn,orange)" id="adv_del_preset_btn">×</button>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div class="form-group">
              <label>标题行数</label>
              <input type="number" id="adv_cmp_title_rows" placeholder="1" min="1" step="1" style="width:100%">
            </div>
            <div class="form-group">
              <label>对比ID列</label>
              <input type="number" id="adv_cmp_id_col" placeholder="1" min="1" step="1" style="width:100%">
            </div>
          </div>
          <div class="form-group">
            <label>输出列表头（逗号分隔）</label>
            <input type="text" id="adv_cmp_output_cols" placeholder="留空=全部列" autocomplete="off" style="width:100%">
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
function saveAdvFilePreset() {
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
  const svn_user = document.getElementById("adv_svn_user").value.trim();
  const svn_pass = document.getElementById("adv_svn_pass").value;
  const exclude_dirs = document.getElementById("adv_exclude_dirs").value.trim();
  const payload = { svn_user, cmp_title_rows: config.cmp_title_rows || "1", cmp_id_col: config.cmp_id_col || "1", cmp_output_cols: config.cmp_output_cols || "" };
  if (svn_pass) payload.svn_pass = svn_pass;
  if (exclude_dirs) payload.exclude_dirs = exclude_dirs;
  else payload.exclude_dirs = "";
  document.querySelector("[data-action='save-adv-settings']").textContent = "保存中…";
  fetch("/api/config", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})
    .then(r=>r.json()).then(d=>{
      if (d.ok) {
        config.svn_user = svn_user;
        config.exclude_dirs = exclude_dirs;
        closeAdvSettings();
      }
    }).finally(()=>{
      document.querySelector("[data-action='save-adv-settings']").textContent = "保存";
    });
}
let _mergeData = {versions:[], checkedRevs:{}, checkedFiles:{}, totalChecked:0, stripPrefix:""};
function _getCheckedVersionFiles() {
  const allActions = {};
  const allFiles = {};
  _mergeData.versions.forEach(v => {
    if (!v.files) return;
    v.files.forEach(f => {
      if (!allActions[f.path]) allActions[f.path] = [];
      allActions[f.path].push({ rev: v.rev, action: f.action });
    });
  });
  _mergeData.versions.forEach(v => {
    if (_mergeData.checkedRevs[v.rev] && v.files) {
      v.files.forEach(f => {
        if (_isPathExcluded(f.path)) return;
        if (!allFiles[f.path]) {
          const acts = allActions[f.path] || [];
          const latest = acts.reduce((a, b) => a.rev > b.rev ? a : b, { rev: 0, action: "" });
          let finalAction;
          if (latest.action === "del") {
            finalAction = "del";
          } else if (acts.some(a => a.action === "add")) {
            finalAction = "add";
          } else {
            finalAction = "mod";
          }
          allFiles[f.path] = { ...f, action: finalAction };
        }
      });
    }
  });
  return Object.values(allFiles);
}
function buildMergeTab(panel) {
  const today = `${cy}-${String(cm).padStart(2,"0")}-${String(cd).padStart(2,"0")}`;
  const yearStart = `${cy}-01-01`;
  panel.innerHTML = `
    <div class="workbench merge-layout">
      <div class="merge-main">
        <div class="card">
          <div class="card-title">SVN 地址</div>
          <div class="form-group">
            <label>源SVN地址（读取版本、变更文件）</label>
            <div class="flex-row">
              <input type="text" id="merge_source" placeholder="输入源SVN仓库URL，如 http://svn/repo/branches/xxx" autocomplete="off" style="flex:1">
              <button class="btn btn-normal" data-action="browse-merge-source"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-merge-source" title="打开文件夹"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
          <div class="form-group">
            <label>目标路径（合并落地的本地工作副本路径）</label>
            <div class="flex-row">
              <input type="text" id="merge_target" placeholder="输入本地SVN工作副本路径，如 D:/workspace/project" autocomplete="off" style="flex:1">
              <button class="btn btn-normal" data-action="browse-merge-target"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-merge-target" title="打开文件夹"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
        </div>
      </div>
      <div class="merge-side">
        <div class="card">
          <div class="section-label" style="display:flex;align-items:center;gap:4px">筛选条件<button data-action="merge-revert-exclude-toggle" title="排除设置" style="background:none;border:none;cursor:pointer;font-size:15px;color:var(--dim);padding:0;line-height:1;flex-shrink:0">⚙</button></div>
          <div class="form-group">
            <label>时间范围</label>
            <div class="flex-row" style="align-items:center">
              <input type="text" id="merge_start" value="${yearStart}" placeholder="YYYY-MM-DD" style="flex:1;min-width:0">
              <span style="color:var(--dim)">—</span>
              <input type="text" id="merge_end" value="${today}" placeholder="YYYY-MM-DD" style="flex:1;min-width:0">
            </div>
          </div>
          <div class="form-group">
            <label>备注关键词（留空不限）</label>
            <input type="text" id="merge_keyword" placeholder="按提交备注模糊匹配（逗号分隔多个）" autocomplete="off">
          </div>
          <div class="form-group">
            <label>提交者（留空不限）</label>
            <input type="text" id="merge_author" placeholder="按SVN用户名过滤" autocomplete="off">
          </div>
        </div>
      </div>
      <div class="action-center" style="display:flex;gap:30px;justify-content:center;margin:14px 0">
        <button class="btn btn-primary" data-action="merge-query" id="merge_query_btn" style="min-width:180px">筛选查询</button>
        <button class="btn btn-primary" data-action="merge-analyze" id="merge_analysis_btn" style="min-width:180px" disabled>语义分析</button>
        <button class="btn btn-primary" data-action="merge-run" id="merge_run_btn" style="min-width:180px" disabled>开始合并</button>
      </div>
      <div class="merge-side-cards">
        <div class="card">
          <div class="card-header compact">
            <span style="font-weight:600;display:flex;align-items:center;gap:2px">版本列表<button data-action="merge-file-filter-toggle" title="只包含路径筛选" style="background:none;border:none;cursor:pointer;font-size:15px;color:var(--dim);padding:0;line-height:1;flex-shrink:0">⚙</button></span>
            <div style="display:flex;gap:6px;align-items:center">
              <button class="btn btn-normal btn-sm merge-ops-hidden" data-action="merge-ver-select-all" id="merge_ver_all_btn">全选</button>
              <button class="btn btn-normal btn-sm merge-ops-hidden" data-action="merge-ver-select-invert" id="merge_ver_inv_btn">反选</button>
              <button class="btn btn-normal btn-sm merge-ops-hidden" data-action="merge-ver-select-clear" id="merge_ver_clr_btn">清空</button>
              <span style="color:var(--dim);font-size:12px" id="merge_version_count"></span>
            </div>
          </div>
          <div class="merge-version-list" id="merge_version_list">
            <div class="merge-empty">请配置筛选条件后点击「筛选查询」</div>
          </div>
          <div class="merge-version-footer merge-ops-hidden" id="merge_version_footer">
            <span class="count merge-ops-hidden" id="merge_version_count_bottom">已选 0 个</span>
          </div>
        </div>
        <div class="card">
          <div class="card-header compact">
            <span style="font-weight:600">变更文件</span>
            <div class="cd-wrap cd-sm" id="merge_file_filter_wrap">
              <div class="cd-trigger" id="merge_file_filter_trigger" data-value=""><span>全部</span><span class="cd-arrow"></span></div>
              <div class="cd-menu" id="merge_file_filter_menu">
                <div class="cd-item cd-action" data-action="select-all">全选</div>
                <div class="cd-item cd-action" data-action="select-invert">反选</div>
                <div class="cd-item cd-action" data-action="select-clear">清空</div>
                <div class="cd-item" data-value="Assets/Resources/UI/Prefabs">Assets/Resources/UI/Prefabs</div>
              </div>
            </div>
            <div style="display:flex;gap:6px;align-items:center">
              <span style="color:var(--dim);font-size:12px" id="merge_file_hint">请先选择一个版本</span>
            </div>
          </div>
          <div class="merge-file-list" id="merge_file_list">
            <div class="merge-empty">请先在左侧选择一个版本查看变更文件</div>
          </div>
          <div class="merge-file-footer" id="merge_file_footer">
            <span class="count merge-ops-hidden" id="merge_file_count_bottom">已选 0 个文件</span>
          </div>
        </div>
      </div>
      <div class="merge-full">
        <div class="card">
          <div class="card-header compact">
            <span style="font-weight:600">执行日志</span>
          </div>
          <div class="log" id="merge_log"><div class="log-anchor"></div></div>
        </div>
      </div>
    </div>
  `;
  S.merge.logEl = document.getElementById("merge_log");
  const savedSource = config.svn_urls?.[0] || "";
  if (savedSource) document.getElementById("merge_source").value = savedSource;
  initSuggest("merge_source", config.svn_urls||[]);
  const savedTarget = config.merge_target_history?.[0] || "";
  if (savedTarget) document.getElementById("merge_target").value = savedTarget;
  initSuggest("merge_target", config.merge_target_history||[]);
  enablePathDrop("merge_target", {mode:"path"});
  initSuggest("merge_author", config.svn_author_history||[], true);
  initSuggest("merge_keyword", config.svn_keyword_history||[], true);
  document.querySelector("[data-action='merge-file-filter-toggle']").addEventListener("click", (e) => {
    e.stopPropagation();
    const existing = document.getElementById("merge_file_filter_popup");
    if (existing) { existing.remove(); return; }
    const popup = document.createElement("div");
    popup.id = "merge_file_filter_popup";
    Object.assign(popup.style, {
      position:"fixed", background:"#151b26", border:"1px solid rgba(94,162,255,.18)",
      borderRadius:"12px", padding:"16px", zIndex:"10001",
      boxShadow:"0 12px 36px rgba(0,0,0,.55)",
      width:"480px", maxWidth:"90vw",
      left:"50%", top:"50%", transform:"translate(-50%,-50%)"
    });
    const mode = config.merge_file_filter_mode || "include";
    const modeBar = document.createElement("div");
    Object.assign(modeBar.style, {display:"flex", gap:"4px", marginBottom:"8px"});
    function mkModeBtn(val, label) {
      const b = document.createElement("button");
      b.textContent = label;
      const active = mode === val;
      Object.assign(b.style, {
        flex:"1", padding:"4px 0", fontSize:"12px", cursor:"pointer",
        borderRadius:"6px", border: active ? "1px solid var(--accent)" : "1px solid var(--line)",
        background: active ? "rgba(94,162,255,.1)" : "var(--bg2)",
        color: active ? "var(--accent)" : "var(--dim)",
        fontWeight: active ? "600" : "400"
      });
      b.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const oldMode = config.merge_file_filter_mode || "include";
        if (oldMode === val) return;
        const oldKey = "merge_file_filter_" + oldMode + "_text";
        const oldTxt = ta.value.split("\n").map(s => s.trim()).filter(Boolean).join(",");
        saveConfig({[oldKey]: oldTxt});
        config[oldKey] = oldTxt;
        saveConfig({merge_file_filter_mode: val});
        config.merge_file_filter_mode = val;
        modeBar.querySelectorAll("button").forEach(bb => {
          const v = bb.dataset.modeVal;
          bb.style.border = v === val ? "1px solid var(--accent)" : "1px solid var(--line)";
          bb.style.background = v === val ? "rgba(94,162,255,.1)" : "var(--bg2)";
          bb.style.color = v === val ? "var(--accent)" : "var(--dim)";
          bb.style.fontWeight = v === val ? "600" : "400";
        });
        const newKey = "merge_file_filter_" + val + "_text";
        const newVal = config[newKey] || "";
        ta.value = newVal ? newVal.replace(/,/g, "\n") : "";
        _refreshMergeFileList();
      });
      b.dataset.modeVal = val;
      return b;
    }
    modeBar.appendChild(mkModeBtn("include", "只包含"));
    modeBar.appendChild(mkModeBtn("exclude", "只排除"));
    const ta = document.createElement("textarea");
    ta.placeholder = "config\nData2/腐败秘境开发";
    Object.assign(ta.style, {
      width:"100%", boxSizing:"border-box", minHeight:"250px",
      background:"var(--bg2)", border:"1px solid var(--panel2)", borderRadius:"8px",
      padding:"6px 8px", color:"var(--text)", fontSize:"12px", outline:"none",
      resize:"vertical", fontFamily:"inherit"
    });
    ta.addEventListener("focus", () => { ta.style.borderColor = "var(--accent)"; ta.style.borderWidth = "1px"; });
    ta.addEventListener("blur", () => { ta.style.borderColor = "var(--panel2)"; ta.style.borderWidth = "1px"; });
    const textKey = "merge_file_filter_" + mode + "_text";
    const saved = config[textKey] || "";
    ta.value = saved ? saved.replace(/,/g, "\n") : "";
    ta.addEventListener("input", () => {
      const txt = ta.value.split("\n").map(s => s.trim()).filter(Boolean).join(",");
      const curMode = config.merge_file_filter_mode || "include";
      const k = "merge_file_filter_" + curMode + "_text";
      saveConfig({[k]: txt});
      config[k] = txt;
      _refreshMergeFileList();
    });
    popup.appendChild(modeBar);
    popup.appendChild(ta);
    document.body.appendChild(popup);
    setTimeout(() => ta.focus(), 50);
  });
  document.addEventListener("mousedown", (e) => {
    const popup = document.getElementById("merge_file_filter_popup");
    if (popup && !e.target.closest("#merge_file_filter_popup") && !e.target.closest("[data-action='merge-file-filter-toggle']")) {
      popup.remove();
    }
    const excludePopup = document.getElementById("merge_revert_exclude_popup");
    if (excludePopup && !e.target.closest("#merge_revert_exclude_popup") && !e.target.closest("[data-action='merge-revert-exclude-toggle']")) {
      excludePopup.remove();
    }
  });
  document.querySelector("[data-action='merge-revert-exclude-toggle']").addEventListener("click", (e) => {
    e.stopPropagation();
    const existing = document.getElementById("merge_revert_exclude_popup");
    if (existing) { existing.remove(); return; }
    const popup = document.createElement("div");
    popup.id = "merge_revert_exclude_popup";
    Object.assign(popup.style, {
      position:"fixed", background:"#151b26", border:"1px solid rgba(94,162,255,.18)",
      borderRadius:"12px", padding:"16px", zIndex:"10001",
      boxShadow:"0 12px 36px rgba(0,0,0,.55)",
      width:"420px", maxWidth:"90vw",
      left:"50%", top:"50%", transform:"translate(-50%,-50%)"
    });
    var title = document.createElement("div");
    title.textContent = "排除设置";
    Object.assign(title.style, {fontWeight:"600", fontSize:"14px", marginBottom:"10px"});
    popup.appendChild(title);
    var defaultPaths = ["Assets/Code_Lua/test/test.lua","Assets/StreamingAssets/LocalVersion.xml","InstallClient.bat"];
    var curVal = (config.merge_revert_exclude_paths||[]).join(",") || defaultPaths.join(",");
    var grp = document.createElement("div");
    grp.className = "form-group";
    var lbl = document.createElement("label");
    lbl.textContent = "排除路径（逗号分隔）";
    grp.appendChild(lbl);
    var row = document.createElement("div");
    row.className = "flex-row";
    var inp = document.createElement("input");
    inp.type = "text";
    inp.className = "wf-modal-input";
    inp.id = "merge_exclude_input";
    inp.value = curVal;
    inp.placeholder = "多个路径用,分隔";
    inp.style.cssText = "flex:1";
    row.appendChild(inp);
    var browseBtn = document.createElement("button");
    browseBtn.className = "btn btn-normal btn-sm";
    browseBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>';
    browseBtn.onclick = function() { browseDir("merge_exclude_input"); };
    row.appendChild(browseBtn);
    grp.appendChild(row);
    popup.appendChild(grp);
    var btnRow = document.createElement("div");
    Object.assign(btnRow.style, {display:"flex", justifyContent:"flex-end", gap:"8px", marginTop:"12px"});
    var saveBtn = document.createElement("button");
    saveBtn.textContent = "保存";
    saveBtn.className = "btn btn-primary";
    saveBtn.onclick = function() {
      var txt = document.getElementById("merge_exclude_input").value.trim();
      var arr = txt ? txt.split(",").map(function(s){return s.trim();}).filter(Boolean) : [];
      saveConfig({merge_revert_exclude_paths: arr});
      popup.remove();
    };
    var closeBtn = document.createElement("button");
    closeBtn.textContent = "关闭";
    closeBtn.className = "btn btn-normal";
    closeBtn.onclick = function() { popup.remove(); };
    btnRow.appendChild(saveBtn);
    btnRow.appendChild(closeBtn);
    popup.appendChild(btnRow);
    document.body.appendChild(popup);
    setTimeout(function() { inp.focus(); }, 50);
  });
  document.getElementById("merge_source").addEventListener("blur", async ()=>{
    const val = document.getElementById("merge_source").value.trim();
    // 自动解析 SVN URL 到本地路径并填入目标路径
    if (val && val.startsWith("http") && !document.getElementById("merge_target").value.trim()) {
      try {
        const r = await fetch("/api/svn/find-wc", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({url: val})
        });
        const d = await r.json();
        if (d.ok && d.path) {
          document.getElementById("merge_target").value = d.path;
          const paths = config.merge_target_history || [];
          if (!paths.includes(d.path)) {
            saveConfig({merge_target_history:[d.path, ...paths].slice(0,20)});
            config.merge_target_history = [d.path, ...paths].slice(0,20);
            initSuggest("merge_target", config.merge_target_history);
          }
        }
      } catch(_) {}
    }
  });
  document.getElementById("merge_target").addEventListener("blur", async ()=>{
    const val = document.getElementById("merge_target").value.trim();
    if (val && !(config.merge_target_history||[]).includes(val)) {
      saveConfig({merge_target_history:[val, ...(config.merge_target_history||[])].slice(0,20)});
      config.merge_target_history = [val, ...(config.merge_target_history||[])].slice(0,20);
      initSuggest("merge_target", config.merge_target_history);
    }
  });
  document.getElementById("merge_author").addEventListener("blur", ()=>{
    const val = document.getElementById("merge_author").value.trim();
    if (val && !(config.svn_author_history||[]).includes(val)) {
      saveConfig({svn_author_history:[val, ...(config.svn_author_history||[])].slice(0,20)});
      initSuggest("merge_author", config.svn_author_history, true);
      initSuggest("svn_author", config.svn_author_history, true);
    }
  });
  document.getElementById("merge_keyword").addEventListener("blur", ()=>{
    const val = document.getElementById("merge_keyword").value.trim();
    if (val && !(config.svn_keyword_history||[]).includes(val)) {
      saveConfig({svn_keyword_history:[val, ...(config.svn_keyword_history||[])].slice(0,20)});
      initSuggest("merge_keyword", config.svn_keyword_history, true);
      initSuggest("svn_keyword", config.svn_keyword_history, true);
    }
  });

  function _initMergeFileFilter() {
    var trigger = document.getElementById("merge_file_filter_trigger");
    var menu = document.getElementById("merge_file_filter_menu");
    if (!trigger || !menu) return;
    trigger.addEventListener("click", function(e) {
      e.stopPropagation();
      var isOpen = menu.classList.contains("show");
      document.querySelectorAll(".cd-menu.show").forEach(function(m){m.classList.remove("show");});
      document.querySelectorAll(".cd-trigger.open").forEach(function(t){t.classList.remove("open");});
      if (!isOpen) { menu.classList.add("show"); trigger.classList.add("open"); }
    });
    menu.querySelectorAll(".cd-item").forEach(function(item) {
      item.addEventListener("click", function(e) {
        e.stopPropagation();
        var act = this.dataset.action;
        if (act === "select-all") { _selectAllMergeFiles(true); _cm(); return; }
        if (act === "select-invert") { _selectAllMergeFiles(null); _cm(); return; }
        if (act === "select-clear") { _selectAllMergeFiles(false); _cm(); return; }
        var v = this.dataset.value;
        if (v !== undefined) {
          trigger.dataset.value = v;
          trigger.querySelector("span").textContent = this.textContent;
          menu.querySelectorAll(".cd-item").forEach(function(x){x.classList.remove("selected");});
          this.classList.add("selected");
        }
        _cm();
        _refreshMergeFileList();
      });
    });
    function _cm() { menu.classList.remove("show"); trigger.classList.remove("open"); }
    document.addEventListener("click", function() { menu.classList.remove("show"); trigger.classList.remove("open"); });
  }
  _initMergeFileFilter();
}
async function runMergeQuery() {
  const sourceUrl = document.getElementById("merge_source").value.trim();
  const targetPath = document.getElementById("merge_target").value.trim();
  const startDate = document.getElementById("merge_start").value;
  const endDate = document.getElementById("merge_end").value;
  if (!sourceUrl) { _showToast("请输入源SVN地址"); return; }
  if (!targetPath) { _showToast("请输入目标本地工作副本路径"); return; }
  const btn = document.getElementById("merge_query_btn");
  btn.dataset.orig = btn.dataset.orig || btn.textContent;
  const logEl = document.getElementById("merge_log");
  _logClear(logEl);
  _incRunning();
  _incTabRunning("merge");
  try {
    const body = {
      source_url: sourceUrl,
      start_date: startDate,
      end_date: endDate,
      author: document.getElementById("merge_author").value.trim() || "",
      keyword: document.getElementById("merge_keyword").value.trim() || "",
    };
    saveConfig({svn_urls:[sourceUrl, ...(config.svn_urls||[]).filter(u=>u!==sourceUrl)].slice(0,20)});
    config.svn_urls = [sourceUrl, ...(config.svn_urls||[]).filter(u=>u!==sourceUrl)].slice(0,20);
    initSuggest("merge_source", config.svn_urls);
    const r = await fetch("/api/merge/query", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d = await r.json();
    if (d.error) { _showToast(d.error); _focusAppOnError("merge", logEl); _decRunning(); _decTabRunning("merge"); return; }
    btn.dataset.taskId = d.task_id;
    btn.innerHTML = _WF_ICONS.stop;
    btn.classList.add("stop");
    if (window._esMergeQ) window._esMergeQ.close();
    const evtSrc = new EventSource("/api/log/stream/" + d.task_id);
    window._esMergeQ = evtSrc;
    let resultData = null;
    const _mergeDone = () => {
      if (!btn.dataset.taskId) return;
      btn.dataset.taskId = '';
      btn.classList.remove("stop");
      btn.innerHTML = btn.dataset.orig;
      _decRunning();
      _decTabRunning("merge");
    };
    evtSrc.onmessage = (e) => {
      if (e.data === "[DONE]") {
        evtSrc.close();
        _mergeDone();
        if (resultData) {
          if (resultData.ok) {
            _mergeData.versions = resultData.versions || [];
            _mergeData.stripPrefix = resultData.strip_prefix || "";
            _mergeData.checkedRevs = {};
            _mergeData.checkedFiles = {};
            _mergeData.totalChecked = 0;
            _mergeData.lastFileIdx = undefined;
            renderMergeVersions();
            document.getElementById("merge_file_list").innerHTML = '<div class="merge-empty">请勾选版本查看变更文件</div>';
            document.getElementById("merge_file_hint").textContent = "请勾选需要合并的版本";
            document.getElementById("merge_file_count_bottom").textContent = "已选 0 个文件";
            document.getElementById("merge_run_btn").disabled = true;
            document.getElementById("merge_version_count").textContent = resultData.total ? `共 ${resultData.total} 个版本` : "";
            if (!resultData.total) {
              document.getElementById("merge_version_list").innerHTML = '<div class="merge-empty">暂无符合筛选条件的版本记录</div>';
            }
          } else {
            _showToast(resultData.error || "查询失败");
          }
        }
        return;
      }
      if (e.data.startsWith("[RESULT]")) {
        try { resultData = JSON.parse(e.data.slice(8)); } catch(_) {}
        return;
      }
      for (const raw of e.data.split("\n")) {
        if (!raw.trim()) continue;
        const div = document.createElement("div");
        div.textContent = raw;
        _logAppend(logEl, div);
        if (/\[error\]/.test(raw)) _focusAppOnError("merge", logEl);
      }
    };
  } catch (err) {
    if (btn.dataset.taskId) { btn.dataset.taskId = ''; btn.classList.remove("stop"); btn.innerHTML = btn.dataset.orig; }
    _decRunning();
    _decTabRunning("merge");
    _showToast("请求失败: " + err.message);
  }
}
function renderMergeVersions() {
  const container = document.getElementById("merge_version_list");
  const versions = _mergeData.versions.slice().sort((a,b) => b.rev - a.rev);
  if (!versions.length) {
    container.innerHTML = '<div class="merge-empty">暂无符合筛选条件的版本记录</div>';
    document.getElementById("merge_ver_all_btn").classList.add("merge-ops-hidden");
    document.getElementById("merge_ver_inv_btn").classList.add("merge-ops-hidden");
    document.getElementById("merge_ver_clr_btn").classList.add("merge-ops-hidden");
    document.getElementById("merge_version_footer").classList.add("merge-ops-hidden");
    return;
  }
  document.getElementById("merge_ver_all_btn").classList.remove("merge-ops-hidden");
  document.getElementById("merge_ver_inv_btn").classList.remove("merge-ops-hidden");
  document.getElementById("merge_ver_clr_btn").classList.remove("merge-ops-hidden");
  document.getElementById("merge_version_footer").classList.remove("merge-ops-hidden");
  container.innerHTML = versions.map((v, i) => {
    const checked = _mergeData.checkedRevs[v.rev] ? " checked" : "";
    const cls = _mergeData.checkedRevs[v.rev] ? " checked" : "";
    const dateStr = (v.date||"").slice(0, 10);
    const timeStr = (v.date||"").length >= 16 ? (v.date||"").slice(11, 16) : "";
    const msgShort = (v.msg||"").slice(0, 80);
    return `<div class="merge-version-item${cls}" data-rev="${v.rev}" data-idx="${i}">
      <input type="checkbox"${checked}>
      <span class="rev">r${v.rev}</span>
      <span class="meta-col">
        <span class="date">${dateStr}</span>
        <span class="time">${timeStr}</span>
        <span class="author">${escapeHtml(v.author)}</span>
      </span>
      <span class="msg" title="${escapeHtml(v.msg)}">${escapeHtml(msgShort)}</span>
    </div>`;
  }).join("");
  _refreshMergeFileList();
}
function _refreshMergeFileList() {
  const files = _getCheckedVersionFiles();
  const hintEl = document.getElementById("merge_file_hint");
  if (!files.length) {
    document.getElementById("merge_file_list").innerHTML = '<div class="merge-empty">请勾选版本查看变更文件</div>';
    hintEl.textContent = "请勾选需要合并的版本";
  } else {
    hintEl.textContent = `共 ${files.length} 个文件`;
    renderMergeFiles(files);
  }
  _updateMergeFileCount();
  _updateMergeVersionCount();
}
function _updateMergeVersionCount() {
  const el = document.getElementById("merge_version_count_bottom");
  const total = Object.values(_mergeData.checkedRevs).filter(Boolean).length;
  if (total > 0) {
    el.textContent = `已选 ${total} 个`;
    el.classList.remove("merge-ops-hidden");
  } else {
    el.classList.add("merge-ops-hidden");
  }
  document.getElementById("merge_analysis_btn").disabled = total === 0;
}
function _isPathExcluded(path) {
  const mode = config.merge_file_filter_mode || "include";
  const key = "merge_file_filter_" + mode + "_text";
  const raw = (config[key] || "").trim();
  if (!raw) return false;
  const terms = raw.split(",").map(s => s.trim().replace(/\\/g, "/")).filter(Boolean);
  if (!terms.length) return false;
  const normalized = path.replace(/\\/g, "/");
  const matches = terms.some(t => normalized === t || normalized.includes("/" + t + "/") || normalized.endsWith("/" + t) || normalized.startsWith(t + "/") || normalized.includes(t));
  return mode === "include" ? !matches : matches;
}
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
function renderMergeFiles(files) {
  const container = document.getElementById("merge_file_list");
  if (!files || !files.length) {
    container.innerHTML = '<div class="merge-empty">该版本无变更文件</div>';
    return;
  }
  const actionCn = {add:"新增", mod:"修改", del:"删除"};
  const sp = _mergeData.stripPrefix || "";
  var filterTrigger = document.getElementById("merge_file_filter_trigger");
  var filterVal = filterTrigger ? filterTrigger.dataset.value : "";
  if (filterVal) {
    files = files.filter(function(f) {
      var pv = (sp && f.path && f.path.startsWith(sp + "/")) ? f.path.slice(sp.length + 1) : (f.path || "");
      return pv.startsWith(filterVal);
    });
  }
  files.sort(function(a, b) {
    var pa = (sp && a.path && a.path.startsWith(sp + "/")) ? a.path.slice(sp.length + 1) : (a.path || "");
    var pb = (sp && b.path && b.path.startsWith(sp + "/")) ? b.path.slice(sp.length + 1) : (b.path || "");
    return pa.localeCompare(pb);
  });
  container.innerHTML = files.map((f, i) => {
    const path = f.path || "";
    const action = f.action || "";
    const checked = _mergeData.checkedFiles[path] ? " checked" : "";
    const isDel = action === "del";
    let displayPath = path;
    if (sp && path.startsWith(sp + "/")) displayPath = path.slice(sp.length + 1);
    const name = _basename(displayPath);
    const dir = _dirname(displayPath);
    return `<div class="merge-file-item${checked}${isDel ? " wf-file-del" : ""}" data-path="${escapeHtml(path)}" data-action="${action}" data-idx="${i}">
      <input type="checkbox"${checked}>
      <span class="action-tag ${action}">${actionCn[action]||action}</span>
      ${isDel ? '<span class="del-tag">已删除</span>' : ""}
      <span class="path" title="${escapeHtml(path)}"><span class="file-name">${escapeHtml(name)}</span> <span class="file-dir">${escapeHtml(dir)}</span></span>
    </div>`;
  }).join("");
  _updateMergeFileCount();
}
function _updateMergeFileCount() {
  const total = _mergeData.totalChecked;
  const el = document.getElementById("merge_file_count_bottom");
  el.textContent = `已选 ${total} 个文件`;
  el.classList.toggle("merge-ops-hidden", total === 0);
  document.getElementById("merge_run_btn").disabled = total === 0;
}
function _toggleMergeFile(path) {
  _mergeData.checkedFiles[path] = !_mergeData.checkedFiles[path];
  if (_mergeData.checkedFiles[path]) {
    _mergeData.totalChecked++;
  } else {
    _mergeData.totalChecked--;
  }
  const items = document.querySelectorAll("#merge_file_list .merge-file-item");
  items.forEach(el => {
    if (el.dataset.path === path) {
      el.classList.toggle("checked", _mergeData.checkedFiles[path]);
      el.querySelector("input[type='checkbox']").checked = _mergeData.checkedFiles[path];
    }
  });
  _updateMergeFileCount();
}
function _selectAllMergeFiles(select) {
  const items = document.querySelectorAll("#merge_file_list .merge-file-item");
  items.forEach(el => {
    const path = el.dataset.path;
    const was = _mergeData.checkedFiles[path];
    _mergeData.checkedFiles[path] = select;
    if (select && !was) _mergeData.totalChecked++;
    if (!select && was) _mergeData.totalChecked--;
    el.classList.toggle("checked", select);
    el.querySelector("input[type='checkbox']").checked = select;
  });
  _updateMergeFileCount();
}
async function runMergeRun() {
  triggerUpdateCheck();
  const sourceUrl = document.getElementById("merge_source").value.trim();
  const targetPath = document.getElementById("merge_target").value.trim();
  if (!sourceUrl) { _showToast("请输入源SVN地址"); return; }
  if (!targetPath) { _showToast("请输入目标路径"); return; }
  const checkedPaths = Object.keys(_mergeData.checkedFiles).filter(k => _mergeData.checkedFiles[k]);
  if (!checkedPaths.length) { _showToast("请至少选择一个文件"); return; }
  const checkedRevs = Object.keys(_mergeData.checkedRevs).map(Number);
  if (!checkedRevs.length) { _showToast("请至少勾选一个版本"); return; }
  const btn = document.getElementById("merge_run_btn");
  btn.dataset.orig = btn.dataset.orig || btn.textContent;
  const logEl = document.getElementById("merge_log");
  _logClear(logEl);
  logEl?.scrollIntoView({behavior:"smooth", block:"nearest"});
  _incRunning();
  _incTabRunning("merge");
  const revFileMap = {};
  _mergeData.versions.forEach(v => {
    if (!_mergeData.checkedRevs[v.rev]) return;
    (v.files || []).forEach(f => {
      if (!_isPathExcluded(f.path) && _mergeData.checkedFiles[f.path]) {
        if (!revFileMap[f.path]) revFileMap[f.path] = [];
        revFileMap[f.path].push(v.rev);
      }
    });
  });
  const body = {
    source_url: sourceUrl,
    target_path: targetPath,
    revisions: checkedRevs,
    rev_file_map: revFileMap,
    exclude_paths: config.merge_revert_exclude_paths || [],
    files: [...document.querySelectorAll("#merge_file_list .merge-file-item input:checked")].map(cb => {
      const item = cb.closest(".merge-file-item");
      return {path: item.dataset.path, action: item.dataset.action || "mod"};
    }),
  };
  try {
    const r = await fetch("/api/merge/run", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d = await r.json();
    if (d.error) {
      logEl.innerHTML = '<span class="error">❌ '+escapeHtml(d.error)+'</span>';
      _focusAppOnError("merge", logEl);
      _decRunning();
      _decTabRunning("merge");
      return;
    }
    btn.dataset.taskId = d.task_id;
    btn.innerHTML = _WF_ICONS.stop;
    btn.classList.add("stop");
    const _mergeRunDone = () => {
      if (!btn.dataset.taskId) return;
      btn.dataset.taskId = '';
      btn.classList.remove("stop");
      btn.innerHTML = btn.dataset.orig;
      _decRunning();
      _decTabRunning("merge");
    };
    if (window._esMergeRun) window._esMergeRun.close();
    const evtSrc = new EventSource("/api/log/stream/" + d.task_id);
    window._esMergeRun = evtSrc;
    evtSrc.onmessage = (e) => {
      if (e.data === "[DONE]") {
        evtSrc.close();
        window._esMergeRun = null;
        _mergeRunDone();
        return;
      }
      const lines = e.data.split("\n");
      for (const raw of lines) {
        if (!raw.trim()) continue;
        const div = document.createElement("div");
        div.textContent = raw;
        _logAppend(logEl, div);
        if (/\[error\]/.test(raw)) _focusAppOnError("merge", logEl);
      }
    };
  } catch (err) {
    logEl.innerHTML = '<span class="error">❌ 请求失败: '+escapeHtml(err.message)+'</span>';
    _focusAppOnError("merge", logEl);
    if (btn.dataset.taskId) { btn.dataset.taskId = ''; btn.classList.remove("stop"); btn.innerHTML = btn.dataset.orig; }
    _decRunning();
    _decTabRunning("merge");
  }
}
async function runMergeAnalysis() {
  triggerUpdateCheck();
  const sourceUrl = document.getElementById("merge_source").value.trim();
  const targetPath = document.getElementById("merge_target").value.trim();
  if (!sourceUrl) { _showToast("请输入源SVN地址"); return; }
  if (!targetPath) { _showToast("请输入目标路径（用于GUID映射查询）"); return; }
  const _hasCheckedFiles = Object.values(_mergeData.checkedFiles).some(Boolean);
  const revFileMap = {};
  _mergeData.versions.forEach(v => {
    if (_mergeData.checkedRevs[v.rev] && v.files) {
      let filtered = v.files.filter(f => !_isPathExcluded(f.path));
      if (_hasCheckedFiles) {
        filtered = filtered.filter(f => _mergeData.checkedFiles[f.path]);
      }
      if (filtered.length) {
        revFileMap[v.rev] = filtered.map(f => ({path: f.path, action: f.action}));
      }
    }
  });
  const checkedRevs = _hasCheckedFiles
    ? Object.keys(revFileMap).map(Number)
    : Object.keys(_mergeData.checkedRevs).filter(k => _mergeData.checkedRevs[k]).map(Number);
  if (!checkedRevs.length) { _showToast("请至少勾选一个版本"); return; }
  const versionFiles = Object.values(revFileMap).flat().map(f => f.path);
  const btn = document.getElementById("merge_analysis_btn");
  btn.dataset.orig = btn.dataset.orig || btn.textContent;
  const logEl = document.getElementById("merge_log");
  _logClear(logEl);
  logEl?.scrollIntoView({behavior:"smooth", block:"nearest"});
  _incRunning();
  _incTabRunning("merge");
  const body = { source_url: sourceUrl, target_path: targetPath, revisions: checkedRevs, version_files: versionFiles, rev_file_map: revFileMap };
  try {
    const r = await fetch("/api/merge/analyze", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d = await r.json();
    if (d.error) { _showToast(d.error); _focusAppOnError("merge", logEl); _decRunning(); _decTabRunning("merge"); return; }
    btn.dataset.taskId = d.task_id;
    btn.innerHTML = _WF_ICONS.stop;
    btn.classList.add("stop");
    const _mergeAnaLogBuf = [];
    let _mergeAnaLogTimer = null;
    function _mergeAnaLogFlush() {
      if (!_mergeAnaLogBuf.length) return;
      const frag = document.createDocumentFragment();
      for (const raw of _mergeAnaLogBuf.splice(0)) {
        if (!raw.trim()) continue;
        const div = document.createElement("div");
        div.textContent = raw;
        frag.appendChild(div);
        if (raw.toLowerCase().indexOf("[error]") >= 0) _focusAppOnError("merge", logEl);
      }
      logEl.appendChild(frag);
    }
    function _mergeAnaLogPush(raw) {
      _mergeAnaLogBuf.push(raw);
      if (!_mergeAnaLogTimer) {
        _mergeAnaLogTimer = setInterval(function() {
          _mergeAnaLogFlush();
          if (!_mergeAnaLogBuf.length && _mergeAnaLogTimer) {
            clearInterval(_mergeAnaLogTimer);
            _mergeAnaLogTimer = null;
          }
        }, 80);
      }
    }
    const _mergeAnaDone = () => {
      if (!btn.dataset.taskId) return;
      if (_mergeAnaLogTimer) { clearInterval(_mergeAnaLogTimer); _mergeAnaLogTimer = null; }
      _mergeAnaLogFlush();
      btn.dataset.taskId = '';
      btn.classList.remove("stop");
      btn.innerHTML = btn.dataset.orig;
      _decRunning();
      _decTabRunning("merge");
    };
    if (window._esMergeAna) window._esMergeAna.close();
    const evtSrc = new EventSource("/api/log/stream/" + d.task_id);
    window._esMergeAna = evtSrc;
    evtSrc.onmessage = (e) => {
      if (e.data === "[DONE]") {
        if (_mergeAnaLogTimer) { clearInterval(_mergeAnaLogTimer); _mergeAnaLogTimer = null; }
        _mergeAnaLogFlush();
        evtSrc.close();
        window._esMergeAna = null;
        _mergeAnaDone();
        return;
      }
      if (e.data.startsWith("[RESULT]")) {
        try { JSON.parse(e.data.slice(8)); } catch(_) {}
        return;
      }
      _mergeAnaLogPush(e.data);
    };
  } catch (err) {
    if (btn.dataset.taskId) { btn.dataset.taskId = ''; btn.classList.remove("stop"); btn.innerHTML = btn.dataset.orig; }
    _decRunning();
    _decTabRunning("merge");
    _showToast("请求失败: " + err.message);
  }
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
      browseDir("svn_output", null, _so || "");
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
      browseDir("merge_source", null, _msDir);
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
      browseDir("merge_target", null, _mtDir);
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
    case "merge-select-all": _selectAllMergeFiles(true); break;
    case "merge-select-invert": {
      const items = document.querySelectorAll("#merge_file_list .merge-file-item");
      items.forEach(el => {
        _toggleMergeFile(el.dataset.path);
      });
      break;
    }
    case "merge-select-clear": _selectAllMergeFiles(false); break;
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
  _toggleMergeFile(item.dataset.path);
});
document.addEventListener("click", e => {
  const item = e.target.closest(".merge-file-item");
  if (!item) return;
  if (e.target.matches("input")) return;
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
    _toggleMergeFile(item.dataset.path);
    _mergeData.lastFileIdx = Number(item.dataset.idx);
  }
});
document.addEventListener("input",e=>{
  // wf_name handler removed - workflow name editing now done via settings modal
});
let _suggests = {};
let _activeInputId = null;
let _portal = null;
function _getPortal() {
  if (!_portal) {
    _portal = document.createElement("div");
    _portal.className = "suggest-drop";
    document.body.appendChild(_portal);
  }
  return _portal;
}
function initSuggest(inputId, items) {
  if (!items.length) return;
  _suggests[inputId] = { items };
}
function _showSuggest(inputId, showAll) {
  const s = _suggests[inputId];
  if (!s) return;
  const inp = document.getElementById(inputId);
  if (!inp) return;
  const val = inp.value.toLowerCase();
  const visible = s.items.map((u,i) => ({val:u, idx:i})).filter(x => showAll || !val || x.val.toLowerCase().includes(val));
  const portal = _getPortal();
  portal.innerHTML = visible.length
    ? visible.map(x => {
        const label = x.val || "⊙ 全局默认";
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
    const _configMap = {svn_url:"svn_urls",merge_source:"svn_urls",svn_keyword:"svn_keyword_history",svn_author:"svn_author_history",svn_output:"output_dir_history",upload_src:"src_dir_history",upload_tgt:"tgt_dir_history",tr_src:"tr_src_history",tr_ref:"tr_ref_history",tr_out:"tr_out_dir",merge_target:"merge_target_history",merge_author:"svn_author_history",merge_keyword:"svn_keyword_history"};
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
        input.value = d.url;
        saveConfig({
          svn_urls: [d.url, ...(config.svn_urls||[]).filter(u=>u!==d.url)].slice(0,20),
          output_dir_history: [path, ...(config.output_dir_history||[]).filter(v=>v!==path)].slice(0,10)
        });
        config.svn_urls = [d.url, ...(config.svn_urls||[]).filter(u=>u!==d.url)].slice(0,20);
        config.output_dir_history = [path, ...(config.output_dir_history||[]).filter(v=>v!==path)].slice(0,10);
        initSuggest("svn_url", config.svn_urls);
      } else {
        _showToast(d.error || "该文件夹不是 SVN 工作副本");
      }
    }).catch(()=>_showToast("无法检测 SVN 仓库"));
}
function _showToast(msg) {
  const t = document.createElement("div");
  Object.assign(t.style, {
    position:"fixed",bottom:"48px",left:"50%",transform:"translateX(-50%)",
    background:"rgba(0,0,0,.85)",color:"#fff",padding:"10px 24px",
    borderRadius:"8px",fontSize:"13px",zIndex:"9999",transition:"opacity .3s"
  });
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=>{t.style.opacity="0";setTimeout(()=>t.remove(),300);},2000);
}
function showConfirm({title="确认", message="", confirmText="确定", cancelText="取消", danger=false}={}){
  return new Promise(resolve => {
    const overlay = document.getElementById("confirm_overlay");
    const titleEl = document.getElementById("confirm_title");
    const msgEl = document.getElementById("confirm_msg");
    const okBtn = document.getElementById("confirm_ok_btn");
    const cancelBtn = document.getElementById("confirm_cancel_btn");
    titleEl.textContent = title;
    msgEl.textContent = message;
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
async function browseFile(inputId, initialDir) {
  if (window.pywebview && pywebview.api && pywebview.api.browseFile) {
    try {
      const path = await pywebview.api.browseFile(initialDir || "");
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
    input.accept = ".xlsx,.xls,.xlsm";
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
window.addEventListener("DOMContentLoaded", async () => {
  await loadConfig();
  switchTab("svn");
  setTimeout(checkZoom, 300);
  setTimeout(checkUpdate, 2000);
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.app_ready) {
      await window.pywebview.api.app_ready();
    }
  } catch(e) {
    console.warn("[Splash] app_ready not available", e);
  }
});
document.getElementById("close_btn")?.addEventListener("click", ()=>{
  fetch("/api/close", {method:"POST"});
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
  if (e.target.closest('.drag-bar')) {
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
