#define AppName "vec4ipa Workbench"
#define AppPublisher "vec4ipa"
#define AppExe "vec4ipa-ui.exe"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{085C8C44-6365-4001-A5B7-24B644885244}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/csiroqa/vec4ipa
AppSupportURL=https://github.com/csiroqa/vec4ipa/issues
AppUpdatesURL=https://github.com/csiroqa/vec4ipa/releases
AppComments=IPA/extIPA to articulatory vector workbench
DefaultDirName={autopf}\vec4ipa
DefaultGroupName=vec4ipa
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=installer
OutputBaseFilename=vec4ipa-setup-{#AppVersion}
SetupIconFile=..\vec_ipa.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AllowNoIcons=yes
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoDescription={#AppName} installer
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Remove the retired C# workbench support files from an older install.
Type: files; Name: "{app}\ipa2vec_core.dll"
Type: files; Name: "{app}\vec4ipa_ui.dll"
Type: files; Name: "{app}\vec4ipa_ui.deps.json"
Type: files; Name: "{app}\vec4ipa_ui.runtimeconfig.json"
Type: files; Name: "{app}\vec4ipa_ui.pdb"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
