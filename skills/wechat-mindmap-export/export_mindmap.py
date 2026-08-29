# -*- coding: utf-8 -*-
"""
腾讯文档思维导图导出脚本
用法: python export_mindmap.py <mind_raw.json> <输出目录> [--no-download]

输入: 通过浏览器 fetch 保存的完整 API 响应 JSON
      (https://doc.weixin.qq.com/dop-api/mind/data/get?... 的响应体)
输出: <标题>_思维导图.md + images/ (自动下载全部图片) + images_manifest.json
"""
import base64
import json
import os
import re
import ssl
import sys
import urllib.request


def rich_title(t):
    """标题可能是字符串，也可能是富文本对象(children->paragraph->text)"""
    if isinstance(t, str):
        return t
    if isinstance(t, dict) and t.get("children"):
        parts = []
        for p in t["children"]:
            if isinstance(p, dict) and p.get("children"):
                parts.append("".join(c.get("text", "") for c in p["children"] if isinstance(c, dict)))
        return " ".join(parts)
    return ""


def build_markdown(root):
    """遍历思维导图树，生成 markdown 文本和图片清单"""
    md_lines = []
    img_map = {}

    def walk(node, level):
        if not node:
            return
        indent = "  " * level
        title = rich_title(node.get("title", "")).replace("\n", " ")
        md_lines.append(f"{indent}- {title}")
        for i, img in enumerate(node.get("images") or []):
            if img and img.get("url"):
                name = f"img_{node['id']}{'_' + str(i) if i else ''}.png"
                img_map[name] = img["url"]
                md_lines.append(f"{indent}  - ![{name}](images/{name})")
        for child in (node.get("children") or {}).get("attached") or []:
            walk(child, level + 1)

    walk(root, 0)
    return "\n".join(md_lines), img_map


def main():
    if len(sys.argv) < 3:
        print("用法: python export_mindmap.py <mind_raw.json> <输出目录> [--no-download]")
        sys.exit(1)

    raw_path = sys.argv[1]
    out_dir = sys.argv[2]
    download = "--no-download" not in sys.argv

    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    data = raw.get("data", {})
    title = data.get("title", "思维导图")
    file_data_str = (data.get("collab_client_vars") or {}).get("fileData")
    if not file_data_str:
        print("错误: 未找到 collab_client_vars.fileData，请确认这是 mind/data/get 接口的完整响应")
        sys.exit(1)

    fd = json.loads(file_data_str)
    root = fd["content"][0]["rootTopic"]

    md, img_map = build_markdown(root)
    header = f"# {title}（思维导图导出）\n\n> 来源：腾讯文档思维导图，导出时间 2026-08-05\n\n"
    md_full = header + md + "\n"

    os.makedirs(out_dir, exist_ok=True)
    img_dir = os.path.join(out_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    md_path = os.path.join(out_dir, f"{title}_思维导图.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_full)
    print(f"已保存: {md_path}")

    manifest_path = os.path.join(out_dir, "images_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(img_map, f, ensure_ascii=False, indent=2)
    print(f"已保存: {manifest_path} ({len(img_map)} 张图片)")

    if download and img_map:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ok, fail = 0, 0
        for name, url in img_map.items():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                    data_b = resp.read()
                with open(os.path.join(img_dir, name), "wb") as f:
                    f.write(data_b)
                ok += 1
            except Exception as e:
                fail += 1
                print(f"下载失败 {name}: {e}")
        print(f"图片下载完成: ok={ok} fail={fail}")

    # 校验: 所有引用都存在
    md_text = open(md_path, encoding="utf-8").read()
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md_text)
    missing = [r for r in refs if not os.path.exists(os.path.join(out_dir, r))]
    if missing:
        print("校验失败，缺失文件:", missing)
        sys.exit(2)
    for bad in ["[object Object]", "!Z[", "](img_"]:
        if bad in md_text:
            print(f"警告: 残留 {bad!r}")
    print(f"校验通过: {len(refs)} 处图片引用全部存在")


if __name__ == "__main__":
    main()
