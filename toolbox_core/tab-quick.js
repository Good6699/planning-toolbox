let _quickData = [];
let _quickExpanded = new Set();
let _quickRenaming = false;

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

// 条目 item 可为 string（路径）或 {p, n}（路径 + 自定义显示名）
function _itemPath(it) { return typeof it === "string" ? it : (it && it.p ? it.p : ""); }
function _itemName(it) {
  if (typeof it === "string") return _quickBase(it);
  if (it && it.n) return it.n;
  return _quickBase(_itemPath(it));
}

function buildQuickTab(panel) {
  panel.innerHTML = `
    <div class="quick-layout">
      <div class="quick-list" id="quick_list"></div>
    </div>`;
  // 改名期间（_quickRenaming）在 document 捕获阶段阻断 dragstart / dragover / drop，
  // 防止在输入框里选文本或拖动被当作拖拽（元素拖拽由 dragstart 启动，必须一并拦）
  document.addEventListener("dragstart", e => { if (_quickRenaming) { e.preventDefault(); e.stopPropagation(); } }, true);
  document.addEventListener("dragover", e => { if (_quickRenaming) { e.preventDefault(); e.stopPropagation(); } }, true);
  document.addEventListener("drop", e => { if (_quickRenaming) { e.preventDefault(); e.stopPropagation(); } }, true);
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
  const finish = (svnMap, folderMap) => {
    list.innerHTML = _quickData.map((g, gi) => _quickGroup(g, gi, svnMap || {}, folderMap || {})).join("") + addItem;
    _quickBind(list);
  };
  if (!_quickData.length) { list.innerHTML = addItem; _quickBind(list); return; }
  const paths = [];
  _quickData.forEach(g => (g.items || []).forEach(it => { const p = _itemPath(it); if (p) paths.push(p); }));
  if (paths.length) {
    fetch("/api/quick/svn-check", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({paths})})
      .then(r => r.json()).then(d => {
        const svnM = {}, folderM = {};
        (d.results || []).forEach(x => { svnM[x.path] = x.is_svn; folderM[x.path] = x.is_folder; });
        finish(svnM, folderM);
      }).catch(() => finish({}, {}));
  } else {
    finish({}, {});
  }
}

