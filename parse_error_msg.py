import struct
import sys
import os
from collections import Counter

def read_leb128(data, start):
    """Read proper LEB128 little-endian variable-length integer"""
    result = 0
    shift = 0
    pos = start
    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        shift += 7
        pos += 1
        if (byte & 0x80) == 0:
            break
    return result, pos

def parse_bin_entries(bin_path):
    """Extract error code + message pairs from ErrorMessage.bin"""
    with open(bin_path, 'rb') as f:
        data = f.read()
    
    entries = []
    i = 0
    while i < len(data):
        if data[i] != 0x12:
            i += 1
            continue
        
        # Found 0x12 marker at position i
        code_start = i + 1
        
        # Read LEB128 code
        code, code_end = read_leb128(data, code_start)
        
        # String starts right after code bytes
        str_start = code_end
        
        # String ends at next 0x12 or end of file
        str_end = str_start
        while str_end < len(data) and data[str_end] != 0x12:
            str_end += 1
        
        raw_str = data[str_start:str_end]
        
        # Try to decode as UTF-8, skip if not valid text
        try:
            text = raw_str.decode('utf-8').strip()
            entries.append((code, text, i))
        except UnicodeDecodeError:
            # Not valid UTF-8 text, skip
            pass
        
        i = str_end
    
    return entries


bin_path = r"c:\Users\admin\.qclaw\workspace\正确文件\ErrorMessage.bin"
hd_path = r"c:\Users\admin\.qclaw\workspace\正确文件\ErrorMessage.hd"
out_path = r"c:\Users\admin\.qclaw\workspace\ErrorMessage_Readable.txt"

# Parse .hd header info
with open(hd_path, 'rb') as f:
    hd_data = f.read()
version = struct.unpack_from('<I', hd_data, 0)[0]
name_len = struct.unpack_from('<I', hd_data, 4)[0]
name = hd_data[8:8+name_len].decode('ascii')
count_field = struct.unpack_from('<I', hd_data, 8+name_len)[0]

# Parse .bin
entries = parse_bin_entries(bin_path)

# Check code uniqueness
codes = [code for code, _, _ in entries]
code_counter = Counter(codes)
unique_codes = len(set(codes))
dupe_codes = [(c, cnt) for c, cnt in code_counter.items() if cnt > 1]

# Write output
with open(out_path, 'w', encoding='utf-8') as out:
    def w(s=""):
        out.write(s + "\n")
    
    w("=" * 70)
    w("  游戏错误消息文件解析结果")
    w("  Game Error Message File - Readable Output")
    w("=" * 70)
    w()
    w("--- 文件信息 ---")
    w(f"  HD文件: ErrorMessage.hd ({len(hd_data)} bytes)")
    w(f"  BIN文件: ErrorMessage.bin ({os.path.getsize(bin_path)} bytes)")
    w(f"  版本: {version}")
    w(f"  名称: {name}")
    w(f"  HD计数: {count_field}")
    w()
    w(f"  解析提取条目数: {len(entries)}")
    w(f"  唯一错误码数: {unique_codes}")
    w(f"  重复错误码数: {len(dupe_codes)}")
    w()
    
    w("--- 重复错误码 (可能有多条消息映射到同一错误码) ---")
    if dupe_codes:
        for code, cnt in sorted(dupe_codes, key=lambda x: -x[1])[:30]:
            texts = [text for c, text, _ in entries if c == code]
            w(f"  code={code:6d} (0x{code:04X}) x{cnt:2d}:")
            for t in texts:
                w(f"    - {t}")
    else:
        w("  (无重复)")
    w()
    
    w("=" * 70)
    w("  错误码 → 错误消息 对照表")
    w("  (按.bin文件中出现顺序)")
    w("=" * 70)
    w()
    
    for i, (code, text, offset) in enumerate(entries):
        w(f"  [{i:4d}] code={code:5d} (0x{code:04X}) | {text}")
    
    w()
    w("-" * 70)
    w(f"  共 {len(entries)} 条条目")
    w(f"  输出文件: {out_path}")

print(f"✅ 完成！输出文件: {out_path}")
print(f"   提取条目: {len(entries)}")
print(f"   唯一错误码: {unique_codes}")
print(f"   重复错误码组: {len(dupe_codes)}")
