# Testa e empacota com o PyInstaller. Devolve a pasta gerada (com argos.exe e argos-app.exe).
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot)

# A .venv fica fora do OneDrive (milhares de arquivos não precisam sincronizar).
# A variável é removida no fim para não vazar para o app aberto depois.
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:LOCALAPPDATA 'argos\venv-dev'
$build = Join-Path $env:LOCALAPPDATA 'argos\build'
try {
    Write-Host '> Dependências' -ForegroundColor Cyan
    uv sync --quiet

    Write-Host '> Testes' -ForegroundColor Cyan
    uv run pytest -q | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Testes falharam.' }

    Write-Host '> Empacotando' -ForegroundColor Cyan
    uv run python empacotar\icone.py empacotar\argos.ico
    uv run pyinstaller empacotar\argos.spec --noconfirm --log-level ERROR --distpath "$build\dist" --workpath "$build\work" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller falhou.' }
} finally {
    Remove-Item env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
}

Join-Path $build 'dist\argos'
