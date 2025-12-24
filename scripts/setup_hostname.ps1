param([string]$LabHost = "llm-lab")

$Line = "127.0.0.1`t$LabHost"
$HostsFile = "$env:WINDIR\System32\drivers\etc\hosts"

Write-Host "This will add the following line to $HostsFile:"
Write-Host "  $Line"
Write-Host ""

$ans = Read-Host "Proceed? [y/N]"
if ($ans -ne "y" -and $ans -ne "Y") {
  Write-Host "Canceled."
  exit 0
}

$IsAdmin = ([Security.Principal.WindowsPrincipal] `
  [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $IsAdmin) {
  Write-Host "Please re-run PowerShell as Administrator, then run:"
  Write-Host "  scripts\setup_hostname.ps1"
  exit 1
}

$content = Get-Content $HostsFile -Raw
if ($content -match "(?m)^\s*127\.0\.0\.1\s+$LabHost(\s|$)") {
  Write-Host "Entry already present."
  exit 0
}

Add-Content -Path $HostsFile -Value "`n$Line`n"
Write-Host "Done. You should now be able to open: http://$LabHost`:3000"
