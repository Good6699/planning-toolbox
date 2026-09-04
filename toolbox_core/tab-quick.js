let _quickData = [];

const _QK = {
  update: '<svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 7a5 5 0 019.9-1"/><path d="M12 7a5 5 0 01-9.9 1"/><path d="M12 2v4h-4"/><path d="M2 12V8h4"/></svg>',
  commit: '<svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M7 12V4"/><path d="M4 7l3-3 3 3"/><path d="M2 2h10"/></svg>',
  log: '<svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="3" x2="11" y2="3"/><line x1="3" y1="7" x2="11" y2="7"/><line x1="3" y1="11" x2="8" y2="11"/></svg>',
  folder: '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4a1.5 1.5 0 011.5-1.5h3l1.5 2H13A1.5 1.5 0 0114.5 6v5A1.5 1.5 0 0113 12.5H3A1.5 1.5 0 011.5 11V4z"/></svg>',
  file: '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 1.5h5l3 3V14a.6.6 0 01-.6.6H4a.6.6 0 01-.6-.6V2.1A.6.6 0 014 1.5z"/><path d="M9 1.5V5h3"/></svg>',
};

function _quickBase(p) {
  const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
  return i >= 0 ? p.substring(i + 1) : p;
}

function buildQuickTab(panel) {
  panel.innerHTML = `
    <div class="quick-layout">
      <div class="quick-list" id="quick_list"></div>
    </div>`;
  _quickLoad();
}

function _quickLoad() {
  fetch("/api/quicklist").then(r => r.json()).then(d => {
    _quickData = Array.isArray(d.quicklist) ? d.quicklist : [];
    _quickRender();
  }).catch(() => {
    _quickData = [];
    _quickRender();
  });
}

function _quickSave() {
  fetch("/api/quicklist", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({quicklist:_quickData})}).catch(()=>{});
}

function _quickRender() {
  const list = document.getElementById("quick_list");
  if (!list) return;
  const addItem = '<div class="quick-group-add" data-action="qk-add-group" style="margin:0"><span class="qk-plus">＋</span><span>新建分组</span></div>';
  const finish = (svnMap) => {
    list.innerHTML = _quickData.map((g, gi) => _quickGroup(g, gi, svnMap || {})).join("") + addItem;
    _quickBind(list);
  };
  if (!_quickData.length) { list.innerHTML = addItem; _quickBind(list); return; }
  const paths = [];
  _quickData.forEach(g => (g.items || []).forEach(p => { if (p) paths.push(p); }));
  if (paths.length) {
    fetch("/api/quick/svn-check", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({paths})})
      .then(r => r.json()).then(d => {
        const m = {};
        (d.results || []).forEach(x => { m[x.path] = x.is_svn; });
        finish(m);
      }).catch(() => finish({}));
  } else {
    finish({});
  }
}

function _quickGroup(g, gi, svnMap) {
  const items = (g.items || []).map((p, ii) => {
    const isSvn = !!svnMap[p];
    const svnBtns = isSvn
      ? `<button class="qk-s-btn" data-act="update" title="更新SVN">${_QK.update}</button>
         <button class="qk-s-btn" data-act="commit" title="提交SVN">${_QK.commit}</button>
         <button class="qk-s-btn" data-act="log" title="查看日志">${_QK.log}</button>`
      : "";
    return `<div class="quick-item" data-gi="${gi}" data-ii="${ii}" title="${escapeHtml(p)}">
      <span class="qk-ico">${isSvn ? _QK.folder : _QK.file}</span>
      <span class="quick-item-name">${escapeHtml(_quickBase(p))}</span>
      <span class="qk-acts">
        ${svnBtns}
        <button class="qk-s-btn" data-act="del-item" title="移除">✕</button>
      </span>
    </div>`;
  }).join("");
  return `<div class="quick-group" data-gi="${gi}" draggable="true">
    <div class="quick-group-header" data-gi="${gi}">
      <span class="qk-arrow">▼</span>
      <span class="quick-group-name" title="双击重命名">${escapeHtml(g.name)}</span>
      <span class="qk-acts">
        <button class="qk-s-btn" data-act="rename-group" title="重命名分组">✎</button>
        <button class="qk-s-btn" data-act="del-group" title="删除分组">✕</button>
      </span>
    </div>
    <div class="quick-items" data-gi="${gi}">${items || '<div class="quick-empty">拖入文件或文件夹</div>'}</div>
  </div>`;
}

