' SVN一键对比GUI - 修复版
' 使用正确的Python 3.13路径

Dim objShell, strPython, strScript, strCmd

' 设置正确的Python路径
strPython = "C:\Users\admin\AppData\Local\Programs\Python\Python313\python.exe"
' 设置脚本路径
strScript = "C:\Users\admin\.qclaw\workspace\svn_compare_gui.py"

' 构建命令
strCmd = Chr(34) & strPython & Chr(34) & " " & Chr(34) & strScript & Chr(34)

' 创建Shell对象并运行命令
Set objShell = CreateObject("WScript.Shell")
objShell.Run strCmd, 1, False

' 释放对象
Set objShell = Nothing