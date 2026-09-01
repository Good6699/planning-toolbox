function buildAssistTab(panel) {
  var state = { templateFile: null, targetFolder: null };
  var _running = false;

  panel.innerHTML = `
    <div class="workbench" style="display:flex;flex-direction:column;gap:12px">
      <div class="form-group" style="flex-direction:row;align-items:center;gap:12px">
        <label style="white-space:nowrap">操作模式</label>
        <div class="toggle-group" id="assist_mode_group">
          <button class="toggle-btn active" data-v="gen-meta">一键生成meta</button>
        </div>
      </div>

      <div class="flex-row" style="gap:8px">
        <button class="btn btn-normal" data-action="assist-browse-meta">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          选择 .meta 文件
        </button>
        <button class="btn btn-normal" data-action="assist-browse-folder">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>
          选择文件夹
        </button>
      </div>

      <div class="card" id="assist_dropzone" style="border:2px dashed var(--line);border-radius:var(--radius);padding:8px 16px;text-align:center;cursor:pointer;transition:border-color .2s,background .2s;position:relative">
        <input type="text" id="assist_drop" style="position:absolute;inset:0;width:100%;height:100%;background:transparent;border:none;outline:none;color:transparent;caret-color:transparent;font-size:1px;cursor:pointer" autocomplete="off">
        <div style="color:var(--dim);margin-bottom:8px;pointer-events:none">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:24px;height:24px">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </div>
        <div style="font-size:15px;color:var(--sub);margin-bottom:4px;pointer-events:none">将 .meta 文件或文件夹拖拽到此处</div>
        <div style="font-size:12px;color:var(--dim);pointer-events:none">或使用上方按钮选择</div>
        <div id="assist_preview_template" style="margin-top:10px;font-size:13px;color:var(--success);display:none"></div>
        <div id="assist_preview_folder" style="margin-top:4px;font-size:13px;color:var(--success);display:none"></div>
      </div>

      <input type="hidden" id="assist_meta_path">
      <input type="hidden" id="assist_folder_path">

      <div class="log-wrap" style="flex:1;min-height:200px">
        <div class="card-header compact" style="padding:0 0 4px 0"><span style="font-weight:600">执行日志</span></div>
        <div class="log" id="assist_log"><div class="log-anchor"></div></div>
      </div>
    </div>`;

  S.assist.logEl = document.getElementById("assist_log");

  // ── 导出全局函数供 core.js 全局 switch 回调 ──
  window._assistHandleFolder = function(path) {
    if (!path || _running) return;
    state.targetFolder = path;
    var pv = document.getElementById("assist_preview_folder");
    pv.innerHTML = "✓ 文件夹: " + path;
    pv.style.display = "block";
    _checkAutoRun();
  };

  // ── 监听 meta 路径隐藏输入变化 ──
  var metaPathInput = document.getElementById("assist_meta_path");
  var _lastMetaVal = "";
  function _pollMetaPath() {
    var v = metaPathInput.value;
    if (v !== _lastMetaVal) {
      _lastMetaVal = v;
      if (v && !_running) {
        if (!v.toLowerCase().endsWith(".meta")) {
          _showToast("请选择一个 .meta 文件");
          metaPathInput.value = "";
          _lastMetaVal = "";
          return;
        }
        state.templateFile = v;
        var pv = document.getElementById("assist_preview_template");
        pv.innerHTML = "✓ 模板: " + v;
        pv.style.display = "block";
        _checkAutoRun();
      }
    }
    if (!_running) setTimeout(_pollMetaPath, 300);
  }
  setTimeout(_pollMetaPath, 300);

  // ── 拖放区 ──
  var inputEl = document.getElementById("assist_drop");
  var dz = document.getElementById("assist_dropzone");
  enablePathDrop("assist_drop", {mode:"path"});

  inputEl.addEventListener("dragover", function(e) {
    e.preventDefault();
    dz.style.borderColor = "var(--accent)";
    dz.style.background = "rgba(94,162,255,.08)";
  });
  inputEl.addEventListener("dragleave", function() {
    dz.style.borderColor = "";
    dz.style.background = "";
  });
  inputEl.addEventListener("drop", function(e) {
    e.preventDefault();
    dz.style.borderColor = "";
    dz.style.background = "";
    if (_running) { _showToast("正在生成中，请等待完成"); return; }

    try {
      if (window.chrome && chrome.webview && chrome.webview.postMessageWithAdditionalObjects && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        chrome.webview.postMessageWithAdditionalObjects("FilesDropped", e.dataTransfer.files);
        var retries = 0;
        function tryConsume() {
          fetch("/api/assist/consume-dropped", {method:"POST"}).then(function(r){
            if (!r.ok) throw new Error("接口返回 " + r.status);
            return r.json();
          }).then(function(d){
            if (d.count > 0) {
              d.paths.forEach(function(p){ _handleDroppedPath(p); });
            } else if (retries < 15) {
              retries++;
              setTimeout(tryConsume, 200);
            } else {
              _showToast("获取路径超时，请使用浏览按钮");
            }
          }).catch(function(error) {
            _showToast("获取拖拽路径失败：" + error.message);
          });
        }
        setTimeout(tryConsume, 200);
      } else {
        _showToast("请使用按钮选择文件");
      }
    } catch(ex) {
      _showToast("拖拽路径获取失败");
    }
  });

  function _handleDroppedPath(path) {
    if (!path) return;
    if (path.toLowerCase().endsWith(".meta")) {
      state.templateFile = path;
      var pv = document.getElementById("assist_preview_template");
      pv.innerHTML = "✓ 模板: " + path;
      pv.style.display = "block";
    } else {
      state.targetFolder = path;
      var pv = document.getElementById("assist_preview_folder");
      pv.innerHTML = "✓ 文件夹: " + path;
      pv.style.display = "block";
    }
    _checkAutoRun();
  }

  // ── 自动执行 ──
  function _checkAutoRun() {
    if (_running) return;
    if (!state.templateFile || !state.targetFolder) {
      if (state.targetFolder && !state.templateFile) {
        _appendLog("info", "目标文件夹已就绪，请选择或拖入 .meta 模板文件");
      }
      return;
    }
    _running = true;
    _startGenMeta();
  }

  function _appendLog(cls, msg) {
    var log = document.getElementById("assist_log");
    if (!log) return;
    var line = document.createElement("div");
    if (cls) line.className = cls;
    line.textContent = msg;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  }

  function _startGenMeta() {
    runTask("/api/assist/run",
      {template: state.templateFile, folder: state.targetFolder},
      null, "assist_log",
      "一键生成meta",
      function() {
        state.templateFile = null;
        state.targetFolder = null;
        metaPathInput.value = "";
        _lastMetaVal = "";
        document.getElementById("assist_folder_path").value = "";
        document.getElementById("assist_preview_template").style.display = "none";
        document.getElementById("assist_preview_folder").style.display = "none";
        _appendLog("info", "任务已结束，请查看上方结果");
        _running = false;
        setTimeout(_pollMetaPath, 300);
      }
    );
  }
}
