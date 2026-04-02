; AutoLISP管理ツール - Inno Setup インストーラースクリプト
; ビルド方法:
;   iscc installer.iss
; または Inno Setup IDE でこのファイルを開いてビルド

#define AppName      "AutoLISP管理ツール"
#define AppVersion   "1.0.0"
#define AppPublisher "Studio Kivi"
#define AppExeName   "AutoLISP管理ツール.exe"
; インストール先: %LOCALAPPDATA%\AutoLISP管理ツール
#define InstallDir   "{localappdata}\AutoLISP管理ツール"

[Setup]
AppId={{9F3A2B1C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppVerName={#AppName} {#AppVersion}

; インストール先（管理者権限不要）
DefaultDirName={#InstallDir}
DisableDirPage=yes

; スタートメニュー
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; 出力ファイル
OutputDir=installer_output
OutputBaseFilename=Setup_{#AppName}_{#AppVersion}

; アンインストール情報（「プログラムの追加と削除」に登録）
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
CreateUninstallRegKey=yes

; 管理者権限不要（ユーザーローカルにインストール）
PrivilegesRequired=lowest

; 圧縮
Compression=lzma
SolidCompression=yes

; インストーラーアイコン
SetupIconFile=assets\logo.ico

; ウィンドウ設定
WizardStyle=modern

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; GroupDescription: "追加タスク:"

[Files]
; アプリケーション（onedir ビルド成果物をまるごとコピー）
Source: "dist\AutoLISP管理ツール\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
; AutoCAD リボンパネル バンドル
Source: "panel\bundle\PackageContents.xml"; DestDir: "{userappdata}\Autodesk\ApplicationPlugins\AutoLispPanel.bundle"; Flags: ignoreversion
Source: "assets\logo.png";                  DestDir: "{userappdata}\Autodesk\ApplicationPlugins\AutoLispPanel.bundle"; Flags: ignoreversion
Source: "panel\AutoLispPanel\bin\Release\net8.0-windows\AutoLispPanel.dll";  DestDir: "{userappdata}\Autodesk\ApplicationPlugins\AutoLispPanel.bundle\Contents\2026"; Flags: ignoreversion
Source: "panel\AutoLispPanel\bin\Release\net10.0-windows\AutoLispPanel.dll"; DestDir: "{userappdata}\Autodesk\ApplicationPlugins\AutoLispPanel.bundle\Contents\2027"; Flags: ignoreversion

[Icons]
; スタートメニュー
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} をアンインストール"; Filename: "{uninstallexe}"
; デスクトップ（タスクで選択した場合のみ）
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; インストール完了後に自動起動（acaddoc.lsp にパスを書き込むため）
Filename: "{app}\{#AppExeName}"; Description: "{#AppName} を起動する"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; 正常終了を要求（PyInstaller bootloader が _MEI* をクリーンアップできるよう /f なし）
Filename: "taskkill.exe"; Parameters: "/im ""{#AppExeName}"""; \
  RunOnceId: "StopApp"; Flags: runhidden waituntilterminated skipifdoesntexist
; 念のため強制終了（まだ残っていれば）
Filename: "taskkill.exe"; Parameters: "/f /im ""{#AppExeName}"""; \
  RunOnceId: "KillApp"; Flags: runhidden waituntilterminated skipifdoesntexist

; アンインストール時の処理順序:
;   1. taskkill で実行中の EXE を終了
;   2. [Code] CurUninstallStepChanged で PowerShell によりレジストリ・フォルダ削除
;   3. Inno Setup が EXE 本体を削除

[Code]
function InitializeSetup(): Boolean;
var
  UninstallKey: string;
  InstalledPath: string;
begin
  Result := True;
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{9F3A2B1C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}_is1';
  if RegQueryStringValue(HKCU, UninstallKey, 'InstallLocation', InstalledPath) then
  begin
    case MsgBox('AutoLISP管理ツール は既にインストールされています。' + #13#10 + #13#10 +
                '再インストール（上書き更新）しますか？',
                mbConfirmation, MB_YESNO) of
      IDNO: Result := False;
    end;
  end;
end;

procedure RegisterTrustedPaths();
var
  ScriptPath: string;
  Lines: TArrayOfString;
  ResultCode: Integer;
begin
  ScriptPath := ExpandConstant('{tmp}\register_trusted.ps1');
  SetArrayLength(Lines, 19);
  Lines[0]  := '$p = "$env:APPDATA\Autodesk\ApplicationPlugins\..."';
  Lines[1]  := '$base = "HKCU:\Software\Autodesk\AutoCAD"';
  Lines[2]  := 'if (-not (Test-Path $base)) { exit }';
  Lines[3]  := 'Get-ChildItem $base -EA SilentlyContinue | ForEach-Object {';
  Lines[4]  := '  Get-ChildItem $_.PSPath -EA SilentlyContinue | ForEach-Object {';
  Lines[5]  := '    $pp = Join-Path $_.PSPath "Profiles"';
  Lines[6]  := '    if (Test-Path $pp) {';
  Lines[7]  := '      Get-ChildItem $pp -EA SilentlyContinue | ForEach-Object {';
  Lines[8]  := '        $sp = Join-Path $_.PSPath "General"';
  Lines[9]  := '        if (Test-Path $sp) {';
  Lines[10] := '          $v = ""';
  Lines[11] := '          try { $v = [string](Get-ItemPropertyValue $sp -Name TRUSTEDPATHS -EA Stop) } catch {}';
  Lines[12] := '          if ($v -notmatch [regex]::Escape($p)) { $v = if ($v) { "$p;$v" } else { $p } }';
  Lines[13] := '          try { Set-ItemProperty $sp -Name TRUSTEDPATHS -Value $v } catch {}';
  Lines[14] := '        }';
  Lines[15] := '      }';
  Lines[16] := '    }';
  Lines[17] := '  }';
  Lines[18] := '}';
  SaveStringsToFile(ScriptPath, Lines, False);
  Exec('powershell.exe',
    '-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + ScriptPath + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RegisterTrustedPaths();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ScriptPath: string;
  Lines: TArrayOfString;
  ResultCode: Integer;
begin
  if CurUninstallStep <> usUninstall then Exit;

  ScriptPath := ExpandConstant('{tmp}\cleanup.ps1');

  SetArrayLength(Lines, 36);
  Lines[0]  := '$pl = "$env:APPDATA\Autodesk\ApplicationPlugins"';
  Lines[1]  := '$bundle = "$pl\AutoLispPanel.bundle"';
  Lines[2]  := '$cfg = "$env:APPDATA\.lisp_manager_config.json"';
  Lines[3]  := '$repo = "$pl\Tool_LISP"';
  Lines[4]  := 'if (Test-Path $cfg) { try { $r = (Get-Content $cfg -Raw | ConvertFrom-Json).repo_path; if ($r) { $repo = $r } } catch {} }';
  Lines[5]  := '$norms = @($pl.ToLower(), ($pl.ToLower() + "\..."), $repo.TrimEnd("\").ToLower(), ($repo.TrimEnd("\").ToLower() + "\...")) | Select-Object -Unique';
  Lines[6]  := '$base = "HKCU:\Software\Autodesk\AutoCAD"';
  Lines[7]  := 'if (Test-Path $base) {';
  Lines[8]  := '  Get-ChildItem $base -EA SilentlyContinue | ForEach-Object {';
  Lines[9]  := '    Get-ChildItem $_.PSPath -EA SilentlyContinue | ForEach-Object {';
  Lines[10] := '      $pp = Join-Path $_.PSPath "Profiles"';
  Lines[11] := '      if (Test-Path $pp) {';
  Lines[12] := '        Get-ChildItem $pp -EA SilentlyContinue | ForEach-Object {';
  Lines[13] := '          foreach ($sub in @("General","Variables")) {';
  Lines[14] := '            $sp = Join-Path $_.PSPath $sub';
  Lines[15] := '            if (Test-Path $sp) {';
  Lines[16] := '              $keys = if ($sub -eq "General") { @("TRUSTEDPATHS","ACAD") } else { @("TRUSTEDPATHS") }';
  Lines[17] := '              foreach ($k in $keys) {';
  Lines[18] := '                $v = ""';
  Lines[19] := '                try { $v = [string](Get-ItemPropertyValue $sp -Name $k -EA Stop) } catch {}';
  Lines[20] := '                if ($v) {';
  Lines[21] := '                  $parts = $v.Split(";") | Where-Object { $_.Trim() -and ($norms -notcontains $_.Trim().TrimEnd("\").ToLower()) }';
  Lines[22] := '                  try { Set-ItemProperty $sp -Name $k -Value ($parts -join ";") } catch {}';
  Lines[23] := '                }';
  Lines[24] := '              }';
  Lines[25] := '            }';
  Lines[26] := '          }';
  Lines[27] := '        }';
  Lines[28] := '      }';
  Lines[29] := '    }';
  Lines[30] := '  }';
  Lines[31] := '}';
  Lines[32] := '$ad = Join-Path $repo "acaddoc.lsp"; if (Test-Path $ad) { Remove-Item $ad -Force -EA SilentlyContinue }';
  Lines[33] := 'if ($repo -ne $pl -and (Test-Path $repo)) { Remove-Item $repo -Recurse -Force -EA SilentlyContinue }';
  Lines[34] := 'if (Test-Path $bundle) { Remove-Item $bundle -Recurse -Force -EA SilentlyContinue }';
  Lines[35] := 'if (Test-Path $cfg) { Remove-Item $cfg -Force -EA SilentlyContinue }';

  SaveStringsToFile(ScriptPath, Lines, False);
  Exec('powershell.exe',
    '-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + ScriptPath + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
