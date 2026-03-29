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

; ウィンドウ設定
WizardStyle=modern

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; GroupDescription: "追加タスク:"

[Files]
; メインの EXE（dist フォルダからコピー）
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

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
; アンインストール前にプロセスを終了（ファイルロック防止）
Filename: "taskkill.exe"; Parameters: "/f /im ""{#AppExeName}"""; \
  RunOnceId: "KillApp"; Flags: runhidden skipifdoesntexist

[Code]
// アンインストール時: acaddoc.lsp のランチャー行が残るが、EXE が消えるだけなので
// AutoCAD での lisp_manager コマンドは静かに失敗する（エラーダイアログなし）。
// 必要であれば管理ツールの「設定を元に戻す」を先に実行してください。
