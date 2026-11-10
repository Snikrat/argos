; Instalador do Argos (Inno Setup 6).
; Compilar: ISCC /DVersao=1.6.0 /DOrigem="<pasta gerada pelo PyInstaller>" /DSaida="<dist>" argos.iss
; (o empacotar\gerar_pacotes.ps1 faz isso)

#ifndef Versao
  #define Versao "0.0.0"
#endif
#ifndef Origem
  #define Origem "..\build\dist\argos"
#endif
#ifndef Saida
  #define Saida "..\dist"
#endif

[Setup]
; O AppId identifica a instalação para atualizar por cima e desinstalar: nunca mudar
AppId={{6F0C5D7E-3B5A-4E63-9C2B-A7E1D4F08A21}
AppName=Argos
AppVersion={#Versao}
AppPublisher=Argos
AppPublisherURL=https://github.com/Snikrat/argos
AppSupportURL=https://github.com/Snikrat/argos/issues
; Só para o usuário atual: não pede administrador
PrivilegesRequired=lowest
DefaultDirName={localappdata}\argos\app
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
UsePreviousAppDir=yes
UninstallDisplayName=Argos
UninstallDisplayIcon={app}\argos-app.exe
OutputDir={#Saida}
OutputBaseFilename=Argos-Setup-{#Versao}
SetupIconFile=argos.ico
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Quem fecha o app somos nós (PrepareToInstall): o "argos mcp" do Claude Code não tem janela
CloseApplications=no
ChangesEnvironment=yes
VersionInfoVersion={#Versao}

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "path"; Description: "Comando ""argos"" no terminal (adiciona ao PATH do usuário)"
Name: "inicializacao"; Description: "Abrir com o Windows, escondido perto do relógio"
Name: "mcp"; Description: "Registrar no Claude Code, se estiver instalado (servidor MCP)"; Flags: unchecked

[Files]
Source: "{#Origem}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; Cache da janela de versões antigas e sobras do instalador por script
Type: filesandordirs; Name: "{localappdata}\argos\webview"
Type: files; Name: "{app}\desinstalar.ps1"
Type: files; Name: "{app}\_internal\*.antigo"
; De quando o app se chamava "devs"
Type: files; Name: "{userstartup}\devs.lnk"
Type: files; Name: "{userprograms}\devs.lnk"
Type: filesandordirs; Name: "{localappdata}\devs\app"

[Registry]
; Entradas em "Aplicativos instalados" criadas pelo instalador por script (o Inno cria a dele)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\argos"; Flags: deletekey dontcreatekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\devs"; Flags: deletekey dontcreatekey

[Icons]
Name: "{userprograms}\Argos"; Filename: "{app}\argos-app.exe"; Comment: "O que está rodando de desenvolvimento: Docker, portas e processos"
Name: "{userstartup}\argos"; Filename: "{app}\argos-app.exe"; Parameters: "--oculto"; Tasks: inicializacao

[Run]
Filename: "{app}\argos.exe"; Parameters: "mcp --instalar"; Tasks: mcp; Flags: runhidden; StatusMsg: "Registrando no Claude Code..."
; Sem skipifsilent: na atualização automática (instalação silenciosa) o app abre de novo sozinho
Filename: "{app}\argos-app.exe"; Description: "Abrir o Argos agora"; Flags: nowait postinstall

[UninstallRun]
; Sem isto o Claude Code ficaria apontando para um executável apagado
Filename: "{cmd}"; Parameters: "/c claude mcp remove --scope user argos"; Flags: runhidden; RunOnceId: "RemoverMcp"

[UninstallDelete]
; A pasta do app é só nossa: sai inteira, inclusive o que veio de instalações antigas por script
Type: filesandordirs; Name: "{app}"
Type: files; Name: "{userstartup}\argos.lnk"
Type: filesandordirs; Name: "{localappdata}\argos\webview"
Type: filesandordirs; Name: "{localappdata}\argos\atualizacao"

[Code]
const
  CHAVE_AMBIENTE = 'Environment';

// Fecha o app e o "argos mcp" (que o Claude Code mantém aberto): com eles rodando
// os executáveis ficam presos e não são substituídos nem apagados.
procedure FecharArgos;
var
  Codigo: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM argos-app.exe', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM argos.exe', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Sleep(600);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  FecharArgos;
  Result := '';
end;

function InitializeUninstall: Boolean;
begin
  FecharArgos;
  Result := True;
end;

function SemPasta(Caminho, Pasta: String): String;
var
  Resto, Item, Saida: String;
  P: Integer;
begin
  Resto := Caminho;
  Saida := '';
  while Resto <> '' do
  begin
    P := Pos(';', Resto);
    if P = 0 then
    begin
      Item := Resto;
      Resto := '';
    end
    else
    begin
      Item := Copy(Resto, 1, P - 1);
      Resto := Copy(Resto, P + 1, Length(Resto));
    end;
    if (Item <> '') and (CompareText(Item, Pasta) <> 0) then
    begin
      if Saida <> '' then
        Saida := Saida + ';';
      Saida := Saida + Item;
    end;
  end;
  Result := Saida;
end;

// PATH do usuário: põe (ou tira) a pasta do app, sem duplicar e sem mexer no resto
procedure AjustarPath(Adicionar: Boolean);
var
  Atual, Novo, App: String;
begin
  App := ExpandConstant('{app}');
  if not RegQueryStringValue(HKEY_CURRENT_USER, CHAVE_AMBIENTE, 'Path', Atual) then
    Atual := '';
  Novo := SemPasta(Atual, App);
  // A pasta de quando o app se chamava "devs" sai junto
  Novo := SemPasta(Novo, ExpandConstant('{localappdata}\devs\app'));
  if Adicionar then
  begin
    if Novo <> '' then
      Novo := Novo + ';';
    Novo := Novo + App;
  end;
  if Novo <> Atual then
    RegWriteExpandStringValue(HKEY_CURRENT_USER, CHAVE_AMBIENTE, 'Path', Novo);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    AjustarPath(WizardIsTaskSelected('path'));
    // Desmarcar a opção numa reinstalação tira o atalho que já existia
    if not WizardIsTaskSelected('inicializacao') then
      DeleteFile(ExpandConstant('{userstartup}\argos.lnk'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AjustarPath(False);
    // Configurações, sessões e logs ficam, a menos que a pessoa peça (nunca no modo silencioso)
    if not UninstallSilent then
      if MsgBox('Apagar também as configurações, sessões e logs do Argos?' + #13#10 +
                '(' + ExpandConstant('{localappdata}\argos') + ')', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{localappdata}\argos'), True, True, True);
  end;
end;
