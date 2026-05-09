Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$srcPath1 = "E:\桌面\其它\1.png"
$srcPath2 = "E:\桌面\其它\2.png"
$outPath = "E:\桌面\其它\result.png"

Write-Host "========== 头像替换工具 =========="
Write-Host ""

# 加载图片
Write-Host "[1/5] 加载图片..."
$img1 = [System.Drawing.Image]::FromFile($srcPath1)
$img2 = [System.Drawing.Image]::FromFile($srcPath2)
Write-Host "  图1: $($img1.Width) x $($img1.Height)"
Write-Host "  图2: $($img2.Width) x $($img2.Height)"

# ====== 参数设置（基于图片尺寸估算）======
# 图1: 720x1064 竖版肖像照
# 典型头像位置: 上部居中
$srcCX = 360
$srcCY = 280
$srcR = 100

# 图2: 202x88 横向小图
# 如果是证件照风格，头像可能在偏左或偏右位置
# 这里假设是右侧人物头像被替换
$dstCX = 152  # 右侧人物中心
$dstCY = 44
$dstR = 30

Write-Host ""
Write-Host "[2/5] 参数设置:"
Write-Host "  源头像 [图1]: 中心($srcCX, $srcCY), 半径 $srcR"
Write-Host "  目标位置 [图2]: 中心($dstCX, $dstCY), 半径 $dstR"

# 边界检查
$srcR = [Math]::Min($srcR, $srcCX, $img1.Width - $srcCX, $srcCY, $img1.Height - $srcCY)
$dstR = [Math]::Min($dstR, $dstCX, $img2.Width - $dstCX, $dstCY, $img2.Height - $dstCY)
Write-Host "  调整后源头像半径: $srcR"
Write-Host "  调整后目标半径: $dstR"

# 创建输出图片
Write-Host ""
Write-Host "[3/5] 创建输出画布..."
$outBmp = New-Object System.Drawing.Bitmap($img2.Width, $img2.Height)
$g = [System.Drawing.Graphics]::FromImage($outBmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$g.Clear([System.Drawing.Color]::Transparent)

# 绘制背景（图2）
Write-Host "[4/5] 执行头像替换..."
$g.DrawImage($img2, 0, 0, $img2.Width, $img2.Height)

# 创建圆形裁剪区域
$clipPath = New-Object System.Drawing.Drawing2D.GraphicsPath
$clipPath.AddEllipse($dstCX - $dstR, $dstCY - $dstR, $dstR * 2, $dstR * 2)
$g.SetClip($clipPath)

# 计算缩放
$srcLeft = $srcCX - $srcR
$srcTop = $srcCY - $srcR
$srcSize = $srcR * 2
$dstSize = $dstR * 2

# 绘制裁剪后的头像
$g.DrawImage($img2, 
    ($dstCX - $dstR), ($dstCY - $dstR), $dstSize, $dstSize,
    $srcLeft, $srcTop, $srcSize, $srcSize,
    [System.Drawing.GraphicsUnit]::Pixel)

# 添加轻微边框效果
$g.ResetClip()
$borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(80, 255, 255, 255), 1)
$g.DrawEllipse($borderPen, ($dstCX - $dstR), ($dstCY - $dstR), ($dstR * 2), ($dstR * 2))

# 清理
$g.Dispose()
$img1.Dispose()
$img2.Dispose()
$clipPath.Dispose()
$borderPen.Dispose()

# 保存
Write-Host "  保存到: $outPath"
$outBmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$outBmp.Dispose()

Write-Host ""
Write-Host "✅ 完成！结果已保存到:"
Write-Host "   $outPath"
Write-Host ""
Write-Host "提示：如果头像位置不准确，请告诉我调整后的坐标，我会重新处理。"
