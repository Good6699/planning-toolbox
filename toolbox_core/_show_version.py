import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "version.json"
with open(path, encoding="utf-8") as f:
    v = json.load(f)
print(f'  Version: {v.get("version", "?")}')
print(f'  Package: {v.get("url", "?")}')
md5 = v.get("md5", "")
if md5:
    print(f'  MD5:     {md5[:16]}...')
print(f'  Force:   {v.get("force", False)}')
print(f'  Notes:   {v.get("notes", "")}')
