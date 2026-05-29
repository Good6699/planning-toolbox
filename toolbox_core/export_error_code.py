#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误码导出工具 - 完整复刻 ExcelTool2.exe 旧格式
"""

import argparse
import os
import shutil
import struct
import sys
import uuid


PROTO_TEMPLATE = '''syntax = "proto3";
message ErrorMessage {
        int32 ID = 1;
        string ErrorString = 2;
}
message ErrorMessageData {
        map<int32,ErrorMessage> data = 1;
}
'''

HRL_TEMPLATE = '''-ifndef(cfg_errorMessage_hrl).
-define(cfg_errorMessage_hrl, true).

-record(errorMessageCfg, {
        iD,
        errorString
}).

-endif.
'''


def _write7bit(value):
    value = value & 0xFFFFFFFF
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _escape_text(s):
    raw = str(s).encode("utf-8")
    parts = []
    for b in raw:
        if b == 0x09:
            parts.append("\\t")
        elif b == 0x0A:
            parts.append("\\n")
        elif b == 0x0D:
            parts.append("\\r")
        elif b == 0x22:
            parts.append('\\"')
        elif b == 0x5C:
            parts.append("\\\\")
        elif 0x20 <= b < 0x7F:
            parts.append(chr(b))
        else:
            parts.append(f"\\{b:03o}")
    return "".join(parts)


def _read_xlsm_data(xlsm_path):
    from openpyxl import load_workbook
    wb = load_workbook(xlsm_path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for xr, row in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
        a = str(row[0]).strip().lower() if row[0] is not None else ""
        if not a or a == "no":
            continue
        c = row[2]
        if c is None or not str(c).strip():
            continue
        b = row[1]
        if b is None:
            continue
        try:
            rid = int(float(str(b)))
        except:
            continue
        rows.append((xr, rid, str(c)))
        if a == "end":
            break
    wb.close()
    return rows


def _build_similars(entries):
    LOOKBACK = 5
    similars = []
    for idx, entry in enumerate(entries):
        xr, rid, text = entry
        found = False
        for prev in range(max(0, idx - 20), idx):
            prev_xr = entries[prev][0]
            if xr - prev_xr > LOOKBACK:
                continue
            if entries[prev][2] == text:
                p_xr = entries[prev][0]
                for g in similars:
                    if p_xr in g:
                        if xr not in g:
                            g.append(xr)
                        found = True
                        break
                if found:
                    break
        if not found:
            similars.append([xr])
    return similars


def _gen_monolith_header(entry_count):
    buf = bytearray()
    buf += struct.pack("<I", 32)
    uuid_str = str(uuid.uuid4()).replace("-", "")[:16]
    buf += uuid_str.encode("utf-16-le")
    buf += struct.pack("<I", 0)
    buf += struct.pack("<I", entry_count)
    buf += struct.pack("<I", 3)
    buf += struct.pack("<I", 1)
    buf += struct.pack("<I", 0)
    fn = "errorMessage".encode("utf-16-le")
    fn_len = struct.pack("<I", len(fn) // 2)
    buf += fn_len
    buf += fn
    buf += fn_len
    buf += fn
    buf += fn_len
    buf += fn
    buf += struct.pack("<I", entry_count)
    for t, p in [(3, 0), (0, 0), (0, 0), (3, 0), (0, 0), (0, 0), (3, 0), (0, 0), (3, 0)]:
        buf += struct.pack("<I", t)
        buf += struct.pack("<I", p)
    buf += struct.pack("<I", 0)
    buf += struct.pack("<I", 1)
    return bytes(buf)


def _gen_monolith_entries(entries):
    buf = bytearray()
    if not entries:
        return bytes(buf)
    e0 = entries[0]
    buf += e0["id_str"].encode("utf-16-le")
    buf += struct.pack("<I", len(e0["quoted"]))
    buf += e0["quoted"].encode("utf-16-le")
    buf += struct.pack("<I", 3)
    buf += struct.pack("<I", 0)
    for e in entries[1:]:
        id_bytes = e["id_str"].encode("utf-16-le")
        buf += struct.pack("<I", len(id_bytes) // 2)
        buf += id_bytes
        buf += struct.pack("<I", len(e["quoted"]))
        buf += e["quoted"].encode("utf-16-le")
        buf += struct.pack("<I", 3)
        buf += struct.pack("<I", 0)
    return bytes(buf)


def _write_export_txt(entries, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    for i, entry in enumerate(entries):
        row_id, text = entry[1], entry[2]
        lines.append(f'ErrorString: "{_escape_text(text)}"')
        lines.append("")
        if i < len(entries) - 1:
            next_id = entries[i + 1][1]
            lines.append(f"ID: {next_id}")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")


def _write_monolith(entries, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    me = []
    for entry in entries:
        rid, text = entry[1], entry[2]
        me.append({"id_str": str(rid), "quoted": '"' + text + '"'})
    hdr = _gen_monolith_header(len(me))
    dat = _gen_monolith_entries(me)
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(dat)


def _write_protobuf(entries, bin_path, hd_path, txt_path):
    """
    BIN: 0x12 write7bit(utf8_len) utf8 (baseline), 去重条目不占BIN空间
    HD Header: LE uint32 × 5 (version, nameLen, name, rowCount, is_int=1)
    HD Body: write7bit(real_id) + write7bit(utf8_data_offset) 每对
    """
    os.makedirs(os.path.dirname(bin_path), exist_ok=True)

    similars = _build_similars(entries)

    def _find_base(xr):
        for g in similars:
            if xr in g:
                return g[0]
        return xr

    base_of = {}
    for entry in entries:
        base_of[entry[0]] = _find_base(entry[0])

    linetoix = {}
    for idx, entry in enumerate(entries):
        linetoix[entry[0]] = idx

    bin_data = bytearray()
    hd_entries = []
    base_utf8_off = {}

    for idx, entry in enumerate(entries):
        xr, rid, text = entry
        base_xr = base_of[xr]
        is_base = (base_xr == xr)

        if is_base:
            str_bytes = text.encode("utf-8")
            strlen = len(str_bytes)
            strlen_7bit = _write7bit(strlen)
            head_len = 1 + len(strlen_7bit)
            serialized = bytearray()
            serialized.append(0x12)
            serialized.extend(strlen_7bit)
            serialized.extend(str_bytes)
            utf8_off = len(bin_data) + head_len
            bin_data.extend(serialized)
            base_utf8_off[base_xr] = utf8_off
            hd_entries.append((rid, utf8_off))
        else:
            base_text = entries[linetoix[base_xr]][2]
            if text == base_text:
                utf8_off = base_utf8_off[base_xr]
                hd_entries.append((rid, utf8_off))
            else:
                str_bytes = text.encode("utf-8")
                strlen = len(str_bytes)
                strlen_7bit = _write7bit(strlen)
                head_len = 1 + len(strlen_7bit)
                serialized = bytearray()
                serialized.append(0x12)
                serialized.extend(strlen_7bit)
                serialized.extend(str_bytes)
                utf8_off = len(bin_data) + head_len
                bin_data.extend(serialized)
                hd_entries.append((rid, utf8_off))

    with open(hd_path, "wb") as f:
        f.write(struct.pack("<I", 1))
        name_bytes = b"ErrorMessage"
        f.write(struct.pack("<I", len(name_bytes)))
        f.write(name_bytes)
        f.write(struct.pack("<I", len(hd_entries)))
        f.write(struct.pack("<I", 1))
        for rid, utf8_off in hd_entries:
            f.write(_write7bit(rid))
            f.write(_write7bit(utf8_off))

    with open(bin_path, "wb") as f:
        f.write(bytes(bin_data))

    with open(txt_path, "w", encoding="utf-8", newline="\n") as f:
        for entry in entries:
            f.write(f"ID: {entry[1]}\n")
            f.write(f'ErrorString: "{entry[2]}"\n')
            f.write("\n")


def _write_erl(entries, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = [e[1] for e in entries]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("-module(cfg_errorMessage).\n")
        f.write('-include("cfg_errorMessage.hrl").\n')
        f.write("-export([row/1, first_row/0, last_row/0, rows/1, rows/0, keys_length/0]).\n")
        f.write("-export([getRow/1, getKeyList/0]).\n")
        f.write("\n%% 指定行\n")
        f.write("row(Id) -> getRow(Id).\n\n")
        f.write("%% 第一行、最后一行\n")
        f.write("first_row() -> getRow(0).\n")
        if keys:
            f.write(f"last_row() -> getRow({keys[-1]}).\n")
        f.write("\n%% 行列表\n")
        f.write("rows(KeyList) -> [row(Key) || Key <- KeyList].\n")
        f.write("rows() -> rows(getKeyList()).\n\n")
        f.write("%% Key列表长度\n")
        f.write(f"keys_length() -> {len(keys)}.\n\n")
        for entry in entries:
            rid, text = entry[1], entry[2]
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            f.write(f"getRow({rid}) -> #errorMessageCfg{{\n")
            f.write(f"\tiD = {rid},\n")
            f.write(f'\terrorString = "{escaped}"}};\n')
        f.write("getKeyList() -> [\n")
        items = [str(k) for k in keys]
        for i in range(0, len(items), 20):
            chunk = items[i:i + 20]
            sep = "].\n" if i + 20 >= len(items) else ",\n"
            f.write("\t" + ",".join(chunk) + sep)


def _derive_project_root(lang_dir):
    parent = os.path.dirname(lang_dir)
    gp = os.path.dirname(parent)
    ggp = os.path.dirname(gp)
    for p in [ggp, gp, parent]:
        if os.path.isdir(os.path.join(p, "gameData")) or os.path.isdir(os.path.join(p, "Client")):
            return p
    return parent


def _derive_client_bin_dir(lang_dir, lang_code):
    root = _derive_project_root(lang_dir)
    return os.path.join(root, "Client", "Assets", "StreamingAssets", "Language", lang_code, "BinData", "bin")


def _ensure_static_files(lang_dir):
    results = []
    pd = os.path.join(lang_dir, "protobuf", "proto", "out")
    cd = os.path.join(lang_dir, "config")
    pp = os.path.join(pd, "ErrorMessage.proto")
    if not os.path.isfile(pp):
        os.makedirs(pd, exist_ok=True)
        with open(pp, "w", encoding="utf-8", newline="\n") as f:
            f.write(PROTO_TEMPLATE)
        results.append("proto")
    hp = os.path.join(cd, "cfg_errorMessage.hrl")
    if not os.path.isfile(hp):
        os.makedirs(cd, exist_ok=True)
        with open(hp, "w", encoding="utf-8", newline="\n") as f:
            f.write(HRL_TEMPLATE)
        results.append("hrl")
    return results


def export_error_code(xlsm_path, lang_dir, lang_code=None, skip_proto=False):
    if not os.path.isfile(xlsm_path):
        return False, f"文件不存在: {xlsm_path}"
    if lang_code is None:
        lang_code = os.path.basename(lang_dir)
    try:
        entries = _read_xlsm_data(xlsm_path)
    except Exception as e:
        return False, f"读取 xlsm 失败: {e}"
    if not entries:
        return False, "没有读取到有效数据"

    parts = []

    if not skip_proto:
        _write_export_txt(entries, os.path.join(lang_dir, "ExportTxt", "ErrorMessage.txt"))
        parts.append("ExportTxt")
        pd = os.path.join(lang_dir, "protobuf", "proto", "out")
        _write_protobuf(entries, os.path.join(pd, "ErrorMessage.bin"), os.path.join(pd, "ErrorMessage.hd"), os.path.join(pd, "ErrorMessage.txt"))
        parts.append("protobuf(bin/hd/txt)")
        sc = _ensure_static_files(lang_dir)
        if sc:
            parts.append(f"静态模板({','.join(sc)})")
        cbd = _derive_client_bin_dir(lang_dir, lang_code)
        cp = os.path.dirname(cbd)
        if os.path.isdir(cp):
            os.makedirs(cbd, exist_ok=True)
            for fn in ["ErrorMessage.bin", "ErrorMessage.hd"]:
                shutil.copy2(os.path.join(pd, fn), os.path.join(cbd, fn))
            parts.append("Client(copy)")
        else:
            parts.append(f"Client目录不存在, 跳过: {cbd}")

    _write_monolith(entries, os.path.join(lang_dir, ".ExcelTool2", "ErrorMessage"))
    parts.append(".ExcelTool2")
    _write_erl(entries, os.path.join(lang_dir, "config", "cfg_errorMessage.erl"))
    parts.append("erl")
    return True, f"成功导出 {len(entries)} 条: {', '.join(parts)}"


def main():
    parser = argparse.ArgumentParser(description="错误码导出工具 - 旧格式")
    parser.add_argument("--xlsm", required=True)
    parser.add_argument("--lang-dir", required=True)
    parser.add_argument("--lang-code", default=None)
    args = parser.parse_args()
    ok, msg = export_error_code(args.xlsm, args.lang_dir, args.lang_code)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
