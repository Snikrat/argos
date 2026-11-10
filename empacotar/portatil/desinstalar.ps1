# Remove o argos: app, atalho de inicialização e entrada no PATH.
# Configurações, histórico e logs (%LOCALAPPDATA%\argos) são mantidos, a menos que se peça.
param([switch]$ApagarDados)
$ErrorActionPreference = 'Stop'
$dados = Join-Path $env:LOCALAPPDATA 'argos'
$app = Join-Path $dados 'app'

Write-Host ''
Write-Host '  Argos - desinstalando' -ForegroundColor Cyan

# Fecha o app e também o `argos mcp` que o Claude Code mantém aberto (senão o argos.exe fica preso)
Get-Process argos-app, argos -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$app*" } | Stop-Process -Force
# Tira o registro do servidor MCP: sem isto o Claude Code ficaria apontando para um exe apagado
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) { try { & $claude.Source mcp remove --scope user argos 2>$null | Out-Null } catch {} }
Start-Sleep -Milliseconds 500

Remove-Item (Join-Path ([Environment]::GetFolderPath('Startup')) 'argos.lnk') -ErrorAction SilentlyContinue
Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) 'Argos.lnk') -ErrorAction SilentlyContinue
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\argos' -Recurse -ErrorAction SilentlyContinue

$path = [Environment]::GetEnvironmentVariable('Path', 'User')
$novo = ($path -split ';' | Where-Object { $_ -and $_ -ne $app }) -join ';'
if ($novo -ne $path) { [Environment]::SetEnvironmentVariable('Path', $novo, 'User') }

if (Test-Path $app) {
    try { Remove-Item $app -Recurse -Force }
    catch { Write-Host "  alguns arquivos estão em uso e ficaram em $app (feche os programas abertos pelo Argos e apague a pasta)" -ForegroundColor Yellow }
}
Write-Host '  app removido' -ForegroundColor Green

if ($ApagarDados) {
    Remove-Item $dados -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host '  configurações, histórico e logs apagados' -ForegroundColor Green
} else {
    Write-Host "  configurações e logs mantidos em $dados"
}
Write-Host '  Processos iniciados pelo Argos continuam rodando; pare-os antes se quiser.'
Write-Host ''
