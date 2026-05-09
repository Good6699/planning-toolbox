#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SVN 一键对比工具
用法:
  python svn_oneclick_compare.py -u <SVN URL> -s <开始日期> -e <结束日期> -o <输出文件>
  python svn_oneclick_compare.py --export -u <SVN URL> -s <开始日期> -e <结束日期> --export-dir <导出目录>

对比模式: 查询日期范围内的版本对，下载并对比 Excel 内容差异
导出模式: 下载日期范围内所有修改的文件
"""

import argparse
import os
import queue
import subprocess
import sys
import threading
import time
import re
import tempfile
import multiprocessing
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import urllib.parse

# psutil 可选导入（用于系统资源监控）
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    psutil = None
    _HAS_PSUTIL = False

# 日志级别控制
LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50
}

# 默认日志级别
LOG_LEVEL = LOG_LEVELS['INFO']

# 系统资源监控
class ResourceMonitor:
    def __init__(self):
        self.start_time = 0
        self.end_time = 0
        self.start_memory = 0
        self.end_memory = 0
        self.start_cpu = 0
        self.end_cpu = 0
    
    def start(self):
        self.start_time = time.time()
        if _HAS_PSUTIL:
            self.start_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            self.start_cpu = psutil.cpu_percent(interval=0.1)
        else:
            self.start_memory = 0
            self.start_cpu = 0
    
    def stop(self):
        self.end_time = time.time()
        if _HAS_PSUTIL:
            self.end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            self.end_cpu = psutil.cpu_percent(interval=0.1)
        else:
            self.end_memory = 0
            self.end_cpu = 0
    
    def get_stats(self):
        return {
            'time': self.end_time - self.start_time,
            'memory': self.end_memory - self.start_memory,
            'cpu': (self.end_cpu + self.start_cpu) / 2
        }

# 资源监控实例
_resource_monitor = ResourceMonitor()

# pandas 可选导入（用于高性能解析）
try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    pd = None
    _HAS_PANDAS = False

# openpyxl 可选导入（用于 read_only 模式）
try:
    from openpyxl import load_workbook
    _HAS_OPENPYXL = True
except ImportError:
    load_workbook = None
    _HAS_OPENPYXL = False

_IN_LOG = False

def _log(*a, level='INFO', **kw):
    global _IN_LOG
    if _IN_LOG:
        return
    if LOG_LEVELS.get(level, 20) < LOG_LEVEL:
        return
    _IN_LOG = True
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}][{level}]", *a, **kw, flush=True)
    finally:
        _IN_LOG = False
from io import BytesIO
from multiprocessing import Pool, cpu_count, Manager, Queue as MPQueue, Process
from typing import Any, Dict, List, Optional, Set, Tuple

from lxml import etree
from zipfile import ZipFile

# ═══════════════════════════════════════════════════════════════════════════════
# 编码修复：Windows 下 sys.stdout 默认是 cp936/GBK，SlikSvn 输出 UTF-8
# 强制 stdout 使用 UTF-8，确保所有中文 print 不乱码
# ═══════════════════════════════════════════════════════════════════════════════
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════════════════════
# 全局缓存
# ═══════════════════════════════════════════════════════════════════════════════
_diff_cache: Dict[Tuple[int, int], bool] = {}  # (cur, prv) → 是否有差异
_parsed_cache: Dict[str, dict] = {}  # 解析结果缓存（内存）
_cache_hits: int = 0
_cache_misses: int = 0
_byte_cache_hits: int = 0
_byte_cache_misses: int = 0

_CACHE_EXPIRY = 7 * 24 * 3600
_MAX_PARSED_CACHE_SIZE = 30

# 共享字符串缓存（CRC → parsed list），文件级缓存用于跨 worker 进程共享
_shared_strings_cache: Dict[int, List[str]] = {}
_MAX_SS_CACHE_SIZE = 5

def _ss_cache_path(crc: int) -> str:
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__ss_cache")
    return os.path.join(cache_dir, f"{crc}.pkl")

def _load_shared_strings(crc: int) -> Optional[List[str]]:
    if crc in _shared_strings_cache:
        return _shared_strings_cache[crc]
    cache_file = _ss_cache_path(crc)
    if os.path.exists(cache_file):
        try:
            import pickle
            with open(cache_file, "rb") as f:
                data = pickle.load(f)
            _shared_strings_cache[crc] = data
            return data
        except Exception:
            pass
    return None

def _save_shared_strings(crc: int, data: List[str]):
    global _shared_strings_cache
    _shared_strings_cache[crc] = data
    if len(_shared_strings_cache) > _MAX_SS_CACHE_SIZE:
        for k in list(_shared_strings_cache)[:-_MAX_SS_CACHE_SIZE]:
            del _shared_strings_cache[k]
    try:
        os.makedirs(os.path.dirname(_ss_cache_path(crc)), exist_ok=True)
        import pickle
        with open(_ss_cache_path(crc), "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass

def _trim_cache():
    global _parsed_cache
    if len(_parsed_cache) > _MAX_PARSED_CACHE_SIZE:
        keys_to_remove = list(_parsed_cache.keys())[:-(_MAX_PARSED_CACHE_SIZE//2)]
        for key in keys_to_remove:
            del _parsed_cache[key]

# ── per-file 配置 ─────────────────────────────────────────────────────────────
_CMP_FILE_SETTINGS: Dict[str, dict] = {}

def sanitize_filename(name: str) -> str:
    """
    清理文件名中的非法字符，并去除前后空格。
    非法字符：反斜杠 / 冒号 * ? " < > |
    """
    import re
    if not name:
        return ""
    # 去除前后空格
    name = name.strip()
    # 替换 \ / : * ? " < > | 为下划线
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    # 去除连续下划线合并为单个
    name = re.sub(r'_+', '_', name)
    # 去除首尾下划线
    name = name.strip('_')
    return name

_XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_SHEETDATA_TAG = "{%s}sheetData" % _XML_NS
_ROW_TAG = "{%s}row" % _XML_NS
_CELL_TAG = "{%s}c" % _XML_NS
_V_TAG = "{%s}v" % _XML_NS
_COL_RE = re.compile(r'^([A-Za-z]+)')


def _load_cmp_file_settings() -> None:
    """从 GUI 配置文件加载 cmp_file_settings 到全局变量"""
    global _CMP_FILE_SETTINGS
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svn_gui_config.json")
    if not os.path.isfile(config_file):
        return
    try:
        import json as _json
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = _json.load(f)
        _CMP_FILE_SETTINGS = cfg.get("cmp_file_settings", {})
        # 加载全局默认值到空文件名配置
        empty_settings = _CMP_FILE_SETTINGS.get("", {})
        empty_settings["cmp_title_rows"] = cfg.get("cmp_title_rows", "1")
        empty_settings["cmp_id_col"] = cfg.get("cmp_id_col", "::ID::")
        empty_settings["cmp_global_id_col"] = cfg.get("cmp_global_id_col", "")
        empty_settings["cmp_output_cols"] = cfg.get("cmp_output_cols", "")
        _CMP_FILE_SETTINGS[""] = empty_settings
        # 确保所有配置项都存在
        for name, settings in _CMP_FILE_SETTINGS.items():
            if "cmp_title_rows" not in settings:
                settings["cmp_title_rows"] = "1"
            if "cmp_id_col" not in settings:
                settings["cmp_id_col"] = "::ID::"
            if "cmp_global_id_col" not in settings:
                settings["cmp_global_id_col"] = ""
            if "cmp_output_cols" not in settings:
                settings["cmp_output_cols"] = ""
    except Exception as e:
        _log(f"[警告] 加载配置文件失败: {e}")
    # 确保空文件名配置存在（无专属配置文件的全局兜底）
    if "" not in _CMP_FILE_SETTINGS:
        _CMP_FILE_SETTINGS[""] = {
            "cmp_title_rows": "1",
            "cmp_id_col": "::ID::",
            "cmp_global_id_col": "",
            "cmp_output_cols": ""
        }


def _get_cmp_config(fname: str) -> Tuple[int, str, Optional[List[str]]]:
    """
    根据文件名（不含扩展名和路径）查找 cmp_file_settings 中的预设配置，
    找不到则用空文件名（""）配置作为全局兜底。
    返回: (title_rows, id_col, out_cols_list)
    """
    # 提取文件名（不含路径和扩展名）
    base_name = os.path.basename(fname)
    name = os.path.splitext(base_name)[0]
    # 首先尝试根据文件名查找配置
    s = _CMP_FILE_SETTINGS.get(name)
    # 如果找不到，使用空文件名配置
    if s is None:
        s = _CMP_FILE_SETTINGS.get("") or {}
    
    # 优先使用与文件名绑定的全局对比ID
    global_id_col = s.get("cmp_global_id_col", "")
    if global_id_col:
        tr = int(s.get("cmp_title_rows") or 1)
        ic = global_id_col  # 使用与文件名绑定的全局对比ID
        oc = s.get("cmp_output_cols") or ""
        out_list = None
        if oc.strip():
            out_list = [c.strip() for c in oc.split(",") if c.strip()]
        
        return tr, ic, out_list
    
    # 原逻辑：使用文件级别的对比ID
    tr = int(s.get("cmp_title_rows") or 1)
    ic = s.get("cmp_id_col") or "1"
    oc = s.get("cmp_output_cols") or ""
    out_list = None
    if oc.strip():
        out_list = [c.strip() for c in oc.split(",") if c.strip()]
    
    return tr, ic, out_list


# 临时文件目录：用于进程间传递大 bytes，避免 pickle 序列化开销
def _get_parse_cache_dir() -> str:
    """解析缓存目录"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "__parse_cache")


def _load_parse_from_disk(content_hash: str) -> Optional[dict]:
    """主进程从磁盘 pickle 缓存加载（避免在 worker 里做 I/O）"""
    cache_file = os.path.join(_get_parse_cache_dir(), f"{content_hash}.pkl")
    if os.path.exists(cache_file):
        # 检查缓存是否过期
        mtime = os.path.getmtime(cache_file)
        if time.time() - mtime < _CACHE_EXPIRY:
            try:
                import pickle
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
            except Exception:
                pass
    return None


def _safe_cache_key(cache_key: str) -> str:
    """将 cache_key 中的 Windows 非法文件名字符替换为安全字符"""
    # Windows 禁止: < > : " / \ | ? *
    for ch in '<>:"/\\|?*':
        cache_key = cache_key.replace(ch, '_')
    return cache_key


def _save_parse_to_disk(content_hash: str, parsed: dict) -> None:
    """主进程写入 pickle 缓存"""
    try:
        cache_dir = _get_parse_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        import pickle
        cache_file = os.path.join(cache_dir, f"{content_hash}.pkl")
        with open(cache_file, "wb") as f:
            pickle.dump(parsed, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        import traceback
        traceback.print_exc()
        _log(f"       [缓存] 写入失败 {content_hash}: {e}")


def _clear_parse_cache() -> int:
    """删除 __parse_cache/、__byte_cache/ 和 __ss_cache/ 三个目录，返回删除的文件数"""
    count = 0
    for sub in ("__parse_cache", "__byte_cache", "__ss_cache"):
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), sub)
        if not os.path.exists(cache_dir):
            continue
        try:
            for fname in os.listdir(cache_dir):
                os.remove(os.path.join(cache_dir, fname))
                count += 1
        except Exception:
            pass
    return count


