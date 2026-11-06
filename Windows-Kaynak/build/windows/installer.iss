#define MyAppName "Rigel Cost Pro"
#define MyAppVersion "4.0.0"
#define MyAppPublisher "Ali Uzkuc"
#define MyAppExeName "RigelCostPro.exe"
#ifndef MySourceDir
  #define MySourceDir "..\..\dist\RigelCost-Pro"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\..\release"
#endif

[Setup]
AppId={{13208175-8947-4555-AC2F-467D51916BDF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppVerName={#MyAppName} v{#MyAppVersion}
DefaultDirName={localappdata}\Programs\Rigel Cost Pro
DefaultGroupName=Rigel Cost Pro
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#MyOutputDir}
OutputBaseFilename=RigelCost-Pro-v4.0.0-Setup
SetupIconFile=..\..\assets\rigel.ico
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=4.0.0.0
VersionInfoCompany=Rigel Aluminum
VersionInfoDescription=Rigel Cost Pro Kurulumu
VersionInfoProductName=Rigel Cost Pro
VersionInfoProductVersion=4.0.0.0
CreateUninstallRegKey=yes
Uninstallable=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek kısayollar:"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "KALDIR.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Rigel Cost Pro"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\Rigel Cost Pro Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Rigel Cost Pro"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Rigel Cost Pro'yu aç"; Flags: nowait postinstall skipifsilent

[Code]
var
  CleanUninstall: Boolean;
  UninstallForm: TSetupForm;
  RadioNormal: TNewRadioButton;
  RadioClean: TNewRadioButton;

procedure TryDeleteDir(const Path: String);
begin
  if (Path <> '') and DirExists(Path) then
  begin
    Log('Temiz kaldir: klasor siliniyor -> ' + Path);
    DelTree(Path, True, True, True);
  end;
end;

procedure TryDeleteFile(const Path: String);
begin
  if (Path <> '') and FileExists(Path) then
  begin
    Log('Temiz kaldir: dosya siliniyor -> ' + Path);
    DeleteFile(Path);
  end;
end;

procedure TryDeleteDocumentsExports(const DocumentsDir: String);
var
  FindRec: TFindRec;
begin
  if (DocumentsDir = '') or (not DirExists(DocumentsDir)) then
    Exit;
  if FindFirst(DocumentsDir + '\RigelCost_*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            TryDeleteDir(DocumentsDir + '\' + FindRec.Name)
          else
            TryDeleteFile(DocumentsDir + '\' + FindRec.Name);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure WipeUserData;
var
  LocalAppData, RoamingAppData, UserProfile, DocumentsDir: String;
begin
  LocalAppData := ExpandConstant('{localappdata}');
  RoamingAppData := ExpandConstant('{userappdata}');
  UserProfile := ExpandConstant('{%USERPROFILE}');
  DocumentsDir := ExpandConstant('{userdocs}');

  TryDeleteDir(LocalAppData + '\Rigel Alüminyum\Rigel Cost Pro');
  TryDeleteDir(RoamingAppData + '\Rigel Alüminyum\Rigel Cost Pro');
  TryDeleteDir(LocalAppData + '\Rigel Alüminyum');
  TryDeleteDir(RoamingAppData + '\Rigel Alüminyum');
  TryDeleteDir(LocalAppData + '\RigelCostPro');
  TryDeleteDir(RoamingAppData + '\RigelCostPro');
  TryDeleteDir(LocalAppData + '\Rigel Cost Pro');
  TryDeleteDir(RoamingAppData + '\Rigel Cost Pro');
  TryDeleteDir(UserProfile + '\.rigelcost');
  TryDeleteDocumentsExports(DocumentsDir);
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\RigelCost');
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Rigel Alüminyum');
end;

function InitializeUninstall(): Boolean;
var
  InfoLabel: TNewStaticText;
  OKButton, CancelButton: TNewButton;
begin
  CleanUninstall := False;
  Result := False;

  if UninstallSilent then
  begin
    Result := True;
    Exit;
  end;

  UninstallForm := CreateCustomForm(ScaleX(460), ScaleY(250), False, False);
  try
    UninstallForm.Caption := 'Rigel Cost Pro - Kaldır';
    UninstallForm.Position := poScreenCenter;

    InfoLabel := TNewStaticText.Create(UninstallForm);
    InfoLabel.Parent := UninstallForm;
    InfoLabel.Left := ScaleX(16);
    InfoLabel.Top := ScaleY(16);
    InfoLabel.Width := ScaleX(428);
    InfoLabel.Height := ScaleY(40);
    InfoLabel.Caption :=
      'Kaldırma türünü seçin. Temiz kaldırma veritabanı, ayarlar,' + #13#10 +
      'ekler ve önbellek dahil tüm kullanıcı dosyalarını siler.';
    InfoLabel.AutoSize := False;
    InfoLabel.WordWrap := True;

    RadioNormal := TNewRadioButton.Create(UninstallForm);
    RadioNormal.Parent := UninstallForm;
    RadioNormal.Left := ScaleX(20);
    RadioNormal.Top := ScaleY(70);
    RadioNormal.Width := ScaleX(420);
    RadioNormal.Height := ScaleY(36);
    RadioNormal.Caption := 'Normal kaldır — yalnız program dosyaları (veriler kalır)';
    RadioNormal.Checked := True;

    RadioClean := TNewRadioButton.Create(UninstallForm);
    RadioClean.Parent := UninstallForm;
    RadioClean.Left := ScaleX(20);
    RadioClean.Top := ScaleY(112);
    RadioClean.Width := ScaleX(420);
    RadioClean.Height := ScaleY(36);
    RadioClean.Caption := 'Temiz kaldır / Tüm dosyaları kaldır — program + tüm veriler';

    OKButton := TNewButton.Create(UninstallForm);
    OKButton.Parent := UninstallForm;
    OKButton.Caption := 'Kaldır';
    OKButton.ModalResult := mrOk;
    OKButton.Default := True;
    OKButton.Width := ScaleX(100);
    OKButton.Height := ScaleY(28);
    OKButton.Left := ScaleX(236);
    OKButton.Top := ScaleY(200);

    CancelButton := TNewButton.Create(UninstallForm);
    CancelButton.Parent := UninstallForm;
    CancelButton.Caption := 'Vazgeç';
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;
    CancelButton.Width := ScaleX(100);
    CancelButton.Height := ScaleY(28);
    CancelButton.Left := ScaleX(344);
    CancelButton.Top := ScaleY(200);

    if UninstallForm.ShowModal <> mrOk then
      Exit;

    CleanUninstall := RadioClean.Checked;
    if CleanUninstall then
    begin
      if MsgBox(
        'UYARI: Temiz kaldırma geri alınamaz.' + #13#10 + #13#10 +
        '• %LOCALAPPDATA% / %APPDATA% Rigel veri klasörleri' + #13#10 +
        '• Veritabanları, ekler, ayarlar ve önbellek' + #13#10 +
        '• Belgelerdeki RigelCost_* dışa aktarımlar' + #13#10 +
        '• .rigelcost yapılandırma klasörü' + #13#10 + #13#10 +
        'Devam edilsin mi?',
        mbConfirmation,
        MB_YESNO
      ) <> IDYES then
        Exit;
    end;
    Result := True;
  finally
    UninstallForm.Free;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and CleanUninstall then
    WipeUserData;
end;
