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
                <button class="wf-update-btn" title="更新SVN工作副本"><svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M2 7a5 5 0 019.9-1"/><path d="M12 7a5 5 0 01-9.9 1"/><path d="M12 2v4h-4"/><path d="M2 12V8h4"/></svg></button>
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
      if (e.target.closest(".wf-parent-check,.wf-copy-btn,.wf-update-btn")) return;
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
    const updateBtn = el.querySelector(".wf-update-btn");
    updateBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const wfIdx = Number(el.dataset.idx);
      const wf = config.workflows[wfIdx];
      if (!wf || !wf.steps) return;
      const prefixes = _wfDetectPrefixes(wf.steps);
      if (!prefixes.length) { _showToast("未检测到需更新的路径前缀"); return; }
      const stateKey = "update_" + wfIdx;
      if (_wfPlayState[stateKey]) { _showToast("该工作流正在更新中"); return; }
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
      _wfPlayState[stateKey] = {taskId: ""};
      _updateWfDot(wfIdx);
      _incRunning();
      _incTabRunning("workflow");
      const bodyEl = document.getElementById(bodyId);
      try {
        const r = await fetch("/api/workflow/update-wc", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prefixes, name: wf.name})});
        const d = await r.json();
        if (d.error) { bodyEl.innerHTML = '<div class="error">❌ '+escapeHtml(d.error)+'</div>'; _wfPlayDone(); return; }
        _wfPlayState[stateKey].taskId = d.task_id;
        const _updateLogBuf = [];
        let _updateLogTimer = null;
        function _updateLogFlush() {
          if (!_updateLogBuf.length) return;
          for (const raw of _updateLogBuf.splice(0)) {
            if (!raw.trim()) continue;
            const div = document.createElement("div");
            div.textContent = raw;
            _logAppend(bodyEl, div);
          }
          bodyEl.scrollTop = bodyEl.scrollHeight;
        }
        function _updateLogPush(raw) {
          _updateLogBuf.push(raw);
          if (!_updateLogTimer) {
            _updateLogTimer = setInterval(function() {
              _updateLogFlush();
              if (!_updateLogBuf.length && _updateLogTimer) {
                clearInterval(_updateLogTimer);
                _updateLogTimer = null;
              }
            }, 80);
          }
        }
        const evtSrc = new EventSource("/api/log/stream/" + d.task_id);
        evtSrc.onmessage = (e) => {
          if (e.data === "[DONE]") {
            if (_updateLogTimer) { clearInterval(_updateLogTimer); _updateLogTimer = null; }
            _updateLogFlush();
            evtSrc.close();
            _wfPlayDone();
            return;
          }
          const lines = e.data.split("\n");
          for (const raw of lines) {
            if (!raw.trim()) continue;
            _updateLogPush(raw);
          }
        };
        evtSrc.onerror = () => {
          if (_updateLogTimer) { clearInterval(_updateLogTimer); _updateLogTimer = null; }
          evtSrc.close(); _wfPlayDone();
        };
      } catch(err) {
        bodyEl.innerHTML = '<div class="error">❌ 请求失败: '+escapeHtml(err.message)+'</div>';
        _wfPlayDone();
      }
      function _wfPlayDone() {
        delete _wfPlayState[stateKey];
        _updateWfDot(wfIdx);
        _decRunning();
        _decTabRunning("workflow");
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
function wfCreate() {
  config.workflows = config.workflows || [];
  config.workflows.push({name:"新工作流",steps:[]});
  saveConfig({workflows:config.workflows});
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