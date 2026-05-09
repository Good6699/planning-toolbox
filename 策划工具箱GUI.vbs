' SVN GUI Launcher
Option Explicit

Dim shell, fso, scriptDir, pyScript, cmdLine, strPython

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pyScript = scriptDir & "\svn_compare_gui.py"

' Use specific Python 3.13 path for reliability
strPython = "C:\Users\admin\AppData\Local\Programs\Python\Python313\python.exe"
cmdLine = Chr(34) & strPython & Chr(34) & " " & Chr(34) & pyScript & Chr(34) & " --dir " & Chr(34) & scriptDir & Chr(34)

' Run
shell.Run cmdLine, 0, False

' Clean up objects
Set shell = Nothing
Set fso = Nothing
