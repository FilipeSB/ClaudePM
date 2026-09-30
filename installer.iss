; Script Inno Setup - gera um instalador "a sério" para a aplicação
; Gestão de Pessoas e Projetos: ícone no ambiente de trabalho/menu Iniciar,
; e entrada em "Aplicações instaladas" do Painel de Controlo, com desinstalador.
;
; Requer: Inno Setup 6 (https://jrsoftware.org/isinfo.php) - gratuito.
; Os runners "windows-latest" do GitHub Actions já o têm pré-instalado.
;
; Gera: Output/GestaoProjetos-Setup.exe

#define MyAppName "Gestão de Pessoas e Projetos"
#define MyAppVersion "1.4.0"
#define MyAppPublisher "A tua empresa"
#define MyAppExeName "GestaoProjetos.exe"

[Setup]
AppId={{B6C6E1A0-6D6A-4C2A-9C9D-GESTAOPROJETOS}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\GestaoProjetos
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=GestaoProjetos-Setup
SetupIconFile=assets\icon.ico
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar ícone no Ambiente de Trabalho"; GroupDescription: "Ícones adicionais:"

[Files]
Source: "dist\GestaoProjetos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
