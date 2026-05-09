#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SVN 提交记录查询工具
功能：查询指定时间范围内包含指定关键词的提交记录，输出版本号
用法：python svn_query.py [选项]
"""

import subprocess
import sys
import argparse
import os
import xml.etree.ElementTree as ET
from datetime import datetime

# ─── 编码配置（必须在第一次 print 之前执行）──────────────────────────
if not sys.stdout.isatty():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
# ────────────────────────────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(
        description="查询 SVN 指定时间范围内包含关键词的提交版本号",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 查询 2024-01-01 到 2024-03-31 之间包含 "bugfix" 的提交
  python svn_query.py --url https://svn.example.com/repo --start 2024-01-01 --end 2024-03-31 --keyword bugfix

  # 查询当前目录 SVN 仓库，多个关键词（任意匹配）
  python svn_query.py --start 2024-06-01 --end 2024-12-31 --keyword "fix" --keyword "hotfix"

  # 查询当前目录 SVN 仓库，多个关键词（全部匹配）
  python svn_query.py --start 2024-06-01 --end 2024-12-31 --keyword "fix" --keyword "login" --match-all

  # 指定路径，输出详细信息，保存到文件
  python svn_query.py --url https://svn.example.com/repo --start 2024-01-01 --end 2024-12-31 --keyword release --verbose --output result.txt

  # 只输出版本号（方便管道处理）
  python svn_query.py --start 2024-01-01 --end 2024-12-31 --keyword fix --only-rev
        """
    )

    parser.add_argument(
        "--url", "-u",
        default=".",
        help="SVN 仓库 URL 或本地工作副本路径（默认：当前目录 .）"
    )
    parser.add_argument(
        "--start", "-s",
        required=True,
        help="开始日期，格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS"
    )
    parser.add_argument(
        "--end", "-e",
        required=True,
        help="结束日期，格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS"
    )
    parser.add_argument(
        "--keyword", "-k",
        action="append",
        dest="keywords",
        default=[],
        help="搜索关键词（可多次指定，默认任意匹配；配合 --match-all 改为全部匹配）"
    )
    parser.add_argument(
        "--match-all",
        action="store_true",
        help="多个关键词时要求全部匹配（默认：任意一个匹配即可）"
    )
    parser.add_argument(
        "--author", "-a",
        default=None,
        help="按提交者过滤（可选）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细信息（版本号、作者、时间、提交说明）"
    )
    parser.add_argument(
        "--only-rev",
        action="store_true",
        help="只输出版本号，每行一个（方便管道处理）"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="最多返回条数（0 = 不限制）"
    )
    parser.add_argument(
        "--svn-path",
        default="svn",
        help="svn 可执行文件路径（默认：svn，即系统 PATH 中的 svn）"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出结果到指定文件（留空则只输出到屏幕）"
    )

    return parser.parse_args()


def format_svn_date(date_str):
    """将用户输入的日期格式化为 SVN 接受的格式 {YYYY-MM-DD}"""
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt == "%Y-%m-%d":
                return "{" + dt.strftime("%Y-%m-%d") + "}"
            else:
                return "{" + dt.strftime("%Y-%m-%dT%H:%M:%S") + "}"
        except ValueError:
            continue
    print(f"[错误] 日期格式不正确：{date_str}，请使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS", file=sys.stderr)
    sys.exit(1)


