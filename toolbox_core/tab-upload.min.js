function buildUploadTab(panel) {
  panel.innerHTML = `
    <div class="workbench upload-layout">
      <div class="upload-main">
        <div class="card">
          <div class="card-title">源目录</div>
          <div class="flex-row">
            <input type="text" id="upload_src" placeholder="选择源目录" style="flex:1" autocomplete="off">
            <button class="btn btn-normal" data-action="browse-upload-src"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
            <button class="btn btn-normal" data-action="refresh-files" title="刷新文件列表"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0115.4-5.6L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 01-15.4 5.6L3 16"/></svg></button>
          </div>
        </div>
      </div>
      <div class="upload-side">
        <div class="card">
          <div class="section-label">目标设置</div>
          <div class="form-group">
            <label>SVN 目标目录</label>
            <div class="flex-row">
              <input type="text" id="upload_tgt" placeholder="选择目标 SVN 工作目录" style="flex:1" autocomplete="off">
              <button class="btn btn-normal" data-action="browse-upload-tgt"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
            </div>
          </div>
        </div>
      </div>
      <div class="upload-files-wrap">
        <div class="card">
          <div class="card-header compact">
            <div class="card-title">文件列表</div>
            <div class="flex-row">
              <button class="btn btn-normal btn-sm" data-action="select-all">全选</button>
              <button class="btn btn-normal btn-sm" data-action="select-none">取消全选</button>
            </div>
          </div>
          <div class="file-list" id="upload_files"></div>
        </div>
      </div>
      <div class="action-center">
        <button class="btn btn-primary" data-action="run-upload">上传到 SVN</button>
      </div>
      <div class="upload-log-wrap">
        <div class="card">
          <div class="card-header compact">
            <span style="font-weight:600">执行日志</span>
            <button class="btn btn-normal btn-sm" data-action="clear-changelist">清理changelist</button>
          </div>
          <div class="log" id="upload_log"><div class="log-anchor"></div></div>
        </div>
      </div>
    </div>
  `;
  if (config.src_dir_history?.length) document.getElementById("upload_src").value = config.src_dir_history[0];
  if (config.tgt_dir_history?.length) document.getElementById("upload_tgt").value = config.tgt_dir_history[0];
  initSuggest("upload_src", config.src_dir_history||[]);
  initSuggest("upload_tgt", config.tgt_dir_history||[]);
  S.upload.logEl = document.getElementById("upload_log");
  enablePathDrop("upload_src", { mode: "path", callback: refreshFiles });
  enablePathDrop("upload_tgt", { mode: "path" });
  let _srcTimer;
  document.getElementById("upload_src").addEventListener("input", ()=>{
    clearTimeout(_srcTimer);
    _srcTimer = setTimeout(refreshFiles, 300);
  });
  _initDirHistory("upload_src", "src_dir_history", refreshFiles);
  _initDirHistory("upload_tgt", "tgt_dir_history");
  const _src = document.getElementById("upload_src").value.trim();
  if (_src) refreshFiles();
}
function renderFileList(){
  const container = document.getElementById("upload_files");
  container.innerHTML = uploadFilesData.map((f,i)=>`
    <div class="file-item ${f._sel ? 'selected':''}" data-idx="${i}">
      <input type="checkbox" ${f._sel ? 'checked':''}>
      <div style="flex:1">${f.is_dir ? '📁':'📄'} ${f.name}</div>
      <div style="color:var(--dim);font-size:0.8125rem">${f.size} ${f.date}</div>
    </div>
  `).join("");
}
function selectAllFiles(v) { uploadFilesData.forEach(f => f._sel = v); renderFileList(); }
function runUpload() {
  triggerUpdateCheck();
  const src = document.getElementById("upload_src").value.trim();
  const tgt = document.getElementById("upload_tgt").value.trim();
  const files = uploadFilesData.filter(f => f._sel).map(f => ({name:f.name,path:f.path,is_dir:f.is_dir}));
  saveConfig({tgt_dir_history: [tgt, ...(config.tgt_dir_history||[]).filter(u=>u!==tgt)].slice(0,20)});
  runTask("/api/upload/run", {src_dir:src, tgt_dir:tgt, files}, document.querySelector("[data-action='run-upload']"), "upload_log");
}
async function refreshFiles() {
  const src = document.getElementById("upload_src").value.trim();
  if (!src) return;
  const r = await fetch("/api/files/list", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:src})});
  const d = await r.json();
  if (d.error) { await showAlert(d.error); return; }
  uploadFilesData = d.entries;
  renderFileList();
}
