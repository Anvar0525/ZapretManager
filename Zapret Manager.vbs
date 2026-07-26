' Double-click this — no console window, one UAC prompt
Option Explicit
Dim shellApp, sh, fso, dir, pyw, candidates, i

Set shellApp = CreateObject("Shell.Application")
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

candidates = Array( _
  sh.ExpandEnvironmentStrings("%LocalAppData%\Programs\Python\Python313\pythonw.exe"), _
  sh.ExpandEnvironmentStrings("%LocalAppData%\Programs\Python\Python312\pythonw.exe"), _
  sh.ExpandEnvironmentStrings("%LocalAppData%\Programs\Python\Python311\pythonw.exe") _
)

pyw = ""
For i = 0 To UBound(candidates)
  If fso.FileExists(candidates(i)) Then
    pyw = candidates(i)
    Exit For
  End If
Next

If pyw = "" Then
  MsgBox "Не найден pythonw.exe. Установите Python 3.", vbCritical, "Zapret Manager"
  WScript.Quit 1
End If

' runas = one UAC; 0 = hidden window
shellApp.ShellExecute pyw, """" & dir & "\app.py""", dir, "runas", 0
