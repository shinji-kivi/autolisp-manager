# AutoLISP 管理ツール

AutoCAD の AutoLISP ファイルをかんたんに管理するデスクトップアプリです。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-blue.svg)]()

---

## ダウンロード

👉 **[最新版をダウンロード（GitHub Releases）](https://github.com/shinji-kivi/autolisp-manager/releases/latest)**

`AutoLISP管理ツール.exe` を任意のフォルダに保存して実行するだけで使えます。
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

1. `AutoLISP管理ツール.exe` を起動
2. **「LISP を追加」** ボタンから `.lsp` ファイルをドラッグ＆ドロップ
3. スイッチで有効 / 無効を切り替え
4. AutoCAD を起動すると登録した LISP が自動でロードされます

---

## 仕組み

- `%APPDATA%\Autodesk\Support\Tool_LISP\acaddoc.lsp` を生成し、AutoCAD のサポートパスに追加することで自動ロードを実現
- 設定は `%APPDATA%\AutoLISP管理ツール\` に保存されます
- EXE の場所は問いません（デスクトップでも USB でも OK）

---

## 動作環境

- Windows 10 / 11（64bit）
- AutoCAD 2020 以降（スタートアップ登録・TRUSTEDPATHS 更新機能）
- LISP ファイルの表示・整理機能は AutoCAD 未インストールでも利用可

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
