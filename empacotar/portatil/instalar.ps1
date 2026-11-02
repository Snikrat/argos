# Instala o Argos a partir do pacote portátil (pasta "app" ao lado deste script).
param(
    [string]$Destino = (Join-Path $env:LOCALAPPDATA 'argos\app'),
    [switch]$SemPath,
    [switch]$SemInicializacao,
    [switch]$SemAbrir,
    [switch]$SemRegistro
)
$ErrorActionPreference = 'Stop'
$origem = Join-Path $PSScriptRoot 'app'
if (-not (Test-Path (Join-Path $origem 'argos-app.exe'))) { throw "Pasta 'app' não encontrada ao lado do instalador." }

Write-Host ''
Write-Host '  Argos - instalando' -ForegroundColor Cyan
Write-Host "  em $Destino"

# Fecha o app se já estiver aberto (atualização)
Get-Process argos-app -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Destino*" } | Stop-Process -Force

# Versão anterior, de quando o app se chamava "devs": sai do Menu Iniciar, da inicialização,
# dos Aplicativos instalados e do PATH. Os dados (registro, preferências, logs) o próprio app
# traz para %LOCALAPPDATA%\argos ao abrir.
$velho = Join-Path $env:LOCALAPPDATA 'devs'
Get-Process devs-app -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath('Startup')) 'devs.lnk') -ErrorAction SilentlyContinue
Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) 'devs.lnk') -ErrorAction SilentlyContinue
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\devs' -Recurse -ErrorAction SilentlyContinue
$pathUsuario = [Environment]::GetEnvironmentVariable('Path', 'User')
$semVelho = ($pathUsuario -split ';' | Where-Object { $_ -and $_ -ne (Join-Path $velho 'app') }) -join ';'
if ($semVelho -ne $pathUsuario.TrimEnd(';')) { [Environment]::SetEnvironmentVariable('Path', $semVelho, 'User') }
Start-Sleep -Milliseconds 800
foreach ($pasta in 'app', 'webview', 'build', 'venv-dev') {
    Remove-Item (Join-Path $velho $pasta) -Recurse -Force -ErrorAction SilentlyContinue
}

# Cache da janela de versões antigas (fazia a interface antiga continuar aparecendo)
Remove-Item (Join-Path (Split-Path $Destino) 'webview') -Recurse -Force -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force $Destino | Out-Null
robocopy $origem $Destino /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw 'Falha ao copiar os arquivos.' }
# O desinstalador fica junto do app, para o "Desinstalar" das Configurações do Windows
Copy-Item (Join-Path $PSScriptRoot 'desinstalar.ps1') $Destino -Force
Write-Host '  arquivos copiados' -ForegroundColor Green

$exe = Join-Path $Destino 'argos-app.exe'
if (-not $SemRegistro) {
    # Atalho no Menu Iniciar (achar digitando "argos")
    $menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Argos.lnk'
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($menu)
    $s.TargetPath = $exe
    $s.WorkingDirectory = $Destino
    $s.Description = 'O que está rodando de desenvolvimento: Docker, portas e processos'
    $s.Save()

    # Entrada em Configurações > Aplicativos instalados (só para este usuário)
    $chave = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\argos'
    # O exe não tem versão nos metadados: pergunta ao próprio CLI ("argos 1.2.0")
    $versao = ((& (Join-Path $Destino 'argos.exe') --versao) -split ' ')[-1]
    $tamanho = [int]((Get-ChildItem $Destino -Recurse -File | Measure-Object Length -Sum).Sum / 1KB)
    New-Item -Path $chave -Force | Out-Null
    $valores = @{
        DisplayName     = 'Argos'
        DisplayIcon     = "$exe,0"
        DisplayVersion  = $(if ($versao) { $versao } else { '1.0.0' })
        Publisher       = 'Argos'
        InstallLocation = $Destino
        UninstallString = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $Destino 'desinstalar.ps1')`""
        EstimatedSize   = $tamanho
        NoModify        = 1
        NoRepair        = 1
    }
    foreach ($k in $valores.Keys) {
        $tipo = if ($valores[$k] -is [int]) { 'DWord' } else { 'String' }
        New-ItemProperty -Path $chave -Name $k -Value $valores[$k] -PropertyType $tipo -Force | Out-Null
    }
    Write-Host '  no Menu Iniciar e em Configurações > Aplicativos' -ForegroundColor Green
}

if (-not $SemPath) {
    $path = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (($path -split ';') -notcontains $Destino) {
        [Environment]::SetEnvironmentVariable('Path', ($path.TrimEnd(';') + ';' + $Destino), 'User')
    }
    Write-Host '  comando `argos` disponível (em terminais abertos depois de agora)' -ForegroundColor Green
}

if (-not $SemInicializacao) {
    $atalho = Join-Path ([Environment]::GetFolderPath('Startup')) 'argos.lnk'
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($atalho)
    $s.TargetPath = $exe
    $s.Arguments = '--oculto'
    $s.Description = 'Argos'
    $s.Save()
    Write-Host '  inicia com o Windows (escondido na bandeja)' -ForegroundColor Green
}

if (-not $SemAbrir) {
    Start-Process $exe
    Write-Host ''
    Write-Host '  Pronto! O ícone do Argos está perto do relógio (Ctrl+Alt+D abre o painel).' -ForegroundColor Cyan
    Write-Host '  Se não vir o ícone, ele pode estar na setinha ^ ao lado do relógio.'
    Write-Host '  Se seus projetos não ficam em Área de Trabalho\projetos, ajuste em Configurações.'
}
Write-Host ''
