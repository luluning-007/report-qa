# ============================================================
# 启动网页.ps1 —— 一键启动年报问答台
#
# 用法：右键这个文件 → 「使用 PowerShell 运行」
#       （或者在终端里输入 .\启动网页.ps1）
# ============================================================

Write-Host ""
Write-Host "  正在启动【年报问答台】..." -ForegroundColor Cyan
Write-Host ""

# 【关键】把 Streamlit 的配置目录指向本项目文件夹
# 原因：系统默认会写到 C:\Users\你\.streamlit，但那个路径没有写入权限
$env:USERPROFILE = $PSScriptRoot

# 切换到脚本所在目录（不管从哪里运行都能正确找到文件）
Set-Location $PSScriptRoot

# 检查虚拟环境是否存在
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "  [错误] 找不到虚拟环境 .venv" -ForegroundColor Red
    Write-Host "  请确认这个脚本放在 report-qa 文件夹里" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

Write-Host "  启动中，浏览器会自动打开 http://localhost:8501" -ForegroundColor Green
Write-Host "  要停止服务，按 Ctrl + C" -ForegroundColor Yellow
Write-Host ""

# 启动 Streamlit
& ".\.venv\Scripts\python.exe" -m streamlit run app.py

# 如果 Streamlit 退出，停在这里让用户看到信息
Read-Host "服务已停止，按回车关闭窗口"