function _quickGroup(g, gi, svnMap, folderMap) {
  const items = (g.items || []).map((p, ii) => {
    const path = _itemPath(p);
    const isSvn = !!svnMap[path];
    const isFolder = !!(folderMap && folderMap[path]);
    const svnBtns = isSvn
      ? `<button class="qk-s-btn" data-act="update" title="更新SVN">${_QK.update}</button>
         <button class="qk-s-btn" data-act="commit" title="提交SVN">${_QK.commit}</button>
         <button class="qk-s-btn" data-act="log" title="查看日志">${_QK.log}</button>`
      : "";
    return `<div class="quick-item" data-gi="${gi}" data-ii="${ii}" draggable="true" title="${escapeHtml(path)}">
      <span class="qk-ico">${isFolder ? _QK.folder : _QK.file}</span>
      <span class="quick-item-name">${escapeHtml(_itemName(p))}</span>
      <span class="qk-acts">
        ${svnBtns}
        <button class="qk-s-btn" data-act="rename-item-name" title="修改名称">✎</button>
        <button class="qk-s-btn" data-act="del-item" title="移除">✕</button>
      </span>
    </div>`;
  }).join("");
  const expanded = _quickExpanded.has(gi);
  return `<div class="quick-group" data-gi="${gi}" draggable="true">
    <div class="quick-group-header" data-gi="${gi}">
      <span class="qk-arrow">${expanded ? "▼" : "▶"}</span>
      <span class="quick-group-name" title="拖拽调整分组顺序">${escapeHtml(g.name)}</span>
      <span class="qk-acts">
        <button class="qk-s-btn" data-act="rename-group" title="重命名分组">✎</button>
        <button class="qk-s-btn" data-act="del-group" title="删除分组">✕</button>
      </span>
    </div>
    <div class="quick-items" data-gi="${gi}" ${expanded ? "" : 'style="display:none"'}>${items || '<div class="quick-empty">拖入文件或文件夹</div>'}</div>
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
    if (e.target.closest("input")) return;  // 改名输入框内点击不触发展开收起
    const gi = Number(h.dataset.gi);
    if (!h.nextElementSibling) return;
    const hidden = h.nextElementSibling.style.display === "none";
    if (hidden) { _quickExpanded.clear(); _quickExpanded.add(gi); }  // 手风琴：同时只展开一个
    else { _quickExpanded.delete(gi); }
    _quickRender();
  }));
  // 条目双击打开
  list.querySelectorAll(".quick-item").forEach(item => item.addEventListener("dblclick", () => {
    const {gi, ii} = item.dataset;
    const p = _itemPath(_quickData[Number(gi)]?.items?.[Number(ii)]);
    if (p) fetch("/api/quick/open", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:p})}).catch(()=>{});
  }));
  // 条目管理 + svn 按钮
  list.querySelectorAll(".quick-item [data-act]").forEach(btn => btn.addEventListener("click", e => {
    e.stopPropagation();
    const item = btn.closest(".quick-item");
    const {gi, ii} = item.dataset;
    const g = _quickData[Number(gi)];
    const itemRaw = g?.items?.[Number(ii)];
    const p = _itemPath(itemRaw);
    if (!p) return;
    const act = btn.dataset.act;
    if (act === "update") { fetch("/api/quick/update", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:p})}).then(r=>r.json()).then(d=>_showToast(d.ok?("SVN 更新完成"):("更新失败: "+(d.msg||d.error||"")))).catch(()=>_showToast("更新请求失败")); }
    else if (act === "commit") fetch("/api/quick/commit", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:p})}).catch(()=>{});
    else if (act === "log") fetch("/api/quick/log", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:p})}).catch(()=>{});
    else if (act === "del-item") { showConfirm({title:"移除条目", message:`从分组移除「${_itemName(itemRaw)}」？`, confirmText:"移除", danger:true}).then(ok => { if (ok) { g.items.splice(Number(ii),1); _quickSave(); _quickRender(); } }); }
    else if (act === "rename-item-name") { _quickInlineItemNameRename(item, Number(gi), Number(ii)); }
  }));
  // 拖放：分组区域接收文件/文件夹
  _quickBindDrop(list);
}

function _quickInlineRename(header, gi) {
  const nameEl = header.querySelector(".quick-group-name");
  const old = _quickData[gi].name || "";
  const card = header.closest(".quick-group");
  if (card) card.setAttribute("draggable", "false");  // 改名期间禁用卡片拖拽
  _quickRenaming = true;
  const input = document.createElement("input");
  input.className = "quick-name-input";
  input.setAttribute("draggable", "false");
  input.addEventListener("dragstart", e => e.preventDefault());
  input.addEventListener("mousedown", e => e.stopPropagation());
  input.value = old;
  nameEl.textContent = "";
  nameEl.appendChild(input);
  input.focus(); input.select();
  const finish = (save) => {
    _quickRenaming = false;
    const v = input.value.trim();
    if (save && v) { _quickData[gi].name = v; _quickSave(); }
    _quickRender();
  };
  input.addEventListener("blur", () => finish(true));
  input.addEventListener("keydown", ke => { if (ke.key === "Enter") { ke.preventDefault(); input.blur(); } else if (ke.key === "Escape") input.blur(); });
}

function _quickInlineItemNameRename(itemEl, gi, ii) {
  const cur = _quickData[gi].items[ii];
  const nameEl = itemEl.querySelector(".quick-item-name");
  const old = _itemName(cur);
  itemEl.setAttribute("draggable", "false");  // 改名期间禁用条目拖拽，避免选文本被当作拖拽
  const card = itemEl.closest(".quick-group");
  if (card) card.setAttribute("draggable", "false");  // 条目在分组卡片内，同时禁用卡片拖拽
  _quickRenaming = true;
  const input = document.createElement("input");
  input.className = "quick-name-input";
  input.setAttribute("draggable", "false");
  input.addEventListener("dragstart", e => e.preventDefault());
  input.addEventListener("mousedown", e => e.stopPropagation());
  input.value = old;
  nameEl.textContent = "";
  nameEl.appendChild(input);
  input.focus(); input.select();
  const finish = (save) => {
    _quickRenaming = false;
    const v = input.value.trim();
    if (save && v) {
      const path = _itemPath(cur);
      if (typeof cur === "string") { _quickData[gi].items[ii] = {p:path, n:v}; }
      else if (cur) { cur.n = v; }
      _quickSave();
    }
    _quickRender();
  };
  input.addEventListener("blur", () => finish(true));
  input.addEventListener("keydown", ke => { if (ke.key === "Enter") { ke.preventDefault(); input.blur(); } else if (ke.key === "Escape") input.blur(); });
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
  if (fromGi === toGi) return;
  const moved = _quickData.splice(fromGi, 1)[0];
  if (!moved) return;
  // 落到目标卡片位置（不补偿）：从左往右 / 从右往左都能正常移动
  _quickData.splice(Math.min(toGi, _quickData.length), 0, moved);
  _quickSave();
  _quickRender();
}

function _quickReorderItem(from, toGi, toIi) {
  const {gi, ii} = from;
  if (gi !== toGi) return; // 条目排序限同分组内
  const g = _quickData[gi];
  if (!g || ii === toIi) return;
  const it = g.items.splice(ii, 1)[0];
  g.items.splice(Math.min(toIi, g.items.length), 0, it);
  _quickSave();
  _quickRender();
}

function _quickBindDrop(list) {
  let _dragGi = null;
  let _itemDrag = null;
  // 条目拖拽排序（组内）
  list.querySelectorAll(".quick-item").forEach(item => {
    item.addEventListener("dragstart", e => {
      _itemDrag = {gi:Number(item.dataset.gi), ii:Number(item.dataset.ii)};
      e.dataTransfer.effectAllowed = "move";
      e.stopPropagation(); // 防止同时触发分组卡片的 dragstart
    });
    item.addEventListener("dragend", () => { _itemDrag = null; list.querySelectorAll(".quick-item").forEach(i => i.classList.remove("drag-over")); });
    item.addEventListener("dragover", e => { if (_itemDrag) { e.preventDefault(); item.classList.add("drag-over"); } });
    item.addEventListener("dragleave", () => item.classList.remove("drag-over"));
    item.addEventListener("drop", e => {
      if (_itemDrag) {
        e.preventDefault(); e.stopPropagation();
        item.classList.remove("drag-over");
        _quickReorderItem(_itemDrag, Number(item.dataset.gi), Number(item.dataset.ii));
        _itemDrag = null;
      }
    });
  });
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
    card.addEventListener("dragover", e => {
      const hasFiles = e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.indexOf("Files") >= 0;
      // 条目拖拽只在同分组内响应；拖到其它分组不响应（禁止落下）
      const sameGroupItem = _itemDrag && _itemDrag.gi === Number(card.dataset.gi);
      if (_dragGi != null || sameGroupItem || hasFiles) { e.preventDefault(); card.classList.add("drag-over"); }
    });
    card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
    card.addEventListener("drop", e => {
      const hasFiles = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0;
      if (_dragGi == null && _itemDrag == null && !hasFiles) return;  // 文本/空拖不处理，避免弹提示
      e.preventDefault();
      card.classList.remove("drag-over");
      const targetGi = Number(card.dataset.gi);
      // 条目拖到分组卡片：仅同分组才移动，跨组忽略（不能拖到其它分组）
      if (_itemDrag) {
        if (_itemDrag.gi === targetGi) _quickReorderItem(_itemDrag, targetGi, (_quickData[targetGi]?.items || []).length);
        _itemDrag = null;
        return;
      }
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
        _quickExpanded.clear(); _quickExpanded.add(targetGi);  // 拖入后自动展开该分组
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
