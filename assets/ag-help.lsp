;;; @file        ag-help.lsp
;;; @description 共通ヘルプユーティリティ（DCLダイアログでREADMEを表示）
;;; @version     1.0
;;; @author      studio kivi

;;; READMEファイルをDCLダイアログで表示する
;;; 引数: readme-filename - READMEファイル名（例: "DIGI_CLOCK_README.md"）
(defun ag:show-readme (readme-filename / fpath fp line lines dcl_id)
  (setq fpath (findfile readme-filename))
  (if (null fpath)
    (progn
      (alert (strcat "取扱説明書が見つかりません:\n" readme-filename))
      (princ)
    )
    (progn
      ;; ファイル読み込み
      (setq lines '())
      (setq fp (open fpath "r"))
      (while (setq line (read-line fp))
        (setq lines (append lines (list line)))
      )
      (close fp)
      ;; DCLダイアログ表示
      (setq dcl_id (load_dialog (findfile "ag-help.dcl")))
      (if (not (new_dialog "ag_help" dcl_id))
        (alert "ダイアログの読み込みに失敗しました")
        (progn
          (start_list "readme_content")
          (foreach ln lines (add_list ln))
          (end_list)
          (start_dialog)
        )
      )
      (unload_dialog dcl_id)
    )
  )
  (princ)
)
