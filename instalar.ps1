# Compila a partir do código e instala nesta máquina, com o mesmo instalador das releases:
#   - argos.exe e argos-app.exe em %LOCALAPPDATA%\argos\app
#   - atalho no Menu Iniciar e entrada em Configurações > Aplicativos
#   - comando `argos` no PATH e abertura com o Windows (as opções da última instalação são mantidas)
# Uso:  .\instalar.ps1            instala/atualiza e abre o app
#       .\instalar.ps1 -Pacotes   gera também o zip portátil em dist\
# Precisa do Inno Setup: winget install JRSoftware.InnoSetup

param([switch]$Pacotes)
$ErrorActionPreference = 'Stop'

$setup = & (Join-Path $PSScriptRoot 'empacotar\gerar_pacotes.ps1') -SemZip:(-not $Pacotes) | Select-Object -Last 1

Write-Host '> Instalando' -ForegroundColor Cyan
# Silencioso: fecha o app aberto, substitui os arquivos e abre de novo
$p = Start-Process $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -PassThru
# WaitForExit espera só o instalador; "-Wait" esperaria também o app que ele abre no fim
$p.WaitForExit()
if ($p.ExitCode -ne 0) { throw "O instalador terminou com erro (código $($p.ExitCode))." }
Write-Host '  Argos instalado. Ctrl+Alt+D abre o painel.' -ForegroundColor Green