function _quickBind(list) {
  const _addBtn = list.querySelector('[data-action=qk-add-group]');
  if (_addBtn) _addBtn.addEventListener("click", e => { e.preventDefault(); _quickAddGroup(list); });
  // 分组操作
  list.querySelectorAll("[data-act=rename-group]").forEach(btn => btn.addEventListener("click", e => {
    e.stopPropagation();
    const gi = Number(btn.closest(".quick-group-header").dataset.gi);
    _quickInlineRename(btn.closest(".quick-group-header"), gi);
  }));
  list.querySelectorAll("[data-act=del-group]").forEach(btn => btn.addEventListener("click", e => {
    e.stopPropagation();
    const gi = Number(btn.closest(".quick-group-header").dataset.gi);
    showConfirm({title:"删除分组", message:`确定删除分组「${_quickData[gi].name}」？`, confirmText:"删除", danger:true}).then(ok => {
      if (ok) { _quickData.splice(gi, 1); _quickSave(); _quickRender(); }
    });
  }));
  list.querySelectorAll(".quick-group-header").forEach(h => h.addEventListener("click", e => {
    if (e.target.closest("[data-act]")) return;
    const gi = Number(h.dataset.gi);
    const items = h.nextElementSibling;
    if (!items) return;
    const hidden = items.style.display === "none";
    items.style.display = hidden ? "" : "none";
    h.querySelector(".qk-arrow").textContent = hidden ? "▼" : "▶";
  }));
  // 条目双击打开
  list.querySelectorAll(".quick-item").forEach(item => item.addEventListener("dblclick", () => {
    const {gi, ii} = item.dataset;
    const p = _quickData[Number(gi)]?.items?.[Number(ii)];
    if (p) fetch("/api/quick/open", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:p})}).catch(()=>{});
  }));
  // 条目管理 + svn 按钮
  list.querySelectorAll(".quick-item [data-act]").forEach(btn => btn.addEventListener("click", e => {
    e.stopPropagation();
    const item = btn.closest(".quick-item");
    const {gi, ii} = item.dataset;
    const g = _quickData[Number(gi)];
    const p = g?.items?.[Number(ii)];
    if (!p) return;
    const act = btn.dataset.act;
    if (act === "update") { fetch("/api/quick/update", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:p})}).then(r=>r.json()).then(d=>_showToast(d.ok?("SVN 更新完成"):("更新失败: "+(d.msg||d.error||"")))).catch(()=>_showToast("更新请求失败")); }
    else if (act === "commit") fetch("/api/quick/commit", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:p})}).catch(()=>{});
    else if (act === "log") fetch("/api/quick/log", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:p})}).catch(()=>{});
    else if (act === "del-item") { showConfirm({title:"移除条目", message:`从分组移除「${_quickBase(p)}」？`, confirmText:"移除", danger:true}).then(ok => { if (ok) { g.items.splice(Number(ii),1); _quickSave(); _quickRender(); } }); }
    else if (act === "rename-item") { _quickInlinePathRename(item, Number(gi), Number(ii)); }
  }));
  // 拖放：分组区域接收文件/文件夹
  _quickBindDrop(list);
}

function _quickInlineRename(header, gi) {
  const nameEl = header.querySelector(".quick-group-name");
  const old = _quickData[gi].name || "";
  const input = document.createElement("input");
  input.className = "quick-name-input";
  input.value = old;
  nameEl.textContent = "";
  nameEl.appendChild(input);
  input.focus(); input.select();
  const finish = (save) => {
    const v = input.value.trim();
    if (save && v) { _quickData[gi].name = v; _quickSave(); }
    _quickRender();
  };
  input.addEventListener("blur", () => finish(true));
  input.addEventListener("keydown", ke => { if (ke.key === "Enter") { ke.preventDefault(); input.blur(); } else if (ke.key === "Escape") input.blur(); });
}

