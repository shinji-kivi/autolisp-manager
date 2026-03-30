;;; @file        ag-help.lsp
;;; @description 共通ヘルプユーティリティ（DCLダイアログでREADMEを表示）
;;; @version     1.1
;;; @author      studio kivi

;;; DCLファイルをランタイムで生成する（文字化け回避）
(defun ag:make-dcl (/ dcl-path fp)
  (setq dcl-path (strcat (getvar "TEMPPREFIX") "ag-help.dcl"))
  (setq fp (open dcl-path "w"))
  (write-line "ag_help : dialog {" fp)
  (write-line "  label = \"取扱説明書\";" fp)
  (write-line "  : list_box {" fp)
  (write-line "    key = \"readme_content\";" fp)
  (write-line "    width = 80;" fp)
  (write-line "    height = 30;" fp)
  (write-line "    multiple_select = false;" fp)
  (write-line "  }" fp)
  (write-line "  ok_only;" fp)
  (write-line "}" fp)
  (close fp)
  dcl-path
)

;;; READMEファイルをDCLダイアログで表示する
;;; 引数: readme-filename - READMEファイル名（例: "DIGI_CLOCK_README.md"）
(defun ag:show-readme (readme-filename / fpath fp line lines dcl_path dcl_id)
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
      ;; DCLを動的生成して表示
      (setq dcl_path (ag:make-dcl))
      (setq dcl_id (load_dialog dcl_path))
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
