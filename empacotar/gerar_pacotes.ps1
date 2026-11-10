# Gera em dist\ os dois pacotes de uma versão:
#   Argos-Setup-<versão>.exe      instalador (Inno Setup), com o .sha256 ao lado
#   argos-<versão>-portatil.zip   para usar sem instalar
# Devolve o caminho do instalador.
param([switch]$SemZip)
$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot
$compilado = & (Join-Path $PSScriptRoot 'compilar.ps1') | Select-Object -Last 1

$versao = (Select-String -Path (Join-Path $raiz 'argos\__init__.py') -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
$dist = Join-Path $raiz 'dist'
New-Item -ItemType Directory -Force $dist | Out-Null

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup não encontrado. Instale com: winget install JRSoftware.InnoSetup' }

Write-Host '> Instalador' -ForegroundColor Cyan
$setup = Join-Path $dist "Argos-Setup-$versao.exe"
& $iscc /Qp "/DVersao=$versao" "/DOrigem=$compilado" "/DSaida=$dist" (Join-Path $PSScriptRoot 'argos.iss') | Out-Host
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $setup)) { throw 'O Inno Setup falhou ao gerar o instalador.' }
# Hash ao lado: o Argos confere antes de instalar uma atualização vinda desta pasta
(Get-FileHash $setup -Algorithm SHA256).Hash.ToLower() + "  Argos-Setup-$versao.exe" | Set-Content "$setup.sha256" -Encoding ascii
Write-Host ('  {0} ({1:N0} MB)' -f $setup, ((Get-Item $setup).Length / 1MB)) -ForegroundColor Green

if (-not $SemZip) {
    Write-Host '> Zip portátil' -ForegroundColor Cyan
    $montagem = Join-Path $env:LOCALAPPDATA 'argos\build\zip\argos'
    $zip = Join-Path $dist "argos-$versao-portatil.zip"
    Remove-Item (Split-Path $montagem) -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force (Join-Path $montagem 'app') | Out-Null
    robocopy $compilado (Join-Path $montagem 'app') /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw 'Falha ao copiar o app.' }
    Copy-Item (Join-Path $PSScriptRoot 'portatil\LEIA-ME.txt') $montagem
    Remove-Item $zip -ErrorAction SilentlyContinue
    Compress-Archive -Path $montagem -DestinationPath $zip -CompressionLevel Optimal
    Write-Host ('  {0} ({1:N0} MB)' -f $zip, ((Get-Item $zip).Length / 1MB)) -ForegroundColor Green
}
$setup
