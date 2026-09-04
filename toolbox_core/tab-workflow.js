// 点击更新后锁定按钮：直到后端确认「所有 SVN 更新弹窗都已弹出」才返回（不再用固定时间冷却），
// 真正的「正在更新」由后端锁检测兜底
let _wfUpdateBusy = new Set();
let _wfSvnPollTimer = null;
let _wfRenaming = false;
let _wfGroupExpanded = new Set();

// ── 工作流分组数据层：每个工作流有稳定 _id；分组 wf_groups 只存 id 列表（归类视图，不复制工作流）──
function _wfEnsureIds() {
  config.workflows = config.workflows || [];
  config.wf_groups = config.wf_groups || [];
  config.wf_top_order = config.wf_top_order || [];
  let n = 0, gn = 0;
  config.workflows.forEach(wf => { if (!wf._id) { wf._id = "wf_" + Date.now().toString(36) + "_" + (++n); } });
  config.wf_groups.forEach(g => { if (!g._id) { g._id = "wg_" + Date.now().toString(36) + "_" + (++gn); } });
  // 清理分组中失效/重复的 id，并保证同一工作流只属于一个分组
  const ids = new Set(config.workflows.map(w => w._id));
  config.wf_groups.forEach(g => { g.workflows = (g.workflows || []).filter(id => ids.has(id)); });
  const seen = new Set();
  config.wf_groups.forEach(g => { g.workflows = (g.workflows || []).filter(id => { if (seen.has(id)) return false; seen.add(id); return true; }); });
  // wf_top_order：缺失时按「分组顺序 + 未分组工作流」推导；否则清理失效项
  if (!config.wf_top_order.length) {
    const inGroup = new Set();
    config.wf_groups.forEach(g => (g.workflows || []).forEach(id => inGroup.add(id)));
    const to = [];
    config.wf_groups.forEach(g => to.push({t:"g", id:g._id}));
    config.workflows.forEach(w => { if (!inGroup.has(w._id)) to.push({t:"w", id:w._id}); });
    config.wf_top_order = to;
  } else {
    const gids = new Set(config.wf_groups.map(g => g._id));
    const wids = new Set(config.workflows.map(w => w._id));
    config.wf_top_order = config.wf_top_order.filter(it => (it.t === "g" ? gids.has(it.id) : wids.has(it.id)));
  }
}
function _wfById(id) { return config.workflows.find(w => w._id === id) || null; }
function _wfGroupOf(id) {
  const gi = config.wf_groups.findIndex(g => (g.workflows || []).indexOf(id) >= 0);
  return gi >= 0 ? config.wf_groups[gi] : null;
}
// 拖拽后从 DOM 重建 config.workflows（顺序）+ wf_groups（分组 id 列表），并重设各工作流 data-idx，保证功能不错位
function _wfSyncFromDom() {
  const byId = {}; (config.workflows || []).forEach(w => { if (w._id) byId[w._id] = w; });
  const seen = new Set();
  const order = [];
  document.querySelectorAll("#wf_tree > .wf-parent").forEach(p => {
    const id = p.dataset.wid; if (byId[id] && !seen.has(id)) { order.push(byId[id]); seen.add(id); }
  });
  document.querySelectorAll("#wf_tree > .wf-group").forEach(gEl => {
    gEl.querySelectorAll(".wf-group-children > .wf-parent").forEach(p => {
      const id = p.dataset.wid; if (byId[id] && !seen.has(id)) { order.push(byId[id]); seen.add(id); }
    });
  });
  (config.workflows || []).forEach(w => { if (w._id && !seen.has(w._id)) { order.push(w); seen.add(w._id); } });
  config.workflows = order;
  const ng = [];
  document.querySelectorAll("#wf_tree > .wf-group").forEach(gEl => {
    const gidx = Number(gEl.dataset.gidx);
    const g = (config.wf_groups && config.wf_groups[gidx]) || { name: "新分组" };
    const wids = [...gEl.querySelectorAll(".wf-group-children > .wf-parent")].map(p => p.dataset.wid).filter(id => byId[id]);
    ng.push({ name: g.name, workflows: wids });
  });
  config.wf_groups = ng;
  document.querySelectorAll("#wf_tree .wf-parent").forEach(p => {
    const idx = config.workflows.findIndex(w => w._id === p.dataset.wid);
    p.dataset.idx = idx;
    const dot = p.querySelector(".wf-status-dot"); if (dot) dot.dataset.idx = idx;
  });
  // 重设分组 data-gidx，保证下次拖拽时索引与 config.wf_groups 对齐
  document.querySelectorAll("#wf_tree > .wf-group").forEach((gEl, i) => { gEl.dataset.gidx = i; });
  // 顶层混合顺序（分组 + 未分组工作流交错）
  const topOrder = [];
  document.querySelectorAll("#wf_tree > .wf-group, #wf_tree > .wf-parent").forEach(el => {
    if (el.classList.contains("wf-group")) {
      const gid = el.getAttribute("data-gid");
      if (gid) topOrder.push({t:"g", id:gid});
    } else {
      topOrder.push({t:"w", id:el.dataset.wid});
    }
  });
  if (topOrder.length) config.wf_top_order = topOrder;
  saveConfig({ workflows: config.workflows, wf_groups: config.wf_groups, wf_top_order: config.wf_top_order });
}

