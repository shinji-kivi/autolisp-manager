# LISP 開発者ガイド — パネル対応

管理ツールのパレットに日本語ボタンを表示するための規約です。

---

## メタデータの書き方

LISPファイルの先頭に以下の形式で記述します。

```lisp
;;; @file        ROOM-TAG.lsp
;;; @description 部屋タグの配置・編集
;;; @version     1.0
;;; @author      your name
;;; @button ROOM-TAG 部屋タグを配置
;;; @button ROOM-TAG-EDIT タグを編集
;;; @button ROOM-TAG-HELP 部屋タグ ヘルプ
```

| メタデータ | 用途 |
|-----------|------|
| `@description` | パレットのグループ名として表示（省略時はファイル名） |
| `@button コマンド名 日本語ラベル` | パレットのボタンラベル（省略時はコマンド名がそのまま表示） |

`@button` の `コマンド名` は `defun c:` で定義した名前と一致させてください（大文字小文字は区別しません）。

---

## パレットでの表示

1ファイル = 1グループとして折りたたみ表示されます。

```
▼ 部屋タグの配置・編集  [3]    ← @description
    部屋タグを配置              ← @button
    タグを編集
    部屋タグ ヘルプ
```

メタデータがなくても、`defun c:` で定義したコマンド名はそのまま表示されます。

---

## ヘルプコマンド

LISPファイルの末尾に `-HELP` コマンドを定義すると、パレットからヘルプを表示できます。

```lisp
(defun c:ROOM-TAG-HELP ()
  (ag:show-readme "ROOM-TAG_README.md")
)
```

- ヘルプ基盤（`ag-help.lsp`）は管理ツールが自動配置するので、開発者が用意する必要はありません
- README ファイル（`〇〇_README.md`）を LISP と同じフォルダに配置してください
- README は DCL の list_box で1行ずつ表示されるため、極端に長い行は避けてください

---

## テンプレート

新しい LISP を作るときの雛形です。

### TEMPLATE.lsp

```lisp
;;; @file        TEMPLATE.lsp
;;; @description [日本語の説明]
;;; @version     1.0
;;; @author      studio kivi
;;; @license     商用利用不可・再配布禁止
;;; @button COMMAND-NAME [日本語ボタン名]
;;; @button COMMAND-NAME-HELP [日本語名] ヘルプ
;;;
;;; (c) 2026 studio kivi. All rights reserved.

;;; メイン処理
(defun c:COMMAND-NAME (/ )
  ;; TODO: 実装
  (princ)
)

;;; ヘルプ
(defun c:COMMAND-NAME-HELP ()
  (ag:show-readme "TEMPLATE_README.md")
)
```

### TEMPLATE_README.md

```markdown
# [コマンド名] - [日本語名称]

[1-2行の概要]

## コマンド一覧

| コマンド | 説明 |
|----------|------|
| `COMMAND1` | 機能の説明 |
| `COMMAND1-HELP` | 本ヘルプを表示 |

## 使い方

### 基本操作
1. コマンドラインに `COMMAND1` と入力してEnter
2. [操作手順を記述]
3. [結果の説明]

## 注意事項
- AutoCAD 2021 以降対応
```

### ファイル構成の例

```
MY-COMMAND/
├── MY-COMMAND.lsp
├── MY-COMMAND_README.md
└── LICENSE.txt
```

---

## チェックリスト

新しいLISPを作るとき:

- [ ] `;;; @description` を書いた
- [ ] 各コマンドに `;;; @button コマンド名 日本語名` を書いた
- [ ] `-HELP` コマンドを定義した（`ag:show-readme` を呼ぶ）
- [ ] `〇〇_README.md` を同じフォルダに作った
- [ ] 管理ツールで登録・動作確認した