function _quickInlinePathRename(item, gi, ii) {
  const old = _quickData[gi].items[ii] || "";
  const v = prompt("输入新的文件/文件夹路径：", old);
  if (v && v.trim()) { _quickData[gi].items[ii] = v.trim(); _quickSave(); _quickRender(); }
}

function _quickAddGroup(list) {
  const addBtn = list.querySelector('[data-action=qk-add-group]');
  if (!addBtn) return;
  const orig = addBtn.innerHTML;
  const input = document.createElement("input");
  input.className = "quick-name-input";
  input.placeholder = "输入分组名称，回车确认";
  addBtn.textContent = "";
  addBtn.appendChild(input);
  input.focus();
  const finish = (save) => {
    const v = input.value.trim();
    if (save && v) { addBtn.innerHTML = orig; _quickData.push({name:v, items:[]}); _quickSave(); _quickRender(); return; }
    addBtn.innerHTML = orig;
  };
  input.addEventListener("blur", () => finish(true));
  input.addEventListener("keydown", ke => {
    if (ke.key === "Enter") { ke.preventDefault(); input.blur(); }
    else if (ke.key === "Escape") { finish(false); }
  });
}

function _quickReorderGroup(fromGi, toGi) {
  const moved = _quickData.splice(fromGi, 1)[0];
  if (!moved) return;
  let insertIdx = toGi;
  if (fromGi < toGi) insertIdx = toGi - 1;
  _quickData.splice(insertIdx, 0, moved);
  _quickSave();
  _quickRender();
}

function _quickBindDrop(list) {
  let _dragGi = null;
  list.querySelectorAll(".quick-group").forEach(card => {
    if (card.getAttribute("draggable") === "true") {
      card.addEventListener("dragstart", e => {
        _dragGi = Number(card.dataset.gi);
        e.dataTransfer.effectAllowed = "move";
      });
      card.addEventListener("dragend", () => {
        _dragGi = null;
        list.querySelectorAll(".quick-group").forEach(c => c.classList.remove("drag-over"));
      });
    }
    card.addEventListener("dragover", e => { e.preventDefault(); card.classList.add("drag-over"); });
    card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
    card.addEventListener("drop", e => {
      e.preventDefault();
      card.classList.remove("drag-over");
      const targetGi = Number(card.dataset.gi);
      if (_dragGi != null && _dragGi !== targetGi) {
        _quickReorderGroup(_dragGi, targetGi);
        _dragGi = null;
        return;
      }
      if (!_quickData[targetGi]) return;
      const finish = (paths) => {
        if (!paths || !paths.length) { _showToast("拖拽路径获取失败"); return; }
        _quickData[targetGi].items = _quickData[targetGi].items || [];
        paths.forEach(p => { if (p && !_quickData[targetGi].items.includes(p)) _quickData[targetGi].items.push(p); });
        _quickSave();
        _quickRender();
      };
      if (window.chrome && chrome.webview && chrome.webview.postMessageWithAdditionalObjects && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        try {
          chrome.webview.postMessageWithAdditionalObjects("FilesDropped", e.dataTransfer.files);
          const tryConsume = (n) => fetch("/api/prefab/consume-dropped", {method:"POST"}).then(r=>r.json()).then(d=>{
            if ((d.paths||[]).length) finish(d.paths);
            else if (n < 15) setTimeout(()=>tryConsume(n+1), 200);
            else _showToast("拖拽路径获取超时");
          });
          setTimeout(()=>tryConsume(0), 200);
        } catch(ex) { _showToast("拖拽路径获取失败"); }
      } else {
        _showToast("请使用桌面版拖拽");
      }
    });
  });
}