function buildWorkflowTab(panel) {
  _wfEnsureIds();
  const wfs = config.workflows || [];
  const wfGroups = config.wf_groups || [];
  const typeCn = {export_text:"导出文字表",export_modified_config:"导出修改配置表",merge_table:"合并文字表",merge_translation:"合并翻译",export_error_code:"导出错误码",unlock_svn:"解锁SVN",open_tables:"打开表格",revert_svn:"SVN回退",copy_files:"整合文字表",merge_error_code:"整合错误码",consolidate:"快速整合",merge_specified_text:"指定合并文字表",merge_config:"合并配置",error_code_entry:"录入错误码"};
  const typeIcon = {export_text:"📄",export_modified_config:"📝",merge_table:"🔗",merge_translation:"🌐",export_error_code:"⚠",unlock_svn:"🔓",open_tables:"📂",revert_svn:"↩",copy_files:"📦",merge_error_code:"🧩",consolidate:"⚡",merge_specified_text:"📑",merge_config:"🔧",error_code_entry:"📥"};
  const _wfCard = (wf, idx) => `
            <div class="wf-parent" data-idx="${idx}" data-wid="${wf._id}">
              <div class="wf-parent-header">
                <span class="wf-arrow">▶</span>
                <span class="wf-parent-name">${escapeHtml(wf.name)}<span class="wf-edit-icon"><svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 1.5L10.5 3.5"/><path d="M2 10L3.5 6.5L8.5 1.5L10.5 3.5L5.5 8.5L2 10Z"/></svg></span></span>
                <span class="wf-status-dot" data-idx="${idx}"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green,#4caf50);margin:0 4px"></span></span>
                <button class="wf-update-btn" title="更新SVN工作副本"><svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M2 7a5 5 0 019.9-1"/><path d="M12 7a5 5 0 01-9.9 1"/><path d="M12 2v4h-4"/><path d="M2 12V8h4"/></svg></button>
                <button class="wf-copy-btn" title="复制工作流"><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="3.5" y="1.5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.2"/><path d="M10 4H11V11.5C11 12.328 10.328 13 9.5 13H3.5C2.672 13 2 12.328 2 11.5V5C2 4.172 2.672 3.5 3.5 3.5H4" stroke="currentColor" stroke-width="1.2"/></svg></button>
              </div>
              <button class="wf-del-btn" title="删除工作流">✕</button>
              <div class="wf-children">
                ${(wf.steps||[]).filter(Boolean).map((s, j) => `
                  <div class="wf-child" data-step="${j}">
                    <span class="wf-child-type ${s.type}"><span class="wf-type-ico">${typeIcon[s.type]||''}</span>${typeCn[s.type]||s.type}</span>
                    <span class="wf-child-name" title="双击修改名称">${escapeHtml(s.type === "unlock_svn" ? (_wfAutoName(s) || s.name) : (!s.custom_name && _wfAutoName(s) || s.name))}</span>
                    ${s.type === 'open_tables' ? '<button class="wf-step-open-btn" title="打开（不锁定SVN）">' + _WF_ICONS.open + '</button>' : ''}
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
            </div>`;
  const renderGroup = (g, gi) => {
    const gIds = (g.workflows || []).filter(id => _wfById(id));
    const gWfs = gIds.map(id => { const idx = config.workflows.findIndex(w => w._id === id); return idx >= 0 ? _wfCard(config.workflows[idx], idx) : ""; }).join("");
    return `<div class="wf-group" data-gidx="${gi}" data-gid="${g._id}">
      <div class="wf-group-header" data-gidx="${gi}">
        <span class="wf-group-arrow">${_wfGroupExpanded.has(gi) ? "▼" : "▶"}</span>
        <span class="wf-group-name" title="拖拽调整分组顺序">${escapeHtml(g.name)}</span>
        <span class="wf-group-acts">
          <button class="qk-s-btn" data-act="rename-group" title="重命名分组">✎</button>
          <button class="qk-s-btn" data-act="del-group" title="删除分组">✕</button>
        </span>
      </div>
      <div class="wf-group-children" ${_wfGroupExpanded.has(gi) ? "" : 'style="display:none"'}>${gWfs || '<div class="wf-group-empty">拖入工作流</div>'}</div>
    </div>`;
  };
  const inWfGroups = new Set();
  wfGroups.forEach(g => (g.workflows || []).forEach(id => inWfGroups.add(id)));
  let treeContent = "";
  if (config.wf_top_order && config.wf_top_order.length) {
    treeContent = config.wf_top_order.map(it => {
      if (it.t === "g") { const gi = wfGroups.findIndex(g => g._id === it.id); return gi >= 0 ? renderGroup(wfGroups[gi], gi) : ""; }
      const idx = config.workflows.findIndex(w => w._id === it.id);
      return idx >= 0 ? _wfCard(config.workflows[idx], idx) : "";
    }).join("");
  } else {
    treeContent = wfGroups.map((g, gi) => renderGroup(g, gi)).join("") +
      config.workflows.map((w, i) => ({w, i})).filter(({w}) => !inWfGroups.has(w._id)).map(({w, i}) => _wfCard(w, i)).join("");
  }
  const isEmpty = !wfs.length && !wfGroups.length;
  panel.innerHTML = `
    <div class="wf-layout">
      <div class="card">
        <div class="card-title">工作流列表</div>
        <div class="wf-tree" id="wf_tree">
          ${isEmpty ? '<div class="empty-state" style="padding:32px 16px;color:var(--dim)">暂无工作流，点击"新建"创建</div>' : treeContent}
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
      if (e.target.closest(".wf-copy-btn,.wf-update-btn")) return;
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
    const updateBtn = el.querySelector(".wf-update-btn");
    updateBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const wfIdx = Number(el.dataset.idx);
      const wf = config.workflows[wfIdx];
      if (!wf || !wf.steps) return;
      // 后端确认「所有更新弹窗已弹出」前不允许再点（避免弹窗没出/更新前连点导致锁死）
      if (_wfUpdateBusy.has(wfIdx)) {
        _showToast("该工作流正在更新中，请勿重复点击，以免 SVN 锁死");
        return;
      }
      const prefixes = _wfDetectPrefixes(wf.steps);
      if (!prefixes.length) { _showToast("未检测到需更新的路径前缀"); return; }
      _wfUpdateBusy.add(wfIdx);
      updateBtn.classList.add("wf-updating");
      const logContainer = document.getElementById("wf_log");
      logContainer.querySelectorAll(".wf-log-section").forEach(sec => {
        const bodyEl = sec.querySelector(".wf-log-body");
        if (bodyEl?.id) {
          let done = false;
          let m = bodyEl.id.match(/^wf_log_step_(\d+)_(\d+)_/);
          if (m) { done = !_wfPlayState["step_" + m[1] + "_" + m[2]]; }
          else {
            m = bodyEl.id.match(/^wf_log_update_(\d+)_/);
            if (m) { done = true; }
          }
          if (done) sec.remove();
        }
      });
      const bodyId = "wf_log_update_" + wfIdx + "_" + Date.now();
      const section = document.createElement("div");
      section.className = "wf-log-section";
      section.innerHTML = `<div class="wf-log-section-header">${escapeHtml(wf.name)} > SVN 工作副本更新</div><div class="wf-log-body" id="${bodyId}"><div class="log-anchor"></div></div>`;
      logContainer.appendChild(section);
      section.scrollIntoView({behavior:"smooth", block:"nearest"});
      const bodyEl = document.getElementById(bodyId);
      try {
        const r = await fetch("/api/workflow/open-update-wc", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prefixes, name: wf.name})});
        const d = await r.json();
        if (d.error) {
          bodyEl.innerHTML = '<div class="error">❌ '+escapeHtml(d.error)+'</div>';
          _showToast(d.error);
          _wfUpdateBusy.delete(wfIdx);
          updateBtn.classList.remove("wf-updating");
          return;
        }
        (d.cleaned || []).forEach(path => {
          const div = document.createElement("div");
          div.textContent = "已自动清理被锁的 SVN 工作副本: " + path;
          _logAppend(bodyEl, div);
        });
        d.opened.forEach(path => {
          const div = document.createElement("div");
          div.textContent = "已打开 TortoiseSVN 更新窗口: " + path;
          _logAppend(bodyEl, div);
        });
        (d.skipped_updating || []).forEach(path => {
          const div = document.createElement("div");
          div.textContent = "该目录正在更新，已跳过: " + path;
          _logAppend(bodyEl, div);
        });
        (d.missing || []).forEach(path => {
          const div = document.createElement("div");
          div.textContent = "跳过不存在目录: " + path;
          _logAppend(bodyEl, div);
        });
      } catch(err) {
        bodyEl.innerHTML = '<div class="error">❌ 请求失败: '+escapeHtml(err.message)+'</div>';
        _showToast("请求失败：" + err.message);
      } finally {
        _wfUpdateBusy.delete(wfIdx);
        updateBtn.classList.remove("wf-updating");
      }
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
          // 挂起新步骤：不写入配置，弹窗点「保存」才创建；取消则丢弃
          _wfModalOpen(wfIdx, -1, step);
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
      _wfRenaming = true;
      _wfSetDragDisabled(true);
      const input = document.createElement("input");
      input.className = "wf-name-input";
      input.placeholder = "输入工作流名称";
      input.value = currentName;
      nameSpan.textContent = "";
      nameSpan.appendChild(input);
      input.focus();
      input.select();
      let finished = false;
      const finish = (save) => {
        if (finished) return;
        finished = true;
        _wfRenaming = false;
        _wfSetDragDisabled(false);
        const val = input.value.trim();
        if (save && !val) _showToast("工作流名称不能为空");
        if (save && val && config.workflows[wfIdx]) {
          config.workflows[wfIdx].name = val;
          saveConfig({workflows:config.workflows});
        }
        if (config.workflows[wfIdx]) {
          nameSpan.innerHTML = `${escapeHtml(config.workflows[wfIdx].name)}<span class="wf-edit-icon"><svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 1.5L10.5 3.5"/><path d="M2 10L3.5 6.5L8.5 1.5L10.5 3.5L5.5 8.5L2 10Z"/></svg></span>`;
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

  function _wfStepValidation(step) {
    const required = {
      export_text:["input_file"],
      export_modified_config:["source_path"],
      upload_svn:["dirs"],
      merge_table:["input_dir","target_dir"],
      merge_translation:["input_file","original_file"],
      export_error_code:["root_dir","lang_codes"],
      lock_svn:["target_path"],
      unlock_svn:["target_path"],
      open_tables:["file_paths"],
      revert_svn:["revert_paths"],
      copy_files:["src_dir","tgt_dir"],
      merge_error_code:["src_path","tgt_path"],
      consolidate:["src_dir","tgt_dir","commit_dir"],
      merge_specified_text:["src_path","tgt_path","commit_dir"],
      merge_config:["src_path","tgt_path"],
      error_code_entry:["translation_file","target_path"]
    };
    const labels = {
      input_file:"输入文件", source_path:"本地 SVN 副本路径", upload_svn_dir:"上传 SVN 路径",
      dirs:"源目录", input_dir:"输入文件", target_dir:"输出文件", original_file:"目标文件",
      root_dir:"根目录", lang_codes:"语言代码", target_path:"目标文件路径", file_paths:"文件路径",
      revert_paths:"回退路径", src_dir:"源目录", tgt_dir:"目标目录", src_path:"源路径", tgt_path:"目标路径",
      commit_dir:"提交路径",
      translation_file:"翻译文件",target_path:"目标路径"
    };
    for (const key of required[step.type] || []) {
      const value = step[key];
      const empty = Array.isArray(value) ? !value.length : !String(value || "").trim();
      if (empty) return {key, message:"请填写" + (labels[key] || key)};
    }
    if (step.type === "merge_table") {
      const titleRows = Number(step.title_rows);
      if (!Number.isInteger(titleRows) || titleRows < 1) return {key:"title_rows", message:"标题行必须是大于等于 1 的整数"};
      const idCol = Number(step.id_col);
      if (!Number.isInteger(idCol) || idCol < 1) return {key:"id_col", message:"ID 列必须是大于等于 1 的整数"};
    }
    return null;
  }

  function _wfModalDoSave() {
    if (_wfSaving) return;
    const ctx = _modalCtx || (overlay.dataset.modalCtx ? JSON.parse(overlay.dataset.modalCtx) : null);
    if (!ctx) return;
    _wfSaving = true;
    const wfIdx = ctx.wfIdx;
    let baseStep;
    if (ctx.isNew) {
      // 新增：从挂起的 newStep 开始，点保存才真正创建
      baseStep = Object.assign({}, ctx.newStep || {});
    } else {
      baseStep = config.workflows[wfIdx]?.steps?.[ctx.stepIdx];
      if (!baseStep) { _wfSaving = false; return; }
    }
    const nextStep = Object.assign({}, baseStep);
    modalBody.querySelectorAll(".wf-modal-input").forEach(inp => {
      const key = inp.dataset.key;
      if (!key) return;
      const arrKeys = ["tools","dirs","file_paths","update_dirs","exclude_paths","upload_svn_dir","revert_paths","commit_dir"];
      if (arrKeys.includes(key)) {
        nextStep[key] = inp.value.split(",").map(s => s.trim()).filter(Boolean);
      } else {
        nextStep[key] = inp.value;
      }
    });
    modalBody.querySelectorAll("input[type=checkbox][data-key]").forEach(inp => {
      nextStep[inp.dataset.key] = inp.checked;
    });
    const validation = _wfStepValidation(nextStep);
    if (validation) {
      _wfSaving = false;
      _showToast(validation.message);
      modalBody.querySelector(`[data-key="${validation.key}"]`)?.focus();
      return;
    }
    let step, stepIdx;
    if (ctx.isNew) {
      config.workflows[wfIdx].steps.push(nextStep);
      step = nextStep;
      stepIdx = config.workflows[wfIdx].steps.length - 1;
    } else {
      Object.assign(baseStep, nextStep);
      step = baseStep;
      stepIdx = ctx.stepIdx;
    }
    const autoName = _wfAutoName(step);
    const _forceAutoName = ["export_error_code", "error_code_entry", "unlock_svn"].includes(step.type);
    if (autoName && (!step.custom_name || _forceAutoName)) step.name = autoName;
    saveConfig({workflows:config.workflows});
    overlay.classList.remove("show");
    _modalCtx = null;
    _wfSaving = false;
    if (ctx.isNew) {
      // 新建后重建树并展开父级，让新步骤显示出来
      _wfRebuild();
      const parentEl = document.querySelector(`.wf-parent[data-idx="${wfIdx}"]`);
      if (parentEl) {
        document.querySelectorAll(".wf-parent.expanded").forEach(p => p.classList.remove("expanded"));
        parentEl.classList.add("expanded");
      }
      _showToast("步骤设置已保存");
      return;
    }
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
      const arrKeys = ["tools","dirs","file_paths","update_dirs","exclude_paths","upload_svn_dir","revert_paths","commit_dir"];
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
    const _forceAutoName = ["export_error_code", "error_code_entry", "unlock_svn"].includes(step.type);
    if (autoName && (!step.custom_name || _forceAutoName)) step.name = autoName;
    saveConfig({workflows:config.workflows});
    _wfSaving = false;
    const childEl = document.querySelector(`.wf-parent[data-idx="${wfIdx}"] .wf-child[data-step="${stepIdx}"] .wf-child-name`);
    if (childEl) childEl.textContent = step.name;
  }
  window._wfModalAutoSave = _wfModalAutoSave;

  function _wfClearOneTimeFlag(wfIdx, stepIdx) {
    // revert_svn 的「删除未版本控制文件」为单次生效：执行过后清掉勾选，
    // 同步内存与配置，保证设置显示/重启后均为未勾选
    const st = config.workflows?.[wfIdx]?.steps?.[stepIdx];
    if (st && st.type === "revert_svn" && st.delete_unversioned) {
      st.delete_unversioned = false;
      saveConfig({workflows: config.workflows});
    }
  }

  function _wfModalFields(type, step) {
    const v = (key) => escapeHtml(Array.isArray(step[key]) ? step[key].join(", ") : step[key]||"");
    const _fb = (label, dataKey, id, browseType, append, placeholder) => `
      <div class="form-group"><label>${label}</label>
        <div class="flex-row"><input type="text" class="wf-modal-input" id="${id}" data-key="${dataKey}" data-browse="${browseType}" value="${v(dataKey)}" style="flex:1" ${append?'data-append="1"':''} placeholder="${escapeHtml(placeholder || (browseType==='dir'?'输入本地目录路径':'输入文件路径'))}">
        <button class="btn btn-normal btn-sm" onclick="(function(t,i,a){if(a){_browseDirAppend(i)}else{var v=document.getElementById(i).value.trim(),d=v.substring(0,v.lastIndexOf('\\\\'));if(!d)d=v;if(t==='file')browseFile(i,d||'');else browseDir(i,null,d||'');}})('${browseType.replace(/'/g,"\\'")}','${id}',${!!append})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button></div></div>`;
    const m = {
      export_text: `
        ${_fb("主文件路径","input_file","wf_m_input_file","file",false,"输入要导出的 Excel 文件路径")}
        <div class="form-group"><label>上传到（自动匹配 gameData + StreamingAssets）</label><div class="flex-row"><input type="text" class="wf-modal-input" readonly id="wf_m_svn_match_export_text" placeholder="输入主路径后自动匹配"></div></div>`,
      export_modified_config: `
        ${_fb("本地SVN副本路径","source_path","wf_m_source_path","dir",false,"输入本地 SVN 工作副本路径")}
        <div class="form-group"><label>上传到（自动匹配 gameData + StreamingAssets）</label><div class="flex-row"><input type="text" class="wf-modal-input" readonly id="wf_m_svn_match_export_modified_config" placeholder="输入主路径后自动匹配"></div></div>`,
      upload_svn: `
        <div class="form-group"><label>源目录（逗号分隔）</label><input type="text" class="wf-modal-input" id="wf_m_dirs" data-key="dirs" value="${v("dirs")}" placeholder="输入待上传的本地目录，多个用逗号分隔"></div>`,
      merge_table: `
        ${_fb("输入文件","input_dir","wf_m_input_dir","file",false,"输入要合并的 Excel 文件路径")}
        ${_fb("输出文件","target_dir","wf_m_target_dir","file",false,"输入合并后的输出文件路径")}
        <div class="form-group"><label>标题行</label><input type="number" class="wf-modal-input" id="wf_m_title_rows" data-key="title_rows" value="${v("title_rows")||"1"}" placeholder="表头占几行，正整数" min="1" step="1"></div>
        <div class="form-group"><label>ID列</label><input type="number" class="wf-modal-input" id="wf_m_id_col" data-key="id_col" value="${v("id_col")||"1"}" placeholder="ID 列是第几列，从 1 开始" min="1" step="1"></div>`,
      merge_translation: `
        ${_fb("翻译文件","input_file","wf_m_tr_input","file",false,"输入已翻译完成的 Excel 文件")}
        ${_fb("目标文件","original_file","wf_m_orig_file","file",false,"输入要合入翻译的目标文件")}`,
      export_error_code: `
        ${_fb("根目录","root_dir","wf_m_root_dir","dir",false,"输入错误码文件所在的根目录")}
        <input type="hidden" class="wf-modal-input" id="wf_m_ec_lang" data-key="lang_codes" value="${v("lang_codes")}">
        <div class="form-group"><label>语言（自动扫描根目录 Language 子目录，勾选导出）</label><div id="wf_lang_list_ec" class="wf-lang-list"></div></div>
        <div class="form-group"><label>上传到（自动匹配 gameData + StreamingAssets）</label><div class="flex-row"><input type="text" class="wf-modal-input" readonly id="wf_m_svn_match_export_error_code" placeholder="输入主路径后自动匹配"></div></div>`,
      lock_svn: `
        ${_fb("目标文件路径","target_path","wf_m_target_path","file",false,"输入要锁定的文件路径")}
        <div class="form-group"><label>更新目录（逗号分隔）</label><input type="text" class="wf-modal-input" id="wf_m_update_dirs" data-key="update_dirs" value="${v("update_dirs")}" placeholder="锁定前先更新的目录，多个用逗号分隔"></div>
        <div class="form-group"><label>锁定消息</label><input type="text" class="wf-modal-input" id="wf_m_lock_msg" data-key="lock_msg" value="${v("lock_msg")}" placeholder="输入 SVN 锁定的说明信息"></div>`,
      unlock_svn: `
        ${_fb("目标路径（逗号分隔）","target_path","wf_m_target_path","file",true,"输入要解锁的文件或文件夹路径，多个用逗号分隔；文件夹将解锁其中本人锁定的全部文件")}`,
      open_tables: `
        <div class="form-group"><label>文件路径（逗号分隔）</label>
          <div class="flex-row"><input type="text" class="wf-modal-input" id="wf_m_file_paths" data-key="file_paths" value="${v("file_paths")}" style="flex:1" placeholder="输入要打开的 Excel 文件路径，多个用逗号分隔">
          <button class="btn btn-normal btn-sm" onclick="_browseFileAppend('wf_m_file_paths')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button></div></div>`,
      revert_svn: `
        <div class="form-group"><label>回退路径（逗号分隔）</label>
          <div class="flex-row"><input type="text" class="wf-modal-input" id="wf_m_rv_paths" data-key="revert_paths" value="${v("revert_paths")}" style="flex:1" placeholder="输入要回退的目录或文件路径，多个用逗号分隔">
          <button class="btn btn-normal btn-sm" onclick="browseDir('wf_m_rv_paths',null,null,true)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button></div></div>
        <div class="form-group"><label>排除路径（逗号分隔）</label>
          <input type="text" class="wf-modal-input" id="wf_m_rv_exclude" data-key="exclude_paths" value="${v("exclude_paths")}" placeholder="输入不参与回退的路径，多个用逗号分隔">
        </div>
        <label class="wf-rv-check"><input type="checkbox" data-key="delete_unversioned" ${step.delete_unversioned?'checked':''}> 永久删除未版本控制的文件</label>`,
      copy_files: `
        ${_fb("源目录","src_dir","wf_m_cf_src","dir",false,"输入源文件所在目录")}
        ${_fb("目标目录","tgt_dir","wf_m_cf_tgt","dir",false,"输入要复制到的目标目录")}`,
      merge_error_code: `
        ${_fb("源路径","src_path","wf_m_mec_src","dir",false,"输入错误码源文件所在目录")}
        ${_fb("目标路径","tgt_path","wf_m_mec_tgt","dir",false,"输入要合入到的目标目录")}
        <input type="hidden" class="wf-modal-input" id="wf_m_mec_lang" data-key="lang_codes" value="${v("lang_codes")}">
        <div class="form-group"><label>语言（自动扫描源路径 Language 子目录，勾选合并）</label><div id="wf_lang_list_mec" class="wf-lang-list"></div></div>`,
      consolidate: `
        ${_fb("来源路径（逗号分隔）","src_dir","wf_m_co_src","dir",true,"输入文件来源目录，多个用逗号分隔")}
        ${_fb("目标路径","tgt_dir","wf_m_co_tgt","dir",false,"输入 SVN 工作副本目标目录")}
        ${_fb("提交路径（逗号分隔）","commit_dir","wf_m_co_commit","dir",true,"输入 TortoiseSVN 提交的根路径，多个用逗号分隔")}
        <div class="form-group"><label>天数</label><input type="number" class="wf-modal-input" id="wf_m_co_days" data-key="days" min="1" value="${v("days") || 3}" placeholder="合并最近几天修改的文件（1=当天）"></div>
        <div class="form-group"><label>SVN提交作者（留空=不限）</label><input type="text" class="wf-modal-input" id="wf_m_co_author" data-key="author" value="${v("author") || ""}" placeholder="只复制指定作者提交的文件，多个用逗号分隔（或关系），留空则不限"></div>
        <div class="form-group"><label>SVN提交备注（留空=不限）</label><input type="text" class="wf-modal-input" id="wf_m_co_msg" data-key="commit_msg" value="${v("commit_msg") || ""}" placeholder="备注包含该关键词才复制，多个用逗号分隔，与提交作者为并（AND）关系"></div>`,
      merge_specified_text: `
        ${_fb("文字表来源路径","src_path","wf_m_mst_src","file",false,"输入来源文字表（SVN工作副本内的 Texts.xlsm 文件路径）")}
        ${_fb("目标文字表路径","tgt_path","wf_m_mst_tgt","file",false,"输入要合并到的目标文字表文件路径")}
        <div class="form-group"><label>SVN提交备注（包含匹配）</label><input type="text" class="wf-modal-input" id="wf_m_mst_msg" data-key="commit_msg" value="${v("commit_msg")}" placeholder="输入提交信息关键词，留空不限"></div>
        <div class="form-group"><label>SVN提交作者</label><input type="text" class="wf-modal-input" id="wf_m_mst_author" data-key="commit_author" value="${v("commit_author")}" placeholder="SVN提交者账户名，多个用逗号分隔，留空不限"></div>
        <div class="form-group"><label>自然日</label><input type="number" class="wf-modal-input" id="wf_m_mst_days" data-key="days" min="1" value="${v("days") || 3}" placeholder="合并距今几天内的提交（1=当天）"></div>
        ${_fb("提交路径（逗号分隔）","commit_dir","wf_m_mst_commit","dir",true,"输入 TortoiseSVN 提交的根路径，多个用逗号分隔")}`,
      merge_config: `
        ${_fb("来源配置表文件夹","src_path","wf_m_mc_src","dir",false,"输入来源配置表所在文件夹（SVN工作副本内）")}
        ${_fb("目标配置表文件夹","tgt_path","wf_m_mc_tgt","dir",false,"输入要合并到的目标配置表文件夹")}
        <div class="form-group"><label>SVN提交备注（包含匹配）</label><input type="text" class="wf-modal-input" id="wf_m_mc_msg" data-key="commit_msg" value="${v("commit_msg")}" placeholder="输入提交信息关键词，留空不限"></div>
        <div class="form-group"><label>SVN提交作者</label><input type="text" class="wf-modal-input" id="wf_m_mc_author" data-key="commit_author" value="${v("commit_author")}" placeholder="SVN提交者账户名，多个用逗号分隔，留空不限"></div>
        <div class="form-group"><label>自然日</label><input type="number" class="wf-modal-input" id="wf_m_mc_days" data-key="days" min="1" value="${v("days") || 3}" placeholder="合并距今几天内的提交（1=当天）"></div>
        <div class="form-group"><label>提交到（自动匹配 gameData + StreamingAssets）</label><div class="flex-row"><input type="text" class="wf-modal-input" readonly id="wf_m_svn_match_merge_config" placeholder="输入主路径后自动匹配"></div></div>`,
      error_code_entry: `
        ${_fb("翻译文件","translation_file","wf_m_ece_input","file",false,"输入包含错误码翻译的 Excel 文件路径")}
        ${_fb("目标路径","target_path","wf_m_ece_target","dir",false,"输入 gameData 所在目录（自动找 Language 子目录）")}
        <input type="hidden" class="wf-modal-input" id="wf_m_ece_lang" data-key="lang_codes" value="${v("lang_codes")}">
        <div class="form-group"><label>语言（自动扫描目标 Language 子目录，勾选导出）</label><div id="wf_lang_list_ece" class="wf-lang-list"></div></div>
        <div class="form-group"><label>上传到（自动匹配 gameData + StreamingAssets）</label><div class="flex-row"><input type="text" class="wf-modal-input" readonly id="wf_m_svn_match_error_code_entry" placeholder="输入主路径后自动匹配"></div></div>`,
    };
    return m[type] || '<div class="form-group"><span style="color:var(--dim)">无可用设置</span></div>';
  }

  function _wfHistoryKey(pool) {
    // 名称以 svn_ 开头的池直接对应 SVN记录页签共享历史（svn_author_history / svn_keyword_history）
    return pool.startsWith("svn_") ? pool : "_" + pool;
  }
  function _wfHistoryPool(key, browse, id) {
    // 快速整合/合并配置：作者/提交备注与 SVN记录页签共享历史
    if (["wf_m_co_author", "wf_m_mc_author"].includes(id)) return "svn_author_history";
    if (["wf_m_co_msg", "wf_m_mc_msg"].includes(id)) return "svn_keyword_history";
    // 4 池语义分类：目录路径 / 文件路径 / 提交信息 / 配置文本；数字等字段不设历史
    if (browse === "dir") return "wf_history_dirs";
    if (browse === "file") return "wf_history_files";
    if (["commit_msg", "commit_author", "author"].includes(key)) return "wf_history_commit";
    if (["lang_codes", "lock_msg", "sheet_name"].includes(key)) return "wf_history_config";
    if (["dirs", "update_dirs", "revert_paths", "exclude_paths", "src_dir", "tgt_dir",
         "root_dir", "source_path", "src_path", "tgt_path", "commit_dir", "upload_svn_dir"].includes(key)) return "wf_history_dirs";
    if (["file_paths", "input_file", "original_file", "target_path",
         "input_dir", "target_dir", "translation_file"].includes(key)) return "wf_history_files";
    return null; // days/title_rows/id_col 等无下拉历史
  }
  function _wfHistorySave(pool, val) {
    if (!val.trim()) return;
    const key = _wfHistoryKey(pool);
    const arr = config[key] || [];
    const updated = [val, ...arr.filter(v => v !== val)].slice(0, 30);
    config[key] = updated;
    saveConfig({[key]: updated});
  }
  function _wfHistoryShow(inp, pool) {
    const key = _wfHistoryKey(pool);
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

  function _wfMigrateLegacyHistory() {
    // 一次性：旧 3 池（paths/msgs/texts）→ 新 4 池（dirs/files/commit/config）
    if (config._wf_history_migrated) return;
    const dirs = [], files = [];
    (config._wf_history_paths || []).forEach(v => {
      if (/\.(xlsm|xlsx|xls|csv|txt|erl|bin|json)$/i.test((v || "").trim())) files.push(v);
      else dirs.push(v);
    });
    const cfg = {
      _wf_history_migrated: true,
      _wf_history_dirs: dirs,
      _wf_history_files: files,
      _wf_history_commit: [],
      _wf_history_config: (config._wf_history_msgs || []).slice(),
    };
    saveConfig(cfg);
    Object.assign(config, cfg);
    // 旧键不再使用，从内存中移除（配置文件残留无害）
    delete config._wf_history_paths;
    delete config._wf_history_msgs;
    delete config._wf_history_texts;
  }

  // 导出/录入错误码：按根目录/目标路径自动扫描 Language 子目录，渲染语言勾选列表，同步隐藏 lang_codes
  async function _wfLoadLangList(containerId, baseInputId, hiddenId) {
    const container = document.getElementById(containerId);
    const base = document.getElementById(baseInputId);
    const hidden = document.getElementById(hiddenId);
    if (!container || !base) return;
    const path = base.value.trim();
    const initCodes = (hidden && hidden.value) ? hidden.value.split(",").map(s => s.trim()).filter(Boolean) : [];
    if (!path) { container.innerHTML = '<div class="wf-lang-empty">请先填写上方路径</div>'; return; }
    container.innerHTML = '<div class="wf-lang-empty">扫描中…</div>';
    try {
      const r = await fetch("/api/workflow/scan-langs", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path})});
      const d = await r.json();
      if (d.error) { container.innerHTML = '<div class="wf-lang-empty">' + escapeHtml(d.error) + '</div>'; return; }
      const langs = d.langs || [];
      if (!langs.length) { container.innerHTML = '<div class="wf-lang-empty">未找到语言子目录</div>'; return; }
      const setHidden = () => {
        if (!hidden) return;
        const checked = [...container.querySelectorAll("input[type=checkbox]:checked")].map(cb => cb.value);
        hidden.value = checked.join(",");
      };
      container.innerHTML = langs.map(code =>
        `<label><input type="checkbox" value="${escapeHtml(code)}" ${initCodes.includes(code) ? 'checked' : ''}><span>${escapeHtml(code)}</span></label>`
      ).join("");
      container.querySelectorAll("input[type=checkbox]").forEach(cb => cb.addEventListener("change", () => {
        setHidden();
        // 勾选调整后自动刷新工作流名称（步骤名取自 lang_codes）；直接调用闭包内函数，避免全局引用时序问题
        _wfModalAutoSave();
      }));
      setHidden();
    } catch (_) {
      container.innerHTML = '<div class="wf-lang-empty">扫描失败</div>';
    }
  }

  function _wfModalAfterOpen() {
    _wfMigrateLegacyHistory();
    // 每次重取弹窗 body：_wfRebuild 会重建面板并 recrea te 弹窗，闭包捕获的引用可能已分离
    const _body = document.getElementById("wf_modal_body");
    if (!_body) return;
    _body.querySelectorAll("[id^=wf_m_]").forEach(inp => {
      if (inp.id) enablePathDrop(inp.id);
    });
    _body.querySelectorAll(".wf-modal-input").forEach(inp => {
      const key = inp.dataset.key;
      if (!key) return;
      const pool = _wfHistoryPool(key, inp.dataset.browse, inp.id);
      if (!pool) return; // 数字等字段无历史
      inp.addEventListener("focus", () => {
        _wfHistoryShow(inp, pool);
      });
      inp.addEventListener("blur", () => {
        setTimeout(() => { if (_wfHistoryDd && !_wfHistoryDd.matches(":hover")) { _wfHistoryDd.remove(); _wfHistoryDd = null; } }, 150);
        _wfHistorySave(pool, inp.value);
      });
    });
    let step = null;
    if (_modalCtx) {
      // 新增步骤挂起时从 newStep 取类型；已有步骤从配置取
      step = _modalCtx.isNew ? _modalCtx.newStep : config.workflows[_modalCtx.wfIdx]?.steps?.[_modalCtx.stepIdx];
    }
    // 隐藏手填上传路径后：按主路径自动匹配 gameData + StreamingAssets 只读展示
    const _WF_SVN_MATCH = {
      export_text: { src:"wf_m_input_file", out:"wf_m_svn_match_export_text" },
      export_modified_config: { src:"wf_m_source_path", out:"wf_m_svn_match_export_modified_config" },
      merge_config: { src:"wf_m_mc_tgt", out:"wf_m_svn_match_merge_config" },
      export_error_code: { src:"wf_m_root_dir", out:"wf_m_svn_match_export_error_code" },
      error_code_entry: { src:"wf_m_ece_target", out:"wf_m_svn_match_error_code_entry" },
    };
    const _wfUpdateSvnMatch = (stepType) => {
      const m = _WF_SVN_MATCH[stepType];
      if (!m) return;
      const inp = document.getElementById(m.src);
      const out = document.getElementById(m.out);
      if (!inp || !out) return;
      const p = inp.value.trim();
      if (!p) { out.value = ""; out.placeholder = "输入主路径后自动匹配"; return; }
      fetch("/api/workflow/resolve-svn-dirs?path=" + encodeURIComponent(p)).then(r=>r.json()).then(d=>{
        const parts = [];
        if (d.gamedata) parts.push(d.gamedata);
        if (d.streaming) parts.push(d.streaming);
        out.value = parts.join("；");
        out.placeholder = parts.length ? "" : "（后端执行时按主路径匹配）";
      }).catch(()=>{ out.value = ""; out.placeholder = "（解析失败）"; });
    };
    if (step) {
      _wfUpdateSvnMatch(step.type);
      const m = _WF_SVN_MATCH[step.type];
      if (m) {
        const inp = document.getElementById(m.src);
        if (inp) inp.addEventListener("input", () => _wfUpdateSvnMatch(step.type));
      }
    }
    // 导出错误码 / 录入错误码 / 整合错误码：语言改为勾选，自动扫描
    if (step && ["export_error_code", "error_code_entry", "merge_error_code"].includes(step.type)) {
      const cfg = step.type === "export_error_code"
        ? {base:"wf_m_root_dir", hidden:"wf_m_ec_lang", list:"wf_lang_list_ec"}
        : step.type === "error_code_entry"
        ? {base:"wf_m_ece_target", hidden:"wf_m_ece_lang", list:"wf_lang_list_ece"}
        : {base:"wf_m_mec_src", hidden:"wf_m_mec_lang", list:"wf_lang_list_mec"};
      const baseEl = document.getElementById(cfg.base);
      _wfLoadLangList(cfg.list, cfg.base, cfg.hidden);
      if (baseEl) baseEl.addEventListener("blur", () => _wfLoadLangList(cfg.list, cfg.base, cfg.hidden));
    }
    // 浏览/历史赋值不触发 input/change：轮询兜底检测主路径变化以刷新上传路径
    clearInterval(_wfSvnPollTimer);
    if (step) {
      const _mtype = step.type;
      const _m = _WF_SVN_MATCH[_mtype];
      const _src = _m ? document.getElementById(_m.src) : null;
      let _lastV = _src ? _src.value : "";
      _wfSvnPollTimer = setInterval(() => {
        if (!_src || !document.getElementById(_m.out)) { clearInterval(_wfSvnPollTimer); _wfSvnPollTimer = null; return; }
        if (_src.value !== _lastV) { _lastV = _src.value; _wfUpdateSvnMatch(_mtype); }
      }, 500);
    }
  }

  document.getElementById("wf_modal_close").addEventListener("click", () => { clearInterval(_wfSvnPollTimer); _wfSvnPollTimer = null; overlay.classList.remove("show"); _modalCtx = null; delete overlay.dataset.modalCtx; if (_wfHistoryDd) { _wfHistoryDd.remove(); _wfHistoryDd = null; } });
  document.getElementById("wf_modal_cancel").addEventListener("click", () => { clearInterval(_wfSvnPollTimer); _wfSvnPollTimer = null; overlay.classList.remove("show"); _modalCtx = null; delete overlay.dataset.modalCtx; if (_wfHistoryDd) { _wfHistoryDd.remove(); _wfHistoryDd = null; } });
  document.getElementById("wf_modal_save").addEventListener("click", _wfModalDoSave);

  panel.querySelectorAll("button,input").forEach(el => {
    el.addEventListener("mousedown", (e) => e.stopPropagation());
  });
  function _wfModalOpen(wfIdx, stepIdx, newStep) {
    const step = newStep || config.workflows[wfIdx]?.steps?.[stepIdx];
    if (!step) return;
    // 每次重取弹窗元素：_wfRebuild 会重建面板并 recrea te 弹窗，闭包捕获的引用可能已分离
    const _title = document.getElementById("wf_modal_title");
    const _body = document.getElementById("wf_modal_body");
    const _overlay = document.getElementById("wf_modal_overlay");
    if (!_title || !_body || !_overlay) return;
    _title.textContent = typeCn[step.type] || step.type;
    _body.innerHTML = _wfModalFields(step.type, step);
    if (newStep) {
      // 新增步骤：挂起（不写入配置），点保存才 push 创建；取消则丢弃
      _modalCtx = { wfIdx, stepIdx: -1, isNew: true, newStep };
      _overlay.dataset.modalCtx = JSON.stringify({ wfIdx, stepIdx: -1, isNew: true, newStep });
    } else {
      _modalCtx = { wfIdx, stepIdx };
      _overlay.dataset.modalCtx = JSON.stringify({ wfIdx, stepIdx });
    }
    _overlay.classList.add("show");
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
  panel.querySelectorAll(".wf-child-name").forEach(nameEl => {
    nameEl.addEventListener("dblclick", (e) => {
      e.stopPropagation();
      if (nameEl.querySelector("input")) return;
      const child = nameEl.closest(".wf-child");
      const parent = nameEl.closest(".wf-parent");
      if (!child || !parent) return;
      const wfIdx = Number(parent.dataset.idx);
      const stepIdx = [...parent.querySelector(".wf-children").children].indexOf(child);
      const step = config.workflows[wfIdx]?.steps?.[stepIdx];
      if (!step) return;
      const currentName = step.name || "";
      _wfRenaming = true;
      _wfSetDragDisabled(true);
      const input = document.createElement("input");
      input.className = "wf-name-input";
      input.placeholder = "输入步骤名称";
      input.value = currentName;
      nameEl.textContent = "";
      nameEl.appendChild(input);
      input.focus();
      input.select();
      let finished = false;
      const finish = (save) => {
        if (finished) return;
        finished = true;
        _wfRenaming = false;
        _wfSetDragDisabled(false);
        const val = input.value.trim();
        if (save && !val) _showToast("步骤名称不能为空");
        if (save && val && config.workflows[wfIdx]?.steps?.[stepIdx]) {
          const _st = config.workflows[wfIdx].steps[stepIdx];
          // unlock_svn 强制自动命名：改名输入无效，回退为自动名
          if (_st.type === "unlock_svn") {
            _st.name = _wfAutoName(_st) || val;
            _st.custom_name = false;
          } else {
            _st.name = val;
            _st.custom_name = true;
          }
          saveConfig({workflows:config.workflows});
        }
        const nextStep = config.workflows[wfIdx]?.steps?.[stepIdx];
        nameEl.textContent = nextStep?.name || currentName;
      };
      input.addEventListener("blur", () => finish(true));
      input.addEventListener("keydown", (ke) => {
        if (ke.key === "Enter") { ke.preventDefault(); input.blur(); }
        if (ke.key === "Escape") { ke.preventDefault(); finish(false); }
      });
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
      // 回退操作前弹窗确认，防止误回退丢失本地修改
      if (step.type === "revert_svn") {
        const paths = (Array.isArray(step.revert_paths) ? step.revert_paths : [step.revert_paths]).filter(Boolean);
        const ok = await showConfirm({
          title: "确认执行 SVN 回退",
          message: "SVN 回退会清除本地修改（含未提交内容），确定执行？" + (paths.length ? "\n\n路径:\n" + paths.join("\n") : "")
        });
        if (!ok) return;
      }
      const validation = _wfStepValidation(step);
      if (validation) { _showToast(validation.message); return; }
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
            m = bodyEl.id.match(/^wf_log_update_(\d+)_/);
            if (m) { done = !_wfPlayState["update_" + m[1]]; }
            else {
              m = bodyEl.id.match(/^wf_log_(\d+)_/);
              if (m) { done = !_wfPlayState[Number(m[1])]; }
            }
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
        _wfClearOneTimeFlag(wfIdx, stepIdx);
        _updateWfDot(wfIdx);
      });
    });
  });

  panel.querySelectorAll(".wf-step-open-btn").forEach(btn => {
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
      const stateKey = "open_" + wfIdx + "_" + stepIdx;
      const state = _wfPlayState[stateKey];
      if (state) {
        if (!(await showConfirm({title:"确认", message:"确定要结束打开操作吗？"}))) return;
        fetch("/api/task/cancel", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task_id: state.taskId})}).catch(()=>{});
        delete _wfPlayState[stateKey];
        btn.innerHTML = _WF_ICONS.open;
        btn.title = "打开（不锁定SVN）";
        return;
      }
      const validation = _wfStepValidation(step);
      if (validation) { _showToast(validation.message); return; }
      const wfName = config.workflows[wfIdx]?.name || "工作流";
      const logContainer = document.getElementById("wf_log");

      logContainer.querySelectorAll(".wf-log-section").forEach(sec => {
        const bodyEl = sec.querySelector(".wf-log-body");
        if (bodyEl?.id) {
          let done = false;
          let m = bodyEl.id.match(/^wf_log_step_(\d+)_(\d+)_/);
          if (m) { done = !_wfPlayState["step_" + m[1] + "_" + m[2]] && !_wfPlayState["open_" + m[1] + "_" + m[2]]; }
          else {
            m = bodyEl.id.match(/^wf_log_update_(\d+)_/);
            if (m) { done = !_wfPlayState["update_" + m[1]]; }
            else {
              m = bodyEl.id.match(/^wf_log_(\d+)_/);
              if (m) { done = !_wfPlayState[Number(m[1])]; }
            }
          }
          if (done) sec.remove();
        }
      });

      const bodyId = "wf_log_step_" + wfIdx + "_" + stepIdx + "_" + Date.now();
      const section = document.createElement("div");
      section.className = "wf-log-section";
      section.innerHTML = `<div class="wf-log-section-header">${escapeHtml(wfName)} > ${escapeHtml(step.name||"步骤"+(stepIdx+1))}（不锁定）</div><div class="wf-log-body" id="${bodyId}"></div>`;
      logContainer.appendChild(section);
      btn.innerHTML = _WF_ICONS.stop;
      btn.classList.add("stop");
      btn.title = "点击停止";
      _wfPlayState[stateKey] = {taskId: ""};
      _updateWfDot(wfIdx);
      runTask("/api/workflow/run", {wf_idx: wfIdx, step_indices: [stepIdx], skip_lock: true, _stateKey: stateKey}, null, bodyId, wfName, () => {
        if (_wfPlayState[stateKey]) {
          delete _wfPlayState[stateKey];
          btn.innerHTML = _WF_ICONS.open;
          btn.classList.remove("stop");
          btn.title = "打开（不锁定SVN）";
        }
        _wfClearOneTimeFlag(wfIdx, stepIdx);
        _updateWfDot(wfIdx);
      });
    });
  });

  const _wfSetDragDisabled = (v) => {
    (_wfSortables || []).forEach(s => { try { s.option("disabled", v); } catch(e){} });
  };

  const sortableOptions = {
    animation: 150,
    delay: 0,
    delayOnTouchOnly: false,
    touchStartThreshold: 5,
    ghostClass: "wf-dragging",
    chosenClass: "wf-drag-ghost",
    direction: "vertical",
    onMove() { return !_wfRenaming; },  // 修改名称期间禁止拖拽
  };

  _wfSortables = [];
  // 顶层 wf_tree：分组容器 + 未分组工作流排序；分组 children：工作流进出分组/组内排序（同 group 共享）
  const wfTree = document.getElementById("wf_tree");
  _wfSortables.push(Sortable.create(wfTree, {
    ...sortableOptions,
    group: "wf-groups",
    onEnd() { setTimeout(() => _wfSyncFromDom(), 0); },
  }));
  document.querySelectorAll("#wf_tree .wf-group-children").forEach((container) => {
    _wfSortables.push(Sortable.create(container, {
      ...sortableOptions,
      group: "wf-groups",
      filter: ".wf-group-empty",
      onAdd(evt) {
        if (evt.item.classList.contains("wf-group")) { wfTree.appendChild(evt.item); return; }  // 分组容器不能嵌套进分组
      },
      onEnd() { setTimeout(() => _wfSyncFromDom(), 0); },
    }));
  });
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

  // ── 分组管理：收缩 / 重命名 / 删除 ──
  const _wfGroupRename = (header, gi) => {
    const el = header.querySelector(".wf-group-name");
    const old = (config.wf_groups[gi] && config.wf_groups[gi].name) || "";
    _wfSetDragDisabled(true);
    const input = document.createElement("input");
    input.className = "wf-name-input";
    input.setAttribute("draggable", "false");
    input.addEventListener("dragstart", e => e.preventDefault());
    input.addEventListener("mousedown", e => e.stopPropagation());
    input.value = old;
    el.textContent = ""; el.appendChild(input); input.focus(); input.select();
    const finish = (save) => {
      _wfSetDragDisabled(false);
      const v = input.value.trim();
      if (save && v && config.wf_groups[gi]) { config.wf_groups[gi].name = v; saveConfig({workflows:config.workflows, wf_groups:config.wf_groups}); }
      _wfRebuild();
    };
    input.addEventListener("blur", () => finish(true));
    input.addEventListener("keydown", ke => { if (ke.key === "Enter") { ke.preventDefault(); input.blur(); } else if (ke.key === "Escape") input.blur(); });
  };
  panel.querySelectorAll(".wf-group-header").forEach(h => {
    if (h.querySelector(".wf-group-arrow")) h.querySelector(".wf-group-arrow").addEventListener("click", e => e.stopPropagation());
    h.addEventListener("click", e => {
      if (e.target.closest("[data-act]")) return;
      if (e.target.closest("input")) return;
      const gi = Number(h.dataset.gidx);
      const ch = h.nextElementSibling;
      if (!ch) return;
      const hidden = ch.style.display === "none";
      if (hidden) { ch.style.display = ""; _wfGroupExpanded.add(gi); h.querySelector(".wf-group-arrow").textContent = "▼"; }
      else { ch.style.display = "none"; _wfGroupExpanded.delete(gi); h.querySelector(".wf-group-arrow").textContent = "▶"; }
    });
  });
  panel.querySelectorAll("[data-act=rename-group]").forEach(btn => btn.addEventListener("click", e => {
    e.stopPropagation();
    const gi = Number(btn.closest(".wf-group-header").dataset.gidx);
    _wfGroupRename(btn.closest(".wf-group-header"), gi);
  }));
  panel.querySelectorAll("[data-act=del-group]").forEach(btn => btn.addEventListener("click", e => {
    e.stopPropagation();
    const gi = Number(btn.closest(".wf-group-header").dataset.gidx);
    const name = (config.wf_groups[gi] && config.wf_groups[gi].name) || "";
    showConfirm({title:"删除分组", message:`确定删除分组「${name}」？组内工作流将移回未分组。`, confirmText:"删除", danger:true}).then(ok => {
      if (ok) { config.wf_groups.splice(gi, 1); saveConfig({workflows:config.workflows, wf_groups:config.wf_groups}); _wfRebuild(); }
    });
  }));

  S.workflow.logEl = document.getElementById("wf_log");
}
function _wfDetectPrefixes(steps) {
  const prefixes = new Set();
  const SKIP_KEYS = new Set(["name","type","lock_msg","lang_codes","merge_mode"]);
  function walk(v) {
    if (typeof v === "string" && /^[A-Za-z]:\\/.test(v)) {
      // 逗号分隔的多值字段（如 src_dir/commit_dir）逐段匹配，避免把逗号吞进前缀
      v.split(",").forEach(part => {
        const s = part.trim();
        if (!s) return;
        const m = s.match(/^(.+?)\\(?:gameData|Client|tools)(?:\\|$)/i);
        if (m) prefixes.add(m[1]);
      });
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
    if (obj.includes(",")) {
      // 逗号分隔的多值路径字段（如 src_dir/tgt_dir）：逐段替换，保留前导空格
      return obj.split(",").map(part => {
        const lead = part.match(/^\s*/)[0];
        const s = part.trim();
        if (!s) return part;
        const r = (s === oldP || s.startsWith(oldP + "\\")) ? newP + s.substring(oldP.length) : s;
        return lead + r;
      }).join(",");
    }
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
  overlay.innerHTML = `<div class="wf-modal" style="max-width:640px">
    <div class="wf-modal-header"><h3>路径前缀替换</h3><button class="wf-modal-close" id="_pfx_close">✕</button></div>
    <div class="wf-modal-body" style="font-size:13px">
      <p style="color:var(--dim);margin-bottom:12px">检测到以下路径前缀，直接填写替换内容；或点击输入框弹出候选项目根下拉选择（留空则不替换该前缀）：</p>
      ${prefixes.map((p, i) => `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <code style="flex-shrink:0;background:rgba(255,255,255,.04);padding:4px 8px;border-radius:4px;font-size:12px">${escapeHtml(p)}</code>
        <span style="color:var(--dim)">→</span>
        <input class="_pfx_input" id="_pfx_${i}" data-old="${escapeHtml(p)}" type="text" autocomplete="off" placeholder="输入替换后的路径，留空不替换" style="flex:1;min-width:0;height:36px;padding:0 10px;border-radius:8px;border:1px solid #2a3040;background:#0e1219;color:#fff;font-size:13px">
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
  _wfFillPrefixCandidates(overlay);
}
// 复制工作流弹窗：把后台扫描到的项目根候选，挂到各输入框的点击下拉（与 SVN 地址输入框同款）
let _pfxCandidatesTimer = null;
function _wfFillPrefixCandidates(overlay) {
  clearInterval(_pfxCandidatesTimer);
  _pfxCandidatesTimer = null;
  const inputs = overlay.querySelectorAll("._pfx_input");
  if (!inputs.length) return;
  const setPlaceholder = (txt) => inputs.forEach(i => i.setAttribute("placeholder", txt));
  const applyResult = (d) => {
    if (d.status !== "done" && d.status !== "error") return false;
    const roots = (d.roots || []).slice();
    inputs.forEach(inp => {
      if (inp.id) initSuggest(inp.id, roots, true);
      if (document.activeElement === inp) _showSuggest(inp.id, true);
    });
    setPlaceholder("输入替换后的路径，留空不替换");
    return true;
  };
  setPlaceholder("后台扫描中，稍候点击输入框可下拉选择…");
  // 首次读取：若仍 idle（启动 POST 还没触发），先兜底触发一次扫描
  fetch("/api/workflow/scan-project-roots").then(r => r.json()).then(d => {
    if (applyResult(d)) return;
    if (d.status === "idle") {
      fetch("/api/workflow/scan-project-roots", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}).catch(() => {});
    }
    _pfxCandidatesTimer = setInterval(async () => {
      if (!document.body.contains(overlay)) { clearInterval(_pfxCandidatesTimer); _pfxCandidatesTimer = null; return; }
      try {
        const rr = await fetch("/api/workflow/scan-project-roots");
        const d2 = await rr.json();
        if (applyResult(d2)) { clearInterval(_pfxCandidatesTimer); _pfxCandidatesTimer = null; }
      } catch (_) {}
    }, 600);
  }).catch(() => {
    setPlaceholder("输入替换后的路径，留空不替换");
  });
}
function _wfRebuild() {
  _wfSortables.forEach(s => s.destroy());
  _wfSortables = [];
  const ep = document.querySelector("#wf_tree .wf-parent.expanded");
  _wfExpandedIdx = ep ? Number(ep.dataset.idx) : -1;
  buildWorkflowTab(S.workflow.panel);
}
function wfCreate() {
  const btn = document.querySelector('[data-action="wf-create"]');
  if (!btn) return;
  const pop = document.createElement("div");
  pop.className = "wf-create-menu";
  pop.innerHTML = `<div class="wf-create-opt" data-wfcreate="workflow">新建工作流</div><div class="wf-create-opt" data-wfcreate="group">新建分组</div>`;
  const r = btn.getBoundingClientRect();
  const pw = Math.max(120, r.width - 8);
  pop.style.position = "fixed";
  pop.style.top = (r.bottom + 4) + "px";
  pop.style.left = (r.left + (r.width - pw) / 2) + "px";
  pop.style.width = pw + "px";
  document.body.appendChild(pop);
  const close = () => pop.remove();
  const onDocClick = () => { close(); document.removeEventListener("click", onDocClick, true); };
  setTimeout(() => document.addEventListener("click", onDocClick, true), 0);
  pop.addEventListener("click", e => {
    e.stopPropagation();
    const b = e.target.closest("[data-wfcreate]");
    if (!b) return;
    close();
    document.removeEventListener("click", onDocClick, true);
    if (b.dataset.wfcreate === "workflow") _wfNewWorkflow();
    else _wfNewGroup();
  });
}
function _wfNewWorkflow() {
  config.workflows = config.workflows || [];
  config.workflows.push({name:"新工作流",steps:[]});
  saveConfig({workflows:config.workflows});
  _wfRebuild();
}
function _wfNewGroup() {
  config.wf_groups = config.wf_groups || [];
  config.wf_groups.push({name:"新分组", workflows:[]});
  saveConfig({workflows:config.workflows, wf_groups:config.wf_groups});
  _wfRebuild();
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
    const targets = String(step.target_path || "").split(",").map(s => s.trim()).filter(Boolean);
    const p = (targets[0] || "").replace(/[\/\\]$/, "");
    if (!p) return "";
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    const last = i >= 0 ? p.substring(i+1) : p;
    // 目标为文件（最后段含 .）→ 取所在文件夹名；否则取该文件夹名（最后段）
    if (last.includes(".")) {
      const dir = i >= 0 ? p.substring(0, i) : "";
      const j = Math.max(dir.lastIndexOf("\\"), dir.lastIndexOf("/"));
      return j >= 0 ? dir.substring(j+1) : dir;
    }
    return last;
  }
  if (t === "export_text") {
    const p = step.input_file || "";
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.substring(i+1) : p;
  }
  if (t === "export_modified_config") {
    const p = (step.source_path || "").replace(/[\\/]$/, "");
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
  if (t === "merge_error_code") {
    const p = (step.tgt_path || "").replace(/[\\/]$/, "");
    const parts = p.split(/[\\/]/);
    return parts.length >= 2 ? parts[1] : p;
  }
  if (t === "consolidate") {
    return step.tgt_dir || "";
  }
  if (t === "merge_specified_text") {
    const p = (step.tgt_path || "").replace(/[\\/]$/, "");
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.substring(i + 1) : p;
  }
  if (t === "merge_config") {
    const p = (step.tgt_path || "").replace(/[\\/]$/, "");
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.substring(i + 1) : p;
  }
  if (t === "error_code_entry") {
    return step.lang_codes || step.target_path || "";
  }
  return "";
}