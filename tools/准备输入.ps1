# 准备一次运行的输入：把 jd_text / resume_text / jd_json_fixed 三样内容依次复制到剪贴板
#
# 为什么要这个脚本：
#   Day 5 实测时，三个输入框被填成了**文件路径**（"data\jd\jd_01.txt"），
#   模型收到 17 个字符的"JD"，返回一堆"未说明"，白跑一次。
#   人手工打开文件、复制、切窗口很容易出错；交给脚本就不会错。
#
# 用法：
#   双击 tools\准备输入.bat         （推荐，脚本会问你要哪一组）
#   或在本目录下：
#     powershell -ExecutionPolicy Bypass -File tools\准备输入.ps1
#     powershell -ExecutionPolicy Bypass -File tools\准备输入.ps1 -Case 01
#
# 编码注意：本文件必须保存为 **UTF-8 with BOM**。
#   PowerShell 5.1 读没有 BOM 的 UTF-8 文件时会按 GBK 解码，中文全乱、脚本直接报语法错误。
param(
    [string]$Case = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$listPath = Join-Path $root 'test\运行清单.csv'

if (-not (Test-Path $listPath)) {
    Write-Host "找不到 $listPath" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

$all = Import-Csv $listPath -Encoding UTF8

# 没给编号就当场问
if ([string]::IsNullOrWhiteSpace($Case)) {
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "  可用的用例（输入编号，直接回车退出）" -ForegroundColor Cyan
    Write-Host "======================================================" -ForegroundColor Cyan
    foreach ($r in $all) {
        $hasArc = if ($r.'档案文件') { '已固化' } else { '未固化' }
        Write-Host ("   {0}  {1,-18} {2} + {3}  [{4}]" -f `
            $r.'用例编号', $r.'场景', $r.'JD文件', $r.'CV文件', $hasArc)
    }
    Write-Host ""
    $Case = Read-Host "  请输入用例编号（如 01）"
    if ([string]::IsNullOrWhiteSpace($Case)) { Write-Host "  已退出。"; exit 0 }
}

$Case = $Case.Trim().PadLeft(2, '0')
$rows = $all | Where-Object { $_.'用例编号' -eq $Case }
if (-not $rows) {
    Write-Host "运行清单里没有用例编号 $Case" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}
$row = $rows[0]

function Send-Content {
    param([string]$Title, [string]$Path, [string]$Target)

    if (-not (Test-Path $Path)) {
        Write-Host "  [x] 找不到文件：$Path" -ForegroundColor Red
        return $false
    }
    $content = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))
    if ($content.Length -lt 1) {
        Write-Host "  [x] 文件是空的：$Path" -ForegroundColor Red
        return $false
    }

    $copied = $true
    try {
        Set-Clipboard -Value $content -ErrorAction Stop
    } catch {
        $copied = $false
    }

    Write-Host ""
    if ($copied) {
        Write-Host "  [$Title] 已复制到剪贴板（$($content.Length) 个字符）" -ForegroundColor Green
    } else {
        Write-Host "  [$Title] 复制到剪贴板失败（$($content.Length) 个字符）" -ForegroundColor Yellow
        Write-Host "      请手动打开这个文件、Ctrl+A 全选、Ctrl+C：" -ForegroundColor Yellow
    }
    Write-Host "      来源文件：$Path"
    Write-Host "      粘贴到　：$Target"
    if ($content.Length -lt 60) {
        Write-Host "      [!] 内容只有 $($content.Length) 个字，可能不对劲" -ForegroundColor Yellow
    }
    $head = $content.Substring(0, [Math]::Min(46, $content.Length)) -replace "`r?`n", " / "
    Write-Host "      开头　　：$head"
    return $true
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  用例 $Case — $($row.'场景')" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

$jdPath = Join-Path $root ("data\jd\{0}.txt" -f $row.'JD文件')
$cvPath = Join-Path $root ("data\resume\{0}.txt" -f $row.'CV文件')

Write-Host ""
Write-Host "步骤 1/3 —— 粘到 Dify 的 jd_text 框" -ForegroundColor White
Send-Content -Title 'JD 原文' -Path $jdPath -Target 'Dify 的 jd_text 框' | Out-Null
Read-Host "      粘好后按回车继续"

Write-Host ""
Write-Host "步骤 2/3 —— 粘到 Dify 的 resume_text 框" -ForegroundColor White
Send-Content -Title '简历原文' -Path $cvPath -Target 'Dify 的 resume_text 框' | Out-Null
Read-Host "      粘好后按回车继续"

Write-Host ""
Write-Host "步骤 3/3 —— 粘到 Dify 的 jd_json_fixed 框" -ForegroundColor White
if ([string]::IsNullOrWhiteSpace($row.'档案文件')) {
    Write-Host "  [!] 用例 $Case 的岗位还没固化过，这一步留空。" -ForegroundColor Yellow
    Write-Host "      跑完这次后可以生成档案（以后再跑这个岗位就有固定分母了）："
    Write-Host "      python tools\freeze_jd.py jd_XX `"岗位关键词`""
} else {
    $arcPath = Join-Path $root ("data\jd_fixed\{0}" -f $row.'档案文件')
    Send-Content -Title '岗位档案（固化版）' -Path $arcPath -Target 'Dify 的 jd_json_fixed 框' | Out-Null
    Read-Host "      粘好后按回车"
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  三样都准备好了，可以去点运行了。" -ForegroundColor Cyan
Write-Host ""
Write-Host "  跑完自检两件事：" -ForegroundColor White
Write-Host "    1. 岗位要求路由 节点的 jd_source 应该是 fixed（档案留空的用例除外）"
Write-Host "    2. 报告里应出现「疑似命中（需人工确认）」小节"
Write-Host ""
Write-Host "  期望行为：$($row.'期望行为（必须满足的客观事实）')" -ForegroundColor White
Write-Host "  参考档位：$($row.'参考档位')" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "按回车关闭这个窗口"
