"""
ExcelTool2.py -- 兼容两版源代码逻辑, 不调 exe。

Asia 新版 (4 参数 _write.py): _fix_py2 修复后导入, 调用 write_test + read_test
KR2 旧版 (2 参数 _write.py / 无文件): _fix_py2 修复后导入, 调用 write_test + read_test
"""

import os, sys, shutil, struct, importlib, xlrd

_script_dir = os.path.dirname(os.path.abspath(__file__))
_asia_tools = r'G:\D3_Asia\tools\ExportScripts\ExportXlsmPBData'

def resolve_paths(lang_dir):
    lang_dir = os.path.abspath(lang_dir)
    lang_code = os.path.basename(lang_dir)
    return {
        'lang_dir': lang_dir, 'lang_code': lang_code,
        'data2': os.path.join(lang_dir, 'Data2'),
        'proto_out': os.path.join(lang_dir, 'protobuf', 'proto', 'out'),
        'export_txt': os.path.join(lang_dir, 'ExportTxt'),
        'config': os.path.join(lang_dir, 'config'),
        'streaming': os.path.join(lang_dir, '..', '..', '..', 'Client', 'Assets',
                                   'StreamingAssets', 'Language', lang_code, 'BinData', 'bin'),
    }

def _has_hd(proto_out_dir):
    p = os.path.join(proto_out_dir, 'ErrorMessage_write.py')
    if not os.path.exists(p):
        return False
    for line in open(p, 'rb').read().decode('utf-8', errors='replace').split('\n'):
        if 'def write_test' in line and 'headFile' in line:
            return True
    return False

def _fix_py2(src):
    lines = src.split('\n')
    fixed = []
    for line in lines:
        s = line.strip()
        if s in ('reload(sys)',):
            continue
        if s.startswith('sys.setdefaultencoding'):
            continue
        if s.startswith('print ') and '(' not in s:
            indent = line[:len(line) - len(line.lstrip())]
            fixed.append(indent + 'print(' + s[6:] + ')')
        else:
            line = line.replace('"proto\\\\out\\\\"', '"protobuf\\\\proto\\\\out\\\\"')
            if '\"wb\"' in line and 'ftxt = open' in line and 'binName' in line:
                line = line.replace('\"wb\"', '\"w\",encoding=\"utf-8\",newline=\"\"')
            fixed.append(line)
    return '\n'.join(fixed)

def _import_write_module(proto_out_dir):
    for fn in ['__init__.py', 'ErrorMessage_write.py', 'ErrorMessage_pb2.py']:
        if not os.path.exists(os.path.join(proto_out_dir, fn)):
            return None
    lang_code = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(proto_out_dir))))
    cache_dir = os.path.join(_script_dir, '.proto_cache', lang_code)
    os.makedirs(cache_dir, exist_ok=True)
    for fn in ['__init__.py', 'ErrorMessage_write.py', 'ErrorMessage_pb2.py']:
        sp = os.path.join(proto_out_dir, fn)
        cp = os.path.join(cache_dir, fn)
        raw = open(sp, 'rb').read()
        fixed = _fix_py2(raw.decode('utf-8', errors='replace'))
        with open(cp, 'w', encoding='utf-8') as f:
            f.write(fixed)
    sys.path.insert(0, proto_out_dir)
    sys.path.insert(0, cache_dir)
    for m in list(sys.modules.keys()):
        if 'ErrorMessage' in m or '__init__' in m:
            sys.modules.pop(m, None)
    return importlib.import_module('ErrorMessage_write')

def _get_similars(xp):
    sys.path.insert(0, _asia_tools)
    import CompressExport as ce
    wb = xlrd.open_workbook(xp)
    sheetDic = ce.AnalyseSheet(['ErrorMessage'])
    outputColumns = ce.AnalyseColumnOutPut(wb, sheetDic)
    outputTypes = ce.AnalyseColumnOutPutType(wb, sheetDic, outputColumns)
    return ce.AnalyseSimilarData(wb, sheetDic, outputColumns, outputTypes)['ErrorMessage']

