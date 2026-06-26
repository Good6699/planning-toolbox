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