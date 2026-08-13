function buildPrefabTab(panel) {
  var state = {
    mode: "clear-text",
    draft: null,
    selectedPrefabId: "",
    dragPayload: null,
    busy: false,
    recoveryChecked: false,
    requestGeneration: 0,
    manualPicker: null
  };

  panel.innerHTML = `
    <div class="workbench prefab-workbench">
      <div class="form-group prefab-mode-row">
        <label>操作模式</label>
        <div class="toggle-group" id="prefab_mode_group">
          <button class="toggle-btn active" data-action="set-prefab-mode" data-mode="clear-text">一键清理文字</button>
          <button class="toggle-btn" data-action="set-prefab-mode" data-mode="atlas">图集引用清理</button>
          <button class="toggle-btn" data-action="set-prefab-mode" data-mode="font-check">字体检测</button>
        </div>
      </div>
      <div class="flex-row prefab-path-actions">
        <button class="btn btn-normal" data-action="browse-prefab-files" title="选择预制文件">
          <svg class="prefab-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          选择文件
        </button>
        <button class="btn btn-normal" data-action="browse-prefab-dir" title="选择文件夹">
          <svg class="prefab-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>
          选择文件夹
        </button>
      </div>
      <div class="card prefab-dropzone" id="prefab_dropzone">
        <input class="prefab-drop-input" type="text" id="prefab_drop_input" autocomplete="off" aria-label="拖入预制文件或文件夹">
        <div class="prefab-drop-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        </div>
        <div class="prefab-drop-title" id="prefab_drop_title">将文件或文件夹拖拽到此处</div>
        <div class="prefab-drop-help" id="prefab_drop_help">或使用上方按钮选择</div>
        <div class="prefab-summary" id="prefab_summary" hidden></div>
      </div>
      <div class="atlas-workspace" id="atlas_workspace" hidden>
        <div class="atlas-main-grid">
          <section class="card atlas-prefab-pane">
            <div class="card-header compact"><span>预制列表</span><span class="atlas-pane-count" id="atlas_prefab_count"></span><button class="btn btn-normal btn-sm" data-action="refresh-prefabs" title="刷新预制引用，删除失效计划" style="margin-left:auto"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0115.4-5.6L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 01-15.4 5.6L3 16"/></svg></button></div>
            <div class="atlas-prefab-list" id="atlas_prefab_list"></div>
          </section>
          <section class="card atlas-group-pane">
            <div class="card-header compact"><span>已有图集组</span><span class="atlas-pane-hint">拖到其他组以创建计划</span></div>
            <div class="atlas-group-list" id="atlas_group_list"></div>
          </section>
        </div>
        <section class="card atlas-plan-pane">
          <div class="card-header compact"><span>当前预制迁移计划</span><span class="atlas-stage" id="atlas_stage"></span></div>
          <div class="atlas-plan-list" id="atlas_plan_list"></div>
          <div class="atlas-phase-actions" id="atlas_phase_actions"></div>
        </section>
      </div>
      <div class="wf-modal-overlay" id="atlas_manual_overlay">
        <div class="wf-modal atlas-manual-modal">
          <div class="wf-modal-header"><h3>手动指定目标 Sprite</h3><button class="wf-modal-close" data-action="close-manual-picker" title="关闭"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></div>
          <div class="atlas-manual-summary" id="atlas_manual_summary"></div>
          <div class="atlas-manual-body">
            <div class="atlas-manual-atlas-col">
              <div class="atlas-manual-label">1. 选择目标图集</div>
              <input class="atlas-manual-search" id="atlas_manual_atlas_filter" data-action="filter-manual-atlas" placeholder="输入图集名关键字进行筛选" autocomplete="off">
              <div class="atlas-manual-atlas-list" id="atlas_manual_atlas_list"></div>
            </div>
            <div class="atlas-manual-sprite-col">
              <div class="atlas-manual-label">2. 搜索目标 Sprite</div>
              <input class="atlas-manual-search" id="atlas_manual_sprite_filter" data-action="filter-manual-sprite" placeholder="输入 Sprite 名关键字进行筛选，需先选择图集" autocomplete="off" disabled>
              <div class="atlas-manual-sprite-list" id="atlas_manual_sprite_list"></div>
            </div>
          </div>
          <div class="atlas-manual-footer">
            <button class="btn btn-normal" data-action="refresh-atlas-catalog">刷新图集索引</button>
            <span class="atlas-manual-selected" id="atlas_manual_selected"></span>
            <button class="btn btn-primary" id="atlas_manual_confirm" data-action="confirm-manual-picker" disabled>确认指定</button>
          </div>
        </div>
      </div>
      <div class="wf-modal-overlay" id="atlas_add_group_overlay">
        <div class="wf-modal" style="width:480px">
          <div class="wf-modal-header"><h3>添加目标图集组</h3><button class="wf-modal-close" data-action="close-add-group-picker" title="关闭"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></div>
          <div class="wf-modal-body">
            <input class="atlas-manual-search" id="atlas_add_group_filter" data-action="filter-add-group" placeholder="输入图集组名关键字进行筛选" autocomplete="off">
            <div class="atlas-manual-atlas-list" id="atlas_add_group_list" style="max-height:360px;overflow:auto"></div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;margin-top:12px">
            <span id="atlas_add_group_selected" style="flex:1;font-size:12px;color:var(--success)"></span>
            <button class="btn btn-primary" id="atlas_add_group_confirm" data-action="confirm-add-group" disabled>确认添加</button>
          </div>
        </div>
      </div>
      <div id="font_check_workspace" hidden>
        <div class="card">
          <div class="card-header compact">
            <span>检测到的字体</span>
            <span class="atlas-pane-count" id="font_scan_summary"></span>
          </div>
          <div id="font_list"><div class="atlas-empty">尚未检测到字体，请拖入预制文件或目录开始扫描</div></div>
        </div>
        <div class="action-center">
          <button class="btn btn-primary" data-action="font-preview" disabled>预览变更</button>
        </div>
      </div>
      <div class="log-wrap prefab-log-wrap" id="log_clear_text">
        <div class="card-header compact"><span>清理文字日志</span></div>
        <div class="log" id="prefab_log"><div class="log-anchor"></div></div>
      </div>
      <div class="log-wrap prefab-log-wrap" id="log_atlas" hidden>
        <div class="card-header compact"><span>图集引用日志</span></div>
        <div class="log" id="atlas_log"><div class="log-anchor"></div></div>
      </div>
      <div class="log-wrap prefab-log-wrap" id="log_font" hidden>
        <div class="card-header compact"><span>字体检测日志</span></div>
        <div class="log" id="font_log"><div class="log-anchor"></div></div>
      </div>
    </div>`;

  S.prefab.logEl = document.getElementById("prefab_log");
  enablePathDrop("prefab_drop_input", {mode:"path"});

  function html(value) {
    return escapeHtml(value === undefined || value === null ? "" : String(value));
  }

  function values(object) {
    return Object.keys(object || {}).map(function(key) { return object[key]; });
  }

  function setSummary(message) {
    var summary = panel.querySelector("#prefab_summary");
    if (!summary) return;
    summary.textContent = message || "";
    summary.hidden = !message;
  }

  function appendPrefabLog(className, message) {
    var log = panel.querySelector("#prefab_log");
    if (!log) return;
    var line = document.createElement("div");
    if (className) line.className = className;
    line.textContent = message;
    _logAppend(log, line);
  }

  function apiPost(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(body || {})
    }).then(function(response) {
      return response.json().then(function(data) {
        if (!response.ok || data.error) throw new Error(data.error || "请求失败");
        return data;
      });
    });
  }

  function setDraft(draft) {
    state.draft = draft || null;
    if (!state.draft) {
      state.selectedPrefabId = "";
      renderAtlas();
      return;
    }
    var selectedExists = state.draft.prefabs.some(function(item) {
      return item.id === state.selectedPrefabId;
    });
    if (!selectedExists) {
      state.selectedPrefabId = state.draft.prefabs.length ? state.draft.prefabs[0].id : "";
    }
    renderAtlas();
  }

  function selectedPrefab() {
    if (!state.draft) return null;
    for (var i = 0; i < state.draft.prefabs.length; i++) {
      if (state.draft.prefabs[i].id === state.selectedPrefabId) return state.draft.prefabs[i];
    }
    return null;
  }

  function selectedPlans() {
    if (!state.draft) return [];
    return values(state.draft.plans).filter(function(plan) {
      return plan.prefab_id === state.selectedPrefabId;
    });
  }

  function planForReference(referenceId) {
    if (!state.draft) return null;
    var plans = values(state.draft.plans).concat(state.draft.completed_plans || []);
    for (var i = 0; i < plans.length; i++) {
      if (plans[i].reference_ids && plans[i].reference_ids.indexOf(referenceId) !== -1) {
        return plans[i];
      }
    }
    return null;
  }

  function manualPlanForReference(referenceId) {
    if (!state.draft) return null;
    var plans = values(state.draft.plans);
    for (var i = 0; i < plans.length; i++) {
      if (plans[i].kind === "manual" && plans[i].reference_ids && plans[i].reference_ids.indexOf(referenceId) !== -1) {
        return plans[i];
      }
    }
    return null;
  }

  function prefabHasPlan(prefabId) {
    if (!state.draft) return false;
    if (values(state.draft.plans).some(function(plan) { return plan.prefab_id === prefabId; })) return true;
    return (state.draft.completed_plans || []).some(function(plan) { return plan.prefab_id === prefabId; });
  }

  function statusText(status) {
    return {
      planning: "规划中",
      copy_partial: "部分复制失败",
      copied: "资源已复制",
      resolution_partial: "部分解析完成",
      resolved: "解析完成",
      rewrite_partial: "部分预制已修改",
      completed: "已完成",
      pending: "等待处理",
      success: "成功",
      failed: "失败",
      partial: "部分成功"
    }[status] || status || "等待处理";
  }

  function statusClass(status) {
    if (status === "success" || status === "completed" || status === "resolved" || status === "copied") return "is-success";
    if (status === "failed") return "is-error";
    if (status === "partial" || status === "copy_partial" || status === "resolution_partial" || status === "rewrite_partial") return "is-warning";
    return "is-pending";
  }

  function isPlannable() {
    return !!state.draft && state.draft.stage !== "completed";
  }

  function renderAtlas() {
    var listEl = panel.querySelector("#atlas_prefab_list");
    var countEl = panel.querySelector("#atlas_prefab_count");
    var groupsEl = panel.querySelector("#atlas_group_list");
    var plansEl = panel.querySelector("#atlas_plan_list");
    var stageEl = panel.querySelector("#atlas_stage");
    var actionsEl = panel.querySelector("#atlas_phase_actions");
    if (!listEl || !groupsEl || !plansEl || !actionsEl) return;
    panel.querySelectorAll("[data-action='set-prefab-mode']").forEach(function(button) { button.disabled = state.busy; });
    var browseDirButton = panel.querySelector("[data-action='browse-prefab-dir']");
    var dropInput = panel.querySelector("#prefab_drop_input");
    if (browseDirButton) browseDirButton.disabled = state.busy;
    if (dropInput) dropInput.disabled = state.busy;

    if (!state.draft) {
      countEl.textContent = "";
      listEl.innerHTML = '<div class="atlas-empty">请选择 Prefabs 目录开始扫描</div>';
      groupsEl.innerHTML = '<div class="atlas-empty">扫描后将在此显示全部已有图集组</div>';
      plansEl.innerHTML = '<div class="atlas-empty">尚无迁移计划</div>';
      stageEl.textContent = "";
      stageEl.className = "atlas-stage";
      actionsEl.innerHTML = "";
      return;
    }

    var draft = state.draft;
    var prefab = selectedPrefab();
    countEl.textContent = draft.prefabs.length + " 个";
    listEl.innerHTML = draft.prefabs.length ? draft.prefabs.map(function(item) {
      var active = item.id === state.selectedPrefabId ? " active" : "";
      var badge = prefabHasPlan(item.id) ? '<span class="atlas-prefab-badge" title="该预制有计划任务"></span>' : "";
      return '<button class="atlas-prefab-item' + active + '" data-action="select-atlas-prefab" data-prefab-id="' + html(item.id) + '">' +
        '<span class="atlas-prefab-name-row"><span class="atlas-prefab-name" title="' + html(item.relative_path) + '">' + html(item.relative_path) + '</span>' + badge + '</span>' +
        '<span class="atlas-prefab-metrics"><span>图集 ' + html(item.source_group_count) + '</span>' +
        '<span class="' + (item.missing_count ? "is-error" : "") + '">缺失 ' + html(item.missing_count) + '</span></span></button>';
    }).join("") : '<div class="atlas-empty">目录中未找到包含图集精灵引用的预制</div>';

    renderGroups(groupsEl, prefab);
    renderPlans(plansEl, prefab);
    stageEl.textContent = "阶段：" + statusText(draft.stage);
    stageEl.className = "atlas-stage " + statusClass(draft.stage);
    renderPhaseActions(actionsEl);
  }

  function renderGroups(container, prefab) {
    if (!prefab) {
      container.innerHTML = '<div class="atlas-empty">没有可选择的预制</div>';
      return;
    }
    var draft = state.draft;
    var sourceGroupIds = {};
    var imagesByGroup = {};
    var seenImages = {};
    var lockedGroupIds = {};
    selectedPlans().forEach(function(plan) {
      var copyItem = draft.copies[plan.copy_id];
      var image = draft.images[plan.source_image_id];
      if (copyItem && copyItem.status === "success" && image && image.source_group_id) {
        lockedGroupIds[image.source_group_id] = true;
      }
    });
    prefab.references.forEach(function(reference) {
      if (reference.source_group_id) sourceGroupIds[reference.source_group_id] = true;
      if (!reference.source_group_id || !reference.source_image_id || seenImages[reference.source_image_id]) return;
      seenImages[reference.source_image_id] = true;
      var image = draft.images[reference.source_image_id];
      if (!image) return;
      if (!imagesByGroup[reference.source_group_id]) imagesByGroup[reference.source_group_id] = [];
      imagesByGroup[reference.source_group_id].push(image);
    });
    Object.keys(imagesByGroup).forEach(function(groupId) {
      imagesByGroup[groupId].sort(function(a, b) { return a.name.localeCompare(b.name); });
    });

    var groups = Object.keys(sourceGroupIds).map(function(groupId) {
      return draft.groups[groupId];
    }).filter(Boolean).sort(function(a, b) {
      return a.relative_path.localeCompare(b.relative_path);
    });
    var manualIds = prefab.manual_group_ids || [];
    var existingIds = {};
    groups.forEach(function(g) { existingIds[g.id] = true; });
    manualIds.forEach(function(gid) {
      if (!existingIds[gid] && draft.groups[gid]) {
        groups.push(draft.groups[gid]);
      }
    });
    var addBtn = '<button class="atlas-group-add-btn" data-action="add-manual-group" title="添加图集组作为目标">+</button>';
    if (!groups.length) {
      container.innerHTML = '<div class="atlas-empty">当前预制没有可迁移的图集引用</div>' + addBtn;
      return;
    }

    container.innerHTML = groups.map(function(group) {
      var images = imagesByGroup[group.id] || [];
      var groupLocked = !!lockedGroupIds[group.id];
      var groupDisabled = state.busy || groupLocked;
      var groupRefs = images.reduce(function(acc, image) {
        return acc.concat(prefab.references.filter(function(reference) {
          return reference.source_image_id === image.id;
        }));
      }, []);
      var groupAllDone = groupRefs.length > 0 && groupRefs.every(function(reference) {
        return !!planForReference(reference.id);
      });
      var doneTag = groupAllDone
        ? '<span class="atlas-group-done" title="该图集组资源已全部处理"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg></span>'
        : "";
      var sourceTools = '<span class="atlas-source-tools"><span class="atlas-group-drag" draggable="' + (groupDisabled ? "false" : "true") + '" data-drag-kind="groups" data-source-group-id="' + html(group.id) + '" title="' + (groupLocked ? "该源组包含已复制成功的计划，不能重新指定目标" : "拖拽此图集组的全部引用") + '">拖拽此组</span></span>';
      var imageHtml = images.map(function(image) {
        var refs = prefab.references.filter(function(reference) {
          return reference.source_image_id === image.id;
        });
        var refHtml = refs.map(function(reference) {
          var plan = planForReference(reference.id);
          var manualPlan = plan && plan.kind === "manual" ? plan : null;
          var name = html(reference.sprite_name || "未知");
          var title = reference.guid + "/" + reference.file_id + (reference.sprite_name ? " · " + reference.sprite_name : "");
          var countTag = reference.count > 1 ? '<span class="atlas-ref-count">×' + html(reference.count) + '</span>' : '';
          var pointerIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 11V7a1.5 1.5 0 0 1 3 0v4"/><path d="M10 10.5V5.5a1.5 1.5 0 0 1 3 0v5"/><path d="M13 10.5V6.5a1.5 1.5 0 0 1 3 0v6"/><path d="M16 12.5v-2a1.5 1.5 0 0 1 3 0V16a6 6 0 0 1-6 6h-1.6a6 6 0 0 1-4.7-2.3l-3-3.9a1.8 1.8 0 0 1 2.9-2.2L9 15.5"/></svg>';
          var pickerDisabled = !isPlannable() || state.busy ? " disabled" : "";
          if (manualPlan && manualPlan.rewrite && manualPlan.rewrite.status === "success") {
            return '<div class="atlas-ref-row is-locked"><span class="atlas-ref-info" title="' + html(title) + '">' + name + '</span>' + countTag + '<span class="atlas-ref-dot is-done" title="已修改"></span></div>';
          }
          if (manualPlan) {
            var targetAtlas = draft.atlases[manualPlan.target_atlas_id] || {};
            return '<div class="atlas-ref-row"><span class="atlas-ref-info" title="' + html(title) + '">' + name + '</span>' + countTag +
              '<span class="atlas-ref-dot is-set" title="已指定 → ' + html(targetAtlas.relative_path + "/" + manualPlan.target_sprite_name) + '"></span>' +
              '<button class="atlas-ref-action" title="重新指定目标 Sprite" data-action="open-manual-picker" data-reference-id="' + html(reference.id) + '"' + pickerDisabled + '>' + pointerIcon + '</button></div>';
          }
          if (plan) {
            return '<div class="atlas-ref-row"><span class="atlas-ref-info" title="' + html(title) + '">' + name + '</span>' + countTag +
              '<span class="atlas-ref-dot is-set" title="已规划迁移"></span>' +
              '<button class="atlas-ref-action" title="手动指定目标 Sprite" data-action="open-manual-picker" data-reference-id="' + html(reference.id) + '"' + pickerDisabled + '>' + pointerIcon + '</button></div>';
          }
          return '<div class="atlas-ref-row"><span class="atlas-ref-info" title="' + html(title) + '">' + name + '</span>' + countTag +
            '<button class="atlas-ref-action" title="手动指定目标 Sprite" data-action="open-manual-picker" data-reference-id="' + html(reference.id) + '"' + pickerDisabled + '>' + pointerIcon + '</button></div>';
        }).join("");
        return '<div class="atlas-source-image">' + refHtml + '</div>';
      }).join("");
      var refCountTag = '<span class="atlas-group-ref-count" title="引用资源数">' + groupRefs.length + '</span>';
      return '<details class="atlas-group-card is-source" data-target-group-id="' + html(group.id) + '">' +
        '<summary class="atlas-group-summary"><span class="atlas-group-name-wrap"><span class="atlas-group-name" title="' + html(group.relative_path) + '">' + html(group.relative_path) + '</span>' + refCountTag + '</span>' + doneTag + sourceTools + '</summary>' +
        '<div class="atlas-group-images">' + imageHtml + '</div></details>';
    }).join("") + addBtn;
  }

  function prefabById(prefabId) {
    var draft = state.draft;
    if (!draft) return null;
    for (var i = 0; i < draft.prefabs.length; i++) {
      if (draft.prefabs[i].id === prefabId) return draft.prefabs[i];
    }
    return null;
  }

  function prefabIdForReference(referenceId) {
    var draft = state.draft;
    if (!draft) return "";
    for (var i = 0; i < draft.prefabs.length; i++) {
      var refs = draft.prefabs[i].references;
      for (var j = 0; j < refs.length; j++) {
        if (refs[j].id === referenceId) return draft.prefabs[i].id;
      }
    }
    return "";
  }

  function renderPlans(container, prefab) {
    var draft = state.draft;
    var allPlans = values(draft.plans);
    if (!allPlans.length) {
      container.innerHTML = '<div class="atlas-empty">尚无迁移计划，请将右侧源图集组拖到其他图集组，或点击资源行的手动指定</div>';
      return;
    }
    var byPrefab = {};
    allPlans.forEach(function(plan) {
      (byPrefab[plan.prefab_id] = byPrefab[plan.prefab_id] || []).push(plan);
    });
    container.innerHTML = Object.keys(byPrefab).map(function(prefabId) {
      var item = prefabById(prefabId);
      var groupPlans = byPrefab[prefabId].slice().sort(function(a, b) {
        var imageA = draft.images[a.source_image_id];
        var imageB = draft.images[b.source_image_id];
        return (imageA ? imageA.name : "").localeCompare(imageB ? imageB.name : "");
      });
      var selected = prefabId === state.selectedPrefabId ? " is-selected" : "";
      return '<section class="atlas-plan-group' + selected + '">' +
        '<div class="atlas-plan-group-header"><span class="atlas-plan-group-name" title="' + html(item ? item.relative_path : prefabId) + '">' + html(item ? item.relative_path : prefabId) + '</span>' +
        '<span class="atlas-plan-group-count">' + html(groupPlans.length) + ' 项</span></div>' +
        '<div class="atlas-plan-list">' + groupPlans.map(function(plan) {
          return renderPlanItem(plan, item || {references: []});
        }).join("") + '</div></section>';
    }).join("");
  }

  function renderPlanItem(plan, prefab) {
    var draft = state.draft;
    var references = prefab.references.filter(function(reference) {
      return plan.reference_ids.indexOf(reference.id) !== -1;
    });
      var snapshot = plan.source_snapshot || {};
      var oldRefs = references.map(function(reference) {
        return reference.guid + "/" + reference.file_id + (reference.count > 1 ? " ×" + reference.count : "");
      }).join("，") || (snapshot.guid ? snapshot.guid + "/" + snapshot.file_id + (snapshot.count > 1 ? " ×" + snapshot.count : "") : "");
      var resolution = plan.resolution || {status:"pending", error:""};
      var rewrite = plan.rewrite || {status:"pending", error:""};
      var errors = [];
      if (resolution.error) errors.push(resolution.error);
      if (rewrite.error) errors.push(rewrite.error);
      if (plan.kind === "manual") {
        var reference = references[0] || {};
        var sourceImage = reference.source_image_id ? (draft.images[reference.source_image_id] || {}) : {};
        var srcGroup = sourceImage.source_group || snapshot.source_group || "未知源组";
        var srcName = reference.sprite_name || snapshot.sprite_name || "未知源Sprite";
        var targetAtlas = draft.atlases[plan.target_atlas_id] || {};
        var manualLocked = rewrite.status === "success";
        var manualEditable = isPlannable() && !manualLocked && !state.busy;
        return '<article class="atlas-plan-item">' +
          '<div class="atlas-plan-route"><span class="atlas-plan-source">' + html(srcGroup) + '/' + html(srcName) + '</span>' +
          '<span class="atlas-route-arrow">→</span><span class="atlas-plan-target" title="' + html(targetAtlas.relative_path + "/" + plan.target_sprite_name) + '">' + html(targetAtlas.relative_path || "未知目标Atlas") + '/' + html(plan.target_sprite_name) + '</span></div>' +
          '<div class="atlas-plan-editor"><span class="atlas-plan-kind">类型：手动指定</span>' +
          '<button class="btn btn-normal btn-sm" data-action="open-manual-picker" data-reference-id="' + html(reference.id || "") + '"' + (manualEditable ? "" : " disabled") + '>重新指定</button>' +
          '<button class="btn btn-danger btn-sm" data-action="remove-atlas-plan" data-plan-id="' + html(plan.id) + '"' + (manualEditable ? "" : " disabled") + '>删除</button></div>' +
          '<div class="atlas-plan-statuses"><span class="is-success">复制：无需复制</span>' +
          '<span class="' + statusClass(resolution.status) + '">解析：已指定</span>' +
          '<span class="' + statusClass(rewrite.status) + '">修改：' + html(statusText(rewrite.status)) + '</span></div>' +
          '<div class="atlas-resolution-detail"><span title="' + html(oldRefs) + '">' + html(oldRefs) + '</span><span class="atlas-route-arrow">→</span><span title="' + html(resolution.guid + "/" + resolution.file_id) + '">' + html(resolution.guid + "/" + resolution.file_id) + '</span></div>' +
          (errors.length ? '<div class="atlas-plan-error">' + html(errors.join("；")) + '</div>' : "") + '</article>';
      }
      var image = draft.images[plan.source_image_id] || {};
      var target = draft.groups[plan.target_group_id] || {};
      var copyItem = draft.copies[plan.copy_id] || {};
      var newRef = resolution.status === "success" ? resolution.guid + "/" + resolution.file_id : "尚未解析";
      if (copyItem.conflict) errors.push(copyItem.conflict);
      if (copyItem.error) errors.push(copyItem.error);
      var editable = isPlannable() && copyItem.status !== "success" && !state.busy;
      var shared = (copyItem.plan_ids || []).length;
      var targetPath = target.relative_path && copyItem.target_name
        ? target.relative_path + "/" + copyItem.target_name + ".png"
        : "未知目标";
      return '<article class="atlas-plan-item' + (copyItem.conflict ? " has-conflict" : "") + '">' +
        '<div class="atlas-plan-route"><span class="atlas-plan-source">' + html(image.source_group || "未知源组") + '/' + html(image.name || "未知图片") + '</span>' +
        '<span class="atlas-route-arrow">→</span><span class="atlas-plan-target" title="' + html(targetPath) + '">' + html(targetPath) + '</span></div>' +
        '<div class="atlas-plan-editor"><label>目标名称<input class="atlas-name-input" placeholder="输入目标 Sprite 名称，不含 .png 后缀" data-action="rename-atlas-plan" data-plan-id="' + html(plan.id) + '" value="' + html(copyItem.target_name) + '"' + (editable ? "" : " disabled") + '></label>' +
        '<button class="btn btn-danger btn-sm" data-action="remove-atlas-plan" data-plan-id="' + html(plan.id) + '"' + (isPlannable() && copyItem.status !== "success" && !state.busy ? "" : " disabled") + '>删除</button></div>' +
        '<div class="atlas-plan-statuses"><span class="' + statusClass(copyItem.status) + '">复制：' + html(statusText(copyItem.status)) + '</span>' +
        '<span class="' + statusClass(resolution.status) + '">解析：' + html(statusText(resolution.status)) + '</span>' +
        '<span class="' + statusClass(rewrite.status) + '">修改：' + html(statusText(rewrite.status)) + '</span>' +
        '<span>共享计划：' + html(shared) + '</span></div>' +
        '<div class="atlas-resolution-detail"><span title="' + html(oldRefs) + '">' + html(oldRefs) + '</span><span class="atlas-route-arrow">→</span><span title="' + html(newRef) + '">' + html(newRef) + '</span></div>' +
        (errors.length ? '<div class="atlas-plan-error">' + html(errors.join("；")) + '</div>' : "") + '</article>';
  }

  function renderPhaseActions(container) {
    var draft = state.draft;
    var plans = values(draft.plans);
    var copies = values(draft.copies);
    var conflict = copies.some(function(item) { return !!item.conflict; });
    var hasCopyFailure = copies.some(function(item) { return item.status === "failed"; });
    var pendingCopy = plans.some(function(plan) {
      return plan.copy_id && draft.copies[plan.copy_id] && draft.copies[plan.copy_id].status !== "success";
    });
    var pendingResolve = plans.some(function(plan) {
      if (plan.kind === "manual") return false;
      if (!plan.copy_id || !draft.copies[plan.copy_id]) return false;
      if (draft.copies[plan.copy_id].status !== "success") return false;
      return !plan.resolution || plan.resolution.status !== "success";
    });
    var canCopy = !state.busy && pendingCopy && !conflict;
    var canResolve = !state.busy && pendingResolve;
    var canRewrite = !state.busy && plans.some(function(plan) {
      return plan.resolution && plan.resolution.status === "success" && (!plan.rewrite || plan.rewrite.status !== "success");
    });
    container.innerHTML =
      '<div class="atlas-phase-note">' + (conflict ? "存在目标重名冲突，请先修改名称" : "整组迁移需复制后在 Unity 中刷新并重新打图集；手动指定的引用可直接修改") + '</div>' +
      '<div class="atlas-phase-buttons">' +
      '<button class="btn btn-normal" data-action="discard-atlas-draft"' + (state.busy ? " disabled" : "") + '>放弃草稿</button>' +
      '<button class="btn btn-primary" data-action="run-atlas-copy"' + (canCopy ? "" : " disabled") + '>' + (hasCopyFailure ? "重试复制" : "复制资源") + '</button>' +
      '<button class="btn btn-primary" data-action="run-atlas-resolve"' + (canResolve ? "" : " disabled") + '>已打图集，解析最终引用</button>' +
      '<button class="btn btn-danger" data-action="run-atlas-rewrite"' + (canRewrite ? "" : " disabled") + '>确认修改预制</button></div>';
  }

  function setMode(mode) {
    if (mode !== "clear-text" && mode !== "atlas" && mode !== "font-check") return;
    state.mode = mode;
    panel.querySelectorAll("[data-action='set-prefab-mode']").forEach(function(button) {
      button.classList.toggle("active", button.dataset.mode === mode);
    });
    var fileButton = panel.querySelector("[data-action='browse-prefab-files']");
    var atlasWorkspace = panel.querySelector("#atlas_workspace");
    var fontWorkspace = panel.querySelector("#font_check_workspace");
    var title = panel.querySelector("#prefab_drop_title");
    var help = panel.querySelector("#prefab_drop_help");
    fileButton.hidden = mode !== "clear-text";
    fileButton.disabled = mode !== "clear-text" || state.busy;
    atlasWorkspace.hidden = mode !== "atlas";
    if (fontWorkspace) fontWorkspace.hidden = mode !== "font-check";
    panel.querySelector("#log_clear_text").hidden = mode !== "clear-text";
    panel.querySelector("#log_atlas").hidden = mode !== "atlas";
    panel.querySelector("#log_font").hidden = mode !== "font-check";
    if (mode === "atlas") {
      title.textContent = "将 Prefabs 目录拖拽到此处";
      help.textContent = "图集引用清理仅接受 Prefabs 或其子目录";
    } else if (mode === "font-check") {
      title.textContent = "将预制文件或目录拖拽到此处";
      help.textContent = "自动遍历 3 层识别预制文件，检测字体引用";
    } else {
      title.textContent = "将文件或文件夹拖拽到此处";
      help.textContent = "或使用上方按钮选择";
    }
    setSummary("");
    if (mode === "atlas") checkAtlasDrafts();
  }

  function checkAtlasDrafts() {
    if (state.recoveryChecked) return;
    state.recoveryChecked = true;
    var requestGeneration = state.requestGeneration;
    fetch("/api/prefab/atlas/drafts").then(function(response) {
      return response.json().then(function(data) {
        if (!response.ok || data.error) throw new Error(data.error || "草稿查询失败");
        return data;
      });
    }).then(function(data) {
      if (requestGeneration !== state.requestGeneration) return;
      var drafts = data.drafts || [];
      if (!drafts.length) return;
      var newest = drafts[0];
      if (state.draft && state.draft.id === newest.id) return;
      return showConfirm({
        title: "发现未完成的图集迁移草稿",
        message: "最新草稿更新时间为 " + (newest.updated_at || "未知时间") + "。选择继续可恢复草稿；选择放弃只会删除草稿，已经复制的文件仍会保留。",
        confirmText: "继续草稿",
        cancelText: "放弃草稿"
      }).then(function(recover) {
        if (requestGeneration !== state.requestGeneration) return;
        if (recover) return recoverDraft(newest.id);
        return discardDraft(newest.id, true);
      });
    }).catch(function(error) {
      if (requestGeneration === state.requestGeneration) _showToast("查询图集迁移草稿失败：" + error.message);
    });
  }

  function recoverDraft(draftId) {
    if (state.busy) return Promise.resolve();
    var requestGeneration = ++state.requestGeneration;
    state.busy = true;
    setSummary("正在恢复图集迁移草稿...");
    renderAtlas();
    return apiPost("/api/prefab/atlas/draft/get", {draft_id:draftId}).then(function(data) {
      if (requestGeneration !== state.requestGeneration) return;
      setDraft(data.draft);
      setSummary("已恢复图集迁移草稿");
      _showToast("已恢复最新草稿");
    }).catch(function(error) {
      if (requestGeneration !== state.requestGeneration) return;
      setSummary("");
      _showToast("恢复草稿失败：" + error.message);
    }).finally(function() {
      if (requestGeneration !== state.requestGeneration) return;
      state.busy = false;
      renderAtlas();
    });
  }

  function discardDraft(draftId, ask) {
    var confirmationGeneration = state.requestGeneration;
    var confirmation = ask ? showConfirm({
      title: "放弃图集迁移草稿",
      message: "确定放弃当前草稿吗？草稿会被删除，但已经复制到目标图集目录的文件仍会保留。",
      confirmText: "放弃草稿",
      cancelText: "取消",
      danger: true
    }) : Promise.resolve(true);
    return confirmation.then(function(confirmed) {
      if (!confirmed || state.busy || confirmationGeneration !== state.requestGeneration) return;
      var requestGeneration = ++state.requestGeneration;
      state.busy = true;
      renderAtlas();
      return apiPost("/api/prefab/atlas/discard", {draft_id:draftId}).then(function() {
        if (requestGeneration !== state.requestGeneration) return;
        if (state.draft && state.draft.id === draftId) setDraft(null);
        setSummary("");
        _showToast("草稿已放弃，已复制文件仍保留");
      }).catch(function(error) {
        if (requestGeneration === state.requestGeneration) _showToast("放弃草稿失败：" + error.message);
      }).finally(function() {
        if (requestGeneration !== state.requestGeneration) return;
        state.busy = false;
        renderAtlas();
      });
    });
  }

  function dispatchPaths(paths) {
    paths = (paths || []).filter(function(path) { return !!path; });
    if (!paths.length) return;
    if (state.mode === "atlas") {
      scanAtlas(paths);
    } else if (state.mode === "font-check") {
      scanFonts(paths);
    } else {
      startPrefabClear(paths);
    }
  }
  window._prefabDispatchPaths = dispatchPaths;

  function scanAtlas(paths) {
    if (state.busy) return;
    var requestGeneration = ++state.requestGeneration;
    state.busy = true;
    state.dragPayload = null;
    setSummary("正在扫描图集引用...");
    renderAtlas();
    apiPost("/api/prefab/atlas/scan", {paths:paths}).then(function(data) {
      if (requestGeneration !== state.requestGeneration) return;
      setDraft(data.draft);
      setSummary("扫描完成，共找到 " + data.draft.prefabs.length + " 个预制");
    }).catch(function(error) {
      if (requestGeneration !== state.requestGeneration) return;
      setSummary("");
      _showToast("图集引用扫描失败：" + error.message);
    }).finally(function() {
      if (requestGeneration !== state.requestGeneration) return;
      state.busy = false;
      renderAtlas();
    });
  }

  // ── 字体检测 ──
  var fontScanData = null;
  var fontScanPaths = [];

  function _fontLog(msg) {
    var el = panel.querySelector("#font_log");
    if (!el) return;
    var anchor = el.querySelector(".log-anchor");
    var line = document.createElement("div");
    var ts = new Date().toLocaleTimeString("zh-CN", {hour12: false});
    line.innerHTML = '<span class="ts">' + ts + '</span> ' + escapeHtml(msg);
    el.insertBefore(line, anchor);
    el.scrollTop = el.scrollHeight;
  }

  function _clearFontLog() {
    var el = panel.querySelector("#font_log");
    if (!el) return;
    var anchor = el.querySelector(".log-anchor");
    while (el.firstChild && el.firstChild !== anchor) el.removeChild(el.firstChild);
  }

  function _clearAtlasLog() {
    var el = panel.querySelector("#atlas_log");
    if (!el) return;
    var anchor = el.querySelector(".log-anchor");
    while (el.firstChild && el.firstChild !== anchor) el.removeChild(el.firstChild);
  }

  function scanFonts(paths) {
    if (state.busy) return;
    var requestGeneration = ++state.requestGeneration;
    state.busy = true;
    fontScanPaths = paths;
    _incRunning();
    _incTabRunning("prefab");
    _clearFontLog();
    _fontLog("开始扫描字体引用...");
    apiPost("/api/prefab/font-scan", {paths:paths}).then(function(data) {
      if (requestGeneration !== state.requestGeneration) return;
      fontScanData = data;
      renderFontList();
      _fontLog("扫描完成，共 " + data.total_prefabs + " 个预制，发现 " + data.fonts.length + " 种字体");
    }).catch(function(error) {
      if (requestGeneration !== state.requestGeneration) return;
      fontScanData = null;
      _fontLog("扫描失败：" + error.message);
      _showToast("字体扫描失败：" + error.message);
    }).finally(function() {
      if (requestGeneration !== state.requestGeneration) return;
      state.busy = false;
      _decRunning();
      _decTabRunning("prefab");
    });
  }

  function renderFontList() {
    var listEl = panel.querySelector("#font_list");
    var summaryEl = panel.querySelector("#font_scan_summary");
    var previewBtn = panel.querySelector("[data-action='font-preview']");
    if (!listEl || !fontScanData) return;
    var fonts = fontScanData.fonts;
    if (summaryEl) summaryEl.textContent = fonts.length + " 种字体";
    if (!fonts.length) {
      listEl.innerHTML = '<div class="atlas-empty">未检测到字体引用</div>';
      if (previewBtn) previewBtn.disabled = true;
      return;
    }
    listEl.innerHTML = fonts.map(function(font, i) {
      var pathText = font.asset_path ? font.asset_path : "GUID: " + font.guid;
      return '<div class="font-item" data-guid="' + html(font.guid) + '">' +
        '<div class="font-item-row1">' +
        '<label class="font-item-left"><input type="checkbox" class="font-item-check" checked>' +
        '<span class="font-item-name">' + html(font.name) + '</span></label>' +
        '<span class="font-item-count">' + font.ref_count + '次引用</span>' +
        '<span class="font-item-arrow">→</span>' +
        '<span class="font-item-right">' +
        '<input type="text" class="font-item-target" placeholder="目标字体名或路径（留空不改）" data-idx="' + i + '">' +
        '<span class="font-item-spacing-wrap">行距<input type="text" class="font-item-spacing" placeholder="不改" data-idx="' + i + '"></span>' +
        '</span></div>' +
        '<input type="text" class="font-item-path" value="' + html(pathText) + '" readonly title="点击复制路径">' +
        '</div>';
    }).join("");
    if (previewBtn) previewBtn.disabled = false;
  }

  function fontPreview() {
    if (!fontScanData || !fontScanPaths.length) return;
    var items = panel.querySelectorAll(".font-item");
    var changes = [];
    items.forEach(function(item) {
      var checkbox = item.querySelector(".font-item-check");
      if (!checkbox || !checkbox.checked) return;
      var guid = item.dataset.guid;
      var target = item.querySelector(".font-item-target").value.trim();
      var spacing = item.querySelector(".font-item-spacing").value.trim();
      if (!target && !spacing) return;
      var font = fontScanData.fonts.filter(function(f) { return f.guid === guid; })[0];
      changes.push({
        old_guid: guid,
        old_name: font ? font.name : guid,
        old_path: font ? (font.asset_path || font.guid) : guid,
        new_font_name: target,
        line_spacing: spacing,
        prefab_files: font ? font.prefab_files : [],
      });
    });
    if (!changes.length) { _showToast("请至少填写一个目标字体或行距"); return; }
    var s = 'font-size:12px;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.06);white-space:nowrap';
    var sh = 'font-size:11px;padding:6px 10px;color:var(--dim);border-bottom:1px solid rgba(255,255,255,.1);white-space:nowrap;text-align:left';
    var h = '<div style="max-height:400px;overflow:auto">';
    h += '<table style="width:100%;border-collapse:collapse;font-size:12px">';
    h += '<tr><th style="' + sh + '">原字体</th><th style="' + sh + '">目标</th><th style="' + sh + '">行距</th><th style="' + sh + '">影响文件</th></tr>';
    changes.forEach(function(c) {
      h += '<tr>';
      h += '<td style="' + s + ';font-weight:600">' + html(c.old_name) + '<div style="color:var(--dim);font-size:11px;font-weight:400;white-space:normal;max-width:300px;word-break:break-all">' + html(c.old_path) + '</div></td>';
      h += '<td style="' + s + ';color:var(--accent)">' + html(c.new_font_name || '不改') + '</td>';
      h += '<td style="' + s + ';color:var(--accent)">' + (c.line_spacing ? html(c.line_spacing) : '不改') + '</td>';
      h += '<td style="' + s + ';color:var(--dim)" title="' + html(c.prefab_files.join("\n")) + '">' + c.prefab_files.length + ' 个</td>';
      h += '</tr>';
    });
    h += '</table></div>';
    showConfirm({title:"确认修改 " + changes.length + " 种字体", message:h, html:true}).then(function(ok) {
      if (ok) fontExecute(changes);
    });
  }

  function fontExecute(changes) {
    if (state.busy) return;
    var requestGeneration = ++state.requestGeneration;
    state.busy = true;
    _incRunning();
    _incTabRunning("prefab");
    _clearFontLog();
    var logEl = panel.querySelector("#font_log");
    if (logEl) setTimeout(function() { logEl.scrollIntoView({behavior:"smooth", block:"nearest"}); }, 100);
    _fontLog("开始修改字体引用...");
    apiPost("/api/prefab/font-modify", {paths:fontScanPaths, changes:changes}).then(function(data) {
      if (requestGeneration !== state.requestGeneration) return;
      _fontLog("修改完成，共修改 " + data.total + " 个文件");
      _showToast("修改完成，共修改 " + data.total + " 个文件");
    }).catch(function(error) {
      if (requestGeneration !== state.requestGeneration) return;
      _fontLog("修改失败：" + error.message);
      _showToast("字体修改失败：" + error.message);
    }).finally(function() {
      if (requestGeneration !== state.requestGeneration) return;
      state.busy = false;
      _decRunning();
      _decTabRunning("prefab");
    });
  }

  function mutateDraft(url, body, errorPrefix) {
    if (state.busy) return Promise.resolve();
    var requestGeneration = ++state.requestGeneration;
    state.busy = true;
    state.dragPayload = null;
    renderAtlas();
    return apiPost(url, body).then(function(data) {
      if (requestGeneration === state.requestGeneration) setDraft(data.draft);
    }).catch(function(error) {
      if (requestGeneration !== state.requestGeneration) return;
      appendPrefabLog("error", errorPrefix + "：" + error.message);
      _showToast(errorPrefix + "：" + error.message);
    }).finally(function() {
      if (requestGeneration !== state.requestGeneration) return;
      state.busy = false;
      renderAtlas();
    });
  }

  function planDrop(payload, targetGroupId) {
    if (!state.draft || !selectedPrefab() || !isPlannable() || state.busy || payload.kind !== "groups") return;
    var hasLockedGroup = payload.sourceGroupIds.some(function(groupId) {
      return selectedPlans().some(function(plan) {
        var copyItem = state.draft.copies[plan.copy_id];
        var image = state.draft.images[plan.source_image_id];
        return copyItem && copyItem.status === "success" && image && image.source_group_id === groupId;
      });
    });
    if (hasLockedGroup) {
      _showToast("该源组包含已复制成功的计划，不能重新指定目标");
      return;
    }
    if (payload.sourceGroupIds.indexOf(targetGroupId) !== -1) {
      _showToast("目标图集组不能是当前源图集组");
      return;
    }
    mutateDraft("/api/prefab/atlas/plan-groups", {
      draft_id:state.draft.id,
      prefab_id:state.selectedPrefabId,
      target_group_id:targetGroupId,
      source_group_ids:payload.sourceGroupIds
    }, "创建迁移计划失败");
  }

  function renamePlan(input) {
    if (!state.draft || !isPlannable() || state.busy) return;
    var plan = state.draft.plans[input.dataset.planId];
    if (!plan) return;
    var copyItem = state.draft.copies[plan.copy_id];
    var targetName = input.value.trim();
    if (!targetName) {
      _showToast("目标名称不能为空");
      input.focus();
      return;
    }
    input.value = targetName;
    if (copyItem && targetName === copyItem.target_name) return;
    if (copyItem && copyItem.status === "success") return;
    mutateDraft("/api/prefab/atlas/rename", {
      draft_id:state.draft.id,
      plan_id:input.dataset.planId,
      target_name:targetName
    }, "修改目标名称失败");
  }

  function removePlan(planId) {
    if (!state.draft || !isPlannable() || state.busy) return;
    var plan = state.draft.plans[planId];
    var copyItem = plan && state.draft.copies[plan.copy_id];
    if (!plan || (copyItem && copyItem.status === "success")) return;
    mutateDraft("/api/prefab/atlas/remove-plan", {draft_id:state.draft.id, plan_id:planId}, "删除迁移计划失败");
  }

  function refreshPrefabs() {
    if (!state.draft || state.busy) return;
    mutateDraft("/api/prefab/atlas/refresh-prefabs", {draft_id:state.draft.id}, "刷新预制失败");
  }

  function refreshAfterTask(operation, previousDraft, outputPath, taskId, requestGeneration) {
    var finished = false;
    var controller = null;

    function finalize() {
      if (finished) return;
      finished = true;
      if (controller) controller.abort();
      if (requestGeneration !== state.requestGeneration) return;
      state.busy = false;
      renderAtlas();
    }

    function applyOutcome(outcome) {
      if (finished) return;
      finished = true;
      if (controller) controller.abort();
      if (requestGeneration !== state.requestGeneration) return;
      if (!outcome.ok) {
        appendPrefabLog("error", "任务失败：" + (outcome.error || "未知错误"));
        _showToast("任务失败：" + (outcome.error || "未知错误"));
        state.busy = false;
        renderAtlas();
        return;
      }
      var result = outcome.result;
      if (result && result.stage === "completed") {
        setDraft(null);
        var path = result.txt_path || outputPath || "";
        appendPrefabLog("success", path ? "图集引用修改完成，记录文件：" + path : "图集引用修改已完成");
        _showToast("图集引用修改已完成");
      } else {
        setDraft(result);
        _showToast(operation === "copy" ? "资源复制任务已结束" : operation === "resolve" ? "最终引用解析任务已结束" : "预制修改任务已结束");
      }
      state.busy = false;
      renderAtlas();
    }

    function fetchDraft(attempt) {
      controller = new AbortController();
      var timer = setTimeout(function() { controller.abort(); }, 10000);
      var url = operation === "rewrite" ? "/api/prefab/atlas/task-result" : "/api/prefab/atlas/draft/get";
      var body = operation === "rewrite" ? {task_id: taskId} : {draft_id: previousDraft.id};
      fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body),
        signal: controller.signal
      }).then(function(response) {
        return response.json().then(function(data) {
          if (!response.ok || data.error) throw new Error(data.error || "请求失败");
          return data;
        });
      }).then(function(data) {
        clearTimeout(timer);
        if (operation === "rewrite") {
          applyOutcome({ok: data.ok, result: data.result, error: data.error});
        } else {
          applyOutcome({ok: true, result: data.draft});
        }
      }).catch(function(error) {
        clearTimeout(timer);
        if (finished) return;
        if (attempt < 2) {
          setTimeout(function() { fetchDraft(attempt + 1); }, 300);
        } else {
          appendPrefabLog("error", "刷新任务结果失败：" + error.message);
          _showToast("刷新任务结果失败：" + error.message + "。已保留任务前草稿。");
          finalize();
        }
      });
    }

    // 延迟 300ms 让 SSE 连接完全关闭后再读取草稿，避免 WebView2 fetch 挂起
    setTimeout(function() {
      fetchDraft(0);
    }, 300);
  }

  function runAtlasTask(operation) {
    if (!state.draft || state.busy) return;
    var draft = state.draft;
    var confirmations = {
      copy: {
        title: "确认复制图集资源",
        message: "将按当前计划复制 PNG 和对应 meta。复制成功的文件不会因放弃草稿而自动删除，是否继续？",
        confirmText: "开始复制"
      },
      rewrite: {
        title: "确认修改预制引用",
        message: (function() {
          var eligible = values(draft.plans).filter(function(plan) {
            return plan.resolution && plan.resolution.status === "success"
              && (!plan.rewrite || plan.rewrite.status !== "success");
          });
          var prefabIds = {};
          var occurrence = 0;
          var manualCount = 0;
          eligible.forEach(function(plan) {
            prefabIds[plan.prefab_id] = true;
            var refs = [];
            if (plan.reference_ids) {
              refs = values(draft.prefabs).filter(function(p) {
                return p.id === plan.prefab_id;
              })[0];
              refs = refs ? refs.references.filter(function(r) {
                return plan.reference_ids.indexOf(r.id) !== -1;
              }) : [];
            }
            refs.forEach(function(r) { occurrence += r.count || 1; });
            if (plan.kind === "manual") manualCount++;
          });
          return "将修改 " + Object.keys(prefabIds).length + " 个 prefab、" + eligible.length +
            " 种旧引用、共 " + occurrence + " 处 m_Sprite" +
            (manualCount ? "（其中手动指定 " + manualCount + " 项）" : "") +
            "。未解析成功的计划会保留在草稿中，是否继续？";
        })(),
        confirmText: "确认修改",
        danger: true
      }
    };
    var confirmationGeneration = state.requestGeneration;
    var confirmation = confirmations[operation] ? showConfirm(confirmations[operation]) : Promise.resolve(true);
    confirmation.then(function(confirmed) {
      if (!confirmed || state.busy || confirmationGeneration !== state.requestGeneration || !state.draft || state.draft.id !== draft.id) return;
      var requestGeneration = ++state.requestGeneration;
      state.busy = true;
      _clearAtlasLog();
      renderAtlas();
      var labels = {copy:"图集资源复制", resolve:"图集最终引用解析", rewrite:"图集预制引用修改"};
      runTask("/api/prefab/atlas/" + operation, {draft_id:draft.id}, null, "atlas_log", labels[operation], function(outputPath, taskId) {
        if (requestGeneration !== state.requestGeneration) return;
        if (!taskId) {
          state.busy = false;
          renderAtlas();
          return;
        }
        refreshAfterTask(operation, draft, outputPath, taskId, requestGeneration);
      });
    });
  }

  panel.addEventListener("click", function(event) {
    var selectableText = event.target.closest(".atlas-prefab-name,.atlas-group-name,.atlas-plan-target,.atlas-manual-source,.atlas-manual-selected,.atlas-manual-atlas-item,.atlas-manual-sprite-item");
    if (selectableText && window.getSelection && window.getSelection().toString()) {
      event.preventDefault();
      return;
    }
    var target = event.target.closest("[data-action]");
    if (!target || !panel.contains(target)) return;
    var action = target.dataset.action;
    if (action === "set-prefab-mode") {
      setMode(target.dataset.mode);
    } else if (action === "browse-prefab-files") {
      if (state.mode !== "clear-text") return;
      if (window.pywebview && pywebview.api && pywebview.api.browseFile) {
        pywebview.api.browseFile("*.prefab").then(function(path) { if (path) dispatchPaths([path]); });
      }
    } else if (action === "browse-prefab-dir") {
      if (window.pywebview && pywebview.api && pywebview.api.browseDir) {
        pywebview.api.browseDir("").then(function(path) { if (path) dispatchPaths([path]); });
      }
    } else if (action === "select-atlas-prefab") {
      state.selectedPrefabId = target.dataset.prefabId;
      renderAtlas();
    } else if (action === "remove-atlas-plan") {
      removePlan(target.dataset.planId);
    } else if (action === "discard-atlas-draft") {
      discardDraft(state.draft.id, true);
    } else if (action === "run-atlas-copy") {
      runAtlasTask("copy");
    } else if (action === "run-atlas-resolve") {
      runAtlasTask("resolve");
    } else if (action === "run-atlas-rewrite") {
      runAtlasTask("rewrite");
    } else if (action === "open-manual-picker") {
      openManualPicker(target.dataset.referenceId);
    } else if (action === "close-manual-picker") {
      closeManualPicker();
    } else if (action === "pick-manual-atlas") {
      var picker = state.manualPicker;
      if (!picker) return;
      picker.selectedAtlasId = target.dataset.atlasId;
      picker.selectedSpriteId = "";
      picker.spriteFilter = "";
      renderManualPicker();
    } else if (action === "pick-manual-sprite") {
      var picker2 = state.manualPicker;
      if (!picker2) return;
      picker2.selectedSpriteId = target.dataset.spriteId;
      renderManualPicker();
    } else if (action === "confirm-manual-picker") {
      confirmManualPicker();
    } else if (action === "refresh-atlas-catalog") {
      refreshAtlasCatalog();
    } else if (action === "add-manual-group") {
      openAddGroupPicker();
    } else if (action === "close-add-group-picker") {
      closeAddGroupPicker();
    } else if (action === "pick-add-group") {
      var agp = state.addGroupPicker;
      if (!agp) return;
      agp.selectedGroupId = target.dataset.groupId;
      renderAddGroupPicker();
    } else if (action === "confirm-add-group") {
      confirmAddGroup();
    } else if (action === "font-preview") {
      fontPreview();
    } else if (action === "refresh-prefabs") {
      refreshPrefabs();
    }
  });

  panel.addEventListener("change", function(event) {
    var target = event.target;
    if (target.dataset.action === "rename-atlas-plan") renamePlan(target);
  });

  panel.addEventListener("input", function(event) {
    var target = event.target;
    if (target.id === "atlas_add_group_filter") {
      if (state.addGroupPicker) {
        state.addGroupPicker.filter = target.value;
        renderAddGroupPicker();
      }
      return;
    }
    var picker = state.manualPicker;
    if (!picker) return;
    if (target.id === "atlas_manual_atlas_filter") {
      picker.atlasFilter = target.value;
      renderManualPicker();
    } else if (target.id === "atlas_manual_sprite_filter") {
      picker.spriteFilter = target.value;
      renderManualPicker();
    }
  });

  panel.addEventListener("dragstart", function(event) {
    var dragEl = event.target.closest("[data-drag-kind]");
    if (!dragEl || !panel.contains(dragEl)) return;
    var payload = dragEl.dataset.dragKind === "groups"
      ? {kind:"groups", sourceGroupIds:[dragEl.dataset.sourceGroupId]}
      : null;
    if (!payload || !isPlannable() || state.busy) {
      event.preventDefault();
      return;
    }
    state.dragPayload = payload;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/x-atlas-plan", JSON.stringify(payload));
  });

  panel.addEventListener("dragover", function(event) {
    var input = event.target.closest("#prefab_drop_input");
    if (input) {
      event.preventDefault();
      panel.querySelector("#prefab_dropzone").classList.add("is-dragover");
      return;
    }
    var group = event.target.closest("[data-target-group-id]");
    if (group && state.dragPayload) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      group.classList.add("is-dragover");
    }
  });

  panel.addEventListener("dragleave", function(event) {
    var dropzone = event.target.closest("#prefab_dropzone");
    if (dropzone && !dropzone.contains(event.relatedTarget)) dropzone.classList.remove("is-dragover");
    var group = event.target.closest("[data-target-group-id]");
    if (group && !group.contains(event.relatedTarget)) group.classList.remove("is-dragover");
  });

  panel.addEventListener("drop", function(event) {
    var input = event.target.closest("#prefab_drop_input");
    if (input) {
      event.preventDefault();
      panel.querySelector("#prefab_dropzone").classList.remove("is-dragover");
      consumeNativeDrop(event);
      return;
    }
    var group = event.target.closest("[data-target-group-id]");
    if (!group) return;
    event.preventDefault();
    group.classList.remove("is-dragover");
    var payload = state.dragPayload;
    if (!payload) {
      try { payload = JSON.parse(event.dataTransfer.getData("application/x-atlas-plan")); } catch (ignore) {}
    }
    if (payload) planDrop(payload, group.dataset.targetGroupId);
    state.dragPayload = null;
  });

  panel.addEventListener("dragend", function() {
    state.dragPayload = null;
    panel.querySelectorAll(".is-dragover").forEach(function(element) { element.classList.remove("is-dragover"); });
  });

  function openManualPicker(referenceId) {
    if (!state.manualPicker || state.manualPicker.referenceId !== referenceId) {
      state.manualPicker = {
        referenceId: referenceId,
        prefabId: prefabIdForReference(referenceId) || state.selectedPrefabId,
        atlasFilter: "",
        selectedAtlasId: "",
        spriteFilter: "",
        selectedSpriteId: ""
      };
    } else {
      state.manualPicker.atlasFilter = "";
      state.manualPicker.spriteFilter = "";
    }
    var existingPlan = manualPlanForReference(referenceId);
    if (existingPlan && existingPlan.target_atlas_id) {
      state.manualPicker.selectedAtlasId = existingPlan.target_atlas_id;
      state.manualPicker.selectedSpriteId = findSpriteIdForPlan(existingPlan);
    }
    renderManualPicker();
  }

  function findSpriteIdForPlan(plan) {
    if (!state.draft) return "";
    var atlas = state.draft.atlases[plan.target_atlas_id];
    if (!atlas) return "";
    for (var i = 0; i < atlas.sprites.length; i++) {
      if (atlas.sprites[i].name === plan.target_sprite_name) return atlas.sprites[i].id;
    }
    return "";
  }

  function closeManualPicker() {
    state.manualPicker = null;
    var overlay = panel.querySelector("#atlas_manual_overlay");
    if (overlay) overlay.classList.remove("show");
  }

  function openAddGroupPicker() {
    state.addGroupPicker = { filter: "", selectedGroupId: "" };
    renderAddGroupPicker();
  }

  function closeAddGroupPicker() {
    state.addGroupPicker = null;
    var overlay = panel.querySelector("#atlas_add_group_overlay");
    if (overlay) overlay.classList.remove("show");
  }

  function renderAddGroupPicker() {
    var overlay = panel.querySelector("#atlas_add_group_overlay");
    if (!overlay || !state.addGroupPicker) return;
    overlay.classList.add("show");
    var draft = state.draft;
    if (!draft) return;
    var prefab = selectedPrefab();
    var sourceGroupIds = {};
    if (prefab) {
      prefab.references.forEach(function(ref) {
        if (ref.source_group_id) sourceGroupIds[ref.source_group_id] = true;
      });
      (prefab.manual_group_ids || []).forEach(function(gid) {
        sourceGroupIds[gid] = true;
      });
    }
    var filter = (state.addGroupPicker.filter || "").trim().toLowerCase();
    var allGroups = values(draft.groups);
    var filtered = allGroups.filter(function(group) {
      if (sourceGroupIds[group.id]) return false;
      if (!filter) return true;
      return group.name.toLowerCase().indexOf(filter) !== -1
        || group.relative_path.toLowerCase().indexOf(filter) !== -1;
    }).sort(function(a, b) {
      return a.relative_path.localeCompare(b.relative_path);
    });
    var listEl = overlay.querySelector("#atlas_add_group_list");
    var selectedId = state.addGroupPicker.selectedGroupId;
    listEl.innerHTML = filtered.map(function(group) {
      var selected = group.id === selectedId ? " selected" : "";
      return '<button class="atlas-manual-atlas-item' + selected + '" data-action="pick-add-group" data-group-id="' + html(group.id) + '">' +
        '<span class="atlas-manual-atlas-name">' + html(group.name) + '</span>' +
        '<span class="atlas-manual-atlas-path">' + html(group.relative_path) + '</span>' +
        '</button>';
    }).join("") || '<div class="atlas-manual-empty">没有可添加的图集组</div>';
    var confirmBtn = overlay.querySelector("#atlas_add_group_confirm");
    var selectedLabel = overlay.querySelector("#atlas_add_group_selected");
    if (confirmBtn) confirmBtn.disabled = !selectedId;
    if (selectedLabel) {
      var selGroup = selectedId ? draft.groups[selectedId] : null;
      selectedLabel.textContent = selGroup ? "已选: " + selGroup.relative_path : "";
    }
    var filterInput = overlay.querySelector("#atlas_add_group_filter");
    if (filterInput && filterInput.value !== (state.addGroupPicker.filter || "")) {
      filterInput.value = state.addGroupPicker.filter || "";
    }
  }

  function confirmAddGroup() {
    var picker = state.addGroupPicker;
    if (!picker || !picker.selectedGroupId || !state.draft || state.busy) return;
    mutateDraft("/api/prefab/atlas/add-manual-group", {
      draft_id: state.draft.id,
      prefab_id: state.selectedPrefabId,
      group_id: picker.selectedGroupId
    }, "添加图集组失败").then(function() {
      closeAddGroupPicker();
    });
  }

  function renderManualPicker() {
    var overlay = panel.querySelector("#atlas_manual_overlay");
    if (!overlay || !state.manualPicker) return;
    overlay.classList.add("show");
    var draft = state.draft;
    if (!draft) return;
    var picker = state.manualPicker;
    var prefab = prefabById(picker.prefabId || state.selectedPrefabId);
    var reference = null;
    if (prefab) {
      for (var i = 0; i < prefab.references.length; i++) {
        if (prefab.references[i].id === picker.referenceId) { reference = prefab.references[i]; break; }
      }
    }
    var summaryEl = overlay.querySelector("#atlas_manual_summary");
    summaryEl.innerHTML = reference
      ? '<div class="atlas-manual-source"><span class="atlas-ref-info">源引用：' + html(reference.sprite_name || "未知") +
        ' · ' + html(reference.guid) + '/' + html(reference.file_id) + (reference.count > 1 ? ' ×' + html(reference.count) : '') + '</span>' +
        '<span class="atlas-ref-hint">将替换当前 prefab 中该引用的全部 ' + html(reference.count) + ' 处</span></div>'
      : '<div class="atlas-manual-source">源引用不存在</div>';

    var atlases = values(draft.atlases);
    var atlasFilter = (picker.atlasFilter || "").trim().toLowerCase();
    var filteredAtlases = atlases.filter(function(atlas) {
      if (!atlasFilter) return true;
      return atlas.name.toLowerCase().indexOf(atlasFilter) !== -1
        || atlas.relative_path.toLowerCase().indexOf(atlasFilter) !== -1;
    }).sort(function(a, b) { return a.relative_path.localeCompare(b.relative_path); });
    var atlasListEl = overlay.querySelector("#atlas_manual_atlas_list");
    atlasListEl.innerHTML = filteredAtlases.map(function(atlas) {
      var selected = atlas.id === picker.selectedAtlasId ? " selected" : "";
      var excluded = atlas.status !== "ready" ? " excluded" : "";
      return '<button class="atlas-manual-atlas-item' + selected + excluded + '" data-action="pick-manual-atlas" data-atlas-id="' + html(atlas.id) + '"' + (atlas.status !== "ready" ? " disabled" : "") + '>' +
        '<span class="atlas-manual-atlas-name">' + html(atlas.name) + '</span>' +
        '<span class="atlas-manual-atlas-path">' + html(atlas.relative_path) + '</span>' +
        (atlas.status !== "ready" ? '<span class="atlas-manual-atlas-error">' + html(atlas.error || "不可选") + '</span>' : "") +
        '</button>';
    }).join("") || '<div class="atlas-manual-empty">没有匹配的图集</div>';

    var atlasFilterInput = overlay.querySelector("#atlas_manual_atlas_filter");
    if (atlasFilterInput && atlasFilterInput.value !== (picker.atlasFilter || "")) {
      atlasFilterInput.value = picker.atlasFilter || "";
    }
    var spriteInput = overlay.querySelector("#atlas_manual_sprite_filter");
    var spriteListEl = overlay.querySelector("#atlas_manual_sprite_list");
    var selectedAtlas = draft.atlases[picker.selectedAtlasId];
    spriteInput.disabled = !selectedAtlas;
    if (spriteInput.value !== (picker.spriteFilter || "")) {
      spriteInput.value = picker.spriteFilter || "";
    }
    if (!selectedAtlas) {
      spriteInput.value = "";
      picker.spriteFilter = "";
      spriteListEl.innerHTML = '<div class="atlas-manual-empty">请先在左侧选择目标图集</div>';
    } else {
      var spriteFilter = (picker.spriteFilter || "").trim().toLowerCase();
      if (!spriteFilter) {
        spriteListEl.innerHTML = '<div class="atlas-manual-empty">输入 Sprite 名称开始搜索</div>';
      } else {
        var matches = selectedAtlas.sprites.filter(function(sprite) {
          return sprite.name.toLowerCase().indexOf(spriteFilter) !== -1;
        }).sort(function(a, b) { return a.name.localeCompare(b.name); });
        var shown = matches.slice(0, 100);
        spriteListEl.innerHTML = shown.map(function(sprite) {
          var selected = sprite.id === picker.selectedSpriteId ? " selected" : "";
          return '<button class="atlas-manual-sprite-item' + selected + '" data-action="pick-manual-sprite" data-sprite-id="' + html(sprite.id) + '">' +
            '<span class="atlas-manual-sprite-name">' + html(sprite.name) + '</span>' +
            '<span class="atlas-manual-sprite-id">fileID ' + html(sprite.file_id) + ' · ' + html(selectedAtlas.guid.slice(0, 8)) + '</span></button>';
        }).join("") || '<div class="atlas-manual-empty">没有匹配的 Sprite</div>';
        if (matches.length > 100) {
          var more = document.createElement("div");
          more.className = "atlas-manual-empty";
          more.textContent = "仅显示前 100 条，请继续输入以缩小范围（共 " + matches.length + " 条）";
          spriteListEl.appendChild(more);
        }
      }
    }

    var selectedEl = overlay.querySelector("#atlas_manual_selected");
    var selectedSprite = null;
    if (selectedAtlas) {
      for (var j = 0; j < selectedAtlas.sprites.length; j++) {
        if (selectedAtlas.sprites[j].id === picker.selectedSpriteId) { selectedSprite = selectedAtlas.sprites[j]; break; }
      }
    }
    selectedEl.textContent = selectedAtlas && selectedSprite
      ? "已选：" + selectedAtlas.name + "/" + selectedSprite.name
      : "";
    var confirmBtn = overlay.querySelector("#atlas_manual_confirm");
    confirmBtn.disabled = !(selectedAtlas && selectedSprite) || state.busy;
  }

  function confirmManualPicker() {
    var picker = state.manualPicker;
    if (!picker || !picker.selectedSpriteId || !state.draft || state.busy) return;
    mutateDraft("/api/prefab/atlas/plan-manual-reference", {
      draft_id: state.draft.id,
      prefab_id: picker.prefabId || state.selectedPrefabId,
      reference_id: picker.referenceId,
      target_sprite_id: picker.selectedSpriteId
    }, "创建手动指定计划失败").then(function() {
      if (state.manualPicker && state.manualPicker.referenceId === picker.referenceId) closeManualPicker();
    });
  }

  function refreshAtlasCatalog() {
    if (!state.draft || state.busy) return;
    var requestGeneration = ++state.requestGeneration;
    state.busy = true;
    renderManualPicker();
    apiPost("/api/prefab/atlas/refresh-atlas-catalog", {draft_id: state.draft.id}).then(function(data) {
      if (requestGeneration !== state.requestGeneration) return;
      setDraft(data.draft);
      var removed = data.removed || [];
      if (removed.length) {
        appendPrefabLog("warn", "已移除 " + removed.length + " 个失效的手动指定计划");
        _showToast("已移除 " + removed.length + " 个失效的手动指定计划");
      } else {
        _showToast("图集索引已刷新");
      }
      renderManualPicker();
    }).catch(function(error) {
      if (requestGeneration !== state.requestGeneration) return;
      appendPrefabLog("error", "刷新图集索引失败：" + error.message);
      _showToast("刷新图集索引失败：" + error.message);
    }).finally(function() {
      if (requestGeneration !== state.requestGeneration) return;
      state.busy = false;
      renderManualPicker();
      renderAtlas();
    });
  }

  function consumeNativeDrop(event) {
    try {
      if (window.chrome && chrome.webview && chrome.webview.postMessageWithAdditionalObjects && event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length) {
        chrome.webview.postMessageWithAdditionalObjects("FilesDropped", event.dataTransfer.files);
        var retries = 0;
        function tryConsume() {
          fetch("/api/prefab/consume-dropped", {method:"POST"}).then(function(response) { return response.json(); }).then(function(data) {
            if (data.count > 0) dispatchPaths(data.paths);
            else if (retries < 15) { retries++; setTimeout(tryConsume, 200); }
            else _showToast("获取路径超时，请使用上方按钮选择");
          }).catch(function(error) {
            _showToast("获取拖拽路径失败：" + error.message);
          });
        }
        setTimeout(tryConsume, 200);
      } else {
        _showToast(state.mode === "atlas" ? "请使用上方的“选择文件夹”按钮" : "请使用上方按钮选择文件或文件夹");
      }
    } catch (error) {
      _showToast("拖拽路径获取失败");
    }
  }

  renderAtlas();
}

function startPrefabClear(paths) {
  console.log("startPrefabClear:", JSON.stringify(paths));
  var summary = document.getElementById("prefab_summary");
  if (!summary) return;
  summary.textContent = "正在扫描 " + paths.length + " 个路径...";
  summary.hidden = false;
  fetch("/api/prefab/scan", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({paths:paths})
  }).then(function(response) { return response.json(); }).then(function(data) {
    if (data.error) { summary.hidden = true; _showToast(data.error); return; }
    if (data.count === 0) { summary.hidden = true; _showToast("未找到 .prefab 文件"); return; }
    summary.textContent = "已扫描 " + data.count + " 个 .prefab 文件，正在清理...";
    runTask("/api/prefab/clear-text", {files:data.files}, null, "prefab_log", null, function() {
      var current = document.getElementById("prefab_summary");
      if (current) {
        current.textContent = "清理完成";
        setTimeout(function() { current.hidden = true; }, 3000);
      }
    });
  }).catch(function(error) {
    summary.hidden = true;
    _showToast("扫描失败：" + error.message);
  });
}
