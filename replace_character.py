# -*- coding: utf-8 -*-
"""
图片合成：将图片2的人物头像替换到图片1的人物位置
"""

from PIL import Image
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 图片路径
img1_path = r'E:\桌面\其它\图片1.png'
img2_path = r'E:\桌面\其它\图片2.png'
output_path = r'E:\桌面\其它\合成结果.png'

# 加载图片
img1 = Image.open(img1_path)
img2 = Image.open(img2_path)

print(f'图片1尺寸: {img1.size}')
print(f'图片2尺寸: {img2.size}')

# 分析图片2的人物区域
# 图片2显示的是完整人物，从截图看人物在画面中央偏上位置
# 需要提取人物主体部分

# 图片2的人物区域大致在中间位置
# 根据截图比例，人物区域大约是图片宽度的40%-80%，高度的20%-80%

img2_width, img2_height = img2.size
# 提取人物区域 (根据截图显示的人物位置)
character_region = img2.crop((
    int(img2_width * 0.2),  # left
    int(img2_height * 0.15),  # top
    int(img2_width * 0.85),  # right
    int(img2_height * 0.85)  # bottom
))

print(f'提取的人物区域尺寸: {character_region.size}')

# 调整人物大小以适配图片1的人物位置
# 图片1的人物位置在左侧，根据截图人物槽位大约300x400左右
target_width = 300
target_height = 450
character_resized = character_region.resize((target_width, target_height), Image.LANCZOS)

# 图片1的人物位置大约在 (100, 800) 附近
# 根据截图可以看到左侧有个圆形/椭圆的人物槽位
paste_x = 80
paste_y = 700

# 创建一个带透明通道的输出图片
result = img1.copy()

# 尝试使用alpha通道进行更自然的融合
# 先将人物转换为RGBA模式
if character_resized.mode != 'RGBA':
    character_resized = character_resized.convert('RGBA')

# 使用alpha通道进行叠加
result.paste(character_resized, (paste_x, paste_y), character_resized)

# 保存结果
result.save(output_path)
print(f'合成结果已保存: {output_path}')
print(f'人物粘贴位置: x={paste_x}, y={paste_y}')