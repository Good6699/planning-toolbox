function buildTranslateTab(panel) {
  const api_url = config.tr_api_url||"https://api.openai.com/v1/chat/completions";
  const model = config.tr_model||"gpt-4o-mini";
  const src_lang = config.tr_src_lang||"zh";
  const out = config.tr_out_dir||"";
  const prompt = config.tr_prompt||"你是一位专业的游戏本地化翻译专家。请将以下文本从{src_lang}翻译为{tgt_lang}。\n\n## 核心规则\n1. 术语一致性：游戏专有名词（技能名、道具名、地名、角色名、系统术语）保持统一。\n2. 格式保护：所有格式占位符、标签、转义序列必须原样保留，不可修改或删除。\n3. 长短控制：英文→中文控制在原文60%-100%字符数；中文→英文自然地道。\n4. 风格统一：遵循目标语言的游戏本地化惯例。\n\n## 格式保护规则（必须原样保留）\n- XML/HTML标签：如 <Item size=25 style=1 cfgid={0}>\n- 格式占位符：{0}, {1}, %s, %d, %f\n- 语言标记：::SC::, ::EN::, ::TH::\n- 转义序列：\\n, \\t\n- 颜色/富文本标签：[c], [/c], [color=red]\n\n## 输出格式\n严格按照以下格式返回：\n编号|翻译1|翻译2|翻译3...\n每行一条，不要包含任何额外说明、解释或空行。";
  panel.innerHTML = `
    <div class="translate-layout tr-layout">
      <div class="tr-main">
        <div class="card">
          <div class="card-title">翻译文件</div>
          <div class="form-group">
            <label>文件路径</label>
            <div class="flex-row">
              <input type="text" id="tr_src" placeholder="输入要翻译的 Excel 文件路径，支持 .xlsx" style="flex:1" autocomplete="off">
              <button class="btn btn-normal" data-action="browse-tr-src"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-tr-src" title="打开文件所在目录"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
          <div class="form-group">
            <label>参考文件</label>
            <div class="flex-row">
              <input type="text" id="tr_ref" placeholder="可选，输入已有的翻译文件用于术语参考" style="flex:1" autocomplete="off">
              <button class="btn btn-normal" data-action="browse-tr-ref"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-tr-ref" title="打开文件所在目录"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-title">语言列设置</div>
          <div class="form-group">
            <label>源语言列</label>
            <div class="flex-row">
              <input type="text" id="tr_src_lang" value="${escapeHtml(src_lang)}" placeholder="输入 Excel 中代表原文的列名，如 zh、SC、::SC::" style="width:6.25rem">
              <button class="btn btn-normal btn-sm" data-action="tr-lang-adv-settings" title="语言ID高级设置" style="font-size:16px;padding:0 8px;line-height:1">⚙</button>
            </div>
          </div>
          <div class="form-group">
            <label>目标语言</label>
            <div class="check-group" id="tr_tgt_langs"></div>
          </div>
        </div>
        <div class="action-center">
          <button class="btn btn-primary" data-action="run-translate" data-output="#tr_out">开始翻译</button>
        </div>
      </div>
      <div class="tr-side">
        <div class="card">
          <div class="section-label">API 设置</div>
          <div class="form-group">
            <label>API URL</label>
            <input type="text" id="tr_api_url" value="${escapeHtml(api_url)}" placeholder="输入翻译接口地址，需以 http:// 或 https:// 开头">
          </div>
          <div class="form-group">
            <label>API Key</label>
            <input type="password" id="tr_api_key" placeholder="输入翻译服务的 API Key">
          </div>
          <div class="form-group">
            <label>模型</label>
            <input type="text" id="tr_model" value="${escapeHtml(model)}" placeholder="输入翻译使用的模型名，如 gpt-4o-mini、deepseek-chat">
          </div>
        </div>
        <div class="card">
          <div class="section-label">输出设置</div>
          <div class="form-group">
            <label>输出目录</label>
            <div class="flex-row">
              <input type="text" id="tr_out" value="${escapeHtml(out)}" placeholder="输入翻译结果的保存目录，不存在会自动创建" style="flex:1">
              <button class="btn btn-normal" data-action="browse-tr-out"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg></button>
              <button class="btn btn-normal" data-action="open-tr-out" title="打开输出目录"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M2 6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v1"/><path d="M2 12l3 7A2 2 0 006.3 19h12.4a2 2 0 001.8-1.5L24 12H2z"/></svg></button>
            </div>
          </div>
          <div class="form-group">
            <label>翻译 Prompt</label>
            <textarea id="tr_prompt" placeholder="输入翻译指令，支持 {src_lang} 和 {tgt_lang} 变量">${escapeHtml(prompt)}</textarea>
          </div>
          <div class="form-group">
            <label>批处理量</label>
            <input type="number" id="tr_batch" value="${config.tr_batch_size||20}" placeholder="每次发送给 API 的条目数，正整数，默认 20">
          </div>
        </div>
      </div>
      <div class="tr-log-wrap">
        <div class="card">
          <div class="card-header compact">
            <span style="font-weight:600">执行日志</span>
          </div>
          <div class="log" id="tr_log"><div class="log-anchor"></div></div>
        </div>
      </div>
    </div>
  `;
  if (config.tr_src_history?.length) document.getElementById("tr_src").value = config.tr_src_history[0];
  if (config.tr_ref_history?.length) document.getElementById("tr_ref").value = config.tr_ref_history[0];
  if (config.tr_api_key) document.getElementById("tr_api_key").value = config.tr_api_key;
  initSuggest("tr_src", config.tr_src_history||[]);
  initSuggest("tr_ref", config.tr_ref_history||[]);
  S.translate.logEl = document.getElementById("tr_log");
  enablePathDrop("tr_src", { mode: "path" });
  enablePathDrop("tr_ref", { mode: "path" });
  enablePathDrop("tr_out", { mode: "path" });
  _initDirHistory("tr_src", "tr_src_history");
  _initDirHistory("tr_ref", "tr_ref_history");
  _initDirHistory("tr_out", "tr_out_dir");
  // 从高级设置加载语言列表，填充复选框
  fetch("/api/translate/lang-id-map").then(r=>r.json()).then(d => {
    const data = d.data || {};
    const names = Object.keys(data).sort();
    const cg = document.getElementById("tr_tgt_langs");
    cg.innerHTML = names.map(n => {
      return `<label><input type="checkbox" value="${escapeHtml(n)}"> ${escapeHtml(n)}</label>`;
    }).join("");
  });
}
function runTranslate() {
  triggerUpdateCheck();
  const tgtLangs = [];
  document.querySelectorAll("#tr_tgt_langs input:checked").forEach(cb=>tgtLangs.push(cb.value));
  const apiKey = document.getElementById("tr_api_key").value.trim();
  const batchValue = Number(document.getElementById("tr_batch").value);
  const body = {
    src_path:document.getElementById("tr_src").value.trim(),
    ref_path:document.getElementById("tr_ref").value.trim(),
    api_url:document.getElementById("tr_api_url").value.trim(),
    api_key:apiKey,
    model:document.getElementById("tr_model").value.trim(),
    src_lang:document.getElementById("tr_src_lang").value.trim(),
    tgt_langs:tgtLangs,
    out_dir:document.getElementById("tr_out").value.trim(),
    prompt:document.getElementById("tr_prompt").value.trim(),
    batch_size:batchValue
  };
  if (!body.src_path) { _showToast("请选择要翻译的 Excel 文件"); document.getElementById("tr_src").focus(); return; }
  if (!body.src_lang) { _showToast("请输入源语言列"); document.getElementById("tr_src_lang").focus(); return; }
  if (!body.tgt_langs.length) { _showToast("请选择目标语言"); return; }
  if (!body.api_url) { _showToast("请输入 API URL"); document.getElementById("tr_api_url").focus(); return; }
  try {
    const parsedUrl = new URL(body.api_url);
    if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") throw new Error();
  } catch (_) {
    _showToast("请输入有效的 HTTP 或 HTTPS API URL");
    document.getElementById("tr_api_url").focus();
    return;
  }
  if (!body.api_key) { _showToast("请输入 API Key"); document.getElementById("tr_api_key").focus(); return; }
  if (!body.model) { _showToast("请输入模型名称"); document.getElementById("tr_model").focus(); return; }
  if (!body.out_dir) { _showToast("请选择输出目录"); document.getElementById("tr_out").focus(); return; }
  if (!body.prompt) { _showToast("请输入翻译 Prompt"); document.getElementById("tr_prompt").focus(); return; }
  if (!Number.isInteger(body.batch_size) || body.batch_size < 1) {
    _showToast("批处理量必须是大于等于 1 的整数");
    document.getElementById("tr_batch").focus();
    return;
  }
  saveConfig({tr_api_url:body.api_url,tr_model:body.model,tr_src_lang:body.src_lang,tr_out_dir:body.out_dir,tr_prompt:body.prompt,tr_batch_size:body.batch_size,tr_api_key:apiKey});
  runTask("/api/translate/run", body, document.querySelector("[data-action='run-translate']"), "tr_log");
}
function openTrLangAdvSettings() {
  if (!trLangAdvModal) {
    trLangAdvModal = document.createElement("div");
    trLangAdvModal.id = "tr_lang_adv_modal";
    trLangAdvModal.style.cssText = "position:fixed;top:4rem;left:50%;transform:translateX(-50%);width:36rem;max-height:44rem;background:var(--panel);border:1px solid rgba(255,255,255,.08);border-radius:1.25rem;z-index:1000;display:none;flex-direction:column;box-shadow:0 1.25rem 3.75rem rgba(0,0,0,.5)";
    trLangAdvModal.innerHTML = `
      <div style="padding:1.25rem 1.5rem;border-bottom:1px solid rgba(255,255,255,.05);display:flex;justify-content:space-between;align-items:center">
        <span style="font-weight:600;font-size:1rem">语言ID高级设置</span>
        <button class="btn btn-normal btn-sm" data-action="tr-lang-close-adv">✕</button>
      </div>
      <div style="padding:0.75rem 1.5rem;font-size:0.8rem;color:var(--dim)">配置每个语言对应的Excel表头ID，用于自动匹配语言列。例如：中文 → SC, ::SC::, CHS</div>
      <div style="padding:0 1.5rem;overflow:auto;flex:1">
        <table style="width:100%;border-collapse:collapse;font-size:0.85rem" id="tr_lang_adv_table">
          <thead>
            <tr style="border-bottom:1px solid rgba(255,255,255,.08)">
              <th style="text-align:left;padding:0.5rem;color:var(--sub)">语言名称</th>
              <th style="text-align:left;padding:0.5rem;color:var(--sub)">匹配ID（逗号分隔）</th>
              <th style="width:3rem"></th>
            </tr>
          </thead>
          <tbody id="tr_lang_adv_body"></tbody>
        </table>
        <div style="text-align:center;padding:0.75rem 0">
          <button class="btn btn-normal btn-sm" data-action="tr-lang-add-row" style="font-size:13px">+ 新增语言</button>
        </div>
      </div>
      <div class="flex-row" style="padding:0.875rem 1.5rem;border-top:1px solid rgba(255,255,255,.05);justify-content:flex-end;gap:8px">
        <button class="btn btn-normal" data-action="tr-lang-close-adv">取消</button>
        <button class="btn btn-primary" data-action="tr-lang-save-adv">保存</button>
      </div>
    `;
    document.body.appendChild(trLangAdvModal);
    trLangAdvModal.addEventListener("click", e => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;
      const a = btn.dataset.action;
      if (a === "tr-lang-add-row") {
        const tbody = document.getElementById("tr_lang_adv_body");
        const row = document.createElement("tr");
        row.style.borderBottom = "1px solid rgba(255,255,255,.05)";
        row.innerHTML = `
          <td style="padding:0.375rem"><input type="text" class="tr-lang-name" placeholder="输入语言显示名，如 中文、英文" style="width:6rem;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:0.3rem 0.5rem;color:var(--text);font-size:0.8rem"></td>
          <td style="padding:0.375rem"><input type="text" class="tr-lang-ids" placeholder="输入匹配 Excel 表头的 ID，逗号分隔" style="width:100%;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:0.3rem 0.5rem;color:var(--text);font-size:0.8rem"></td>
          <td style="padding:0.375rem;text-align:center"><button class="btn btn-normal btn-sm" style="font-size:12px;padding:0 6px;color:var(--danger)" data-action="tr-lang-del-row">✕</button></td>
        `;
        tbody.appendChild(row);
      } else if (a === "tr-lang-del-row") {
        const tr = btn.closest("tr");
        if (tr) tr.remove();
      }
    });
  }
  fetch("/api/translate/lang-id-map").then(r=>r.json()).then(d => {
    const data = d.data || {};
    const tbody = document.getElementById("tr_lang_adv_body");
    tbody.innerHTML = "";
    Object.keys(data).sort().forEach(lang => {
      const ids = (data[lang] || []).join(", ");
      const row = document.createElement("tr");
      row.style.borderBottom = "1px solid rgba(255,255,255,.05)";
      row.innerHTML = `
        <td style="padding:0.375rem"><input type="text" class="tr-lang-name" value="${escapeHtml(lang)}" placeholder="输入语言显示名，如 中文、英文" style="width:6rem;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:0.3rem 0.5rem;color:var(--text);font-size:0.8rem"></td>
        <td style="padding:0.375rem"><input type="text" class="tr-lang-ids" value="${escapeHtml(ids)}" placeholder="输入匹配 Excel 表头的 ID，逗号分隔" style="width:100%;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:0.3rem 0.5rem;color:var(--text);font-size:0.8rem"></td>
        <td style="padding:0.375rem;text-align:center"><button class="btn btn-normal btn-sm" style="font-size:12px;padding:0 6px;color:var(--danger)" data-action="tr-lang-del-row">✕</button></td>
      `;
      tbody.appendChild(row);
    });
  });
  trLangAdvModal.style.display = "flex";
  // 添加关闭点击外部支持
  const overlay = document.getElementById("tr_lang_adv_overlay");
  if (!overlay) {
    const o = document.createElement("div");
    o.id = "tr_lang_adv_overlay";
    o.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.3);z-index:999;display:none";
    o.addEventListener("click", function() { closeTrLangAdvSettings(); });
    document.body.appendChild(o);
  }
  document.getElementById("tr_lang_adv_overlay").style.display = "block";
}
function closeTrLangAdvSettings() {
  if (trLangAdvModal) trLangAdvModal.style.display = "none";
  const o = document.getElementById("tr_lang_adv_overlay");
  if (o) o.style.display = "none";
}
function saveTrLangAdvSettings() {
  const rows = document.querySelectorAll("#tr_lang_adv_body tr");
  const data = {};
  for (const tr of rows) {
    const nameInput = tr.querySelector(".tr-lang-name");
    const idsInput = tr.querySelector(".tr-lang-ids");
    if (!nameInput || !idsInput) continue;
    const name = nameInput.value.trim();
    const idsText = idsInput.value.trim();
    if (!name && !idsText) continue;
    if (!name || !idsText) {
      _showToast("语言名称和匹配 ID 必须同时填写");
      (name ? idsInput : nameInput).focus();
      return;
    }
    const ids = idsText.split(",").map(s => s.trim()).filter(Boolean);
    if (!ids.length) {
      _showToast("请至少填写一个有效的匹配 ID");
      idsInput.focus();
      return;
    }
    if (Object.prototype.hasOwnProperty.call(data, name)) {
      _showToast("语言名称不能重复：" + name);
      nameInput.focus();
      return;
    }
    data[name] = ids;
  }
  const btn = document.querySelector("[data-action='tr-lang-save-adv']");
  const orig = btn.textContent;
  btn.textContent = "保存中...";
  btn.disabled = true;
  fetch("/api/translate/lang-id-map", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({lang_id_map: data})
  }).then(r=>r.json()).then(d => {
    if (d.ok) {
      closeTrLangAdvSettings();
    } else {
      _showToast(d.error || "语言设置保存失败");
    }
  }).catch(error => {
    _showToast("语言设置保存失败：" + error.message);
  }).finally(() => {
    btn.textContent = orig;
    btn.disabled = false;
  });
}