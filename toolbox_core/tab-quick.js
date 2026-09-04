let _quickData = [];
let _quickExpanded = new Set();
let _quickRenaming = false;
let _quickDragGeo = null;   // 拖拽期间缓存的网格几何（减少 dragover 时读布局）
let _guideLast = null;      // 上次引导框位置，避免跨格子导致重复布局

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
  // 窗口宽度变化时重算列数
  let _qResT = null;
  window.addEventListener("resize", () => { clearTimeout(_qResT); _qResT = setTimeout(() => { if (window._quickRender) window._quickRender(); }, 200); });
  _quickLoad();
}

function _quickColCount(list) {
  const w = (list && list.parentElement && list.parentElement.clientWidth) ||
            (list && list.clientWidth) || window.innerWidth || 900;
  return Math.max(1, Math.floor((w + 6) / 346));  // 列宽 340 + 间隙 6
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

// 渲染空白格子（淡色虚线）：占满分组行，并额外铺到刚好填满一个窗口，让网格区域可见
function _quickPlaceholders(nCols, list, addRow) {
  let maxRow = 0;
  const occupied = new Set();
  _quickData.forEach(g => {
    const r = g.r ?? 0, c = g.c ?? 0;
    occupied.add(r + ":" + c);
    if (r > maxRow) maxRow = r;
  });
  // 按可视高度算出铺满窗口所需行数（行高 44 + 间隙 6）
  const area = list && (list.parentElement || list) ? (list.parentElement || list).clientHeight : 0;
  const ROW = 44, GAP = 6;
  let needRows = 0;
  if (area > 0) needRows = Math.max(1, Math.ceil((area - 8) / (ROW + GAP)));
  const totalRows = Math.max(maxRow, needRows - 1, (addRow || 0));
  let html = "";
  for (let r = 0; r <= totalRows; r++) {
    for (let c = 0; c < nCols; c++) {
      if ((addRow != null && r === addRow && c === 0)) continue;  // 跳过新建分组按钮那一格
      if (!occupied.has(r + ":" + c)) html += `<div class="quick-cell" style="grid-row:${r+1};grid-column:${c+1}"></div>`;
    }
  }
  return html;
}

function _quickRender() {
  const list = document.getElementById("quick_list");
  if (!list) return;
  // 新建分组按钮：显式放在最高分组下一行（grid-row 1-based = maxGroupRow+2）
  const addItem = (row) => `<div class="quick-group-add" data-action="qk-add-group" style="margin:0;grid-row:${row};grid-column:1"><span class="qk-plus">＋</span><span>新建分组</span></div>`;
  const finish = (svnMap, folderMap) => {
    const nCols = _quickColCount(list);
    list.style.setProperty("--qc-n", nCols);
    list.style.alignItems = "start";  // 收起=紧凑、展开=长高；防止 stretch 把行钳在最小高导致展开内容被裁剪
    let maxGroupRow = 0;
    _quickData.forEach(g => {
      if (g.r == null) g.r = 0;
      if (g.c == null) g.c = 0;
      if (g.c >= nCols) g.c = nCols - 1;
      if (g.r > maxGroupRow) maxGroupRow = g.r;
    });
    list.innerHTML = _quickData.map((g, gi) => _quickGroup(g, gi, svnMap || {}, folderMap || {})).join("")
      + _quickPlaceholders(nCols, list, maxGroupRow + 1)
      + addItem(maxGroupRow + 2);
    _quickBind(list);
  };
  if (!_quickData.length) { list.style.setProperty("--qc-n", 1); list.innerHTML = addItem(1); _quickBind(list); return; }
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
  return `<div class="quick-group" data-gi="${gi}" style="grid-row:${(g.r||0)+1};grid-column:${(g.c||0)+1}">
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
    if (save && v) {
      addBtn.innerHTML = orig;
      // 放到最下方整行空的行的第一位（不叠在任何已有分组上）
      const maxR = Math.max(0, ..._quickData.map(g => g.r ?? 0));
      _quickData.push({name:v, items:[], c:0, r:maxR + 1});
      _quickSave(); _quickRender();
      return;
    }
    addBtn.innerHTML = orig;
  };
  input.addEventListener("blur", () => finish(true));
  input.addEventListener("keydown", ke => {
    if (ke.key === "Enter") { ke.preventDefault(); input.blur(); }
    else if (ke.key === "Escape") { finish(false); }
  });
}

// 交换两个分组占据的网格格点（拖动分组落到另一分组所在格 → 交换位置）
function _quickSwapGroup(a, b) {
  if (a === b) return;
  const A = _quickData[a], B = _quickData[b];
  if (!A || !B) return;
  const ar = A.r ?? 0, ac = A.c ?? 0;
  A.r = B.r ?? 0; A.c = B.c ?? 0;
  B.r = ar; B.c = ac;
  _quickSave();
  _quickDropApply();
}

// 落子后仅原地更新分组/按钮位置（不整页重渲染、不重新 svn-check），让释放即时生效
function _quickDropApply() {
  const list = document.getElementById("quick_list");
  if (!list) return;
  let maxR = 0;
  list.querySelectorAll(".quick-group").forEach(card => {
    const gi = Number(card.dataset.gi);
    const g = _quickData[gi];
    if (g) {
      const r = (g.r ?? 0), c = (g.c ?? 0);
      card.style.gridRow = r + 1;
      card.style.gridColumn = c + 1;
      if (r > maxR) maxR = r;
    }
    card.classList.remove("quick-drag-collapsed", "drag-over");
  });
  const add = list.querySelector(".quick-group-add");
  if (add) add.style.gridRow = (maxR + 2);
  _quickGuideHide();
}

// 生成拖拽浮层（小标签），跟随鼠标；内联关键样式保证不依赖 index.html 缓存
function _makeDragGhost(card) {
  const g = document.createElement("div");
  g.className = "quick-drag-ghost";
  g.style.cssText = "position:fixed;z-index:99;pointer-events:none;background:#1d2330;border:1px solid #5ea2ff;color:#f2f5ff;padding:6px 12px;border-radius:8px;font-size:12px;font-weight:600;box-shadow:0 8px 20px rgba(0,0,0,.45);white-space:nowrap;";
  const name = (card.querySelector(".quick-group-name") || {}).textContent || "";
  g.textContent = name || "拖动中";
  return g;
}

// 指针自绘拖拽分组（换位置）：按住 → 浮层跟随 + 引导框 → 松开落子
function _startGroupPointerDrag(e, card, gi, list) {
  const startX = e.clientX, startY = e.clientY;
  let moved = false, ghost = null;
  const onMove = (ev) => {
    if (!moved) {
      if (Math.hypot(ev.clientX - startX, ev.clientY - startY) < 6) return;  // 拖拽阈值
      moved = true;
      _groupDrag = gi;
      _quickDragGeo = _quickBuildGeo(list);
      ghost = _makeDragGhost(card);
      document.body.appendChild(ghost);
      card.classList.add("quick-drag-collapsed");
    }
    if (ghost) {
      ghost.style.left = (ev.clientX - ghost.offsetWidth / 2) + "px";
      ghost.style.top = (ev.clientY - 10) + "px";
    }
    const cell = _quickCellFromXY(ev.clientX, ev.clientY, _quickDragGeo);
    const own = _quickData[gi];
    if (cell.row === (own?.r ?? 0) && cell.col === (own?.c ?? 0)) _quickGuideHide();
    else {
      const occ = _quickData.findIndex(g => (g.r ?? 0) === cell.row && (g.c ?? 0) === cell.col);
      _quickGuideShow(cell.row, cell.col, (occ >= 0 && occ !== gi) ? "swap" : "place");
    }
  };
  const onUp = (ev) => {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
    if (ghost) ghost.remove();
    if (moved) {
      // 拖拽结束会紧跟一个 click（浏览器行为），把它吞掉，避免误触发展开/收起
      const suppress = (ce) => { ce.stopPropagation(); ce.preventDefault(); document.removeEventListener("click", suppress, true); };
      document.addEventListener("click", suppress, true);
      setTimeout(() => document.removeEventListener("click", suppress, true), 200);
    }
    if (moved && _groupDrag != null) {
      const cell = _quickCellFromXY(ev.clientX, ev.clientY, _quickDragGeo);
      const occ = _quickData.findIndex(g => (g.r ?? 0) === cell.row && (g.c ?? 0) === cell.col);
      if (occ >= 0 && occ !== gi) _quickSwapGroup(gi, occ);
      else { _quickData[gi].r = cell.row; _quickData[gi].c = cell.col; _quickSave(); _quickDropApply(); }
    }
    _groupDrag = null;
    _quickDragGeo = null;
    _quickGuideHide();
    list.querySelectorAll(".quick-group").forEach(c => c.classList.remove("drag-over", "quick-drag-collapsed"));
  };
  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp);
}

// 拖拽开始时缓存网格几何：卡片视口位置 + 列数，此后 dragover 只用纯算术推算，避免反复读布局
function _quickBuildGeo(list) {
  const rect = list.getBoundingClientRect();
  const nCols = _quickColCount(list);
  const MIN = 44, GAP = 6;  // 与 CSS grid-auto-rows 的 min(44=新建分组高) 及 gap(6=减半) 一致
  // 每行实测高度（取该行最高卡片；空行 = MIN）
  const byRow = {};
  let maxGroupRow = 0;
  list.querySelectorAll(".quick-group").forEach(c => {
    const gi = Number(c.dataset.gi);
    const row = _quickData[gi]?.r ?? 0;
    const h = c.offsetHeight;
    if (h > (byRow[row] || 0)) byRow[row] = h;
    if (row > maxGroupRow) maxGroupRow = row;
  });
  // 占位格会铺到填满窗口，几何也要覆盖到那一行，否则下面空格拖不进去
  const area = (list.parentElement || list).clientHeight || 0;
  const needRows = area > 0 ? Math.max(1, Math.ceil((area - 8) / (MIN + GAP))) : 0;
  const maxRow = Math.max(maxGroupRow, needRows - 1);
  // 每行顶部（内容坐标系）累进，空行也占 MIN 高度 → 可落到任何空行
  const rowTop = [];
  let acc = 0;
  for (let r = 0; r <= maxRow; r++) {
    rowTop[r] = acc;
    acc += Math.max(MIN, byRow[r] || 0) + GAP;
  }
  const scrollTop = list.scrollTop || 0;
  const topBase = rect.top + 4 - scrollTop;  // 内容区顶（padding 4），行 0 的视口顶
  return { rect, nCols, rowTop, byRow, maxRow, MIN, GAP, topBase };
}

// 由鼠标位置推算目标网格格点：列按固定列宽；行按累计轨道高度映射（空行也可命中）
function _quickCellFromXY(x, y, geo) {
  let col = Math.floor((x - geo.rect.left) / (340 + 6));
  col = Math.max(0, Math.min(col, geo.nCols - 1));
  if (!geo.rowTop.length) return {row: 0, col};
  const yc = y - geo.topBase;
  const lastBottom = geo.rowTop[geo.maxRow] + Math.max(geo.MIN, geo.byRow[geo.maxRow] || 0);
  if (yc >= lastBottom) return {row: geo.maxRow + 1, col};
  for (let r = 0; r <= geo.maxRow; r++) {
    if (yc < geo.rowTop[r] + Math.max(geo.MIN, geo.byRow[r] || 0)) return {row: r, col};
  }
  return {row: geo.maxRow, col};
}

// 拖拽落点引导框：绝对定位覆盖在目标格上（不参与网格布局，避免拖动时重排），目标格未变化时跳过
function _quickGuideShow(row, col, mode) {
  const key = row + ":" + col + ":" + mode;
  if (_guideLast === key) return;
  _guideLast = key;
  const list = document.getElementById("quick_list");
  if (!list) return;
  let guide = list.querySelector(".quick-drop-guide");
  if (!guide) {
    guide = document.createElement("div");
    guide.className = "quick-drop-guide";
    list.appendChild(guide);
  }
  guide.style.position = "absolute";
  guide.textContent = mode === "swap" ? "↻ 交换位置" : "⇩ 释放放置";
  const geo = _quickDragGeo;
  if (geo) {
    const pad = 4, colW = 340, gap = 6;
    let top = geo.rowTop[row];
    if (top == null) top = (geo.rowTop[geo.maxRow] || 0) + Math.max(geo.MIN, geo.byRow[geo.maxRow] || 0) + geo.GAP + (row - geo.maxRow - 1) * (geo.MIN + geo.GAP);
    guide.style.left = (pad + col * (colW + gap)) + "px";
    guide.style.top = (pad + top) + "px";
    guide.style.width = colW + "px";
    guide.style.height = (Math.max(geo.MIN, geo.byRow[row] || 0)) + "px";
  }
}
function _quickGuideHide() {
  _guideLast = null;
  const g = document.querySelector("#quick_list .quick-drop-guide");
  if (g) g.remove();
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
  let _itemDrag = null;
  let _groupDrag = null;

  // 分组卡片：保留 OS 文件 drop 目标；分组换位置用指针自绘拖拽（绕开 HTML5 拖放）
  list.querySelectorAll(".quick-group").forEach(card => {
    const gi = Number(card.dataset.gi);
    card.addEventListener("dragover", e => {
      const hasFiles = e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.indexOf("Files") >= 0;
      if (hasFiles && !_groupDrag) { e.preventDefault(); card.classList.add("drag-over"); }
    });
    card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
    card.addEventListener("drop", e => {
      card.classList.remove("drag-over");
      const hasFiles = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0;
      if (!hasFiles) return;
      e.preventDefault();
      const targetGi = gi;
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

    // 指针拖拽（换位置）：按住标题栏 → 浮层跟随 → 松开落子
    card.addEventListener("pointerdown", e => {
      if (e.button !== 0) return;
      if (_quickRenaming) return;
      if (e.target.closest("[data-act]") || e.target.closest("input")) return;
      if (e.target.closest(".quick-item")) return;  // 条目排序走 HTML5 拖拽
      _startGroupPointerDrag(e, card, gi, list);
    });
  });

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

  // 容器空白区：仅拦截 OS 文件拖放（分组落子已由指针拖拽处理）
  list.addEventListener("dragover", e => {
    if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.indexOf("Files") >= 0) e.preventDefault();
  });
  list.addEventListener("drop", e => {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) e.preventDefault();
  });
}
