# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

file_path = r'E:\桌面\其它\策划案模版.xlsx'
df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)

# 读取前10行的所有非空列
for idx, row in df.iterrows():
    if 0 <= idx <= 10:
        vals = []
        for col in range(0, 31):
            v = row[col] if pd.notna(row[col]) else ''
            if str(v).strip():
                vals.append(f'col{col}={v}')
        if vals:
            print(f'row{idx}: ' + ' | '.join(vals))

print()
print('=== 功能入口区域 (行121-145) ===')
for idx, row in df.iterrows():
    if 121 <= idx <= 145:
        vals = []
        for col in range(0, 31):
            v = row[col] if pd.notna(row[col]) else ''
            if str(v).strip():
                vals.append(f'col{col}={str(v)[:60]}')
        if vals:
            print(f'row{idx}: ' + ' | '.join(vals))
