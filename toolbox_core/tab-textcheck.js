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
