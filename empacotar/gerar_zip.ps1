# Gera dist\argos-<versão>.zip para instalar em outra máquina (sem Python nem uv).
$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot
$compilado = & (Join-Path $PSScriptRoot 'compilar.ps1') | Select-Object -Last 1

$versao = (Select-String -Path (Join-Path $raiz 'argos\__init__.py') -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
$montagem = Join-Path $env:LOCALAPPDATA 'argos\build\zip\argos'
$zip = Join-Path $raiz "dist\argos-$versao.zip"

Write-Host '> Montando o pacote' -ForegroundColor Cyan
Remove-Item (Split-Path $montagem) -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force (Join-Path $montagem 'app') | Out-Null
robocopy $compilado (Join-Path $montagem 'app') /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw 'Falha ao copiar o app.' }
Copy-Item (Join-Path $PSScriptRoot 'portatil\*') $montagem

New-Item -ItemType Directory -Force (Split-Path $zip) | Out-Null
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path $montagem -DestinationPath $zip -CompressionLevel Optimal
Write-Host ('Pronto: {0} ({1:N0} MB)' -f $zip, ((Get-Item $zip).Length / 1MB)) -ForegroundColor Green
