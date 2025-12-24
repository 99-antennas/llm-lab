if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama is not installed. Please install it from https://ollama.com"
  exit 1
}

Get-Content ../models/models.txt | ForEach-Object {
  ollama pull $_
}

Write-Host "Models installed."