def _get_data(var, rowtype):
    """匹配 __init__.py 的 getdata()"""
    rt = rowtype.lower()
    if rt in ('float', 'double'):
        return float(var)
    if rt in ('short', 'byte', 'int', 'uint', 'uint64', 'int64', 'integer'):
        return int(float(var))
    if rt in ('str', 'str_utf'):
        if isinstance(var, float) and var == 0.0:
            return ""
        return str(var).replace('.0', '')
    return var

def _make_erl(entries, paths):
    N = '\r\n'
    os.makedirs(paths['config'], exist_ok=True)
    fp = os.path.join(paths['config'], 'cfg_errorMessage.erl')
    with open(fp, 'w', encoding='utf-8', newline='') as f:
        ks = [e[1] for e in entries]
        f.write(f'-module(cfg_errorMessage).{N}')
        f.write(f'-include("cfg_errorMessage.hrl").{N}')
        f.write(f'-export([row/1, first_row/0, last_row/0, rows/1, rows/0, keys_length/0]).{N}')
        f.write(f'-export([getRow/1, getKeyList/0]).{N}')
        f.write(f'{N}%% 指定行{N}')
        f.write(f'row(Id) -> getRow(Id).{N}')
        f.write(f'{N}%% 第一行、最后一行{N}')
        f.write(f'first_row() -> getRow(0).{N}')
        f.write(f'last_row() -> getRow({ks[-1]}).{N}')
        f.write(f'{N}%% 行列表{N}')
        f.write(f'rows(KeyList) -> [row(Key) || Key <- KeyList].{N}')
        f.write(f'rows() -> rows(getKeyList()).{N}')
        f.write(f'{N}%% Key列表长度{N}')
        f.write(f'keys_length() -> {len(ks)}.{N}{N}')
        for _, rid, text in entries:
            te = text.replace('\\', '\\\\').replace('"', '\\"')
            f.write(f'getRow({rid}) -> #errorMessageCfg{{{N}')
            f.write(f'\tiD = {rid},{N}')
            f.write(f'\terrorString = "{te}"}};{N}')
        f.write(f'getRow(_) ->{N}\t{{}}.{N}{N}')
        f.write(f'getKeyList() -> [{N}')
        for i2, k in enumerate(ks):
            sep = f'].{N}' if i2 + 1 >= len(ks) else f',{N}'
            f.write(f'\t{k}{sep}')
    print(f"  [ERL] {fp}")
    hrl = os.path.join(paths['config'], 'cfg_errorMessage.hrl')
    with open(hrl, 'w', encoding='utf-8', newline='') as f:
        for line in ['-ifndef(cfg_errorMessage_hrl).', '-define(cfg_errorMessage_hrl, true).', '',
                      '-record(errorMessageCfg, {', '\tiD,', '\terrorString', '}).', '', '-endif.']:
            f.write(line + '\r\n')

def _copy_to_streaming(paths):
    streaming = os.path.normpath(paths['streaming'])
    os.makedirs(streaming, exist_ok=True)
    for fn in ['ErrorMessage.hd', 'ErrorMessage.bin']:
        sf = os.path.join(paths['proto_out'], fn)
        if os.path.exists(sf):
            shutil.copy2(sf, os.path.join(streaming, fn))
    print(f"  [COPY] StreamingAssets/")

