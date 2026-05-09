# -*- coding: utf-8 -*-
"""
图片合成：将图片1的人物头像替换到图片2的人物头像位置
"""

from PIL import Image
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 图片路径
img1_path = r'E:\桌面\其它\1.png'
img2_path = r'E:\桌面\其它\2.png'
output_path = r'E:\桌面\其它\合成结果.png'

# 加载图片
img1 = Image.open(img1_path)
img2 = Image.open(img2_path)

print(f'图片1尺寸: {img1.size}')
print(f'图片2尺寸: {img2.size}')

# 图片1是较大的图，需要提取人物头像区域
# 图片2是较小的图，需要替换其中的人物头像

# 分析图片1 - 提取人物头像区域
# 根据尺寸720x1064，人物头像大约在中间偏上的位置
img1_width, img1_height = img1.size

# 提取图片1中的人物头像区域（大致在中间偏上位置）
# 假设人物头像区域在图片1的中间位置
avatar_region = img1.crop((
    int(img1_width * 0.25),   # left
    int(img1_height * 0.15),  # top
    int(img1_width * 0.75),   # right
    int(img1_height * 0.65)   # bottom
))

print(f'从图片1提取的头像区域尺寸: {avatar_region.size}')

# 图片2尺寸是202x88，比较小
# 需要调整提取的头像大小以适配图片2
img2_width, img2_height = img2.size

# 调整头像大小 - 适配图片2的尺寸
# 图片2高度只有88，所以头像高度应该小于88
target_height = int(img2_height * 0.8)  # 留出边距
target_width = int(avatar_region.width * (target_height / avatar_region.height))

avatar_resized = avatar_region.resize((target_width, target_height), Image.LANCZOS)
print(f'调整后的头像尺寸: {avatar_resized.size}')

# 创建结果图片（基于图片2）
result = img2.copy()

# 确保头像有透明通道
if avatar_resized.mode != 'RGBA':
    avatar_resized = avatar_resized.convert('RGBA')

# 计算粘贴位置 - 居中
paste_x = (img2_width - target_width) // 2
paste_y = (img2_height - target_height) // 2

# 粘贴头像到图片2
result.paste(avatar_resized, (paste_x, paste_y), avatar_resized)

# 保存结果
result.save(output_path)
print(f'合成结果已保存: {output_path}')
print(f'头像粘贴位置: x={paste_x}, y={paste_y}')