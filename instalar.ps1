# Compila a partir do código e instala nesta máquina:
#   - argos.exe e argos-app.exe em %LOCALAPPDATA%\argos\app
#   - essa pasta no PATH do usuário (comando `argos` em qualquer terminal)
#   - atalho na inicialização do Windows (app abre escondido na bandeja)
# Uso:  .\instalar.ps1           (instala/atualiza)
#       .\instalar.ps1 -SemInicializacao
# Para levar a outra máquina: .\empacotar\gerar_zip.ps1

param([switch]$SemInicializacao)
$ErrorActionPreference = 'Stop'

$compilado = & (Join-Path $PSScriptRoot 'empacotar\compilar.ps1') | Select-Object -Last 1

# Remove os atalhos antigos do script PowerShell, se existirem
foreach ($antigo in "$HOME\.local\bin\devs.ps1", "$HOME\.local\bin\devs.cmd") {
    if (Test-Path $antigo) { Remove-Item $antigo; Write-Host "  removido $antigo" }
}

# O mesmo instalador do pacote portátil, apontando para a pasta recém-compilada
$temp = Join-Path $env:LOCALAPPDATA 'argos\build\local'
Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $temp | Out-Null
New-Item -ItemType Junction -Path (Join-Path $temp 'app') -Target $compilado | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'empacotar\portatil\*.ps1') $temp
& (Join-Path $temp 'instalar.ps1') -SemInicializacao:$SemInicializacao