def _get_byte_cache_dir() -> str:
    """下载字节缓存目录"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "__byte_cache")


def _load_byte_from_cache(fname: str, rev: int) -> Optional[bytes]:
    """从字节缓存加载（命中则跳过 SVN 下载），返回 None 表示未命中。
    仅查磁盘缓存，不保留内存副本（临时文件已承担存储职责）"""
    global _byte_cache_hits, _byte_cache_misses
    import hashlib
    safe_fname = hashlib.md5(fname.encode()).hexdigest()[:12]
    cache_dir = _get_byte_cache_dir()
    cache_file = os.path.join(cache_dir, f"{safe_fname}_{rev}.bin")
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if time.time() - mtime < _CACHE_EXPIRY:
            try:
                with open(cache_file, "rb") as f:
                    data = f.read()
                    _byte_cache_hits += 1
                    return data
            except Exception:
                pass
    _byte_cache_misses += 1
    return None


def _save_byte_to_cache(fname: str, rev: int, data: bytes) -> None:
    """下载成功后写入磁盘字节缓存（不保留内存副本）"""
    try:
        import hashlib
        safe_fname = hashlib.md5(fname.encode()).hexdigest()[:12]
        cache_dir = _get_byte_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{safe_fname}_{rev}.bin")
        with open(cache_file, "wb") as f:
            f.write(data)
    except Exception:
        pass


def warm_parse_cache() -> int:
    """
    启动时预加载磁盘缓存到内存，减少重复解析。
    受 _MAX_PARSED_CACHE_SIZE 限制，最多预加载上限个条目。
    返回预加载的缓存条目数。
    """
    global _parsed_cache
    cache_dir = _get_parse_cache_dir()
    if not os.path.exists(cache_dir):
        return 0
    count = 0
    max_warm = _MAX_PARSED_CACHE_SIZE // 2  # 预加载不超过缓存上限的一半
    try:
        import pickle
        for fname in os.listdir(cache_dir):
            if not fname.endswith(".pkl"):
                continue
            if len(_parsed_cache) >= max_warm:
                break
            fpath = os.path.join(cache_dir, fname)
            try:
                with open(fpath, "rb") as f:
                    data = pickle.load(f)
                cache_key = fname[:-4]  # 去掉 .pkl
                _parsed_cache[cache_key] = data
                count += 1
            except Exception:
                pass
    except Exception:
        pass
    return count


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════
def _svn(cmd: List[str], timeout: int = 60, svn_user: str = "", svn_pass: str = "") -> subprocess.CompletedProcess:
    """统一执行 SVN 命令，Windows 下隐藏窗口"""
    # 添加认证参数
    cmd_with_auth = cmd.copy()
    if svn_user:
        cmd_with_auth.extend(["--username", svn_user])
    if svn_pass:
        cmd_with_auth.extend(["--password", svn_pass])
    cmd_with_auth.extend(["--non-interactive", "--trust-server-cert"])
    
    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
    process = subprocess.Popen(cmd_with_auth, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd_with_auth, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(cmd_with_auth, 1, stdout, stderr)


def _get_svn_path() -> str:
    """返回 svn 命令路径"""
    # 尝试多个可能的 SVN 路径
    possible_paths = [
        "C:\\Program Files\\SlikSvn\\bin\\svn.exe",
        "C:\\Program Files (x86)\\SlikSvn\\bin\\svn.exe",
        "C:\\Program Files\\TortoiseSVN\\bin\\svn.exe",
        "C:\\Program Files (x86)\\TortoiseSVN\\bin\\svn.exe"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            _log(f"  使用 SVN 路径: {path}", level='DEBUG')
            return path
    # 如果都找不到，尝试使用系统 PATH 中的 svn
    _log("  未找到 SVN 可执行文件，尝试使用系统 PATH", level='WARNING')
    return "svn"


def _svn_log_range(start_date: str, end_date: str) -> str:
    """SVN log -r 的日期范围参数。
    svn log -r {date} 把日期解释为当天 00:00:00 UTC，所以结束日期要加一天才能覆盖全天。
    """
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    return f"{{{start_date}}}:{{{end_dt.strftime('%Y-%m-%d')}}}"


def _content_hash(raw_bytes: bytes) -> str:
    """快速计算内容哈希（取前64KB，兼顾速度和准确性）"""
    import hashlib
    sample = raw_bytes[:65536]
    return hashlib.md5(sample).hexdigest()


# ── _normalize_value 缓存 ────────────────────────────────────────────────────
_NORM_CACHE: Dict[str, str] = {}
_NORM_CACHE_MAX = 10000

def _normalize_value(val: str) -> str:
    """规范化数值字符串，带 LRU 缓存"""
    if not val or not isinstance(val, str):
        return val
    val = val.strip()
    if not val:
        return val
    if val in _NORM_CACHE:
        return _NORM_CACHE[val]
    try:
        f = float(val)
        normalized = "%g" % f
        if "e" in val.lower() or "E" in val:
            normalized = normalized.replace("E", "e")
        result = normalized
    except (ValueError, OverflowError):
        result = val
    if len(_NORM_CACHE) < _NORM_CACHE_MAX:
        _NORM_CACHE[val] = result
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: 查询文件及其版本对
# ═══════════════════════════════════════════════════════════════════════════════
def step1_query_file_pairs(
    svn_url: str, start_date: str, end_date: str,
    author: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    svn_user: str = "",
    svn_pass: str = "") -> Tuple[Dict[str, List[Tuple[int, int]]], bool]:
    """
    查询每个 Excel 文件在其 SVN 路径下的版本对。
    返回: ({文件名: [版本对列表], ...}, is_direct_file_url)
           版本对列表为空 [] 表示新增文件（直接输出整个文件）
           is_direct_file_url=True 时表示 svn_url 直接是文件 URL，调用方应跳过 svn_diff_filter
    """
    # 检测是否为直接文件 URL
    url_path = urllib.parse.urlparse(svn_url).path or ""
    is_direct_file_url = url_path.lower().endswith((".xlsx", ".xlsm", ".xls"))

    svn_path = _get_svn_path()

    # ── Step 1a: 获取 Excel 文件列表 ─────────────────────────────────────────────
    excel_file_list: List[Tuple[str, str]] = []
    if is_direct_file_url:
        # 直接文件 URL 模式：用递归扫描获取文件名
        _log("       正在扫描 Excel 文件...")
        excel_file_list = _find_excel_files_recursive(svn_url, timeout=120, svn_user=svn_user, svn_pass=svn_pass)
        if not excel_file_list:
            _log("[警告] 未找到 Excel 文件")
            return {}, is_direct_file_url
        _log(f"▶ 找到 {len(excel_file_list)} 个 Excel 文件")
    else:
        # 目录模式：文件列表将在 Step 1b 的 svn log -v 中顺便收集，不需要预扫描
        pass

    # ── Step 1b: 查日期范围内的所有版本 ──────
    # 加上 -v 同时获取每个版本的变更文件列表，一步到位筛选 Excel
    cmd = [svn_path, "log", svn_url, "--xml", "-v", "-r", _svn_log_range(start_date, end_date)]
    # author/keyword 在 Python 端过滤，不依赖 svn log --search

    _log("       正在查询 SVN 版本...")
    r = _svn(cmd, timeout=300, svn_user=svn_user, svn_pass=svn_pass)
    if r.returncode != 0:
        # Windows SlikSvn 输出 GBK 编码，先试 GBK 再试 UTF-8
        try:
            err_msg = r.stderr.decode("gbk", errors="strict")
        except Exception:
            err_msg = r.stderr.decode("utf-8", errors="replace")
        _log(f"[警告] svn log 查询失败: {err_msg[:200]}")
        return {}, is_direct_file_url

    try:
        root = etree.fromstring(r.stdout)
    except etree.XMLSyntaxError as e:
        _log(f"[警告] XML 解析失败: {e}")
        return {}, is_direct_file_url

    # 解析所有版本，按 keyword 过滤；同时从 -v 路径中收集 Excel 文件
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    filtered_revs: List[int] = []
    excel_paths_raw: List[str] = []  # 变更路径中的 Excel 文件（来自 svn log -v）
    new_files_set: Set[str] = set()  # 记录新增文件
    
    for entry in root.findall(".//logentry"):
        rev_text = entry.get("revision", "")
        if not rev_text:
            continue
        try:
            rev = int(rev_text)
        except ValueError:
            continue
        # 日期过滤
        date_el = entry.find("date")
        if date_el is not None and date_el.text:
            try:
                dt = datetime.fromisoformat(date_el.text.replace("Z", "+00:00"))
                dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
                if not (start_dt <= dt_naive <= end_dt):
                    continue
            except Exception:
                pass
        # author 过滤
        if author:
            auth_el = entry.find("author")
            auth_text = auth_el.text.strip() if auth_el is not None and auth_el.text else ""
            if auth_text.lower() != author.lower():
                continue
        # keyword 过滤
        if keywords:
            msg_el = entry.find("msg")
            msg = msg_el.text or "" if msg_el is not None else ""
            if not any(kw in msg for kw in keywords):
                continue
        filtered_revs.append(rev)
        # 从 -v 路径中收集 Excel 文件（svn log -v 的 path 是仓库根起始的相对路径）
        if not is_direct_file_url:
            for path_el in entry.findall("paths/path"):
                p = path_el.text or ""
                if p.lower().endswith((".xlsx", ".xlsm", ".xls")):
                    # 检查是否为新增文件（action="A"）
                    action = path_el.get("action", "")
                    if action == "A":
                        new_files_set.add(p.strip("/"))
                    excel_paths_raw.append(p.strip("/"))
            # 诊断：打印第一个关键词版本的路径样例
            if len(filtered_revs) == 1:
                sample_paths = [pe.text or "" for pe in entry.findall("paths/path")]


    filtered_revs = sorted(filtered_revs, reverse=True)  # 最新→最旧
    _log(f"▶ 过滤后共 {len(filtered_revs)} 个版本")

    if not filtered_revs:
        return {}, is_direct_file_url

    # Step 2 修正：直接对每个文件 URL 查其版本历史中的关键词 revision，
    # 不依赖 svn diff --summarize（后者检查的是"哪些文件在该 revision 被修改"，
    # 与关键词过滤维度不一致）。
    # 对于每个文件，直接 svn log file_url -r {start}:{end} 拿到文件所有版本，
    # 再与 filtered_revs 取交集（commit message 关键词过滤后的版本集合）。
    _log(f"       正在查询文件版本历史...")
    result: Dict[str, List[Tuple[int, int]]] = {}
    rev_set = set(filtered_revs)

    # ── 目录模式：svn log -v 已一次性收集了所有变更 Excel 路径，直接去重构建文件列表 ─
    if not is_direct_file_url:
        _log(f"       从 {len(excel_paths_raw)} 个 Excel 路径中筛选...")
        url_segments = urllib.parse.urlparse(svn_url).path.strip("/").split("/")  # ['svn', 'D3', 'branches', ..., 'gameData', 'Text']
        seen_files: set = set()
        excel_file_list: List[Tuple[str, str]] = []
        for p in excel_paths_raw:
            p = p.strip("/")
            p_segments = p.split("/")  # ['branches', '20240606_KR2', 'gameData', 'Text', 'Texts.xlsm']
            # 检查 p 的路径段序列是否以 url_segments 为前缀（真正的目录匹配，而非字符串子串）
            # url_segments = ['svn', 'D3', 'branches', '20240606_KR2', 'gameData', 'Text']
            # p_segments   = ['branches', '20240606_KR2', 'gameData', 'Text', 'Texts.xlsm']
            # 需要从 p_segments 中找到 url_segments 中除前两段（svn, D3）之外的部分作为目标
            # 即 ['branches', '20240606_KR2', 'gameData', 'Text'] 必须是 p_segments 的前缀
            if len(p_segments) < len(url_segments) - 2:
                continue  # p 比 url_path 还短，不可能匹配
            # p_segments 前 len(url_segments)-2 段应等于 url_segments[2:]
            target_prefix = url_segments[2:]  # ['branches', '20240606_KR2', 'gameData', 'Text']
            if p_segments[:len(target_prefix)] != target_prefix:
                continue
            # 提取相对路径（去掉前缀目录部分）
            rel = "/".join(p_segments[len(target_prefix):])
            if not rel or rel in seen_files:
                continue
            seen_files.add(rel)
            # 构造完整文件 URL：http://host:port/svn/D3 + / + p
            # svn_url 格式：http://192.168.1.41:8080/svn/D3/branches/20240606_KR2/gameData/Text
            # file_url 应为：http://192.168.1.41:8080/svn/D3/branches/20240606_KR2/gameData/Text/Texts.xlsm
            parsed_base = urllib.parse.urlparse(svn_url)  # 原始完整 URL
            # server_root = scheme://netloc/svn/D3
            server_root = f"{parsed_base.scheme}://{parsed_base.netloc}/" + "/".join(url_segments[:2])
            file_url = server_root + "/" + p
            excel_file_list.append((rel, file_url))
        _log(f"▶ 共发现 {len(excel_file_list)} 个被修改的 Excel 文件")
        _log(f"▶ 其中新增文件: {len(new_files_set)} 个")

        if not excel_file_list:
            _log("[警告] 关键词版本中无 Excel 文件变更")
            return {}, is_direct_file_url

    total_files = len(excel_file_list)
    
    # 串行执行 SVN 命令，减少内存使用
    def _get_file_revs(fname, file_url):
        """获取单个文件的版本历史"""
        # 查该文件的版本历史（筛选范围内）
        cmd_file = [svn_path, "log", file_url, "--xml", "-r", _svn_log_range(start_date, end_date)]
        r_file = _svn(cmd_file, timeout=120)
        if r_file.returncode != 0:
            return fname, []

        try:
            root_file = etree.fromstring(r_file.stdout)
            entries_file = root_file.findall(".//logentry")
        except Exception:
            return fname, []

        # 解析该文件在日期范围内的所有版本号
        file_all_revs_range: List[int] = []
        for entry in entries_file:
            rev_text = entry.get("revision", "")
            if rev_text:
                try:
                    file_all_revs_range.append(int(rev_text))
                except ValueError:
                    pass

        # 找出该文件在关键词版本列表中的版本
        file_revs = sorted([r for r in file_all_revs_range if r in rev_set], reverse=True)

        if not file_revs:
            return fname, []

        # 按版本号降序排列
        file_all_revs_range.sort(reverse=True)
        rev_to_index = {rev: i for i, rev in enumerate(file_all_revs_range)}

        # 优先在日期范围内查找上一版本，找不到再查全量历史
        pairs: List[Tuple[int, int]] = []
        need_full_history: List[int] = []
        for cur_rev in file_revs:
            if cur_rev in rev_to_index:
                idx = rev_to_index[cur_rev]
                if idx + 1 < len(file_all_revs_range):
                    prev_rev = file_all_revs_range[idx + 1]
                    pairs.append((cur_rev, prev_rev))
                else:
                    need_full_history.append(cur_rev)
            else:
                need_full_history.append(cur_rev)

        if need_full_history:
            cmd_file_full = [svn_path, "log", file_url, "--xml"]
            r_file_full = _svn(cmd_file_full, timeout=120)
            if r_file_full.returncode == 0:
                try:
                    root_file_full = etree.fromstring(r_file_full.stdout)
                    entries_file_full = root_file_full.findall(".//logentry")
                    full_file_all_revs: List[int] = []
                    for entry in entries_file_full:
                        rev_text = entry.get("revision", "")
                        if rev_text:
                            try:
                                full_file_all_revs.append(int(rev_text))
                            except ValueError:
                                pass
                    full_file_all_revs.sort(reverse=True)
                    full_rev_to_index = {rev: i for i, rev in enumerate(full_file_all_revs)}

                    for cur_rev in need_full_history:
                        if cur_rev in full_rev_to_index:
                            idx = full_rev_to_index[cur_rev]
                            if idx + 1 < len(full_file_all_revs):
                                prev_rev = full_file_all_revs[idx + 1]
                                pairs.append((cur_rev, prev_rev))
                except Exception:
                    pass

        return fname, pairs
    
    # 串行执行，减少内存使用（但最多10个文件时使用并行以提高效率）
    if total_files <= 10:
        for idx, (fname, file_url) in enumerate(excel_file_list, 1):
            if idx % 5 == 0 or idx == total_files:
                _log(f"       查询文件版本: {idx}/{total_files}")
            try:
                fname_result, pairs = _get_file_revs(fname, file_url)
                result[fname_result] = pairs
            except Exception as e:
                _log(f"       查询文件版本失败 {fname}: {e}")
                result[fname] = []
    else:
        # 文件数量多时，使用少量线程并行执行
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_file = {executor.submit(_get_file_revs, fname, file_url): (idx, fname) 
                             for idx, (fname, file_url) in enumerate(excel_file_list, 1)}
            
            for future in concurrent.futures.as_completed(future_to_file):
                idx, fname = future_to_file[future]
                if idx % 5 == 0 or idx == total_files:
                    _log(f"       查询文件版本: {idx}/{total_files}")
                try:
                    fname_result, pairs = future.result()
                    result[fname_result] = pairs
                except Exception as e:
                    _log(f"       查询文件版本失败 {fname}: {e}")
                    result[fname] = []

    # 统计
    total_pairs = sum(len(p) for p in result.values())
    
    # 处理新增文件：确保新增文件的版本对列表为空
    for fname in result.keys():
        # 检查文件是否在新增文件集合中
        # 直接检查文件名是否在新增文件集合中（更简单可靠）
        if fname in new_files_set:
            # 新增文件，清空版本对列表
            result[fname] = []
        else:
            # 检查完整路径
            full_path = None
            if not is_direct_file_url:
                # 构建完整路径
                url_segments = urllib.parse.urlparse(svn_url).path.strip("/").split("/")
                target_prefix = url_segments[2:]
                # 构建完整路径
                full_path = "/".join(target_prefix + fname.split("/"))
            
            if full_path in new_files_set:
                # 新增文件，清空版本对列表
                result[fname] = []
    
    new_files = sum(1 for p in result.values() if not p)
    _log(f"▶ 建立版本对完成: {total_pairs} 对, 新增文件: {new_files} 个")

    return result, is_direct_file_url


def step1_query_revisions(
    svn_url: str, start_date: str, end_date: str,
    author: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    svn_user: str = "",
    svn_pass: str = "") -> List[int]:
    """查询日期范围内的版本列表，支持 keyword/author 过滤。
    返回: 版本号列表（从新到旧）
    """
    svn_path = _get_svn_path()
    cmd = [svn_path, "log", svn_url, "--xml", "-r", _svn_log_range(start_date, end_date)]
    # author/keyword 在 Python 端过滤，不依赖 svn log --search

    _log("       正在查询 SVN 版本...")
    r = _svn(cmd, timeout=300, svn_user=svn_user, svn_pass=svn_pass)
    if r.returncode != 0:
        try:
            err_msg = r.stderr.decode("gbk", errors="strict")
        except Exception:
            err_msg = r.stderr.decode("utf-8", errors="replace")
        _log(f"[警告] svn log 查询失败: {err_msg[:200]}")
        return []

    try:
        root = etree.fromstring(r.stdout)
    except etree.XMLSyntaxError as e:
        _log(f"[警告] XML 解析失败: {e}")
        return []

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    filtered_revs: List[int] = []

    for entry in root.findall(".//logentry"):
        rev_text = entry.get("revision", "")
        if not rev_text:
            continue
        try:
            rev = int(rev_text)
        except ValueError:
            continue
        date_el = entry.find("date")
        if date_el is not None and date_el.text:
            try:
                dt = datetime.fromisoformat(date_el.text.replace("Z", "+00:00"))
                dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
                if not (start_dt <= dt_naive <= end_dt):
                    continue
            except Exception:
                pass
        if author:
            auth_el = entry.find("author")
            auth_text = auth_el.text.strip() if auth_el is not None and auth_el.text else ""
            if auth_text.lower() != author.lower():
                continue
        if keywords:
            msg_el = entry.find("msg")
            msg = msg_el.text or "" if msg_el is not None else ""
            if not any(kw in msg for kw in keywords):
                continue
        filtered_revs.append(rev)

    filtered_revs = sorted(filtered_revs, reverse=True)
    _log(f"▶ 过滤后共 {len(filtered_revs)} 个版本")
    return filtered_revs


def _col_str(cell_ref: str) -> str:
    """从单元格引用提取列字母（优化版：预编译正则）"""
    m = _COL_RE.match(cell_ref)
    return m.group(1) if m else ""


def _parse_excel_lxml(raw_bytes: bytes, rev: int,
                       title_rows: int = 1,
                       id_col: str = "ID",
                       output_cols: Optional[List[str]] = None) -> Optional[dict]:
    """
    v8 lxml 解析引擎（后备方案）。
    """
    # 限制文件大小，避免内存溢出
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    if len(raw_bytes) > MAX_FILE_SIZE:
        if LOG_LEVEL <= LOG_LEVELS['WARNING']:
            _log(f"r{rev} 文件过大 ({len(raw_bytes)/1024/1024:.1f}MB)，跳过解析", level='WARNING')
        return None
    
    if not raw_bytes or len(raw_bytes) < 4 or raw_bytes[:2] != b"PK":
        if raw_bytes and (b"<html" in raw_bytes[:200] or b"<HTML" in raw_bytes[:200]
                          or b"<!DOC" in raw_bytes[:200]):
            if LOG_LEVEL <= LOG_LEVELS['WARNING']:
                _log(f"r{rev} 下载内容是HTML页面（非Excel）", level='WARNING')
        return None

    try:
        zf = ZipFile(BytesIO(raw_bytes))
    except Exception as e:
        if LOG_LEVEL <= LOG_LEVELS['ERROR']:
            _log(f"r{rev} ZIP 解析失败: {e}", level='ERROR')
        return None

    # ── sharedStrings（lxml）──────────────────────────────────────────────────
    shared_strings: List[str] = []
    try:
        MAX_SS_SIZE = 50 * 1024 * 1024
        ss_info = zf.getinfo("xl/sharedStrings.xml")
        if ss_info.file_size > MAX_SS_SIZE:
            if LOG_LEVEL <= LOG_LEVELS['WARNING']:
                _log(f"r{rev} sharedStrings.xml 过大 ({ss_info.file_size/1024/1024:.1f}MB)，跳过解析", level='WARNING')
            return None

        ss_crc = ss_info.CRC
        cached = _load_shared_strings(ss_crc)
        if cached is not None:
            shared_strings = cached
            if LOG_LEVEL <= LOG_LEVELS['DEBUG']:
                _log(f"r{rev} 共享字符串缓存命中 ({len(shared_strings)} 条)", level='DEBUG')
        else:
            ss_xml = zf.read("xl/sharedStrings.xml")
            ss_root = etree.fromstring(ss_xml)
            MAX_SHARED_STRINGS = 1000000
            count = 0
            for si in ss_root:
                if count >= MAX_SHARED_STRINGS:
                    if LOG_LEVEL <= LOG_LEVELS['WARNING']:
                        _log(f"r{rev} 共享字符串数量超过限制，跳过解析", level='WARNING')
                    return None
                t_els = si.findall(".//{%s}t" % _XML_NS)
                shared_strings.append("".join(t.text or "" for t in t_els))
                count += 1
            _save_shared_strings(ss_crc, shared_strings)
            if LOG_LEVEL <= LOG_LEVELS['DEBUG']:
                _log(f"r{rev} 成功加载 {len(shared_strings)} 个共享字符串", level='DEBUG')
    except KeyError:
        if LOG_LEVEL <= LOG_LEVELS['DEBUG']:
            _log("r{rev} 没有共享字符串表", level='DEBUG')
        pass
    except MemoryError:
        if LOG_LEVEL <= LOG_LEVELS['WARNING']:
            _log(f"r{rev} 解析 sharedStrings.xml 内存不足", level='WARNING')
        return None

    # ── workbook.xml → sheet id → rId → filename（lxml）────────────────────────
    wb_map: Dict[str, str] = {}
    try:
        wb_xml = zf.read("xl/workbook.xml")
        wb_root = etree.fromstring(wb_xml)
        RELS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        sheet_name_to_rid: Dict[str, str] = {}
        for sh in wb_root.iter("{%s}sheet" % _XML_NS):
            nm = sh.get("name", "")
            rid = sh.get("{%s}id" % RELS_NS, "")
            if nm and rid:
                sheet_name_to_rid[nm] = rid
        rels_map: Dict[str, str] = {}
        try:
            rels_xml = zf.read("xl/_rels/workbook.xml.rels")
            rels_root = etree.fromstring(rels_xml)
            for rel in rels_root:
                rels_map[rel.get("Id", "")] = rel.get("Target", "")
        except KeyError:
            if LOG_LEVEL <= LOG_LEVELS['DEBUG']:
                _log("r{rev} 没有工作簿关系文件", level='DEBUG')
            pass
        for nm, rid in sheet_name_to_rid.items():
            target = rels_map.get(rid, "")
            if target:
                wb_map[target] = nm
        if LOG_LEVEL <= LOG_LEVELS['DEBUG']:
            _log(f"r{rev} 成功加载 {len(wb_map)} 个工作表", level='DEBUG')
    except Exception as e:
        if LOG_LEVEL <= LOG_LEVELS['ERROR']:
            _log(f"r{rev} workbook 解析失败: {e}", level='ERROR')

    result: dict = {"sharedStrings": shared_strings, "sheets": {}, "map": {}}

    # ── 预解析：在第一个 sheet 中查找 ID 列，后续 sheet 复用 ──────────────────
    global_id_col = None
    global_id_hdr = None
    global_sc_hdr = None
    global_sub_hdr = None
    
    is_numeric_id_col = id_col.isdigit()
    id_col_index = int(id_col) if is_numeric_id_col else 0
    header_row = title_rows

    for target, sheet_name in wb_map.items():
        if not target.endswith(".xml"):
            target = target + ".xml"
        if not target.startswith("xl/"):
            target = "xl/" + target

        try:
            sheet_fh = zf.open(target)
        except KeyError:
            continue

        try:
            context = etree.iterparse(sheet_fh, events=('end',), tag=_ROW_TAG)
        except Exception:
            sheet_fh.close()
            continue

        header_to_col: Dict[str, str] = {}
        col_to_hdr: Dict[str, str] = {}
        _seen_hdrs: set = set()
        cols = []
        header_cells = []
        found_id_col = None
        found_id_hdr = None
        found_sc_hdr = None
        found_sub_hdr = None
        header_done = False
        needed_col_set = set()
        sheet_map_setup = False
        if sheet_name not in result["sheets"]:
            result["sheets"][sheet_name] = {"map": {}}
        sheet_map = result["sheets"][sheet_name]["map"]

        for ev, row in context:
            row_num = int(row.get("r", 0))

            # ── 标题行及以上行处理 ──────────────────────────────────
            if not header_done:
                if row_num == header_row:
                    for cell in row:
                        if cell.tag != _CELL_TAG:
                            continue
                        col = _col_str(cell.get("r", ""))
                        cols.append(col)
                        header_cells.append((col, cell))
                    col_index_map = {i+1: c for i, c in enumerate(cols)}

                    if global_id_col:
                        found_id_col = global_id_col
                        found_id_hdr = global_id_hdr
                        found_sc_hdr = global_sc_hdr
                        found_sub_hdr = global_sub_hdr
                        for col, cell in header_cells:
                            t_attr = cell.get("t", "")
                            v_el = cell.find(_V_TAG)
                            val = ""
                            if t_attr == "s" and v_el is not None and v_el.text:
                                try:
                                    val = shared_strings[int(v_el.text)]
                                except (ValueError, IndexError):
                                    val = ""
                            elif v_el is not None and v_el.text:
                                val = v_el.text
                            if val:
                                _key = val if val not in _seen_hdrs else f"{val}__{col}"
                                _seen_hdrs.add(val)
                                header_to_col[_key] = col
                                col_to_hdr[col] = _key
                    elif is_numeric_id_col:
                        if id_col_index in col_index_map:
                            found_id_col = col_index_map[id_col_index]
                            for col, cell in header_cells:
                                if col == found_id_col:
                                    t_attr = cell.get("t", "")
                                    v_el = cell.find(_V_TAG)
                                    if t_attr == "s" and v_el is not None and v_el.text:
                                        try:
                                            val = shared_strings[int(v_el.text)]
                                        except (ValueError, IndexError):
                                            val = ""
                                    elif v_el is not None and v_el.text:
                                        val = v_el.text
                                    if val:
                                        found_id_hdr = val
                                        header_to_col[val] = col
                                        col_to_hdr[col] = val
                                    break
                    else:
                        for col, cell in header_cells:
                            t_attr = cell.get("t", "")
                            v_el = cell.find(_V_TAG)
                            val = ""
                            if t_attr == "s" and v_el is not None and v_el.text:
                                try:
                                    val = shared_strings[int(v_el.text)]
                                except (ValueError, IndexError):
                                    val = ""
                            elif v_el is not None and v_el.text:
                                val = v_el.text
                            if not val:
                                continue
                            _key = val if val not in _seen_hdrs else f"{val}__{col}"
                            _seen_hdrs.add(val)
                            header_to_col[_key] = col
                            col_to_hdr[col] = _key
                            if val == "::ID::" or val in (id_col, id_col.lower(), id_col.capitalize()):
                                found_id_hdr = _key
                                found_id_col = col
                            elif val == "::SC::" or val in ("SC", "Sc", "sc"):
                                found_sc_hdr = val
                            elif val in ("SubstituteId", "Substitute_ID"):
                                found_sub_hdr = val

                    header_done = True
                    if not global_id_col and found_id_col:
                        global_id_col = found_id_col
                        global_id_hdr = found_id_hdr
                        global_sc_hdr = found_sc_hdr
                        global_sub_hdr = found_sub_hdr

                    if not found_id_col:
                        row.clear()
                        break  # 找不到 ID 列，跳过本 sheet

                    # 构建 needed_col_set
                    if output_cols:
                        needed_hdr_set = {h for h in output_cols if h in header_to_col}
                        for hdr in (found_id_hdr, found_sc_hdr, found_sub_hdr):
                            if hdr:
                                needed_hdr_set.add(hdr)
                        needed_col_set = {header_to_col[h] for h in needed_hdr_set}
                    else:
                        needed_col_set = {col for col, _ in header_cells}
                        for col, cell in header_cells:
                            if col in col_to_hdr:
                                continue
                            t_attr = cell.get("t", "")
                            v_el = cell.find(_V_TAG)
                            val = ""
                            if t_attr == "s" and v_el is not None and v_el.text:
                                try:
                                    val = shared_strings[int(v_el.text)]
                                except (ValueError, IndexError):
                                    val = ""
                            elif v_el is not None and v_el.text:
                                val = v_el.text
                            if val:
                                _key = val if val not in _seen_hdrs else f"{val}__{col}"
                                _seen_hdrs.add(val)
                                header_to_col[_key] = col
                                col_to_hdr[col] = _key
                    sheet_map_setup = True
                    
                    # ── 存储标题行原始数据（供输出表头用）────────────────
                    if "_header_data" not in result:
                        result["_header_data"] = {}
                    hr_data = {}
                    for col, cell in header_cells:
                        t_attr = cell.get("t", "")
                        v_el = cell.find(_V_TAG)
                        val = ""
                        if t_attr == "s" and v_el is not None and v_el.text:
                            try:
                                val = shared_strings[int(v_el.text)]
                            except (ValueError, IndexError):
                                val = ""
                        elif v_el is not None and v_el.text:
                            val = v_el.text
                        if val.strip():
                            hr_data[col] = val
                    if "_header_data" not in result:
                        result["_header_data"] = {}
                    if sheet_name not in result["_header_data"]:
                        result["_header_data"][sheet_name] = {}
                    result["_header_data"][sheet_name][header_row] = hr_data
                    
                    row.clear()
                    continue
                elif row_num < header_row:
                    if "_header_data" not in result:
                        result["_header_data"] = {}
                    if sheet_name not in result["_header_data"]:
                        result["_header_data"][sheet_name] = {}
                    hr_data = {}
                    for cell in row:
                        if cell.tag != _CELL_TAG:
                            continue
                        col = _col_str(cell.get("r", ""))
                        t_attr = cell.get("t", "")
                        v_el = cell.find(_V_TAG)
                        val = ""
                        if t_attr == "s" and v_el is not None and v_el.text:
                            try:
                                val = shared_strings[int(v_el.text)]
                            except (ValueError, IndexError):
                                val = ""
                        elif v_el is not None and v_el.text:
                            val = v_el.text
                        if val.strip():
                            hr_data[col] = val
                    result["_header_data"][sheet_name][row_num] = hr_data
                    row.clear()
                    continue
                else:
                    row.clear()
                    continue

            # ── 标题行的下一行：存储为第二表头 ──────────────────────────
            if not sheet_map_setup:
                row.clear()
                continue
            if row_num == header_row + 1:
                hr2_data = {}
                for cell in row:
                    if cell.tag != _CELL_TAG:
                        continue
                    col = _col_str(cell.get("r", ""))
                    t_attr = cell.get("t", "")
                    v_el = cell.find(_V_TAG)
                    val = ""
                    if t_attr == "s" and v_el is not None and v_el.text:
                        try:
                            val = shared_strings[int(v_el.text)]
                        except (ValueError, IndexError):
                            val = ""
                    elif v_el is not None and v_el.text:
                        val = v_el.text
                    if val.strip():
                        hr2_data[col] = val
                result["_header_data"][sheet_name][header_row + 1] = hr2_data
                row.clear()
                continue
            if row_num <= header_row:
                row.clear()
                continue

            cell_vals: Dict[str, str] = {}
            sid = ""

            for cell in row:
                if cell.tag != _CELL_TAG:
                    continue
                col = _col_str(cell.get("r", ""))
                if output_cols and col not in needed_col_set:
                    continue
                t_attr = cell.get("t", "")
                v_el = cell.find(_V_TAG)
                if t_attr == "s" and v_el is not None and v_el.text:
                    try:
                        val = shared_strings[int(v_el.text)]
                    except (ValueError, IndexError):
                        val = ""
                elif v_el is not None and v_el.text:
                    val = v_el.text
                else:
                    val = ""
                if col == found_id_col:
                    sid = val.strip()
                hdr = col_to_hdr.get(col, "")
                if hdr:
                    cell_vals[hdr] = val

            if not sid and found_id_hdr:
                sid = cell_vals.get(found_id_hdr, "").strip()
            
            if not sid or sid in ("::ID::", "ID"):
                if sid == "":
                    break
                row.clear()
                continue

            sc_val = cell_vals.get(found_sc_hdr, "").strip() if found_sc_hdr else ""
            sub_val = cell_vals.get(found_sub_hdr, "").strip() if found_sub_hdr else ""

            if sid not in result["map"]:
                result["map"][sid] = {
                    "sc": sc_val,
                    "sheet": sheet_name,
                    "sub": sub_val,
                    "cells": cell_vals,
                }
            else:
                old = result["map"][sid]
                if sc_val:
                    old["sc"] = sc_val
                if sub_val:
                    old["sub"] = sub_val
                if not old.get("cells"):
                    old["cells"] = cell_vals

            if sid not in sheet_map:
                sheet_map[sid] = {
                    "sc": sc_val,
                    "sheet": sheet_name,
                    "sub": sub_val,
                    "cells": cell_vals,
                }
            else:
                old = sheet_map[sid]
                if sc_val:
                    old["sc"] = sc_val
                if sub_val:
                    old["sub"] = sub_val
                if not old.get("cells"):
                    old["cells"] = cell_vals

            row.clear()

        del context
        sheet_fh.close()
        
        # ── 计算 sheet 内容哈希（用于跳过相同 sheet）────────────────
        if sheet_map_setup and sheet_map:
            import hashlib
            parts = []
            for sid in sorted(sheet_map.keys()):
                cells = sheet_map[sid].get("cells", {})
                cell_str = "|".join(f"{k}={v}" for k, v in sorted(cells.items()))
                parts.append(f"{sid}:{cell_str}")
            result["sheets"][sheet_name]["_hash"] = hashlib.md5(
                "\n".join(parts).encode()).hexdigest()

    result["_sheet_order"] = list(result["sheets"].keys())
    return result




# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: 下载 & 对比
# ═══════════════════════════════════════════════════════════════════════════════
def _download_rev(svn_path: str, excel_url: str, rev: int, svn_user: str = "", svn_pass: str = "") -> Tuple[int, Optional[bytes]]:
    """下载单个版本的 Excel 文件内容（bytes）"""
    # 尝试带认证的命令
    cmd = [svn_path, "cat", "-r", str(rev), "--non-interactive", "--trust-server-cert"]
    # 添加认证参数
    if svn_user:
        cmd.extend(["--username", svn_user])
    if svn_pass:
        cmd.extend(["--password", svn_pass])
    cmd.extend(["--", excel_url])
    try:
        # 使用 Popen 并直接读取 stdout，减少启动开销
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        stdout, stderr = process.communicate(timeout=180)
        if process.returncode == 0:
            return rev, stdout
        # 检查是否是认证错误
        stderr_str = stderr.decode('utf-8', errors='replace')
        if '401 Authorization Required' in stderr_str or 'authorization failed' in stderr_str.lower():
            _log(f"r{rev} 认证失败: {stderr_str}", level='ERROR')
        else:
            _log(f"r{rev} 下载失败，返回码: {process.returncode}, 错误: {stderr_str}", level='WARNING')
        return rev, None
    except subprocess.TimeoutExpired:
        if LOG_LEVEL <= LOG_LEVELS['DEBUG']:
            _log(f"r{rev} 下载超时", level='DEBUG')
        return rev, None
    except Exception as e:
        if LOG_LEVEL <= LOG_LEVELS['WARNING']:
            _log(f"r{rev} 下载异常: {e}", level='WARNING')
        return rev, None


def _download_batch(svn_path: str, tasks: List[Tuple[str, int]]) -> Dict[Tuple[str, int], Optional[bytes]]:
    """批量下载多个版本的文件内容（bytes），减少进程启动开销"""
    result = {}
    if not tasks:
        return result
    
    # 构建批量下载命令
    cmd = [svn_path, "cat"]
    for url, rev in tasks:
        cmd.extend(["-r", str(rev), "--", url])
    
    try:
        # 使用 Popen 并直接读取 stdout，减少启动开销
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        stdout, stderr = process.communicate(timeout=300)  # 批量下载超时时间更长
        if process.returncode == 0:
            # 解析输出，每个文件的内容是连续的
            # 注意：这种方式可能不适用，因为 svn cat 多个文件时，输出是连续的，无法区分每个文件的内容
            # 因此，这里仍然使用单个文件下载的方式，但通过批量提交任务来减少线程创建开销
            for url, rev in tasks:
                _, data = _download_rev(svn_path, url, rev)
                result[(url, rev)] = data
        else:
            # 批量下载失败，回退到单个文件下载
            if LOG_LEVEL <= LOG_LEVELS['DEBUG']:
                _log("批量下载失败，回退到单个文件下载", level='DEBUG')
            for url, rev in tasks:
                _, data = _download_rev(svn_path, url, rev)
                result[(url, rev)] = data
    except Exception as e:
        if LOG_LEVEL <= LOG_LEVELS['WARNING']:
            _log(f"批量下载异常: {e}", level='WARNING')
        # 异常时回退到单个文件下载
        for url, rev in tasks:
            _, data = _download_rev(svn_path, url, rev)
            result[(url, rev)] = data
    
    return result


def _download_worker(args: Tuple[str, str, int, str, str]) -> Tuple[int, Optional[bytes]]:
    """下载 worker"""
    svn_path, excel_url, rev, svn_user, svn_pass = args
    return _download_rev(svn_path, excel_url, rev, svn_user, svn_pass)




def _cells_equal(cells1: dict, cells2: dict) -> bool:
    """比较两个单元格字典是否相等（数值规范化后比较）"""
    # 首先比较键的数量，快速判断不相等的情况
    if len(cells1) != len(cells2):
        return False
    # 比较键是否相同
    if set(cells1.keys()) != set(cells2.keys()):
        return False
    # 比较值
    for k in cells1:
        v1 = cells1[k]
        v2 = cells2[k]
        # 先直接比较，避免不必要的规范化
        if v1 == v2:
            continue
        # 再进行规范化比较
        v1_norm = _normalize_value(str(v1)) if v1 is not None else ""
        v2_norm = _normalize_value(str(v2)) if v2 is not None else ""
        if v1_norm != v2_norm:
            return False
    return True


def _row_hash(info: dict, cols: Optional[List[str]], id_col: str) -> int:
    """计算行的内容哈希。当 cols 指定时只按指定列哈希，否则按全部 cells。
    自动检测退化情况（列名不匹配导致全空）并回退到全部 cells"""
    cells = info.get("cells", {})
    if cols:
        items = tuple((k, cells.get(k, '')) for k in cols)
        # 退化为全空 → 用全部 cells 回退（列名可能不匹配 Excel 真实表头）
        if all(v == '' for _, v in items):
            items = tuple((k, v) for k, v in sorted(cells.items())
                          if k not in (id_col, "::ID::"))
    else:
        items = tuple((k, v) for k, v in sorted(cells.items())
                       if k not in (id_col, "::ID::"))
    return hash(items)


def _compare_pair_merge(
    cur_sm: dict, prv_sm: dict, cur_rev: int, prv_rev: int,
    output_cols, id_col: str, results: list
) -> None:
    """哈希匹配 → ID 匹配 → 新增/删除，三合一单次遍历"""
    # ── 构建 cur 哈希索引 ──────────────────────────────
    cur_by_hash: dict = {}
    for sid, info in cur_sm.items():
        h = _row_hash(info, output_cols, id_col)
        cur_by_hash.setdefault(h, []).append(sid)

    cur_matched: set = set()   # 所有已匹配的 cur sid
    prv_matched: set = set()   # 所有已匹配的 prv sid
    prv_pending: dict = {}     # prv 中未匹配的 sid→info

    # ── 阶段1：遍历 prv，每行先查哈希 ────────────────
    for psid, pi in prv_sm.items():
        h = _row_hash(pi, output_cols, id_col)
        if h in cur_by_hash and cur_by_hash[h]:
            csid = cur_by_hash[h].pop(0)
            if not cur_by_hash[h]:
                del cur_by_hash[h]
            cur_matched.add(csid)
            prv_matched.add(psid)
        else:
            prv_pending[psid] = pi

    # ── 阶段2：ID 匹配（剩余行）─────────────────────
    # 直接在 cur_sm 中查找未匹配的 ID
    cur_remaining = {}
    for sid, ci in cur_sm.items():
        if sid not in cur_matched:
            if sid in prv_pending:
                # ID 匹配命中
                pi = prv_pending.pop(sid)
                cur_matched.add(sid)
                prv_matched.add(sid)
                if not output_cols:
                    if not _cells_equal(ci.get("cells", {}), pi.get("cells", {})):
                        results.append(_build_row(sid, ci, cur_rev, prv_rev, "修改", output_cols))
                else:
                    csc, psc = ci.get("sc", ""), pi.get("sc", "")
                    csub, psub = ci.get("sub", ""), pi.get("sub", "")
                    sc_ch = (csc != psc) and (_normalize_value(csc) != _normalize_value(psc) if csc != psc else False)
                    sub_ch = (csub != psub) and (_normalize_value(csub) != _normalize_value(psub) if csub != psub else False)
                    cell_ch = not _cells_equal(ci.get("cells", {}), pi.get("cells", {}))
                    if sc_ch or sub_ch or cell_ch:
                        row = _build_row(sid, ci, cur_rev, prv_rev, "修改", output_cols)
                        row["前一版本_SC"] = psc
                        row["前一版本_sub"] = psub
                        results.append(row)
            else:
                cur_remaining[sid] = ci

    # ── 剩余 → 新增/删除 ────────────────────────────
    for sid, ci in cur_remaining.items():
        results.append(_build_row(sid, ci, cur_rev, prv_rev, "新增", output_cols))
    for psid, pi in prv_pending.items():
        results.append(_build_row(psid, pi, cur_rev, prv_rev, "删除", output_cols))

    # ── 阶段3（仅无 output_cols）：哈希内容回退 ────
    if not output_cols and cur_remaining and prv_pending:
        pr_by_hash: dict = {}
        for psid, pi in prv_pending.items():
            h = _row_hash(pi, None, id_col)
            pr_by_hash.setdefault(h, []).append(psid)
        for csid, ci in list(cur_remaining.items()):
            h = _row_hash(ci, None, id_col)
            if h in pr_by_hash and pr_by_hash[h]:
                psid = pr_by_hash[h].pop(0)
                if not pr_by_hash[h]:
                    del pr_by_hash[h]
                pi = prv_pending[psid]
                cur_remaining.pop(csid, None)
                prv_pending.pop(psid, None)
                row = _build_row(csid, ci, cur_rev, prv_rev, "ID变更", output_cols)
                row["_id_changed"] = True
                row["前一版本_ID"] = psid
                results.append(row)


def _compare_pair(cur: int, prv: int,
                   cur_parsed: Optional[dict],
                   prv_parsed: Optional[dict],
                   title_rows: int = 1,
                   id_col: str = "ID",
                   output_cols: Optional[List[str]] = None) -> List[dict]:
    """对比一对版本（哈希匹配→ID匹配→哈希回退）"""
    if cur_parsed is None and prv_parsed is None:
        return []

    cur_sheets = cur_parsed.get("sheets", {}) if cur_parsed else {}
    prv_sheets = prv_parsed.get("sheets", {}) if prv_parsed else {}

    results: List[dict] = []

    csn, psn = set(cur_sheets), set(prv_sheets)

    for sheet_name in csn - psn:
        for sid, info in cur_sheets[sheet_name].get("map", {}).items():
            results.append(_build_row(sid, info, cur, prv, "新增", output_cols))
    for sheet_name in psn - csn:
        for sid, info in prv_sheets[sheet_name].get("map", {}).items():
            results.append(_build_row(sid, info, cur, prv, "删除", output_cols))

    for sheet_name in csn & psn:
        cur_sm = cur_sheets[sheet_name].get("map", {})
        prv_sm = prv_sheets[sheet_name].get("map", {})

        if (cur_sheets[sheet_name].get("_hash")
                and prv_sheets[sheet_name].get("_hash")
                and cur_sheets[sheet_name]["_hash"] == prv_sheets[sheet_name]["_hash"]):
            continue

        _compare_pair_merge(cur_sm, prv_sm, cur, prv, output_cols, id_col, results)

    return results


def _build_row(sid: str, info: dict, cur_rev: int, prv_rev: int,
               op_type: str, output_cols: Optional[List[str]]) -> dict:
    """构造输出行"""
    sc = info.get("sc", "")
    sub = info.get("sub", "")
    sheet = info.get("sheet", "")
    cells = info.get("cells", {})

    # 构建输出行，按照要求的顺序排列
    row: dict = {
        "操作": op_type,
        "当前版本": cur_rev,
        "前一版本": prv_rev,
    }

    # 始终添加 sheet 列，以便在没有输出列时也能按 sheet 分组
    row["sheet"] = sheet

    # 如果有整行数据且需要列筛选，按需添加
    if cells and output_cols:
        row["ID"] = sid
        for col in output_cols:
            if col in cells:
                row[col] = cells[col]
    elif cells:
        row["ID"] = sid
        for col, val in cells.items():
            row[col] = val

    return row


def _dedupe_by_id(results: List[dict]) -> List[dict]:
    """
    按ID去重，合并多版本对的操作记录。
    
    去重规则：
    1. 有删除操作：
       - 最新操作是删除 → 删除
       - 先删除后新增 → 修改
    2. 无删除操作：
       - 有新增 → 新增
       - 全是修改 → 修改
    
    版本号：取最新版本对的 cur 和 prv
    """
    if not results:
        return []
    
    # 按 ID 分组
    id_to_records: Dict[str, List[dict]] = defaultdict(list)
    for row in results:
        sid = row.get("ID", "")
        if sid:
            id_to_records[sid].append(row)
    
    deduped: List[dict] = []
    
    for sid, records in id_to_records.items():
        if len(records) == 1:
            deduped.append(records[0])
            continue
        
        # 按当前版本号排序（升序，最早的在前）
        records.sort(key=lambda r: r.get("当前版本", 0))
        
        # 收集所有操作类型
        ops = [r.get("操作", "") for r in records]
        has_delete = "删除" in ops
        has_add = "新增" in ops
        has_modify = "修改" in ops
        
        # 判断最终操作类型
        if has_delete:
            # 最新操作是删除？
            if records[-1].get("操作") == "删除":
                final_op = "删除"
            else:
                # 先删除后新增 → 修改
                final_op = "修改"
        else:
            # 无删除
            if has_add:
                final_op = "新增"
            else:
                final_op = "修改"
        
        # 取最新版本对的信息
        latest = records[-1]
        merged = dict(latest)
        merged["操作"] = final_op
        
        deduped.append(merged)
    
    
    return deduped


def _parse_excel_with_cache(raw_bytes: bytes, rev: int,
                              title_rows: int = 1,
                              id_col: str = "ID",
                              output_cols: Optional[List[str]] = None,
                              fname: str = "",
                              _return_cache_key: bool = False
                              ) -> Tuple[Optional[dict], Optional[str]]:
    """
    带缓存的 Excel 解析。优先级：内存缓存 > 文件缓存 > 解析。
    _return_cache_key=True 时返回 (result, cache_key)，
    其中 cache_key 用于主进程写入 pickle（避免 worker 直接写文件出错）
    """
    global _parsed_cache, _cache_hits, _cache_misses

    if not raw_bytes:
        return (None, None) if _return_cache_key else None

    # 计算内容哈希（只取前 16KB 加速），缓存 key 加入 title_rows/id_col 以区分不同参数解析结果
    content_hash = _content_hash(raw_bytes)
    cache_key = _safe_cache_key(f"{content_hash}_{title_rows}_{id_col}")

    # 1. 查内存缓存
    if cache_key in _parsed_cache:
        _cache_hits += 1
        return (_parsed_cache[cache_key], cache_key) if _return_cache_key else _parsed_cache[cache_key]

    # 2. 查文件缓存
    disk_result = _load_parse_from_disk(cache_key)
    if disk_result is not None:
        _cache_hits += 1
        _parsed_cache[cache_key] = disk_result
        return (disk_result, cache_key) if _return_cache_key else disk_result

    # 3. 未命中，解析（使用 v8 lxml 引擎，最稳定快速）
    _cache_misses += 1
    result = _parse_excel_lxml(raw_bytes, rev, title_rows, id_col, output_cols)

    # 写入内存缓存 + 磁盘缓存
    if result is not None:
        _parsed_cache[cache_key] = result
        _save_parse_to_disk(cache_key, result)
        _trim_cache()

    return (result, cache_key) if _return_cache_key else result



def _process_pair_bytes_worker(
    args: Tuple[int, int, int, str, str, int, str, Optional[List[str]], str]
) -> Tuple[str, List[dict], int, int, int, str, List[str], Optional[dict]]:
    """
    Worker 函数（v10 进程隔离）：从临时文件读取数据做解析+对比。
    args: (pair_idx, cur_rev, prv_rev, cur_path, prv_path, title_rows, id_col, output_cols, fname)
    返回: (fname, diff_rows, cur_rev, prv_rev, title_rows, id_col, temp_paths, header_data)
    """
    pair_idx, cur_rev, prv_rev, cur_path, prv_path, title_rows, id_col, output_cols, fname = args
    temp_paths = [cur_path, prv_path]
    empty_ret = (fname, [], cur_rev, prv_rev, title_rows, id_col, temp_paths, None, [])
    try:
        def read_temp_file(path):
            if not os.path.exists(path):
                _log(f"[Worker错误] 临时文件不存在: {path}", level='ERROR')
                return None
            try:
                with open(path, 'rb') as f:
                    return f.read()
            except Exception as e:
                _log(f"[Worker错误] 读取临时文件失败: {path}, 错误: {e}", level='ERROR')
                return None
        
        cur_bytes = read_temp_file(cur_path)
        if not cur_bytes:
            _log(f"[Worker错误] 无法读取当前版本临时文件: {cur_path}", level='ERROR')
            return empty_ret
        
        prv_bytes = read_temp_file(prv_path)
        if not prv_bytes:
            _log(f"[Worker错误] 无法读取先前版本临时文件: {prv_path}", level='ERROR')
            return empty_ret
        
        _log(f"[Worker] 对比文件: {fname}，版本对: {cur_rev} -> {prv_rev}", level='DEBUG')
        cur_parsed = _parse_excel_with_cache(cur_bytes, cur_rev, title_rows, id_col, output_cols, fname)
        if not cur_parsed or not cur_parsed.get('map'):
            _log(f"[Worker警告] 解析 {fname} r{cur_rev} 失败或无数据", level='WARNING')
            return empty_ret
        _log(f"[Worker] 解析 {fname} r{cur_rev} 成功，数据行数: {len(cur_parsed.get('map', {}))}", level='DEBUG')

        prv_parsed = _parse_excel_with_cache(prv_bytes, prv_rev, title_rows, id_col, output_cols, fname)
        if not prv_parsed or not prv_parsed.get('map'):
            _log(f"[Worker警告] 解析 {fname} r{prv_rev} 失败或无数据", level='WARNING')
            return empty_ret
        _log(f"[Worker] 解析 {fname} r{prv_rev} 成功，数据行数: {len(prv_parsed.get('map', {}))}", level='DEBUG')

        diff_rows = _compare_pair(cur_rev, prv_rev, cur_parsed, prv_parsed, title_rows, id_col, output_cols)
        _log(f"[Worker] 对比 {fname} 完成，差异行数: {len(diff_rows)}", level='DEBUG')
        header_data = cur_parsed.get("_header_data")
        sheet_order = cur_parsed.get("_sheet_order", [])
    except Exception as e:
        _log(f"[Worker错误] {fname} r{cur_rev}->{prv_rev}: {type(e).__name__}: {e}", level='ERROR')
        import traceback
        traceback.print_exc()
        diff_rows = []
        header_data = None
        sheet_order = []
    return fname, diff_rows, cur_rev, prv_rev, title_rows, id_col, temp_paths, header_data, sheet_order





def _find_excel_files_recursive(svn_url: str, timeout: int = 60, svn_user: str = "", svn_pass: str = "") -> List[Tuple[str, str]]:
    """
    递归扫描 SVN 目录，返回所有 Excel 文件（含子目录）。
    返回: [(相对路径, 完整URL), ...]
    相对路径不含 URL 前缀，如 "Text/Texts.xlsm"
    """
    # 判断 svn_url 是否直接是 Excel 文件 URL，若是则直接返回
    url_path = urllib.parse.urlparse(svn_url).path or ""
    if url_path.lower().endswith((".xlsx", ".xlsm", ".xls")):
        fname = urllib.parse.unquote(url_path.split("/")[-1])
        return [(fname, svn_url)]

    svn_path = _get_svn_path()
    cmd = [svn_path, "list", "--recursive", "--xml", svn_url]
    r = _svn(cmd, timeout=timeout, svn_user=svn_user, svn_pass=svn_pass)
    if r.returncode != 0:
        return []

    results: List[Tuple[str, str]] = []
    base = svn_url.rstrip("/") + "/"
    try:
        root = etree.fromstring(r.stdout)
        for entry in root.findall(".//entry"):
            kind = entry.get("kind", "")
            if kind != "file":
                continue
            name_el = entry.find("name")
            if name_el is None:
                continue
            name: str = name_el.text or ""
            if name.lower().endswith((".xlsx", ".xlsm", ".xls")):
                full_url = base + name
                results.append((name, full_url))
    except Exception:
        pass
    return results


def _get_changed_files_for_pair(cur: int, prv: int, svn_url: str, svn_user: str = "", svn_pass: str = "") -> Tuple[int, int, List[str]]:
    """
    调用 svn diff --summarize，返回指定版本对之间变更的文件路径列表。
    返回: (cur, prv, [rel_path, ...])，无变更时返回空列表
    """
    svn_path = _get_svn_path()
    cmd = [svn_path, "diff", "--summarize", "-r", f"{prv}:{cur}", svn_url]
    try:
        r = _svn(cmd, timeout=60, svn_user=svn_user, svn_pass=svn_pass)
        if r.returncode != 0:
            return (cur, prv, [])
        changed: List[str] = []
        base = svn_url.rstrip("/") + "/"
        for line in r.stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) >= 2:
                full_url = parts[1]
                if full_url.startswith(base):
                    rel = full_url[len(base):]
                elif full_url.startswith(svn_url.rstrip("/")):
                    rel = full_url[len(svn_url.rstrip("/")):].lstrip("/")
                else:
                    rel = os.path.basename(full_url)
                changed.append(urllib.parse.unquote(rel))
        return (cur, prv, changed)
    except Exception:
        return (cur, prv, [])


def _batch_check_changed_pairs(
    pairs: List[Tuple[int, int]],
    svn_url: str,
    workers: int = 10,
    svn_user: str = "",
    svn_pass: str = ""
) -> Dict[Tuple[int, int], List[str]]:
    """
    并发查询所有版本对的变更文件列表。
    返回: {(cur, prv): [changed_rel_path, ...]}
    """
    if not pairs:
        return {}
    results: Dict[Tuple[int, int], List[str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_get_changed_files_for_pair, cur, prv, svn_url, svn_user, svn_pass): (cur, prv)
                    for cur, prv in pairs}
        done = 0
        for future in as_completed(futures):
            cur, prv, changed = future.result()
            results[(cur, prv)] = changed
            done += 1
            if done % 20 == 0 or done == len(pairs):
                _log(f"       变更检查: {done}/{len(pairs)}")
    return results


def step3_download_and_compare(svn_url: str,
                                workers: int = 6, parse_workers: int = 0,
                                file_pairs: Optional[Dict[str, List[Tuple[int, int]]]] = None,
                                svn_diff_filter: bool = True,
                                svn_user: str = "", svn_pass: str = ""
                                ) -> Tuple[Dict[str, List[dict]], dict, Dict[str, list]]:
    """
    下载并对比 Excel 版本对。

    返回: {文件名: [差异行, ...], ...}
    file_pairs: {文件名: [版本对列表], ...}，版本对列表为空 [] 表示新增文件
    """
    # ── 预加载磁盘缓存到内存，大幅减少重复解析 ───────────────────────────────
    cached = warm_parse_cache()
    if cached > 0:
        _log(f"       [缓存] 已预加载 {cached} 个缓存条目")

    svn_path = _get_svn_path()

    # 预声明 all_pairs_data，避免嵌套函数 _on_version_ready 导致 Python
    # 将其视为局部变量（UnboundLocalError）
    all_pairs_data: List[Tuple[int, int, str]] = []   # [(cur, prv, fname), ...]

    if not file_pairs:
        _log("[警告] file_pairs 为空，无对比任务")
        return {}, {}, {}

    # ── 确定要对比的文件列表（从 file_pairs 提取）───────────────────────────
    excel_file_list: List[Tuple[str, str]] = []  # (相对路径, URL)

    # 检测 svn_url 是否直接是文件 URL（末尾已含文件名）
    url_path = urllib.parse.urlparse(svn_url).path or ""
    svn_url_is_file = url_path.lower().endswith((".xlsx", ".xlsm", ".xls"))

    # 解析 URL  segments，用于构建完整文件 URL
    url_segments = urllib.parse.urlparse(svn_url).path.strip("/").split("/")
    parsed_base = urllib.parse.urlparse(svn_url)
    # server_root = scheme://netloc/svn/D3
    server_root = f"{parsed_base.scheme}://{parsed_base.netloc}/" + "/".join(url_segments[:2])

    for fname in file_pairs.keys():
        # 构建文件的完整 URL
        # 如果 svn_url 本身就是文件 URL，直接用它
        if svn_url_is_file:
            file_url = svn_url
        else:
            # 使用与 step1_query_file_pairs 相同的逻辑构建文件 URL
            # 构建完整路径
            target_prefix = url_segments[2:]
            full_path = "/".join(target_prefix + fname.split("/"))
            file_url = server_root + "/" + full_path
        excel_file_list.append((fname, file_url))

    if not excel_file_list:
        _log("[警告] 未找到 Excel 文件")
        return {}, {}, {}

    # ── 构建版本号集合（用于下载调度）──────────────────────────────────────
    all_cur_revs = set()
    for pair_list in file_pairs.values():
        for cur, prv in pair_list:
            all_cur_revs.add(cur)
            all_cur_revs.add(prv)
    all_revs = sorted(all_cur_revs)

    # ── 构建 pair 列表 ──
    all_pair_list: List[Tuple[int, int]] = []
    for fname, pair_list in file_pairs.items():
        for p in pair_list:
            if p not in all_pair_list:
                all_pair_list.append(p)
    total_pairs = len(all_pair_list)
    _log(f"       共 {total_pairs} 个版本对，{len(all_revs)} 个版本")

    # ── v9 流水线：Pool 启动与下载并行，pair 就绪即提交 ──────────────
    parse_w = parse_workers if parse_workers > 0 else cpu_count()
    # 根据系统资源动态调整线程数，最大限制但避免内存溢出
    try:
        import psutil
        available_memory = psutil.virtual_memory().available / (1024 * 1024 * 1024)  # GB
        cpu_cores = psutil.cpu_count(logical=True)
        
        # 内存保护：根据可用内存限制并发数（v3阈值，基于无byte_cache后的低内存占用）
        if available_memory < 2:
            parse_w = 1
            workers = 1
        elif available_memory < 4:
            parse_w = 2
            workers = 3
        elif available_memory < 8:
            parse_w = min(cpu_cores, 4)
            workers = min(cpu_cores, 5)
        else:
            parse_w = min(cpu_cores, 8)
            workers = min(cpu_cores, 10)
        
        _log(f"▶ 下载 + Pool 解析+对比（v10 进程隔离，{parse_w} 进程 + {workers} 下载线程）...")
        _log(f"       系统资源: {cpu_cores} 核心, {available_memory:.1f}GB 可用内存")
    except ImportError:
        cpu = cpu_count()
        parse_w = max(2, min(cpu, 6))
        workers = max(3, min(cpu, 8))
        _log(f"▶ 下载 + Pool 解析+对比（v10 进程隔离，{parse_w} 进程 + {workers} 下载线程）...")
        _log(f"       系统资源: {cpu} 核心, 内存检测不可用")
    start_time = time.time()

    # 构建 fname → URL 映射
    fname_url_map: Dict[str, str] = {fname: url for fname, url in excel_file_list}

    # ── 构建 pair 跟踪结构 ──
    pair_queue = queue.Queue()           # 就绪的 pair 任务
    dl_ready: Dict[Tuple[int, str], str] = {}  # (rev, fname) → 临时文件路径
    dl_lock = threading.Lock()
    rev_to_pairs: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
    pair_submitted = set()

    # ── 构建任务列表 ──
    for fname, pair_list in file_pairs.items():
        if not pair_list:
            # 新增文件：跳过对比，后续单独处理
            _log(f"  跳过新增文件: {fname}")
            continue
        _log(f"  处理文件: {fname}，版本对数量: {len(pair_list)}")
        for cur, prv in pair_list:
            _log(f"    版本对: {cur} -> {prv}")
            idx = len(all_pairs_data)
            all_pairs_data.append((cur, prv, fname))
            rev_to_pairs[cur].append((idx, prv))
            rev_to_pairs[prv].append((idx, cur))

    expected_pairs = len(all_pairs_data)
    _log(f"       共 {expected_pairs} 个对比任务")
    if all_pairs_data:

        def _on_version_ready(rev, fname):
            """版本下载完成后，检查关联 pair 是否就绪"""
            with dl_lock:
                submitted_before = len(pair_submitted)
                _log(f"  版本 {rev} 下载完成，文件名: {fname}", level='DEBUG')
                for idx, other_rev in rev_to_pairs.get(rev, []):
                    if idx in pair_submitted:
                        _log(f"  跳过已提交的任务: {idx}", level='DEBUG')
                        continue
                    _, _, f = all_pairs_data[idx]
                    # pair 中的 fname 必须与当前下载的 fname 一致
                    if f != fname:
                        _log(f"  跳过文件名不匹配的任务: {f} != {fname}", level='DEBUG')
                        continue
                    other_path = dl_ready.get((other_rev, f))
                    if other_path is None:
                        _log(f"  跳过另一个版本未就绪的任务: {other_rev}", level='DEBUG')
                        continue
                    pair_submitted.add(idx)
                    cur, prv, fname2 = all_pairs_data[idx]
                    tr, ic, oc = _get_cmp_config(fname2)
                    # 直接使用已保存的临时文件路径
                    cur_path = dl_ready.get((cur, fname2))
                    prv_path = dl_ready.get((prv, fname2))
                    
                    # 验证临时文件路径是否存在
                    if not cur_path:
                        _log(f"  提交任务失败：当前版本临时文件路径不存在: {cur}, {fname2}", level='ERROR')
                        continue
                    if not prv_path:
                        _log(f"  提交任务失败：先前版本临时文件路径不存在: {prv}, {fname2}", level='ERROR')
                        continue
                    
                    # 验证临时文件是否存在
                    if not os.path.exists(cur_path):
                        _log(f"  提交任务失败：当前版本临时文件不存在: {cur_path}", level='ERROR')
                        continue
                    if not os.path.exists(prv_path):
                        _log(f"  提交任务失败：先前版本临时文件不存在: {prv_path}", level='ERROR')
                        continue
                    
                    pair_queue.put((idx, cur, prv, cur_path, prv_path, tr, ic, oc, fname2))
                    _log(f"  提交任务: {idx}, 版本对: {cur} -> {prv}, 文件名: {fname2}", level='DEBUG')

                if len(pair_submitted) == submitted_before:
                    _log(f"  无新任务可提交", level='DEBUG')


        def _download_and_enqueue():
            """下载线程：按 (rev, fname) 下载版本并在就绪时提交 pair 到队列"""
            # 收集所有需要下载的 (rev, fname) 组合（去重）
            dl_tasks_set: set = set()
            for idx2, (cur, prv, fname2) in enumerate(all_pairs_data):
                dl_tasks_set.add((cur, fname2))
                dl_tasks_set.add((prv, fname2))
            dl_tasks = sorted(dl_tasks_set)
            dl_done = 0
            dl_total = len(dl_tasks)

            # 字节缓存命中计数（跨线程累加需加锁）
            byte_cache_hits = [0]
            byte_cache_lock = threading.Lock()

            def _dl(rev, fname):
                # ── 字节缓存优先：命中则跳过 SVN 下载 ──────────────────────────
                import hashlib
                safe_fname = hashlib.md5(fname.encode()).hexdigest()[:12]
                cache_dir = _get_byte_cache_dir()
                cache_file = os.path.join(cache_dir, f"{safe_fname}_{rev}.bin")
                if os.path.exists(cache_file):
                    with byte_cache_lock:
                        byte_cache_hits[0] += 1
                    _log(f"  字节缓存命中: {cache_file}", level='DEBUG')
                    return rev, cache_file, fname, ""
                base = fname_url_map.get(fname, base_url_fallback)
                if base.endswith("/" + fname) or base.endswith(fname):
                    url = base
                else:
                    url = base.rstrip("/") + "/" + fname
                r, data = _download_worker((svn_path, url, rev, svn_user, svn_pass))
                if data:
                    _save_byte_to_cache(fname, rev, data)
                    if os.path.exists(cache_file):
                        return rev, cache_file, fname, url
                    _log(f"  下载成功但缓存文件不存在: {cache_file}", level='ERROR')
                    return rev, None, fname, url
                else:
                    return rev, None, fname, url

            # fallback URL（用于 fname_url_map 中找不到的情况）
            # 如果 excel_file_list[0] 的 URL 末尾已含文件名（直接文件 URL），
            # 则去掉文件名得到目录 URL，以免拼接时产生 fname/fname
            if excel_file_list:
                first_url = excel_file_list[0][1]
                first_fname = excel_file_list[0][0]
                if first_url.endswith("/" + first_fname) or first_url.endswith(first_fname):
                    base_url_fallback = first_url[:first_url.rfind("/") + 1]
                else:
                    base_url_fallback = first_url
            else:
                base_url_fallback = svn_url

            _log(f"  开始下载 {dl_total} 个版本...")
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(_dl, rev, fname): (rev, fname) for rev, fname in dl_tasks}
                for future in as_completed(futures):
                    try:
                        rev, temp_path, fname, url = future.result()
                        dl_done += 1
                        if temp_path:
                            with dl_lock:
                                dl_ready[(rev, fname)] = temp_path
                            _on_version_ready(rev, fname)
                        else:
                            _log(f"  下载失败: 版本 {rev}, 文件 {fname}", level='WARNING')

                        if dl_done % 5 == 0 or dl_done == dl_total:
                            ready = len(pair_submitted)
                            hits = byte_cache_hits[0]
                            cache_hint = f"，字节缓存命中 {hits}" if hits > 0 else ""
                            _log(f"  下载: {dl_done}/{dl_total}，就绪 pair: {ready}/{expected_pairs}{cache_hint}")
                    except Exception as e:
                        _log(f"  下载任务异常: {e}", level='ERROR')
                        dl_done += 1
            pair_queue.put(None)  # 哨兵

        def _task_generator():
            """从 pair_queue 延迟产出任务（Pool 启动时队列为空，等待下载）"""
            _log("  任务生成器已启动，等待任务...", level='DEBUG')
            task_count = 0
            while True:
                try:
                    task = pair_queue.get(timeout=60)
                    if task is None:
                        _log("  收到哨兵，任务生成器结束", level='DEBUG')
                        break
                    task_count += 1
                    _log(f"  生成任务 {task_count}: {task[0]} - 版本对 {task[1]} -> {task[2]}", level='DEBUG')
                    yield task
                except queue.Empty:
                    _log("  任务队列空，等待中...", level='DEBUG')
                    # 检查下载线程是否还在运行
                    if not dl_thread.is_alive():
                        _log("  下载线程已结束，任务生成器结束", level='DEBUG')
                        break

        # ── 启动：下载线程 + Pool 并行 ──
        dl_thread = threading.Thread(target=_download_and_enqueue, daemon=True)
        dl_thread.start()

        all_file_results: Dict[str, List[dict]] = {fname: [] for fname, _ in excel_file_list}
        done_count = 0
        # 跟踪每个文件最新版本的 header 数据（用于输出表头）
        file_max_rev: Dict[str, int] = defaultdict(int)
        file_header_data: Dict[str, dict] = {}
        file_sheet_order: Dict[str, list] = {}

        # 监控下载线程状态
        def monitor_download():
            while dl_thread.is_alive():
                import time
                time.sleep(30)
                with dl_lock:
                    ready_pairs = len(pair_submitted)
                    ready_versions = len(dl_ready)
                _log(f"  下载线程状态: 活跃，就绪版本: {ready_versions}，就绪任务: {ready_pairs}")

        monitor_thread = threading.Thread(target=monitor_download, daemon=True)
        monitor_thread.start()

        with Pool(processes=parse_w, maxtasksperchild=50) as pool:
            for fname, diff_rows, cur_rev, prv_rev, title_rows, id_col, temp_paths, hdr, sheet_order in pool.imap_unordered(
                _process_pair_bytes_worker, _task_generator(), chunksize=1
            ):
                all_file_results[fname].extend(diff_rows)
                # 跟踪最新版本的表头数据
                if hdr and cur_rev > file_max_rev[fname]:
                    file_max_rev[fname] = cur_rev
                    file_header_data[fname] = hdr
                if sheet_order and not file_sheet_order.get(fname):
                    file_sheet_order[fname] = sheet_order
                done_count += 1
                if done_count == 1 or done_count % 5 == 0 or done_count == expected_pairs:
                    _log(f"  对比进度: {done_count}/{expected_pairs}")
                if done_count % 2 == 0:
                    import gc
                    gc.collect()

        dl_thread.join()
        _log("  下载线程已完成")
        
        # 释放所有中间数据结构内存
        global _parsed_cache
        _parsed_cache.clear()
        dl_ready.clear()
        rev_to_pairs.clear()
        pair_submitted.clear()
        import gc
        gc.collect()
        
        total_time = time.time() - start_time
        # 打印解析缓存统计
        total = _cache_hits + _cache_misses
        if total > 0:
            _log(f"       [缓存] 命中 {_cache_hits}/{total}，未命中 {_cache_misses}/{total}")
        _log(f"       总耗时: {total_time:.1f}s")

        # 每个文件的最终汇总 + 去重
        for fname, file_results in all_file_results.items():
            # 按ID去重（排序已在 write_excel 中按 sheet+ID数字进行）
            file_results = _dedupe_by_id(file_results)
            all_file_results[fname] = file_results
            if file_results:
                _log(f"  {fname}: {len(file_results)} 条差异")
        


    # 不处理新增文件，让 main 函数来处理
    return all_file_results, dict(file_header_data), dict(file_sheet_order)


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4: 导出模式
# ═══════════════════════════════════════════════════════════════════════════════
def step4_export_files(svn_url: str, revisions: List[int],
                        export_dir: str,
                        start_date: str = "",
                        end_date: str = "",
                        workers: int = 6,
                        exclude_dirs: str = "",
                        keywords: Optional[List[str]] = None,
                        summary_only: bool = False,
                        svn_user: str = "",
                        svn_pass: str = "") -> None:
    """
    导出指定版本范围内的修改文件。
    按路径段前缀匹配排除目录，保留目录结构导出。
    自动生成 TXT 修改总结文档，智能分类新增/修改/删除文件。
    分类规则：
      - 删除：该文件在当前筛选版本范围内的最新版本操作为 D
      - 新增：任何版本中该文件有 A 操作（且非删除）
      - 修改：所有版本中只有 M 操作
    """
    svn_path = _get_svn_path()
    exclude_set = {d.strip() for d in exclude_dirs.split(",") if d.strip()}

    # 收集每个文件的变更记录：{rel_path: [(rev, action), ...]}
    file_actions: Dict[str, List[Tuple[int, str]]] = {}
    total_revs = len(revisions)
    _log(f"       共 {total_revs} 个版本，正在查询变更文件...")

    # 提取 svn_url 的路径段，用于从 diff 输出中裁剪相对路径
    url_path = urllib.parse.urlparse(svn_url).path.strip("/")
    url_segments = url_path.split("/")
    # 跳过 svn/D3，取分支路径前缀，如 ['branches', '20240606_KR2', 'Client']
    branch_prefix = url_segments[2:] if len(url_segments) > 2 else []

    for i, rev in enumerate(revisions):
        cmd = [svn_path, "diff", "--summarize", "-r", f"{rev - 1}:{rev}", svn_url]
        r = _svn(cmd, timeout=60, svn_user=svn_user, svn_pass=svn_pass)
        # 先记录进度（不受 continue 影响）
        if (i + 1) % 5 == 0 or (i + 1) == total_revs:
            _log(f"       查询进度: {i + 1}/{total_revs}")
        if r.returncode != 0:
            continue
        for line in r.stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            action = parts[0].strip()
            fpath = parts[1].strip()

            # diff 输出可能是 完整URL / 仓库根相对路径 / URL 相对路径
            # 统一提取为相对于 svn_url 的路径
            if fpath.startswith("http://") or fpath.startswith("https://"):
                full_path = urllib.parse.urlparse(fpath).path.strip("/")
            else:
                full_path = fpath.strip("/")

            if not full_path:
                continue

            # 策略1: 匹配完整仓库路径前缀（如 svn/D3/branches/.../Client）
            if full_path.startswith(url_path):
                rel = full_path[len(url_path):].strip("/")
            # 策略2: 匹配分支路径前缀（如 branches/20240606_KR2/Client）
            elif branch_prefix and full_path.split("/")[:len(branch_prefix)] == branch_prefix:
                rel = "/".join(full_path.split("/")[len(branch_prefix):])
            else:
                rel = full_path

            if not rel:
                continue

            # 按路径段匹配排除目录（匹配任意段即排除整个文件夹及其子文件夹）
            rel_segments = rel.split("/")
            if any(seg in exclude_set for seg in rel_segments):
                continue

            if rel not in file_actions:
                file_actions[rel] = []
            file_actions[rel].append((rev, action))

    if not file_actions:
        _log("未找到修改文件")
        return

    _log(f"▶ 共发现 {len(file_actions)} 个修改文件")

    # ── 分类文件 ────────────────────────────────────────────────────────────
    added_files: Dict[str, int] = {}     # rel -> latest_rev
    modified_files: Dict[str, int] = {}  # rel -> latest_rev
    deleted_files: List[str] = []        # rel

    for rel, actions in file_actions.items():
        actions_sorted = sorted(actions, key=lambda x: x[0], reverse=True)
        latest_action = actions_sorted[0][1]

        if latest_action == "D":
            deleted_files.append(rel)
        elif any(a == "A" for _, a in actions_sorted):
            added_files[rel] = actions_sorted[0][0]
        else:
            modified_files[rel] = actions_sorted[0][0]

    # ── 生成 TXT 修改总结文档 ──────────────────────────────────────────────
    kw_prefix = sanitize_filename("_".join(keywords)) if keywords else ""
    txt_name = f"{kw_prefix}_修改总结.txt" if kw_prefix else "修改总结.txt"
    txt_path = os.path.join(export_dir, txt_name)

    os.makedirs(export_dir, exist_ok=True)

    lines = []
    lines.append("=" * 60)
    lines.append("  SVN 修改文件导出总结")
    lines.append("=" * 60)
    lines.append(f"  SVN URL: {svn_url}")
    if keywords:
        lines.append(f"  关键词: {', '.join(keywords)}")
    if start_date:
        lines.append(f"  筛选日期: {start_date} ~ {end_date}")
    if exclude_dirs:
        lines.append(f"  排除文件夹: {exclude_dirs}")
    lines.append(f"  版本范围: r{revisions[-1]} ~ r{revisions[0]}")
    lines.append(f"  导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  导出目录: {export_dir}")
    lines.append("=" * 60)
    lines.append("")

    total_count = len(added_files) + len(modified_files) + len(deleted_files)
    lines.append(f"📊 共 {total_count} 个文件")
    lines.append(f"  ├─ 新增: {len(added_files)} 个")
    lines.append(f"  ├─ 修改: {len(modified_files)} 个")
    lines.append(f"  └─ 删除: {len(deleted_files)} 个")
    lines.append("")

    # ── 按目录分组输出 ──────────────────────────────────
    def _group_by_dir(items):
        """将文件按目录分组，返回 [(目录名, [(文件名, 版本号), ...]), ...]
        过滤掉子目录条目（无文件扩展名），无实际文件的组不显示。
        """
        groups: Dict[str, List[Tuple[str, Optional[int]]]] = {}
        if isinstance(items, dict):
            for rel, rev in sorted(items.items()):
                display = urllib.parse.unquote(rel)
                base = os.path.basename(display)
                if "." not in base:
                    continue
                d = os.path.dirname(display) or "根目录"
                if d not in groups:
                    groups[d] = []
                groups[d].append((base, rev))
        else:
            for rel in sorted(items):
                display = urllib.parse.unquote(rel)
                base = os.path.basename(display)
                if "." not in base:
                    continue
                d = os.path.dirname(display) or "根目录"
                if d not in groups:
                    groups[d] = []
                groups[d].append((base, None))
        result = []
        for d in sorted(groups.keys()):
            entry = (d, sorted(groups[d], key=lambda x: x[0]))
            if entry[1]:
                result.append(entry)
        return result

    # 新增文件中屏蔽 .meta 文件
    added_no_meta = {rel: rev for rel, rev in added_files.items()
                     if not urllib.parse.unquote(rel).endswith(".meta")}
    added_display_count = len(added_no_meta)

    if added_no_meta:
        lines.append("=" * 60)
        lines.append(f"  ✅ 新增文件 ({added_display_count})")
        lines.append("=" * 60)
        lines.append("")
        for d, files in _group_by_dir(added_no_meta):
            lines.append(f"  [{d}]  ({len(files)}个)")
            for base_name, rev in files:
                lines.append(f"    {base_name}")
            lines.append("")

    if modified_files:
        lines.append("=" * 60)
        lines.append(f"  📝 修改文件 ({len(modified_files)})")
        lines.append("=" * 60)
        lines.append("")
        for d, files in _group_by_dir(modified_files):
            lines.append(f"  [{d}]  ({len(files)}个)")
            for base_name, rev in files:
                lines.append(f"    {base_name}")
            lines.append("")

    if deleted_files:
        lines.append("=" * 60)
        lines.append(f"  ❌ 删除文件 ({len(deleted_files)})")
        lines.append("=" * 60)
        lines.append("")
        for d, files in _group_by_dir(deleted_files):
            lines.append(f"  [{d}]  ({len(files)}个)")
            for base_name, _ in files:
                lines.append(f"    {base_name}")
            lines.append("")

    lines.append("=" * 60)
    lines.append("  🛈 说明")
    lines.append("=" * 60)
    if summary_only:
        lines.append("  仅生成修改总结，不导出文件")
    else:
        lines.append("  新增/修改文件已导出到上方目录（保留目录结构）")
    lines.append("  删除文件仅记录，不导出")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    _log(f"📄 修改总结: {txt_path}")

    if summary_only:
        _log("  仅生成总结，跳过文件导出")
        return

    # ── 下载新增/修改文件（保留目录结构）───────────────────────────────────
    download_items = []
    for rel, rev in added_files.items():
        download_items.append((rel, rev))
    for rel, rev in modified_files.items():
        download_items.append((rel, rev))

    if not download_items:
        _log("无新增/修改文件需要导出")
        return

    _log(f"📥 开始导出 {len(download_items)} 个文件...")

    def download_file(item: Tuple[str, int]) -> Tuple[str, bool]:
        rel_path, rev = item
        # 文件 URL = svn_url + / + rel_path（保持 URL 编码）
        file_url = svn_url.rstrip("/") + "/" + rel_path

        # 文件系统路径需要解码 URL 编码（如 %20 → 空格）
        fs_path = urllib.parse.unquote(rel_path)
        out_path = os.path.join(export_dir, fs_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        cmd = [svn_path, "cat", "-r", str(rev), "--non-interactive", "--trust-server-cert"]
        if svn_user:
            cmd.extend(["--username", svn_user])
        if svn_pass:
            cmd.extend(["--password", svn_pass])
        cmd.extend(["--", file_url])
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=120,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if r.returncode == 0:
                with open(out_path, "wb") as out:
                    out.write(r.stdout)
                return rel_path, True
        except Exception:
            pass
        return rel_path, False

    items = [(rel, rev) for rel, rev in download_items]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(download_file, item) for item in items]
        done = 0
        success = 0
        for future in as_completed(futures):
            rel_path, ok = future.result()
            done += 1
            if ok:
                success += 1
            if done % 10 == 0 or done == len(items):
                _log(f"  导出进度: {done}/{len(items)}")

    _log(f"✅ 导出完成: {success}/{len(items)} 个文件成功导出")
    _log(f"📂 输出目录: {export_dir}")


# ═══════════════════════════════════════════════════════════════════════════════
# Excel 输出
# ═══════════════════════════════════════════════════════════════════════════════
def write_excel(results: List[dict], output_path: str,
                  output_cols: Optional[List[str]] = None, title_rows: int = 1,
                  header_data: Optional[dict] = None,
                  sheet_order: Optional[List[str]] = None) -> None:
    """将结果写入 Excel 文件（openpyxl）"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        _write_excel_fallback(results, output_path, output_cols, title_rows)
        return

    wb = Workbook()

    if not results:
        ws = wb.active
        ws.title = "对比结果"
        ws.append(["无差异内容"])
        wb.save(output_path)
        return

    # 排序：按sheet分组（如果有），每组内按ID数字排序
    def _extract_id_num(row: dict) -> int:
        """从ID中提取数字部分用于排序"""
        sid = row.get("ID", "")
        if not sid:
            return 0
        # 提取所有数字
        import re
        nums = re.findall(r'\d+', str(sid))
        if nums:
            # 取最后一个数字（通常是序号）
            return int(nums[-1])
        return 0

    # 样式
    header_fill = PatternFill("solid", fgColor="4472C4")
    header_font = Font(color="FFFFFF", bold=True)
    alt_fill = PatternFill("solid", fgColor="DCE6F1")
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    default_max_width = 55
    min_col_width = 10
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=False)

    if output_cols:
        # 有输出列的文件：输出到一个sheet下面，添加sheet列区分不同sheet
        ws = wb.active
        ws.title = "对比结果"
        
        # 构建表头：操作、当前版本、上一版本 + sheet列 + 配置的输出列
        all_cols = ["操作", "当前版本", "上一版本", "sheet"]
        for col in output_cols:
            if col not in all_cols:
                all_cols.append(col)
        
        # 排序：按原表 sheet 顺序，每组内按ID数字排序
        if sheet_order:
            sheet_order_map = {sn: i for i, sn in enumerate(sheet_order)}
            results.sort(key=lambda r: (sheet_order_map.get(r.get("sheet", "") or "", 999), _extract_id_num(r)))
        else:
            results.sort(key=lambda r: (r.get("sheet", "") or "", _extract_id_num(r)))
        
        # 写入标题行（根据 title_rows 确定标题行数）
        header_rows = title_rows
        # 构建列名→列字母映射（从 header_data 第一个 sheet 的标题行数据）
        col_to_letter_out = {}
        first_sheet = None
        if header_data:
            for sn in header_data:
                first_sheet = sn
                break
            if first_sheet and title_rows in header_data[first_sheet]:
                for letter, hdr_val in header_data[first_sheet][title_rows].items():
                    col_to_letter_out[hdr_val] = letter
        for row_offset in range(header_rows):
            row_num = row_offset + 1
            for col_idx, col_name in enumerate(all_cols, 1):
                if col_idx <= 4:  # 固定列
                    cell = ws.cell(row=row_num, column=col_idx, value=col_name if row_offset == 0 else "")
                else:
                    val = ""
                    if col_name in col_to_letter_out:
                        letter = col_to_letter_out[col_name]
                        if header_data and first_sheet and row_num in header_data[first_sheet]:
                            val_orig = header_data[first_sheet][row_num].get(letter, "")
                            if val_orig:
                                val = val_orig
                    cell = ws.cell(row=row_num, column=col_idx, value=val)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center
                cell.border = border
        
        # 写入数据行（全部左对齐）
        for row_idx, row_data in enumerate(results, title_rows + 1):
            fill = alt_fill if (row_idx - title_rows) % 2 == 0 else None
            for col_idx, col_name in enumerate(all_cols, 1):
                # 映射表头名称到数据字段
                data_key = col_name
                if col_name == "上一版本":
                    data_key = "前一版本"
                val = row_data.get(data_key, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.border = border
                if fill:
                    cell.fill = fill
                # 全部左对齐
                cell.alignment = left_align

            # 操作类型颜色
            op_cell = ws.cell(row=row_idx, column=all_cols.index("操作") + 1)
            if op_cell.value == "新增":
                op_cell.font = Font(color="00B050", bold=True)
            elif op_cell.value == "修改":
                op_cell.font = Font(color="C00000", bold=True)
            elif op_cell.value == "删除":
                op_cell.font = Font(color="808080", bold=True)

        # 设置列宽：自适应内容，最大不超过 default_max_width
        for col_idx, col_name in enumerate(all_cols, 1):
            # 计算该列最大内容长度
            max_len = len(col_name)
            for row_idx in range(title_rows + 1, len(results) + title_rows + 1):
                val = ws.cell(row=row_idx, column=col_idx).value
                if val:
                    max_len = max(max_len, len(str(val)))
            # 列宽 = 内容长度 + 2，最小8，最大50
            col_width = min(max(max_len + 4, min_col_width), default_max_width)
            ws.column_dimensions[get_column_letter(col_idx)].width = col_width

        # 冻结首行
        ws.freeze_panes = f"A{title_rows + 1}"
    else:
        # 没有输出列: 按 sheet 分组，输出 2 行原始表头（来自最新版本）
        sheet_groups = {}
        for row in results:
            sheet_name = row.get("sheet", "对比结果")
            if sheet_name not in sheet_groups:
                sheet_groups[sheet_name] = []
            sheet_groups[sheet_name].append(row)

        header_rows = title_rows + 1  # 标题行数：原第1行~第 title_rows+1 行

        for sheet_name in sheet_groups:
            sheet_results = sheet_groups[sheet_name]
            sheet_results.sort(key=lambda r: _extract_id_num(r))

        sorted_sheets = sheet_order if sheet_order else sorted(sheet_groups.keys())
        for sheet_name in sorted_sheets:
            if sheet_name not in sheet_groups:
                continue
            sheet_results = sheet_groups[sheet_name]
            ws = wb.create_sheet(title=sheet_name)

            fixed_cols = {"操作", "当前版本", "上一版本", "前一版本", "sheet",
                          "_id_changed", "前一版本_ID", "前一版本_SC", "前一版本_sub"}
            all_cols = ["操作", "当前版本", "上一版本"]
            data_cols_set: set = set()
            for row in sheet_results:
                for k in row.keys():
                    if k not in fixed_cols and k not in all_cols and k.strip():
                        data_cols_set.add(k)

            # ── 构建 col_name → letter 映射（从标题行原始数据）────────────────
            col_to_letter: Dict[str, str] = {}
            if header_data and sheet_name in header_data:
                hd_sheet = header_data[sheet_name]
                if title_rows in hd_sheet:
                    _seen_hdrs_w: set = set()
                    for letter, hdr_val in hd_sheet[title_rows].items():
                        safe_val = hdr_val if hdr_val not in _seen_hdrs_w else f"{hdr_val}__{letter}"
                        _seen_hdrs_w.add(hdr_val)
                        col_to_letter[safe_val] = letter

            # 按原表列字母序排列数据列
            def _col_letter_to_num(letter: str) -> int:
                n = 0
                for ch in letter.upper():
                    n = n * 26 + (ord(ch) - ord('A') + 1)
                return n
            def _col_sort_key(name: str) -> tuple:
                letter = col_to_letter.get(name, "")
                if letter:
                    return (0, _col_letter_to_num(letter))
                return (1, name)
            # 只保留有表头的列
            data_cols_set = {k for k in data_cols_set if k in col_to_letter}
            all_cols.extend(sorted(data_cols_set, key=_col_sort_key))

            # ── header_rows 行表头 ─────────────────────────────
            for row_idx in range(1, header_rows + 1):
                for col_idx, col_name in enumerate(all_cols, 1):
                    if col_idx <= 3:  # 固定列
                        if row_idx == 1:
                            cell = ws.cell(row=1, column=col_idx, value=col_name)
                        else:
                            cell = ws.cell(row=row_idx, column=col_idx, value="")
                    else:
                        val = ""
                        if (header_data and sheet_name in header_data
                                and col_name in col_to_letter):
                            letter = col_to_letter[col_name]
                            val = header_data[sheet_name].get(row_idx, {}).get(letter, "")
                        cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = center
                    cell.border = border

            # ── 数据行（从第 3 行开始）─────────────────────────────
            for row_idx, row_data in enumerate(sheet_results, header_rows + 1):
                fill = alt_fill if (row_idx - header_rows) % 2 == 0 else None
                for col_idx, col_name in enumerate(all_cols, 1):
                    data_key = col_name
                    if col_name == "上一版本":
                        data_key = "前一版本"
                    val = row_data.get(data_key, "")
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.border = border
                    if fill:
                        cell.fill = fill
                    cell.alignment = left_align

                op_cell = ws.cell(row=row_idx, column=all_cols.index("操作") + 1)
                if op_cell.value == "新增":
                    op_cell.font = Font(color="00B050", bold=True)
                elif op_cell.value == "修改":
                    op_cell.font = Font(color="C00000", bold=True)
                elif op_cell.value == "删除":
                    op_cell.font = Font(color="808080", bold=True)

            # 列宽
            for col_idx, col_name in enumerate(all_cols, 1):
                max_len = len(col_name)
                for row_idx in range(header_rows + 1, len(sheet_results) + header_rows + 1):
                    val = ws.cell(row=row_idx, column=col_idx).value
                    if val:
                        max_len = max(max_len, len(str(val)))
                col_width = min(max(max_len + 4, min_col_width), default_max_width)
                ws.column_dimensions[get_column_letter(col_idx)].width = col_width

            ws.freeze_panes = f"A{header_rows + 1}"

    # 删除默认的工作表（如果存在）
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])

    wb.save(output_path)


