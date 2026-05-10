' �߻������� - ����������
' �Զ���� Python �������״������Զ��޸�·��
Option Explicit

Dim shell, fso, scriptDir, pythonExe, checker, cmdLine, statusCode
Dim cacheFile, cacheText, cachedExe
Dim launcher

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' ---- Step 1: find Python (cache first, then search) --------
cacheFile = scriptDir & "\_env_cache.json"
cachedExe = GetCachedPythonPath(cacheFile)

If cachedExe <> "" Then
    pythonExe = cachedExe
Else
    pythonExe = FindPython()
End If

If pythonExe = "" Then
    MsgBox "No Python found. Run �����޸�.bat �Զ���װ.", 48, "Ce Hua Gong Ju Xiang"
    shell.Run Chr(34) & scriptDir & "\�����޸�.bat" & Chr(34), 1, False
    WScript.Quit 1
End If

' ---- Step 2: run setup_checker.py (silent) --------
'   exit code: 0=OK, 1=warnings(no Office/SVN), 2=errors
checker = scriptDir & "\setup_checker.py"
If fso.FileExists(checker) Then
    cmdLine = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & checker & Chr(34) & " --dir " & Chr(34) & scriptDir & Chr(34)
    statusCode = shell.Run(cmdLine, 0, True)
    If statusCode >= 2 Then
        MsgBox "Environment check failed (code: " & statusCode & "). Some features may not work." & vbCrLf & _
               "Run 'huanjing xiufu.bat' to fix.", 48, "Ce Hua Gong Ju Xiang"
    End If
End If

' ---- Step 3: launch main program --------
launcher = scriptDir & "\svn_launcher.py"
cmdLine = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & launcher & Chr(34) & " --dir " & Chr(34) & scriptDir & Chr(34)
shell.Run cmdLine, 0, False

' ---- cleanup --------
Set shell = Nothing
Set fso = Nothing

' ===============================================
' Read Python path from cache file
' ===============================================
Function GetCachedPythonPath(filePath)
    Dim stream, content, regexObj, matches
    If Not fso.FileExists(filePath) Then
        GetCachedPythonPath = ""
        Exit Function
    End If
    On Error Resume Next
    Set stream = fso.OpenTextFile(filePath, 1)
    content = stream.ReadAll()
    stream.Close
    Set stream = Nothing
    Set regexObj = New RegExp
    regexObj.Pattern = Chr(34) & "python_exe" & Chr(34) & "\s*:\s*" & Chr(34) & "([^" & Chr(34) & "]+)" & Chr(34)
    Set matches = regexObj.Execute(content)
    If matches.Count > 0 Then
        GetCachedPythonPath = matches(0).SubMatches(0)
        If Not fso.FileExists(GetCachedPythonPath) Then
            GetCachedPythonPath = ""
        End If
    Else
        GetCachedPythonPath = ""
    End If
    On Error Goto 0
End Function

' ===============================================
' Find Python by scanning common locations
' ===============================================
Function FindPython()
    Dim i, p, exe, ws, execOut
    Dim userHome, progFiles, progFiles86, searchRoots
    userHome = shell.ExpandEnvironmentStrings("%USERPROFILE%")
    progFiles = shell.ExpandEnvironmentStrings("%ProgramFiles%")
    progFiles86 = shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%")
    searchRoots = Array( _
        userHome & "\AppData\Local\Programs\Python", _
        progFiles & "\Python", _
        progFiles86 & "\Python", _
        "C:\Python313", "C:\Python312", "C:\Python311", "C:\Python310", _
        "D:\Python313", "D:\Python312" _
    )
    For i = 0 To UBound(searchRoots)
        p = searchRoots(i)
        If fso.FolderExists(p) Then
            exe = FindPythonRecursive(p)
            If exe <> "" Then
                FindPython = exe
                Exit Function
            End If
        End If
    Next
    On Error Resume Next
    Set ws = CreateObject("WScript.Shell")
    Set execOut = ws.Exec("%ComSpec% /c where python")
    If Err.Number = 0 Then
        Do While Not execOut.StdOut.AtEndOfStream
            exe = Trim(execOut.StdOut.ReadLine())
            If LCase(Right(exe, 12)) = "\python.exe" Or LCase(Right(exe, 14)) = "\python3.exe" Then
                If fso.FileExists(exe) Then
                    FindPython = exe
                    Exit Function
                End If
            End If
        Loop
    End If
    On Error Goto 0
    exe = FindPythonInRegistry()
    If exe <> "" Then
        FindPython = exe
        Exit Function
    End If
    FindPython = ""
End Function

Function FindPythonRecursive(folder)
    Dim f, subFolder, exe
    Set f = fso.GetFolder(folder)
    exe = folder & "\python.exe"
    If fso.FileExists(exe) Then
        FindPythonRecursive = exe
        Exit Function
    End If
    For Each subFolder In f.SubFolders
        exe = FindPythonRecursive(subFolder.Path)
        If exe <> "" Then
            FindPythonRecursive = exe
            Exit Function
        End If
    Next
    FindPythonRecursive = ""
End Function

Function FindPythonInRegistry()
    Dim regPaths, i, key, exe, versions, ver
    Dim regSubKeys, installPath
    regPaths = Array( _
        "HKLM\SOFTWARE\Python\PythonCore\", _
        "HKCU\SOFTWARE\Python\PythonCore\", _
        "HKLM\SOFTWARE\Wow6432Node\Python\PythonCore\" _
    )
    On Error Resume Next
    For i = 0 To UBound(regPaths)
        key = regPaths(i)
        regSubKeys = shell.RegRead(key & "InstallPath\")
        If Err.Number = 0 Then
            exe = regSubKeys & "\python.exe"
            If fso.FileExists(exe) Then
                FindPythonInRegistry = exe
                Exit Function
            End If
        End If
        Err.Clear
    Next
    On Error Goto 0
    On Error Resume Next
    versions = Array("3.13", "3.12", "3.11", "3.10")
    For i = 0 To UBound(versions)
        ver = versions(i)
        For Each key In regPaths
            installPath = shell.RegRead(key & ver & "\InstallPath\")
            If Err.Number = 0 Then
                exe = installPath & "\python.exe"
                If fso.FileExists(exe) Then
                    FindPythonInRegistry = exe
                    Exit Function
                End If
            End If
            Err.Clear
        Next
    Next
    On Error Goto 0
    FindPythonInRegistry = ""
End Function
