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

## コンパイル版（.fas / .vlx）で配布する

外部に配るときは、ソースをそのまま渡さずコンパイルして渡します。管理ツールは
`.lsp` / `.fas` / `.vlx` のどれでも登録できます。

### コンパイルのしかた

AutoCAD のコマンドラインに次の1行を入力します（VLIDE のウィザードは不要）。

```lisp
(vl-load-com)(vlisp-compile 'st "C:/path/to/MY-COMMAND.lsp")
```

`T` が返れば成功で、同じフォルダに `MY-COMMAND.fas` ができます。複数ファイルを
1つにまとめたい場合は VLIDE の **File → Make Application** で `.vlx` を作ります。

### メタデータのサイドカー（`.meta`）が必要

`.fas` は文字列テーブルが難読化されるため、**コマンド名も `@description` も
`@button` も読み取れません**。そのままだとパレットのボタンが作られないので、
メタデータだけを書いた `MY-COMMAND.meta` を添えます。

`.fas` の隣に元の `.lsp` を置いた状態で管理ツールに登録すると、`.meta` は
**自動生成**されます。生成物はリポジトリフォルダにできるので、そこからコピーして
配布物に含めてください。手で書く場合の中身はこの形式です。

```
;;; @description 部屋タグの配置・編集
;;; @command ROOM-TAG
;;; @command ROOM-TAG-EDIT
;;; @command ROOM-TAG-HELP
;;; @button ROOM-TAG 部屋タグを配置
;;; @button ROOM-TAG-EDIT タグを編集
;;; @button ROOM-TAG-HELP 部屋タグ ヘルプ
```

`@command` はパレット非表示のコマンドも含めた一覧です。`@button` に書いた
コマンド名も一覧に取り込まれるので、`@button` だけの手書きでも動きます。

### 配布物の構成

```
MY-COMMAND/
├── MY-COMMAND.fas          ← .lsp は入れない
├── MY-COMMAND.meta         ← コマンド名・ボタンラベル
├── MY-COMMAND_README.md    ← ヘルプの本文（そのまま表示される）
└── LICENSE.txt
```

### 注意

- **同じ名前の `.lsp` と `.fas` を両方置かない**。管理ツールは二重ロードを防ぐため
  片方（`.vlx` → `.fas` → `.lsp` の順で優先）しか読み込みません
- `.fas` は `(load "MY-COMMAND.fas")` と拡張子付きでロードされます。`acaddoc.lsp`
  への記述は管理ツールが自動で行います
- README は `.fas` に含まれないので必ず同梱してください。`ag:show-readme` は
  ファイル名で探すだけなので、コンパイル版でもそのまま動きます

---

## チェックリスト

新しいLISPを作るとき:

- [ ] `;;; @description` を書いた
- [ ] 各コマンドに `;;; @button コマンド名 日本語名` を書いた
- [ ] `-HELP` コマンドを定義した（`ag:show-readme` を呼ぶ）
- [ ] `〇〇_README.md` を同じフォルダに作った
- [ ] 管理ツールで登録・動作確認した

外部に配布するとき:

- [ ] `.fas` / `.vlx` にコンパイルした
- [ ] `.meta` を用意した（`.lsp` を隣に置いて登録すれば自動生成される）
- [ ] 配布物に `.lsp` を混ぜていない
- [ ] `〇〇_README.md` を同梱した
