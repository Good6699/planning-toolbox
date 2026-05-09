Add-Type -AssemblyName System.Drawing

$srcPath1 = "E:\桌面\其它\1.png"
$srcPath2 = "E:\桌面\其它\2.png"

$img1 = New-Object System.Drawing.Bitmap($srcPath1)
$img2 = New-Object System.Drawing.Bitmap($srcPath2)

function Analyze-Image([System.Drawing.Bitmap]$bmp, [string]$name) {
    Write-Host ""
    Write-Host "=== 分析 $name ($($bmp.Width)x$($bmp.Height)) ==="
    
    # 采样分析（每隔若干像素）
    $step = [Math]::Max(1, [Math]::Floor([Math]::Min($bmp.Width, $bmp.Height) / 50))
    
    # 检测肤色区域（肤色的RGB范围）
    $skinPixels = @()
    $totalSampled = 0
    
    for ($y = 0; $y -lt $bmp.Height; $y += $step) {
        for ($x = 0; $x -lt $bmp.Width; $x += $step) {
            $pixel = $bmp.GetPixel($x, $y)
            $r = $pixel.R; $g = $pixel.G; $b = $pixel.B; $a = $pixel.A
            $totalSampled++
            
            # 简单肤色检测 (基于RGB范围)
            if ($a -gt 100 -and $r -gt 60 -and $g -gt 40 -and $b -gt 20 -and 
                $r -gt $g -and $r -gt $b -and ($r - $g) -gt 15 -and $r -lt 250) {
                $skinPixels += @{X=$x; Y=$y}
            }
        }
    }
    
    Write-Host "  总采样像素: $totalSampled"
    Write-Host "  检测到肤色像素: $($skinPixels.Count)"
    
    if ($skinPixels.Count -gt 10) {
        # 计算肤色区域中心和范围
        $sumX = 0; $sumY = 0; $minX = 9999; $maxX = 0; $minY = 9999; $maxY = 0
        foreach ($p in $skinPixels) {
            $sumX += $p.X; $sumY += $p.Y
            if ($p.X -lt $minX) { $minX = $p.X }
            if ($p.X -gt $maxX) { $maxX = $p.X }
            if ($p.Y -lt $minY) { $minY = $p.Y }
            if ($p.Y -gt $maxY) { $maxY = $p.Y }
        }
        $avgX = [Math]::Floor($sumX / $skinPixels.Count)
        $avgY = [Math]::Floor($sumY / $skinPixels.Count)
        $rangeX = $maxX - $minX
        $rangeY = $maxY - $minY
        $radius = [Math]::Floor([Math]::Max($rangeX, $rangeY) / 2 * 0.7)
        
        Write-Host "  肤色区域中心: ($avgX, $avgY)"
        Write-Host "  肤色范围: X[$minX-$maxX], Y[$minY-$maxY]"
        Write-Host "  建议头像半径: ~$radius"
    }
    
    # 获取边缘像素和角落颜色
    Write-Host ""
    Write-Host "  关键位置颜色采样:"
    $samples = @(
        @{Label="左上(0,0)"; X=0; Y=0},
        @{Label="右上(W-1,0)"; X=$bmp.Width-1; Y=0},
        @{Label="左下(0,H-1)"; X=0; Y=$bmp.Height-1},
        @{Label="右下(W-1,H-1)"; X=$bmp.Width-1; Y=$bmp.Height-1},
        @{Label="中心"; X=[Math]::Floor($bmp.Width/2); Y=[Math]::Floor($bmp.Height/2)},
        @{Label="上部中心"; X=[Math]::Floor($bmp.Width/2); Y=[Math]::Floor($bmp.Height*0.2)}
    )
    foreach ($s in $samples) {
        $px = $bmp.GetPixel($s.X, $s.Y)
        Write-Host "    $($s.Label)($($s.X),$($s.Y)): RGBA($($px.R),$($px.G),$($px.B),$($px.A))"
    }
    
    # 每10%高度取一行中心点颜色
    Write-Host ""
    Write-Host "  垂直颜色扫描 (每10%高度):"
    for ($pct = 0; $pct -le 100; $pct += 10) {
        $y = [Math]::Floor($bmp.Height * $pct / 100)
        $x = [Math]::Floor($bmp.Width / 2)
        if ($y -ge $bmp.Height) { $y = $bmp.Height - 1 }
        $px = $bmp.GetPixel($x, $y)
        Write-Host "    Y=$y ($pct%): RGBA($($px.R),$($px.G),$($px.B),$($px.A))"
    }
}

Analyze-Image $img1 "图1 (源头像)"
Analyze-Image $img2 "图2 (目标图)"

$img1.Dispose()
$img2.Dispose()