def run_svn_log(svn_path, url, start_rev, end_rev, limit):
    """执行 svn log 命令，返回 XML 输出"""
    cmd = [
        svn_path, "log",
        "--xml",
        "-r", f"{start_rev}:{end_rev}",
        url
    ]
    if limit > 0:
        cmd += ["--limit", str(limit * 10)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )
    except FileNotFoundError:
        print(f"[错误] 找不到 svn 命令：{svn_path}", file=sys.stderr)
        print("请确认已安装 SVN 客户端，或通过 --svn-path 指定 svn 可执行文件路径", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("[错误] svn log 命令超时（120秒），请检查网络或仓库连接", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"[错误] svn log 执行失败：\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    return result.stdout


def parse_log_xml(xml_content):
    """解析 svn log XML 输出，返回日志条目列表"""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"[错误] 解析 SVN 日志 XML 失败：{e}", file=sys.stderr)
        sys.exit(1)

    entries = []
    for entry in root.findall("logentry"):
        rev = entry.get("revision", "")
        author_el = entry.find("author")
        date_el = entry.find("date")
        msg_el = entry.find("msg")

        author = author_el.text.strip() if author_el is not None and author_el.text else ""
        date_raw = date_el.text.strip() if date_el is not None and date_el.text else ""
        msg = msg_el.text.strip() if msg_el is not None and msg_el.text else ""

        date_display = date_raw
        if date_raw:
            try:
                dt = datetime.strptime(date_raw[:19], "%Y-%m-%dT%H:%M:%S")
                date_display = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        entries.append({
            "rev": rev,
            "author": author,
            "date": date_display,
            "msg": msg
        })

    return entries


def match_keywords(entry, keywords, match_all):
    """检查日志条目是否匹配关键词"""
    if not keywords:
        return True

    msg_lower = entry["msg"].lower()
    results = [kw.lower() in msg_lower for kw in keywords]

    if match_all:
        return all(results)
    else:
        return any(results)


def build_output(args, matched):
    """构建输出内容字符串"""
    lines = []

    if not args.only_rev:
        lines.append(f"[SVN 查询]")
        lines.append(f"  仓库/路径 : {args.url}")
        lines.append(f"  时间范围  : {args.start}  ->  {args.end}")
        if args.keywords:
            mode = "全部匹配" if args.match_all else "任意匹配"
            lines.append(f"  关键词    : {args.keywords}  ({mode})")
        else:
            lines.append(f"  关键词    : （不过滤，显示全部）")
        if args.author:
            lines.append(f"  提交者    : {args.author}")
        lines.append(f"  SVN 命令  : {args.svn_path}")
        lines.append("-" * 60)
        lines.append("")

    if not matched:
        lines.append("未找到符合条件的提交记录。")
        return "\n".join(lines)

    if args.only_rev:
        for entry in matched:
            lines.append(entry["rev"])
    elif args.verbose:
        lines.append(f"共找到 {len(matched)} 条匹配记录：")
        lines.append("")
        for entry in matched:
            lines.append(f"版本号 : r{entry['rev']}")
            lines.append(f"作者   : {entry['author']}")
            lines.append(f"时间   : {entry['date']}")
            lines.append(f"说明   : {entry['msg']}")
            lines.append("-" * 60)
    else:
        lines.append(f"共找到 {len(matched)} 条匹配记录：")
        lines.append("")
        lines.append(f"{'版本号':<10} {'作者':<15} {'时间':<22}  提交说明")
        lines.append("-" * 80)
        for entry in matched:
            msg_short = entry["msg"].replace("\n", " ")
            if len(msg_short) > 50:
                msg_short = msg_short[:47] + "..."
            lines.append(f"r{entry['rev']:<9} {entry['author']:<15} {entry['date']:<22}  {msg_short}")

    return "\n".join(lines)


def main():
    args = parse_args()

    # 格式化日期为 SVN revision 格式
    start_rev = format_svn_date(args.start)
    end_rev = format_svn_date(args.end)

    # 执行 svn log
    xml_content = run_svn_log(args.svn_path, args.url, start_rev, end_rev, args.limit)

    # 解析日志
    entries = parse_log_xml(xml_content)

    # 过滤
    matched = []
    for entry in entries:
        if args.author and entry["author"].lower() != args.author.lower():
            continue
        if not match_keywords(entry, args.keywords, args.match_all):
            continue
        matched.append(entry)

    # 限制数量
    if args.limit > 0:
        matched = matched[:args.limit]

    # 构建输出内容
    output_text = build_output(args, matched)

    # 输出到屏幕
    print(output_text)

    # 输出到文件
    if args.output:
        output_path = os.path.abspath(args.output)
        try:
            with open(args.output, "w", encoding="utf-8-sig", newline="\r\n") as f:
                f.write(output_text)
            print(f"\n[文件已保存] {output_path}")
        except Exception as e:
            print(f"\n[警告] 保存文件失败：{e}", file=sys.stderr)


if __name__ == "__main__":
    main()
