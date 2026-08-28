;;; @file        AGFASTEST.lsp
;;; @description コンパイル版(.fas)動作確認用のテストコマンド
;;; @version     1.0
;;; @author      studio kivi
;;; @button AGFASTEST FASテスト
;;; @button AGFASTEST-HELP FASテスト ヘルプ
;;;
;;; (c) 2026 studio kivi. All rights reserved.

;==============================================================================
; ファイル名: AGFASTEST.lsp
; 機能: .fas コンパイル版がオートロード・コマンド実行・ヘルプ表示まで通るかを
;       確認するためだけのテスト用 LISP。図面には一切変更を加えない。
; 作成日: 2026/08/28
;==============================================================================

;;; ロード時に一度だけメッセージを出す（オートロードされたかの確認用）
(princ "\nAGFASTEST: ロードされました。AGFASTEST / AGFASTEST-HELP が使えます。")

;;;----------------------------------------------------------------------------
;;; AGFASTEST コマンド
;;; 図面を変更せず、動作確認用の情報だけを表示する
;;;----------------------------------------------------------------------------
(defun c:AGFASTEST (/ *error* dwgname src)

  (defun *error* (msg)
    (if (and msg (not (wcmatch (strcase msg) "*BREAK*,*CANCEL*,*EXIT*")))
      (princ (strcat "\nエラー: " msg))
    )
    (princ)
  )

  (setq dwgname (getvar "DWGNAME"))
  ;; findfile は拡張子なしだと効かないので、.fas / .lsp のどちらが存在するか個別に見る
  (setq src
    (cond
      ((findfile "AGFASTEST.fas") "コンパイル版 (.fas) がサポートパス上にあります")
      ((findfile "AGFASTEST.lsp") "ソース版 (.lsp) がサポートパス上にあります")
      (T "AGFASTEST の実体をサポートパス上に見つけられませんでした")
    )
  )

  (alert
    (strcat
      "AGFASTEST 動作確認\n\n"
      "コマンドは正常に実行されました。\n\n"
      "現在の図面: " dwgname "\n"
      src "\n\n"
      "続けて AGFASTEST-HELP を実行し、\n"
      "取扱説明書が表示されるか確認してください。"
    )
  )
  (princ)
)

;;;----------------------------------------------------------------------------
;;; AGFASTEST-HELP コマンド
;;; ag-help の共通ヘルプ（DCLダイアログ）で README を表示する
;;;----------------------------------------------------------------------------
(defun c:AGFASTEST-HELP ()
  (if (null ag:show-readme)
    (alert "ag-help.lsp が読み込まれていません。")
    (ag:show-readme "AGFASTEST_README.md")
  )
  (princ)
)

(princ)
