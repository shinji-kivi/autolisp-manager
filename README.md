# AutoLISP 管理ツール

AutoCAD の AutoLISP ファイルをかんたんに管理するデスクトップアプリです。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-blue.svg)]()

---

## ダウンロード

👉 **[最新版をダウンロード（GitHub Releases）](https://github.com/shinji-kivi/autolisp-manager/releases/latest)**

`autolisp-manager.exe` を任意のフォルダに保存して実行するだけで使えます。
インストール不要・単一ファイル。

> ⚠️ Windows SmartScreen の警告が出る場合は「詳細情報」→「実行」を選択してください。

---

## 機能

| 機能 | 内容 |
|------|------|
| **スタートアップ登録** | AutoCAD 起動時に自動ロードする LISP を登録 |
| **有効 / 無効 切り替え** | スイッチ1つでロードのオン・オフ |
| **コマンド表示** | 各 LISP が定義するコマンド名を自動抽出・表示 |
| **リポジトリ管理** | LISP ファイルを指定フォルダに自動コピー・重複リネーム |
| **TRUSTEDPATHS 更新** | AutoCAD 起動中にセキュリティパスを自動登録 |

---

## 使い方

1. `autolisp-manager.exe` を起動
2. **「LISP を追加」** ボタンからファイルを選択、またはアプリの画面に直接ドラッグ＆ドロップで LISP ファイルを登録
3. AutoCAD を起動すると登録した LISP が自動でロードされます
4. スイッチで有効 / 無効を切り替え
5. 不要なファイルは各ファイル右側の **「×」ボタン** で削除できます（登録先フォルダからも削除されるので注意）

### 初回起動時の注意

AutoCAD が LISP ファイルを読み込む際、セキュリティ確認ダイアログが表示される場合があります。

> **「常にロード」を選択してください。**
> 「1回のみ」を選ぶと次回起動時に再度表示されます。

このアプリは LISP フォルダを AutoCAD の信頼済みパス（TRUSTEDPATHS）に自動登録するため、正常にセットアップが完了すると以降はダイアログが表示されなくなります。

---

## 仕組み

- `%APPDATA%\Autodesk\Support\Tool_LISP\acaddoc.lsp` を生成し、AutoCAD のサポートパスに追加することで自動ロードを実現
- 設定は `%APPDATA%\.lisp_manager_config.json` に保存されます
- EXE の場所は問いません（デスクトップでも USB でも OK）

---

## 動作環境

- Windows 10 / 11（64bit）
- AutoCAD 2020 以降

---

## 削除・クリーンアップ

このアプリはインストーラーを使用しないため、以下のファイルを手動で削除してください。

| 削除するもの | パス |
|------------|------|
| アプリ本体 | `autolisp-manager.exe`（保存した場所） |
| 設定ファイル | `%APPDATA%\.lisp_manager_config.json` |
| 自動ロード設定 | `%APPDATA%\Autodesk\Support\Tool_LISP\` フォルダごと |

> **AutoCAD をお使いの場合**、削除後に AutoCAD の「オプション」→「ファイル」→「サポートファイル検索パス」から `Tool_LISP` のパスを手動で取り除いてください。

---

## 開発者向け（ソースからビルド）

```bash
# 依存ライブラリのインストール
pip install -r requirements.txt

# アプリ起動
cd src
python main.py

# EXE ビルド
build.bat
```

**必要な Python バージョン**: 3.11 以上

---

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。

---

## 作者

**studio kivi**
AutoCAD を使う建築・設計事務所のための小さなツールを作っています。
