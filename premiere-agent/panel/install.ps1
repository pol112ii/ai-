# PP AutoCut 패널 설치 스크립트 (Windows, 관리자 권한 불필요)
# 1) 미서명 확장 허용(PlayerDebugMode=1) 2) 패널을 CEP extensions 폴더로 복사
#    3) 파이썬 분석기 설치(pip install -e)
#
# 사용: PowerShell에서  ->  powershell -ExecutionPolicy Bypass -File .\install.ps1

$ErrorActionPreference = "Stop"
$panelId = "com.joybear.ppautocut"
$src = $PSScriptRoot
$repo = Split-Path $src -Parent  # premiere-agent 폴더

Write-Host "== PP AutoCut 설치 ==" -ForegroundColor Cyan

# 1) 미서명 CEP 확장 허용
foreach ($v in 9..12) {
  $key = "HKCU:\Software\Adobe\CSXS.$v"
  New-Item -Path $key -Force | Out-Null
  Set-ItemProperty -Path $key -Name "PlayerDebugMode" -Value "1" -Type String
}
Write-Host "[1/3] 미서명 확장 허용(PlayerDebugMode=1) 완료" -ForegroundColor Green

# 2) 패널 복사
$dest = Join-Path $env:APPDATA "Adobe\CEP\extensions\$panelId"
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item (Join-Path $src "*") $dest -Recurse -Force
Write-Host "[2/3] 패널 복사 완료 -> $dest" -ForegroundColor Green

# 3) 파이썬 분석기 설치
try {
  python -m pip install -e $repo
  Write-Host "[3/3] 분석기 설치 완료 (python -m pp_autocut 사용 가능)" -ForegroundColor Green
} catch {
  Write-Host "[3/3] 파이썬 설치 실패 - 수동으로 'pip install -e `"$repo`"' 실행하세요." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "끝났습니다. 프리미어프로를 재시작하고" -ForegroundColor Cyan
Write-Host "  창(Window) > 확장(Extensions) > PP AutoCut" -ForegroundColor Cyan
Write-Host "을 열어주세요." -ForegroundColor Cyan