def _write_excel_fallback(results: List[dict], output_path: str,
                           output_cols: Optional[List[str]] = None, title_rows: int = 1) -> None:
    """openpyxl 不可用时的 CSV 降级"""
    import csv
    if not results:
        with open(output_path.replace(".xlsx", ".csv"), "w", encoding="utf-8-sig", newline="") as f:
            f.write("\ufeff")
            f.write("无差异内容\n")
        return

    # 构建表头：操作、当前版本、上一版本 + 配置的输出列
    all_cols = ["操作", "当前版本", "上一版本"]
    # 输出列不为空时，添加 sheet 列和 ID 列
    if output_cols:
        all_cols.append("ID")
        all_cols.append("sheet")
        for col in output_cols:
            if col not in all_cols:
                all_cols.append(col)
    else:
        fixed_cols = {"操作", "当前版本", "上一版本", "前一版本", "sheet"}
        for row in results:
            for k in row.keys():
                if k not in fixed_cols and k not in all_cols:
                    all_cols.append(k)

    csv_path = output_path.replace(".xlsx", ".csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_cols)
        # 写入标题行（根据 title_rows 确定标题行数）
        for row_offset in range(title_rows):
            if row_offset == 0:
                writer.writeheader()
            else:
                # 写入空行作为标题行
                f.write("," * (len(all_cols) - 1) + "\n")
        # 映射数据行
        mapped_results = []
        for row in results:
            mapped = {}
            for col in all_cols:
                data_key = col
                if col == "上一版本":
                    data_key = "前一版本"
                mapped[col] = row.get(data_key, "")
            mapped_results.append(mapped)
        writer.writerows(mapped_results)
    _log(f"[注意] 写为 CSV: {csv_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════════

# 自动检测 CPU 核心数
try:
    _cpu_count = multiprocessing.cpu_count()
except:
    _cpu_count = 8  # 默认Fallback

# 全局并发设置（可通过命令行参数覆盖）
def _get_optimal_workers():
    try:
        import psutil
        cpu_cores = psutil.cpu_count(logical=True)
        available_memory = psutil.virtual_memory().available / (1024 * 1024 * 1024)  # GB
        # 下载线程：I/O密集，可适当多些，但不超过20
        download_workers = min(20, max(4, cpu_cores * 2))
        # 解析线程：CPU密集，不超过CPU核心数
        parse_workers = min(cpu_cores, max(4, cpu_cores))
        # 根据可用内存调整
        if available_memory < 8:
            download_workers = min(10, download_workers)
            parse_workers = min(cpu_cores // 2, parse_workers)
        elif available_memory < 16:
            download_workers = min(15, download_workers)
        return download_workers, parse_workers
    except Exception:
        # psutil 不可用时，使用默认值
        cpu_cores = _cpu_count
        download_workers = max(4, min(12, cpu_cores * 2))
        parse_workers = max(4, min(cpu_cores, 8))
        return download_workers, parse_workers

_download_workers, _parse_workers = _get_optimal_workers()

def main():
    # 重置全局缓存和统计变量，避免多次执行时的状态残留
    global _parsed_cache, _cache_hits, _cache_misses, _byte_cache_hits, _byte_cache_misses
    _parsed_cache = {}
    _cache_hits = 0
    _cache_misses = 0
    _byte_cache_hits = 0
    _byte_cache_misses = 0

    parser = argparse.ArgumentParser(description="SVN 一键对比工具")
    parser.add_argument("-u", "--url", required=True, help="SVN 文件地址")
    parser.add_argument("-s", "--start", required=True, help="开始日期 YYYY-MM-DD")
    parser.add_argument("-e", "--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("-k", "--keyword", action="append", default=[], help="关键词")
    parser.add_argument("--author", default="", help="提交者")
    parser.add_argument("-o", "--output", default="", help="输出目录（对比模式，默认输出\\Excel）")
    parser.add_argument("-w", "--workers", default=str(_download_workers), help=f"下载并发数（默认 {_download_workers}）")
    parser.add_argument("-p", "--parse", default=str(_parse_workers), help=f"解析并发数（默认 {_parse_workers}）")
    parser.add_argument("--export", action="store_true", help="导出模式")
    parser.add_argument("--summary", action="store_true", help="仅生成修改总结（不导出文件）")
    parser.add_argument("--export-dir", default="", help="导出模式输出目录")
    parser.add_argument("--exclude-dirs", default="", help="导出模式：过滤目录")
    parser.add_argument("--svn-diff-filter", action="store_true", default=True,
                        help="对比模式：先用 svn diff --summarize 过滤版本对，跳过无变更的对（默认开启）")
    parser.add_argument("--clear-cache", action="store_true",
                        help="清除解析缓存后退出")
    parser.add_argument("--log-level", default="INFO", choices=LOG_LEVELS.keys(),
                        help="日志级别（默认 INFO）")
    parser.add_argument("--svn-user", default="", help="SVN 用户名")
    parser.add_argument("--svn-pass", default="", help="SVN 密码")
    args = parser.parse_args()

    # 设置日志级别
    global LOG_LEVEL
    LOG_LEVEL = LOG_LEVELS[args.log_level]

    # ── 清除缓存 ─────────────────────────────────────────────────────────────────
    if getattr(args, "clear_cache", False):
        n = _clear_parse_cache()
        _log(f"🗑 缓存已清除，删除 {n} 个缓存文件")
        return

    keywords = [k.strip() for k in args.keyword if k.strip()]
    workers = max(1, int(args.workers))
    parse_workers = max(1, int(args.parse))

    # 启动资源监控
    _resource_monitor.start()

    t0 = time.time()

    # ── 导出模式 ─────────────────────────────────────────────────────────────
    if args.export:
        export_dir = args.export_dir.strip() or os.path.dirname(os.path.abspath(__file__))
        revisions = step1_query_revisions(
            args.url, args.start, args.end,
            author=args.author or None, keywords=keywords or None,
            svn_user=args.svn_user,
            svn_pass=args.svn_pass)
        if not revisions:
            _log("[警告] 未找到符合条件的提交记录")
            _log("完成!")
            return
        _log(f"\n共计 {len(revisions)} 个版本，开始导出修改文件...\n")
        step4_export_files(args.url, revisions, export_dir,
                           start_date=args.start,
                           end_date=args.end,
                           workers=workers, exclude_dirs=args.exclude_dirs,
                           keywords=keywords,
                           svn_user=args.svn_user,
                           svn_pass=args.svn_pass)
        total = time.time() - t0
        _log(f"\n总耗时: {total:.1f}s")
        _log("完成!")
        return

    # ── 总结模式 ─────────────────────────────────────────────────────────────
    if args.summary:
        summary_dir = args.export_dir.strip() or os.path.dirname(os.path.abspath(__file__))
        _log(f"\n📋 仅生成修改总结，不导出文件...\n")
        revisions = step1_query_revisions(
            args.url, args.start, args.end,
            author=args.author or None, keywords=keywords or None,
            svn_user=args.svn_user,
            svn_pass=args.svn_pass)
        if not revisions:
            _log("[警告] 未找到符合条件的提交记录")
            _log("完成!")
            return
        step4_export_files(args.url, revisions, summary_dir,
                           start_date=args.start,
                           end_date=args.end,
                           workers=workers, exclude_dirs=args.exclude_dirs,
                           keywords=keywords,
                           summary_only=True,
                           svn_user=args.svn_user,
                           svn_pass=args.svn_pass)
        total = time.time() - t0
        _log(f"\n总耗时: {total:.1f}s")
        _log("完成!")
        return

    # ── 对比模式 ─────────────────────────────────────────────────────────────

    # Step 1: 查询每个文件的版本对
    t1 = time.time()
    _log("\n" + "=" * 50)
    _log("▶ Step 1/2  查询文件版本对...")
    file_pairs, is_direct_file_url = step1_query_file_pairs(
        args.url, args.start, args.end,
        author=args.author or None, keywords=keywords or None,
        svn_user=args.svn_user,
        svn_pass=args.svn_pass)
    t1e = time.time() - t1
    _log(f"       耗时: {t1e:.1f}s")

    if not file_pairs:
        _log("[警告] 未找到任何文件，写入空结果")
        if args.output:
            out_abs = os.path.abspath(args.output)
            if os.path.splitext(out_abs)[1].lower() in (".xlsx", ".xls", ".xlsm"):
                write_excel([], out_abs)
            else:
                os.makedirs(out_abs, exist_ok=True)
                write_excel([], os.path.join(out_abs, "对比结果.xlsx"))
        _log("完成!")
        return

    # 加载 per-file 配置（GUI 预设）
    _load_cmp_file_settings()

    t2 = time.time()
    _log("▶ Step 2/2  下载 & 解析 & 对比...")
    all_file_results, file_header_data, file_sheet_order = step3_download_and_compare(
        args.url,
        workers=workers,
        parse_workers=parse_workers,
        file_pairs=file_pairs,
        svn_diff_filter=args.svn_diff_filter and not is_direct_file_url,
        svn_user=args.svn_user,
        svn_pass=args.svn_pass)
    t2e = time.time() - t2
    _log(f"       耗时: {t2e:.1f}s")

    # 写出
    t3 = time.time()
    _log("\n▶ 写入 Excel 文件...")
    # 智能构建文件名前缀：sanitize(关键词_joined) 或 fallback 为 对比结果
    kw_prefix = sanitize_filename("_".join(keywords)) if keywords else ""
    base_name = kw_prefix if kw_prefix else "对比结果"
    if not args.output:
        # 对比模式默认输出到 输出\Excel 目录
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "输出", "Excel")
    else:
        out_abs = os.path.abspath(args.output)
        # 智能判断：如果是文件路径（有扩展名），提取目录
        if os.path.splitext(out_abs)[1].lower() in (".xlsx", ".xls", ".xlsm"):
            out_dir = os.path.dirname(out_abs)
        else:
            out_dir = out_abs
    os.makedirs(out_dir, exist_ok=True)
    # 关键词作为父文件夹，文件按 SVN 目录结构输出（如 输出/Excel/裂隙/Text/Texts.xlsm）
    if base_name:
        out_dir = os.path.join(out_dir, base_name)
    os.makedirs(out_dir, exist_ok=True)

    # 有具体文件名时按文件名读高级设置的 output_cols（见下方循环）
    # 空结果写单个文件时无文件名，用 None（全列）
    out_cols_list = None

    # 处理有差异的文件
    total_results = 0
    processed_files = set()
    
    if all_file_results:
        for fname, results in all_file_results.items():
            if fname in file_pairs and not file_pairs[fname]:
                continue
            tr, _, oc = _get_cmp_config(fname)
            out_cols_list = oc if oc else None
            out_file = os.path.join(out_dir, fname)
            out_subdir = os.path.dirname(out_file)
            if out_subdir:
                os.makedirs(out_subdir, exist_ok=True)
            if results:
                _log(f"\n{fname}: {len(results)} 条差异 -> {out_file}")
            else:
                _log(f"\n{fname}: 无差异 -> {out_file}")
            write_excel(results, out_file, out_cols_list, tr,
                        file_header_data.get(fname),
                        file_sheet_order.get(fname))
            total_results += len(results)
            processed_files.add(fname)
    
    # 处理新增文件（版本对列表为空的文件）
    svn_path = _get_svn_path()
    
    # 收集所有筛选出来的版本号
    all_filtered_revs = set()
    for pairs in file_pairs.values():
        for cur, prv in pairs:
            all_filtered_revs.add(cur)
            all_filtered_revs.add(prv)
    
    # 收集新增的文件名
    new_files_list = []
    
    for fname, pair_list in file_pairs.items():
        if fname in processed_files:
            continue
        
        # 只处理新增文件（版本对列表为空）
        if pair_list:
            continue
        
        # 收集新增的文件名
        new_files_list.append(fname)
        
        # 构建文件的完整 URL
        url_path = urllib.parse.urlparse(args.url).path or ""
        svn_url_is_file = url_path.lower().endswith((".xlsx", ".xlsm", ".xls"))
        if svn_url_is_file:
            file_url = args.url
        else:
            # 使用与 step1_query_file_pairs 相同的逻辑构建文件 URL
            url_segments = urllib.parse.urlparse(args.url).path.strip("/").split("/")
            parsed_base = urllib.parse.urlparse(args.url)
            server_root = f"{parsed_base.scheme}://{parsed_base.netloc}/" + "/".join(url_segments[:2])
            target_prefix = url_segments[2:]
            full_path = "/".join(target_prefix + fname.split("/"))
            file_url = server_root + "/" + full_path
        
        # 为新增文件添加前缀
        base_name = os.path.basename(fname)
        dir_name = os.path.dirname(fname)
        new_base_name = f"新增_{base_name}"
        new_fname = os.path.join(dir_name, new_base_name) if dir_name else new_base_name
        out_file = os.path.join(out_dir, new_fname)
        out_subdir = os.path.dirname(out_file)
        if out_subdir:
            os.makedirs(out_subdir, exist_ok=True)
        
        # 直接复制原文件（使用筛选出来的版本号的最新版本）
        _log(f"\n{fname}: 新增文件，直接复制原文件 -> {out_file}")
        try:
            # 获取该文件的所有版本
            cmd_file = [svn_path, "log", file_url, "--xml", "-r", _svn_log_range(args.start, args.end)]
            r_file = _svn(cmd_file, timeout=120, svn_user=args.svn_user, svn_pass=args.svn_pass)
            if r_file.returncode != 0:
                _log(f"  [警告] 无法获取 {fname} 的版本历史")
                continue
            
            try:
                root_file = etree.fromstring(r_file.stdout)
                entries_file = root_file.findall(".//logentry")
            except Exception:
                _log(f"  [警告] 无法解析 {fname} 的版本历史")
                continue
            
            # 解析该文件在日期范围内的所有版本号
            file_all_revs: List[int] = []
            for entry in entries_file:
                rev_text = entry.get("revision", "")
                if rev_text:
                    try:
                        file_all_revs.append(int(rev_text))
                    except ValueError:
                        pass
            
            # 找出该文件在筛选出来的版本号中的版本
            filtered_revs = sorted([r for r in file_all_revs if r in all_filtered_revs], reverse=True)
            
            if not filtered_revs:
                # 如果没有筛选出来的版本号，使用最新版本
                if file_all_revs:
                    latest_rev = max(file_all_revs)
                else:
                    # 如果没有版本历史，获取最新版本
                    cmd = [svn_path, "log", file_url, "-l", "1", "--xml"]
                    r = _svn(cmd, timeout=30, svn_user=args.svn_user, svn_pass=args.svn_pass)
                    if r.returncode != 0:
                        _log(f"  [警告] 无法获取 {fname} 的最新版本")
                        continue
                    
                    root = etree.fromstring(r.stdout)
                    entry = root.find(".//logentry")
                    if entry is None:
                        _log(f"  [警告] 无法获取 {fname} 的最新版本")
                        continue
                    
                    latest_rev = int(entry.get("revision"))
            else:
                # 使用筛选出来的版本号的最新版本
                latest_rev = filtered_revs[0]
            
            # 下载文件内容
            cmd_cat = [svn_path, "cat", "-r", str(latest_rev), file_url]
            r_cat = _svn(cmd_cat, timeout=60, svn_user=args.svn_user, svn_pass=args.svn_pass)
            if r_cat.returncode != 0 or not r_cat.stdout:
                _log(f"  [警告] 下载 {fname} r{latest_rev} 失败")
                continue
            
            # 写入文件
            with open(out_file, "wb") as f:
                f.write(r_cat.stdout)
            _log(f"  [成功] 已复制 {fname} r{latest_rev}")
        except Exception as e:
            _log(f"  [警告] 复制 {fname} 失败: {e}")
    
    # 生成修改总结的 txt 文档
    if new_files_list or processed_files:
        # 计算 excel 文件夹的路径
        if args.output:
            # 如果用户指定了输出目录，使用该目录
            excel_dir = os.path.abspath(args.output)
            # 如果指定的是文件，使用其所在目录
            if os.path.isfile(excel_dir):
                excel_dir = os.path.dirname(excel_dir)
        else:
            # 使用默认的 excel 文件夹
            excel_dir = out_dir
        
        # 根据是否有关键词决定输出路径
        if keywords:
            # 有关键词：文件夹用关键词命名，文件名是"修改总结.txt"
            keyword_str = '_'.join(keywords)
            txt_dir = os.path.join(excel_dir, keyword_str)
            os.makedirs(txt_dir, exist_ok=True)
            txt_path = os.path.join(txt_dir, "修改总结.txt")
        else:
            # 没有关键词：直接放在excel文件夹里面
            txt_path = os.path.join(excel_dir, "修改总结.txt")
        
        # 写入 txt 文档
        with open(txt_path, "w", encoding="utf-8-sig") as f:
            f.write(f"修改总结\n")
            f.write(f"开始日期: {args.start}\n")
            f.write(f"结束日期: {args.end}\n")
            if keywords:
                f.write(f"关键词: {', '.join(keywords)}\n")
            
            # 记录新增文件
            if new_files_list:
                f.write(f"\n共计 {len(new_files_list)} 个新增文件:\n")
                for i, fname in enumerate(new_files_list, 1):
                    f.write(f"{i}. 原文件: {fname}\n")
            
            # 记录修改文件
            if processed_files:
                f.write(f"\n共计 {len(processed_files)} 个修改文件:\n")
                for i, fname in enumerate(processed_files, 1):
                    diff_count = len(all_file_results.get(fname, []))
                    if diff_count > 0:
                        f.write(f"{i}. 原文件: {fname}（{diff_count} 条差异）\n")
                    else:
                        f.write(f"{i}. 原文件: {fname}（无差异）\n")
        
        _log(f"\n[成功] 已生成修改总结: {txt_path}")
    
    if total_results > 0:
        _log(f"\n共计 {len(all_file_results)} 个文件，{total_results} 条差异")
    else:
        _log("\n无差异内容")

    t3e = time.time() - t3
    _log(f"       耗时: {t3e:.1f}s")

    # 停止资源监控
    _resource_monitor.stop()
    stats = _resource_monitor.get_stats()

    total = time.time() - t0
    _log(f"总耗时: {total:.1f}s")
    _log(f"资源使用: CPU {stats['cpu']:.1f}%, 内存 {stats['memory']:.1f}MB")
    _log(f"缓存命中: 解析 {_cache_hits}/{_cache_hits + _cache_misses} ({_cache_hits/(max(1, _cache_hits + _cache_misses))*100:.1f}%), 字节 {_byte_cache_hits}/{_byte_cache_hits + _byte_cache_misses} ({_byte_cache_hits/(max(1, _byte_cache_hits + _byte_cache_misses))*100:.1f}%)")
    _log("完成!")


if __name__ == "__main__":
    main()
