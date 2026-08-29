---
name: "wechat-mindmap-export"
description: "把腾讯文档/企业微信文档的思维导图（doc.weixin.qq.com/mind/...）导出为本地 Markdown 文件。Invoke when user gives a mind map link and asks to 导出/转MD/转markdown/保存到本地."
---

# 腾讯文档思维导图导出为 Markdown

把腾讯文档/企业微信文档的思维导图导出为本地 `.md` 文件（含图片）。

## 适用场景

- 用户给一个 `https://doc.weixin.qq.com/mind/m4_xxx?scode=xxx` 链接，要求"导出"、"转成 MD"、"保存到本地"
- 文档是 **mind 类型**（URL 路径含 `/mind/`）

## 核心原理

思维导图内容**不在 HTML 里**（canvas 渲染），必须走数据接口：

```
https://doc.weixin.qq.com/dop-api/mind/data/get?id=<padId>&shortcut_id=&req_from=1&normal=1&scode=<scode>&subId=<subId>
```

- `<padId>` = URL 中 `/mind/` 后面的 ID（如 `m4_AQkAcwb8AEkCNAGHmbnVWR9OXbq8n`）
- `<scode>` = URL 的 `scode` 参数值
- `<subId>` = 可选；从浏览器 Network 里首次请求的响应 URL 中拿到（不传一般也能返回）
- 接口需要**登录态 cookie**，直接用 `curl`/`WebFetch` 抓不到（返回空白壳），必须用带会话的浏览器执行 `fetch`（`credentials: 'include'`）

## 执行流程

### Step 1: 解析 URL 提取参数

```
padId = url 中 /mind/ 之后、? 之前的字符串
scode = url 查询参数 scode
```

### Step 2: 浏览器打开文档，确认登录态

- 用 WebBrowserTool 打开完整 URL
- 页面能出现思维导图工具栏（"脑图模式/大纲模式/插入/结构"等文字）即加载成功
- 若出现登录墙/空白壳，说明浏览器会话未登录企业微信，需提示用户登录后重试
- 页面上的弹窗/遮罩（如"取消/确定"、"移除图标"）不影响数据抓取，可忽略

### Step 3: 在页面上下文 fetch 数据接口

在浏览器 tab 里执行 JavaScript：

```js
(async () => {
  const url = 'https://doc.weixin.qq.com/dop-api/mind/data/get?id=<padId>&shortcut_id=&req_from=1&normal=1&scode=<scode>&subId=<subId>';
  const resp = await fetch(url, { credentials: 'include' });
  window.__mindRaw = await resp.text();
  return 'len=' + window.__mindRaw.length;
})()
```

- 返回 `len` 为几千到几万即成功
- 若从 Network 面板看到实际请求带 `subId`，补上更稳妥

### Step 4: 在页面上下文解析并生成 Markdown

```js
(() => {
  const json = JSON.parse(window.__mindRaw);
  const fd = JSON.parse(json.data.collab_client_vars.fileData);  // fileData 是字符串，需二次 parse
  const root = fd.content[0].rootTopic;

  // 渲染标题：可能是字符串，也可能是富文本对象（children→paragraph→text）
  function richTitle(t) {
    if (typeof t === 'string') return t;
    if (t && t.children) {
      return t.children.map(p => (p.children || []).map(c => c.text || '').join('')).join(' ');
    }
    return '';
  }

  let md = '';
  const imgMap = {};
  function walk(node, level) {
    if (!node) return;
    const indent = '  '.repeat(level);
    md += indent + '- ' + richTitle(node.title).replace(/\n/g, ' ') + '\n';
    if (node.images && node.images.length) {
      node.images.forEach((img, i) => {
        if (img && img.url) {
          const name = 'img_' + node.id + (i ? '_' + i : '') + '.png';
          imgMap[name] = img.url;
          md += indent + '  - ![' + name + '](images/' + name + ')\n';  // 必须带 images/ 前缀
        }
      });
    }
    if (node.children && node.children.attached) {
      node.children.attached.forEach(ch => walk(ch, level + 1));
    }
  }
  walk(root, 0);
  window.__mindMd = md;
  window.__mindImgs = imgMap;
  return JSON.stringify({ mdLen: md.length, imgCount: Object.keys(imgMap).length });
})()
```

**节点结构速查：**

```
rootTopic: { id, title, children: { attached: [...] }, images: [{ url, w, h, ow, oh }] }
```

- `title` 可能是字符串，也可能是**富文本对象**（`type: document`，`children: [{type: paragraph, children: [{type: text, text: "..."}]}]`），导出时提取所有 `text` 拼起来
- 富文本标题导出成 `[object Object]` 就是没做这一步（常见错误）
- 图片 `url` 是腾讯 CDN（`wdcdn.qpic.cn`），可直接下载，无需登录

### Step 5: 取回 md 内容，保存到本地

- 在页面里把 `window.__mindMd` 用 `btoa(unescape(encodeURIComponent(md)))` 编码为 base64 取回（避免超长文本截断/转义问题），本地再解码
- 输出目录默认：用户指定；未指定时放在文档所在文件夹下，名为 `思维导图_<标题>/`
- 生成 `特权卡_思维导图.md`（标题从数据 `title` 字段取）+ `images/` 子目录

### Step 6: 下载图片

- 用 `images_manifest.json`（本地保存的 `{文件名: URL}` 映射）逐张下载到 `images/` 目录
- 直接用 Python `urllib` 下载即可（`ssl` 上下文可放宽证书校验）

### Step 7: 校验

- 正则提取 md 里所有 `![...](...)` 引用，确认每个目标文件都存在
- 确认无 `[object Object]`、`!Z[` 等残留
- 确认图片路径带 `images/` 前缀

## 可复用脚本

目录内提供 `export_mindmap.py`：

- 用法：`python export_mindmap.py <mind_raw.json> <输出目录>`
- 输入：Step 3 保存的完整 API 响应 JSON（含 `data.collab_client_vars.fileData`）
- 输出：`<标题>_思维导图.md` + `images/`（自动下载全部图片）+ `images_manifest.json`
- 脚本内部完成了 Step 4-6 的解析、md 生成、图片下载和校验

## 常见坑

| 坑 | 说明 |
|----|------|
| 图片路径漏 `images/` 前缀 | 引用写成 `](img_x.png)`，文件却在 `images/` 下 → 加载失败 |
| 富文本标题变成 `[object Object]` | `title` 是对象不是字符串，要递归提取 `text` |
| 直接 curl/WebFetch 拿不到数据 | 接口需要登录 cookie，必须用浏览器会话 fetch |
| 长文本被截断 | 用 base64 编码传递页面内生成的 md |
| 页面有弹窗 | 弹窗不影响数据抓取，忽略即可；不要陷入关弹窗的循环 |
