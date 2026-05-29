"""xlsm_zipper - Apply data changes to .xlsm files via Excel (VBScript).

Strategy:
  Instead of using openpyxl to write (which corrupts formulas/VBA),
  we use openpyxl only for READ-ONLY analysis, then delegate all
  cell writes + row inserts to Excel via VBScript automation.
  This ensures formulas, cached values, and VBA stay intact.

Encoding: .vbs files are written as UTF-16LE with BOM so that Windows
  Script Host correctly handles Unicode characters in string literals.
"""
import os
import subprocess


def _looks_like_excel_number(s):
    if not s:
        return False
    if s.startswith("(") and s.endswith(")"):
        inner = s[1:-1]
        cleaned = inner.replace(",", "").strip()
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    cleaned = s.replace(",", "").strip()
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def _vbs_val(val):
    """Serialize a Python value to VBScript literal, safe for VBS string rules."""
    if val is None:
        return "Empty"
    if isinstance(val, bool):
        return "True" if val else "False"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val)
    s = s.replace('"', '""')
    s = "".join(ch if ord(ch) >= 32 or ord(ch) == 9 else " " for ch in s)
    while "  " in s:
        s = s.replace("  ", " ")
    return '"' + s.strip() + '"'


def apply_via_excel(filepath, sheet_ops_list):
    """Apply changes to an .xlsm file using Excel automation (VBScript).

    Args:
        filepath: absolute path to the target .xlsm file
        sheet_ops_list: list of dicts, each:
            {
                "sheet": str,
                "updates": [(row, col, value), ...],  # 1-based
                "inserts": [
                    {
                        "after_row": int,   # insert row = after_row + 1
                        "col_data": {col: value, ...},  # col is 1-based index
                    }
                ]
            }
    Returns: True on success, False on failure
    """
    if not sheet_ops_list:
        return True

    lines = [
        'Dim xl, wb, ws',
        'Set xl = CreateObject("Excel.Application")',
        'xl.Visible = False',
        'xl.DisplayAlerts = False',
        'xl.AskToUpdateLinks = False',
        'xl.ScreenUpdating = False',
        'On Error Resume Next',
        'Set wb = xl.Workbooks.Open("' + filepath + '")',
        'If Err.Number <> 0 Then',
        '  WScript.Echo Err.Description',
        '  WScript.StdErr.WriteLine Err.Description',
        '  xl.Quit',
        '  Set xl = Nothing',
        '  WScript.Quit 1',
        'End If',
        'On Error Goto 0',
    ]

    for ops in sheet_ops_list:
        sheet_name = ops["sheet"]
        vbs_sheet_name = sheet_name.replace('"', '""')
        lines.append('Set ws = wb.Sheets("' + vbs_sheet_name + '")')

        for row, col, val in ops.get("updates", []):
            if isinstance(val, str) and _looks_like_excel_number(val):
                lines.append('ws.Cells(' + str(row) + ', ' + str(col) + ').NumberFormat = "@"')
                lines.append('ws.Cells(' + str(row) + ', ' + str(col) + ').Value = "' + "'" + val.replace('"', '""') + '"')
            else:
                lines.append('ws.Cells(' + str(row) + ', ' + str(col) + ').Value = ' + _vbs_val(val))

        inserts = ops.get("inserts", [])
        inserts.sort(key=lambda x: x["after_row"], reverse=True)
        if inserts and len(set(i["after_row"] for i in inserts)) == 1:
            inserts.reverse()

        for ins in inserts:
            new_row = ins["after_row"] + 1
            lines.append('ws.Rows("' + str(new_row) + ':' + str(new_row) + '").Insert -4121, 0')

            col_data = ins.get("col_data", {})
            for col in sorted(col_data.keys()):
                val = col_data[col]
                if isinstance(val, str) and _looks_like_excel_number(val):
                    lines.append('ws.Cells(' + str(new_row) + ', ' + str(col) + ').NumberFormat = "@"')
                    lines.append('ws.Cells(' + str(new_row) + ', ' + str(col) + ').Value = "' + "'" + val.replace('"', '""') + '"')
                else:
                    lines.append('ws.Cells(' + str(new_row) + ', ' + str(col) + ').Value = ' + _vbs_val(val))

    lines.extend([
        'On Error Resume Next',
        'xl.CalculateFull',
        'wb.Save',
        'If Err.Number <> 0 Then',
        '  WScript.Echo Err.Description',
        '  wb.Close False',
        '  xl.Quit',
        '  Set xl = Nothing',
        '  WScript.Quit 1',
        'End If',
        'wb.Close',
        'xl.Quit',
        'Set xl = Nothing',
        'WScript.Quit 0',
    ])

    vbs_content = '\n'.join(lines)

    vbs_path = filepath + ".merge.vbs"
    try:
        with open(vbs_path, "w", encoding="utf-16") as f:
            f.write(vbs_content)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        proc = subprocess.Popen(
            ["cscript.exe", vbs_path, "/nologo"],
            startupinfo=startupinfo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_data, stderr_data = proc.communicate(timeout=300)
        if proc.returncode != 0:
            console_enc = "gbk"
            err_text = (stdout_data or b"").decode(console_enc, errors="replace").strip()
            if not err_text:
                err_text = (stderr_data or b"").decode(console_enc, errors="replace").strip()
            return False, err_text or "未知错误"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "VBS 脚本执行超时"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            if os.path.exists(vbs_path):
                os.unlink(vbs_path)
        except Exception:
            pass
