// 语义合并日志批量追加：80ms 批处理 + DocumentFragment + 行数上限，避免逐条 append 拖慢渲染
function _mergeLogBatch(logEl, maxLines) {
  const buf = [];
  let timer = null;
  function flush() {
    if (!buf.length) return;
    const lines = buf.splice(0);
    const frag = document.createDocumentFragment();
    for (const raw of lines) {
      if (!raw.trim()) continue;
      const div = document.createElement("div");
      div.textContent = raw;
      frag.appendChild(div);
      if (/\[error\]/.test(raw)) _focusAppOnError("merge", logEl);
    }
    _logAppend(logEl, frag);
    while (logEl.children.length - 1 > (maxLines || 3000)) {
      const first = logEl.firstElementChild;
      if (!first || first.classList.contains("log-anchor")) break;
      first.remove();
    }
  }
  function push(raw) {
    buf.push(raw);
    if (!timer) {
      timer = setInterval(() => {
        flush();
        if (!buf.length && timer) { clearInterval(timer); timer = null; }
      }, 80);
    }
  }
  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
    flush();
  }
  return { push, stop };
}

function _getCheckedVersionFiles() {
  // 文件列表来自懒加载缓存 versionFiles（按勾选版本聚合），不再依赖查询阶段的 v.files
  const allActions = {};
  const allFiles = {};
  const revs = Object.keys(_mergeData.checkedRevs).filter(k => _mergeData.checkedRevs[k]);
  revs.forEach(rev => {
    (_mergeData.versionFiles[rev] || []).forEach(f => {
      if (!allActions[f.path]) allActions[f.path] = [];
      allActions[f.path].push({ rev: Number(rev), action: f.action });
    });
  });
  revs.forEach(rev => {
    (_mergeData.versionFiles[rev] || []).forEach(f => {
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
  });
  return Object.values(allFiles);
}

async function _ensureMergeVersionFiles(revs) {
  // 确保勾选版本的变更文件已加载（懒加载并缓存到 _mergeData.versionFiles）
  const missing = revs.filter(r => !_mergeData.versionFiles[r]);
  if (!missing.length) return;
  const sourceUrl = await _ensureMergeSourceUrl();
  if (!sourceUrl) return;
  const hintEl = document.getElementById("merge_file_hint");
  if (hintEl) hintEl.textContent = `正在加载 ${missing.length} 个版本的变更文件…`;
  const _CONC = 8; // 并发上限，避免全选时一次性打几百个请求
  for (let i = 0; i < missing.length; i += _CONC) {
    const batch = missing.slice(i, i + _CONC);
    await Promise.all(batch.map(async (r) => {
      try {
        const rr = await fetch("/api/merge/version-files", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source_url: sourceUrl, revision: r})});
        const dd = await rr.json();
        _mergeData.versionFiles[r] = dd.ok ? (dd.files || []) : [];
      } catch(_) {
        _mergeData.versionFiles[r] = [];
      }
    }));
  }
}
async function _ensureMergeSourceUrl() {
  /* 查询/合并前确保拿到 URL：输入框是本地路径时每次反查（不信任 dataset.url 缓存，避免切换路径后残留错位） */
  const el = document.getElementById("merge_source");
  if (!el) return "";
  const v = el.value.trim();
  if (!v) return "";
  if (isSvnUrl(v)) { el.dataset.url = v; return v; }
  try {
    const r = await fetch("/api/svn/detect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path: v})});
    const d = await r.json();
    if (d.ok) {
      el.dataset.url = d.url;
      return d.url;
    }
  } catch(_) {}
  return "";
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
              <input type="text" id="merge_source" placeholder="输入要合入的分支 SVN 链接，或拖入本地工作副本自动识别" autocomplete="off" style="flex:1">
              <button class="btn btn-normal" data-action="browse-merge-source"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-merge-source" title="打开文件夹"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
          <div class="form-group">
            <label>目标路径（合并落地的本地工作副本路径）</label>
            <div class="flex-row">
              <input type="text" id="merge_target" placeholder="输入要合入到的本地 SVN 工作副本路径" autocomplete="off" style="flex:1">
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
              <input type="text" id="merge_start" value="${yearStart}" placeholder="YYYY-MM-DD 格式，默认当年 1 月 1 日" style="flex:1;min-width:0">
              <span style="color:var(--dim)">—</span>
              <input type="text" id="merge_end" value="${today}" placeholder="YYYY-MM-DD 格式，默认今天" style="flex:1;min-width:0">
            </div>
          </div>
          <div class="form-group">
            <label>备注关键词（留空不限）</label>
            <input type="text" id="merge_keyword" placeholder="输入提交信息中的关键字，多个用逗号分隔" autocomplete="off">
          </div>
          <div class="form-group">
            <label>提交者（留空不限）</label>
            <input type="text" id="merge_author" placeholder="SVN提交者账户名，多个用逗号分隔" autocomplete="off">
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
                <div class="cd-item selected" data-value="">全部</div>
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
  const svnUrlHistory = getSvnUrlHistory();
  const savedSource = config.merge_source_current || svnUrlHistory[0] || "";
  if (savedSource) {
    const _ms = document.getElementById("merge_source");
    _ms.value = savedSource;
    if (isSvnUrl(savedSource)) _ms.dataset.url = savedSource;
  }
  initSuggest("merge_source", svnUrlHistory);
  // 下拉候选合并本机 SVN 工作副本本地路径
  fetch("/api/svn/working-copies")
    .then(r=>r.json()).then(d => {
      if (d.ok && d.paths && d.paths.length) initSuggest("merge_source", [...new Set([...(config.svn_urls||[]), ...d.paths])]);
    })
    .catch(()=>{});
  document.getElementById("merge_source").addEventListener("change", () => {
    const v = document.getElementById("merge_source").value.trim();
    if (!v) return;
    if (isSvnUrl(v)) {
      document.getElementById("merge_source").dataset.url = v;
    } else {
      // 本地路径 → 反查 SVN 链接
      fetch("/api/svn/detect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path: v})})
        .then(r=>r.json()).then(d => { if (d.ok) document.getElementById("merge_source").dataset.url = d.url; })
        .catch(()=>{});
    }
  });
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
    // 标题栏 + 关闭按钮（设置弹窗不点空白关闭，必须点按钮）
    const headRow = document.createElement("div");
    Object.assign(headRow.style, {display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"8px"});
    const title = document.createElement("span");
    title.textContent = "只包含路径筛选";
    Object.assign(title.style, {fontWeight:"600", fontSize:"13px"});
    const closeBtn = document.createElement("button");
    closeBtn.textContent = "✕";
    closeBtn.title = "关闭";
    Object.assign(closeBtn.style, {background:"none", border:"none", color:"var(--dim)", fontSize:"15px", cursor:"pointer", lineHeight:"1", padding:"0"});
    closeBtn.addEventListener("click", (ev) => { ev.stopPropagation(); popup.remove(); });
    headRow.appendChild(title);
    headRow.appendChild(closeBtn);
    popup.appendChild(headRow);
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
        // 一次原子保存两个键，避免两个并发 POST 互相覆盖（丢失 mode）
        saveConfig({[oldKey]: oldTxt, merge_file_filter_mode: val});
        config[oldKey] = oldTxt;
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
    ta.placeholder = "输入要排除的路径，每行一个，不需要完整路径";
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
  // 设置弹窗不点空白关闭，必须点按钮（✕/保存/关闭）
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
    inp.placeholder = "输入不参与回退的路径，多个用逗号分隔";
    inp.style.cssText = "flex:1";
    row.appendChild(inp);
    var browseBtn = document.createElement("button");
    browseBtn.className = "btn btn-normal btn-sm";
    browseBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>';
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
    if (!val) return;
    if (!isSvnUrl(val)) {
      // 本地路径 → 反查 SVN 链接（手输/粘贴本地路径也支持）
      try {
        const r = await fetch("/api/svn/detect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path: val})});
        const d = await r.json();
        if (d.ok) document.getElementById("merge_source").dataset.url = d.url;
      } catch(_) {}
      return;
    }
    // URL 输入：保存（不入历史）+ 自动解析本地路径填入目标路径（目标为空时）
    saveSvnUrlValue("merge_source", val);
    document.getElementById("merge_source").dataset.url = val;
    if (!document.getElementById("merge_target").value.trim()) {
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
async function _refreshMergeFileList() {
  const revs = Object.keys(_mergeData.checkedRevs).filter(k => _mergeData.checkedRevs[k]).map(Number);
  const hintEl = document.getElementById("merge_file_hint");
  if (!revs.length) {
    document.getElementById("merge_file_list").innerHTML = '<div class="merge-empty">请勾选版本查看变更文件</div>';
    hintEl.textContent = "请勾选需要合并的版本";
    _updateMergeFileCount();
    _updateMergeVersionCount();
    return;
  }
  // 懒加载缺失的勾选版本文件（异步，完成后渲染）
  await _ensureMergeVersionFiles(revs);
  const files = _getCheckedVersionFiles();
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
    // copyfrom 合并来源显示（svn copy / svn merge 复制）
    let cfTag = "";
    if (f.copyfrom_path && f.copyfrom_rev) {
      const cfM = f.copyfrom_path.match(/^\/branches\/([^/]+)/);
      const cfShort = cfM ? cfM[1] : f.copyfrom_path;
      cfTag = `<span class="file-cf" title="${escapeHtml(f.copyfrom_path)}" style="color:var(--dim);font-size:11px;margin-left:8px">来自 ${escapeHtml(cfShort)}@r${escapeHtml(f.copyfrom_rev)}</span>`;
    }
    return `<div class="merge-file-item${checked}${isDel ? " wf-file-del" : ""}" data-path="${escapeHtml(path)}" data-action="${action}" data-idx="${i}">
      <input type="checkbox"${checked}>
      <span class="action-tag ${action}">${actionCn[action]||action}</span>
      ${isDel ? '<span class="del-tag">已删除</span>' : ""}
      <span class="path" title="${escapeHtml(path)}"><span class="file-name">${escapeHtml(name)}</span> <span class="file-dir">${escapeHtml(dir)}</span>${cfTag}</span>
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
    if (select === null) {
      const was = _mergeData.checkedFiles[path];
      _mergeData.checkedFiles[path] = !was;
      if (!was) _mergeData.totalChecked++;
      if (was) _mergeData.totalChecked--;
      el.classList.toggle("checked", !was);
      el.querySelector("input[type='checkbox']").checked = !was;
      return;
    }
    const was = _mergeData.checkedFiles[path];
    _mergeData.checkedFiles[path] = select;
    if (select && !was) _mergeData.totalChecked++;
    if (!select && was) _mergeData.totalChecked--;
    el.classList.toggle("checked", select);
    el.querySelector("input[type='checkbox']").checked = select;
  });
  _updateMergeFileCount();
}
async function runMergeQuery() {
  const sourceUrl = await _ensureMergeSourceUrl();
  const targetPath = document.getElementById("merge_target").value.trim();
  const startDate = document.getElementById("merge_start").value;
  const endDate = document.getElementById("merge_end").value;
  if (!sourceUrl) { _showToast("请输入源SVN地址"); return; }
  if (!isSvnUrl(sourceUrl)) { _showToast("请输入有效的 SVN 链接"); return; }
  if (!targetPath) { _showToast("请输入目标本地工作副本路径"); document.getElementById("merge_target").focus(); return; }
  const dateError = _dateRangeError(startDate, endDate);
  if (dateError) { _showToast(dateError); document.getElementById("merge_start").focus(); return; }
  // 重新查询前清空上次查询的版本列表与勾选状态
  _mergeData.versions = [];
  _mergeData.versionFiles = {};
  _mergeData.checkedRevs = {};
  _mergeData.checkedFiles = {};
  _mergeData.totalChecked = 0;
  _mergeData.lastFileIdx = undefined;
  document.getElementById("merge_version_list").innerHTML = '<div class="merge-empty">查询中…</div>';
  document.getElementById("merge_file_list").innerHTML = '<div class="merge-empty">请勾选版本查看变更文件</div>';
  document.getElementById("merge_file_hint").textContent = "请勾选需要合并的版本";
  document.getElementById("merge_file_count_bottom").textContent = "已选 0 个文件";
  document.getElementById("merge_run_btn").disabled = true;
  document.getElementById("merge_version_count").textContent = "";
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
      target_path: targetPath,
    };
    saveSvnUrlValue("merge_source", sourceUrl);
    const r = await fetch("/api/merge/query", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d = await r.json();
    if (d.error) { _showToast(d.error); _focusAppOnError("merge", logEl); _decRunning(); _decTabRunning("merge"); return; }
    btn.dataset.taskId = d.task_id;
    btn.innerHTML = _WF_ICONS.stop;
    btn.classList.add("stop");
    if (window._esMergeQ) window._esMergeQ.close();
    const _qLog = _mergeLogBatch(logEl);
    const evtSrc = new EventSource("/api/log/stream/" + d.task_id);
    window._esMergeQ = evtSrc;
    let resultData = null;
    const _chunks = [];
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
        _qLog.stop();
        evtSrc.close();
        _mergeDone();
        if (resultData) {
          if (resultData.ok) {
            _mergeData.versions = _chunks.flat() || [];
            _mergeData.versionFiles = {};
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
      if (e.data.startsWith("[CHUNK]")) {
        // 版本摘要分片，逐批累积
        try { _chunks.push(JSON.parse(e.data.slice(7))); } catch(_) {}
        return;
      }
      if (e.data.startsWith("[RESULT]")) {
        try { resultData = JSON.parse(e.data.slice(8)); } catch(_) {}
        return;
      }
      _qLog.push(e.data);
    };
    evtSrc.onerror = () => {
      _qLog.stop();
      evtSrc.close();
      if (window._esMergeQ === evtSrc) window._esMergeQ = null;
      _mergeDone();
      const div = document.createElement("div");
      div.className = "warn";
      div.textContent = "⚠ 日志连接中断";
      _logAppend(logEl, div);
      _focusAppOnError("merge", logEl);
    };
  } catch (err) {
    if (btn.dataset.taskId) { btn.dataset.taskId = ''; btn.classList.remove("stop"); btn.innerHTML = btn.dataset.orig; }
    _decRunning();
    _decTabRunning("merge");
    _showToast("请求失败: " + err.message);
  }
}
async function runMergeAnalysis() {
  triggerUpdateCheck();
  const sourceUrl = await _ensureMergeSourceUrl();
  const targetPath = document.getElementById("merge_target").value.trim();
  if (!sourceUrl) { _showToast("请输入源SVN地址"); return; }
  if (!isSvnUrl(sourceUrl)) { _showToast("请输入有效的 SVN 链接"); document.getElementById("merge_source").focus(); return; }
  if (!targetPath) { _showToast("请输入目标路径（用于GUID映射查询）"); return; }
  const _hasCheckedFiles = Object.values(_mergeData.checkedFiles).some(Boolean);
  const checkedRevsAll = Object.keys(_mergeData.checkedRevs).filter(k => _mergeData.checkedRevs[k]).map(Number);
  if (!checkedRevsAll.length) { _showToast("请至少勾选一个版本"); return; }
  // 懒加载勾选版本的变更文件（缺失则先拉取）
  await _ensureMergeVersionFiles(checkedRevsAll);
  const revFileMap = {};
  checkedRevsAll.forEach(rev => {
    let filtered = (_mergeData.versionFiles[rev] || []).filter(f => !_isPathExcluded(f.path));
    if (_hasCheckedFiles) {
      filtered = filtered.filter(f => _mergeData.checkedFiles[f.path]);
    }
    if (filtered.length) {
      revFileMap[rev] = filtered.map(f => ({path: f.path, action: f.action}));
    }
  });
  const checkedRevs = _hasCheckedFiles
    ? Object.keys(revFileMap).map(Number)
    : checkedRevsAll;
  if (!checkedRevs.length) { _showToast("请至少勾选一个版本"); return; }
  const versionFiles = Object.values(revFileMap).flat().map(f => f.path);
  const btn = document.getElementById("merge_analysis_btn");
  btn.dataset.orig = btn.dataset.orig || btn.textContent;
  const logEl = document.getElementById("merge_log");
  _logClear(logEl);
  logEl?.scrollIntoView({behavior:"smooth", block:"nearest"});
  _incRunning();
  _incTabRunning("merge");
  const _srcLocal = document.getElementById("merge_source")?.value.trim() || "";
  const body = { source_url: sourceUrl, source_local: _srcLocal, target_path: targetPath, revisions: checkedRevs, version_files: versionFiles, rev_file_map: revFileMap };
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
    evtSrc.onerror = () => {
      evtSrc.close();
      window._esMergeAna = null;
      _mergeAnaDone();
      const div = document.createElement("div");
      div.className = "warn";
      div.textContent = "⚠ 日志连接中断";
      _logAppend(logEl, div);
      _focusAppOnError("merge", logEl);
    };
  } catch (err) {
    if (btn.dataset.taskId) { btn.dataset.taskId = ''; btn.classList.remove("stop"); btn.innerHTML = btn.dataset.orig; }
    _decRunning();
    _decTabRunning("merge");
    _showToast("请求失败: " + err.message);
  }
}
async function runMergeRun() {
  triggerUpdateCheck();
  const sourceUrl = await _ensureMergeSourceUrl();
  const targetPath = document.getElementById("merge_target").value.trim();
  if (!sourceUrl) { _showToast("请输入源SVN地址"); return; }
  if (!isSvnUrl(sourceUrl)) { _showToast("请输入有效的 SVN 链接"); document.getElementById("merge_source").focus(); return; }
  if (!targetPath) { _showToast("请输入目标路径"); return; }
  const checkedPaths = Object.keys(_mergeData.checkedFiles).filter(k => _mergeData.checkedFiles[k]);
  if (!checkedPaths.length) { _showToast("请至少选择一个文件"); return; }
  const checkedRevs = Object.keys(_mergeData.checkedRevs).map(Number);
  if (!checkedRevs.length) { _showToast("请至少勾选一个版本"); return; }
  // 懒加载勾选版本的变更文件（缺失则先拉取）
  await _ensureMergeVersionFiles(checkedRevs);
  const btn = document.getElementById("merge_run_btn");
  btn.dataset.orig = btn.dataset.orig || btn.textContent;
  const logEl = document.getElementById("merge_log");
  _logClear(logEl);
  logEl?.scrollIntoView({behavior:"smooth", block:"nearest"});
  _incRunning();
  _incTabRunning("merge");
  const revFileMap = {};
  checkedRevs.forEach(rev => {
    (_mergeData.versionFiles[rev] || []).forEach(f => {
      if (!_isPathExcluded(f.path) && _mergeData.checkedFiles[f.path]) {
        if (!revFileMap[f.path]) revFileMap[f.path] = [];
        revFileMap[f.path].push(rev);
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
      _showToast(d.error);
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
    const _runLog = _mergeLogBatch(logEl);
    evtSrc.onmessage = (e) => {
      if (e.data === "[DONE]") {
        _runLog.stop();
        evtSrc.close();
        window._esMergeRun = null;
        _mergeRunDone();
        return;
      }
      _runLog.push(e.data);
    };
    evtSrc.onerror = () => {
      _runLog.stop();
      evtSrc.close();
      window._esMergeRun = null;
      _mergeRunDone();
      const div = document.createElement("div");
      div.className = "warn";
      div.textContent = "⚠ 日志连接中断";
      _logAppend(logEl, div);
      _focusAppOnError("merge", logEl);
    };
  } catch (err) {
    logEl.innerHTML = '<span class="error">❌ 请求失败: '+escapeHtml(err.message)+'</span>';
    _showToast("请求失败：" + err.message);
    _focusAppOnError("merge", logEl);
    if (btn.dataset.taskId) { btn.dataset.taskId = ''; btn.classList.remove("stop"); btn.innerHTML = btn.dataset.orig; }
    _decRunning();
    _decTabRunning("merge");
  }
}
