# -*- coding: utf-8 -*-
"""
生成职业切换按钮图片：圣职
- 尺寸：202 x 88
- 左边：弓手胸部及以上部位
- 背景：暗色
- 右边：空白区域（预留4个26号汉字空间）
"""

from PIL import Image, ImageDraw
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 图片参数
WIDTH = 202
HEIGHT = 88

# 右边文字预留区域：4个26号汉字 ≈ 104像素宽
TEXT_AREA_WIDTH = 104
CHARACTER_AREA_WIDTH = WIDTH - TEXT_AREA_WIDTH  # 98像素

# 背景暗色（深紫色调，适合圣职主题）
BG_COLOR = (30, 25, 40, 255)  # 深紫色背景

# 读取参考图
ref_img = Image.open(r'E:\桌面\其它\1.png')
ref_width, ref_height = ref_img.size

print(f'参考图尺寸: {ref_img.size}')
print(f'目标图片尺寸: {WIDTH} x {HEIGHT}')
print(f'人物区域宽度: {CHARACTER_AREA_WIDTH}')
print(f'文字预留区域宽度: {TEXT_AREA_WIDTH}')

# 创建目标图片
result = Image.new('RGBA', (WIDTH, HEIGHT), BG_COLOR)

# 从参考图提取人物上半身（胸部及以上）
# 720x1064的图片，头部大约在顶部20%区域，胸部在30-50%区域
# 提取上半身区域
avatar_region = ref_img.crop((
    int(ref_width * 0.3),   # left - 人物大约在中间
    int(ref_height * 0.05),  # top - 从顶部开始
    int(ref_width * 0.7),   # right
    int(ref_height * 0.45)   # bottom - 到胸部位置
))

print(f'提取的人物区域尺寸: {avatar_region.size}')

# 调整人物大小以适配左边区域
# 人物区域宽度98，高度88
# 保持人物比例，宽度填满，高度可能需要裁剪
target_width = CHARACTER_AREA_WIDTH
scale = target_width / avatar_region.width
target_height = int(avatar_region.height * scale)

avatar_resized = avatar_region.resize((target_width, target_height), Image.LANCZOS)
print(f'缩放后人物尺寸: {avatar_resized.size}')

# 如果缩放后高度超过88，需要裁剪底部
if target_height > HEIGHT:
    crop_top = (target_height - HEIGHT) // 2  # 从中间裁剪，保留头部
    avatar_final = avatar_resized.crop((
        0,
        crop_top,
        target_width,
        crop_top + HEIGHT
    ))
    print(f'裁剪后人物尺寸: {avatar_final.size}')
else:
    avatar_final = avatar_resized

# 确保人物有透明通道
if avatar_final.mode != 'RGBA':
    avatar_final = avatar_final.convert('RGBA')

# 粘贴人物到左边区域
paste_x = 0
paste_y = 0

if avatar_final.height < HEIGHT:
    paste_y = (HEIGHT - avatar_final.height) // 2

result.paste(avatar_final, (paste_x, paste_y), avatar_final)

# 保存结果
output_path = r'E:\桌面\其它\圣职按钮.png'
result.save(output_path)

print(f'结果已保存: {output_path}')
print(f'最终尺寸: {result.size}')