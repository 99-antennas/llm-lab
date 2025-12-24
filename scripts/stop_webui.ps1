if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker is not installed."
  exit 1
}

$exists = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq "open-webui" }

if ($exists) {
  Write-Host "Stopping Open WebUI container..."
  docker stop open-webui | Out-Null
  Write-Host "Open WebUI stopped."
} else {
  Write-Host "Open WebUI container not found. Nothing to stop."
}