def export_all_files(paths):
    xp = os.path.join(paths['data2'], 'ErrorMessage.xlsm')
    if not os.path.exists(xp):
        print(f"文件不存在: {xp}")
        return
    print(f"读取: {xp}")

    wb = xlrd.open_workbook(xp)
    ws = wb.sheet_by_name('ErrorMessage')

    entries = []
    for i in range(4, ws.nrows):
        r = [ws.cell(i, c).value for c in range(ws.ncols)]
        if not r: continue
        dt = str(r[0]).lower()
        if dt == 'no': continue
        try: rid = int(float(str(r[1])))
        except: continue
        text = _get_data(r[2], 'str_utf')
        entries.append((i, rid, text))
        if dt == 'end': break

    print(f"  解析到 {len(entries)} 条记录")

    old_cwd = os.getcwd()
    os.chdir(paths['lang_dir'])

    try:
        if _has_hd(paths['proto_out']):
            write_mod = _import_write_module(paths['proto_out'])
            similars = _get_similars(xp)
            hd_path = os.path.join(paths['proto_out'], 'ErrorMessage.hd')
            bin_path = os.path.join(paths['proto_out'], 'ErrorMessage.bin')
            with open(hd_path, 'wb') as hd:
                hd.write(struct.pack('i', 1))
                write_mod.write_test(bin_path, ws, similars, hd)
            print(f"  [HD]  {hd_path}")
            print(f"  [BIN] {bin_path}")
            write_mod.read_test(hd_path)
            txt_path = os.path.join(paths['proto_out'], 'ErrorMessage.txt')
            print(f"  [TXT] {txt_path}")
        else:
            write_mod = _import_write_module(paths['proto_out'])
            bin_path = os.path.join(paths['proto_out'], 'ErrorMessage.bin')
            if write_mod:
                write_mod.write_test(bin_path, ws)
                with open(bin_path, 'ab') as pad:
                    pad.write(b'\x00\x00\x00\x00')
                print(f"  [BIN] {bin_path}")
                write_mod.read_test(bin_path)
                txt_path = os.path.join(paths['proto_out'], 'ErrorMessage.txt')
                print(f"  [TXT] {txt_path}")
            else:
                lang_root = os.path.dirname(os.path.dirname(os.path.dirname(paths['proto_out'])))
                from_dir = os.path.join(lang_root, 'ZH_CN', 'protobuf', 'proto', 'out')
                for fn in ['__init__.py', 'ErrorMessage_write.py', 'ErrorMessage_pb2.py']:
                    sp = os.path.join(from_dir, fn)
                    dp = os.path.join(paths['proto_out'], fn)
                    if os.path.exists(sp) and not os.path.exists(dp):
                        with open(sp, 'rb') as src, open(dp, 'wb') as dst:
                            dst.write(src.read())
                write_mod = _import_write_module(paths['proto_out'])
                write_mod.write_test(bin_path, ws)
                with open(bin_path, 'ab') as pad:
                    pad.write(b'\x00\x00\x00\x00')
                print(f"  [BIN] {bin_path}")
                write_mod.read_test(bin_path)
                txt_path = os.path.join(paths['proto_out'], 'ErrorMessage.txt')
                print(f"  [TXT] {txt_path}")

        txt_path = os.path.join(paths['proto_out'], 'ErrorMessage.txt')
        os.makedirs(paths['export_txt'], exist_ok=True)
        shutil.copy2(txt_path, os.path.join(paths['export_txt'], 'ErrorMessage.txt'))

        _make_erl(entries, paths)
        _copy_to_streaming(paths)

    finally:
        os.chdir(old_cwd)

def _find_lang_dirs(root):
    ld = os.path.join(root, 'gameData', 'Language')
    if not os.path.isdir(ld): return []
    return sorted(os.path.join(ld, d) for d in os.listdir(ld)
                  if os.path.isdir(os.path.join(ld, d)) and not d.startswith('.'))

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', default='ErrorMessage')
    ap.add_argument('--lang-dir', default=None)
    ap.add_argument('--all-langs', default=None)
    args = ap.parse_args()

    if args.all_langs:
        for ld in _find_lang_dirs(args.all_langs):
            print(f"\n{'=' * 60}\n[{os.path.basename(ld)}] {ld}")
            export_all_files(resolve_paths(ld))
    elif args.lang_dir:
        export_all_files(resolve_paths(args.lang_dir))
    else:
        cwd = os.getcwd()
        while cwd and not os.path.isdir(os.path.join(cwd, 'Data2')):
            p = os.path.dirname(cwd)
            if p == cwd: break
            cwd = p
        if os.path.isdir(os.path.join(cwd, 'Data2')):
            export_all_files(resolve_paths(cwd))
        else:
            print("用法: python ExcelTool2.py ErrorMessage --lang-dir G:/.../TH_TH")
