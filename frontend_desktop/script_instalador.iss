; Script para o Inno Setup - Sistema de Gestão de Estoque

[Setup]
; Informações básicas da aplicação
AppName=Sistema de Gestão de Estoque
AppVersion=2.3
AppPublisher=MatheusLopes
DefaultDirName={autopf}\SistemaEstoque
DefaultGroupName=Sistema de Gestão de Estoque
DisableProgramGroupPage=yes
; Onde guardar o setup.exe final e qual o seu nome
OutputDir=.\instalador
OutputBaseFilename=setup_estoque_2.3
; Configurações de compressão e aparência
Compression=lzma
SolidCompression=yes
WizardStyle=classic

[Languages]
; Adiciona o idioma Português do Brasil ao instalador
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
; Adiciona a opção de criar um atalho no Ambiente de Trabalho
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkablealone

[Files]
; A parte mais importante: diz ao Inno Setup para incluir TODOS os ficheiros da nossa pasta 'dist\run'
Source: "dist\run\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTA: Este script deve estar na pasta 'frontend_desktop' para este caminho funcionar

[Icons]
; Cria os atalhos no Menu Iniciar e no Ambiente de Trabalho
Name: "{group}\Sistema de Gestão de Estoque"; Filename: "{app}\run.exe"
Name: "{autodesktop}\Sistema de Gestão de Estoque"; Filename: "{app}\run.exe"; Tasks: desktopicon

[Run]
; Oferece a opção de iniciar a aplicação logo após a instalação
Filename: "{app}\run.exe"; Description: "{cm:LaunchProgram,Sistema de Gestão de Estoque}"; Flags: nowait postinstall skipifsilent