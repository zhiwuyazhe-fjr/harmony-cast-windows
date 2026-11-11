Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
base = fs.GetParentFolderName(WScript.ScriptFullName)
exe = fs.BuildPath(base, "dist\MirrorStage\MirrorStage.exe")
shell.CurrentDirectory = base
If fs.FileExists(exe) Then
    shell.Run Chr(34) & exe & Chr(34), 1, False
Else
    shell.Run Chr(34) & fs.BuildPath(base, ".venv\Scripts\pythonw.exe") & Chr(34) & " " & Chr(34) & fs.BuildPath(base, "main.py") & Chr(34), 1, False
End If
