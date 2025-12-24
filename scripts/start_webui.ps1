param(
  [string]$LabHost = "llm-lab"
)

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker is not installed. Please install Docker Desktop from https://www.docker.com/products/docker-desktop/"
  exit 1
}

$BaseUrl = "http://localhost:3000"
$WebuiUrlEnv = "http://localhost:3000"
$NeedHostsSetup = $false

try {
  Resolve-DnsName $LabHost -ErrorAction Stop | Out-Null
  $BaseUrl = "http://$LabHost`:3000"
  $WebuiUrlEnv = $BaseUrl
} catch {
  $NeedHostsSetup = $true
}

docker volume create open-webui-data | Out-Null
docker rm -f open-webui | Out-Null

docker run -d `
  -p 3000:8080 `
  -e ENV=dev `
  -e ENABLE_API_KEYS=true `
  -e WEBUI_URL=$WebuiUrlEnv `
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 `
  -v open-webui-data:/app/backend/data `
  --name open-webui `
  ghcr.io/open-webui/open-webui:main | Out-Null

Write-Host "Open WebUI started."
Write-Host "UI:  $BaseUrl"
Write-Host "API: $BaseUrl/docs"
Write-Host ""

if ($NeedHostsSetup) {
  Write-Host "Optional: enable the friendly URL http://$LabHost`:3000"
  Write-Host "Run PowerShell as Administrator, then:"
  Write-Host "  scripts\setup_hostname.ps1"
  Write-Host ""
  Write-Host "Or add this line to your hosts file:"
  Write-Host "  127.0.0.1   $LabHost"
}
