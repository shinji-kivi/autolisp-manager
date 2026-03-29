"""
lisp_manager.py - AutoLISP ファイル管理のコアロジック

責務:
- LISPリポジトリへのファイルコピー・連番リネーム
- acaddoc.lsp の生成・更新（有効/無効のコメントアウト管理）
- LISP ファイルからのコマンド名抽出

AutoCAD COM API は acad_sync.py に委譲する。
"""
from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from models import LispEntry, OperationResult

logger = logging.getLogger(__name__)


class LispManager:
    """LISP ファイルの整理・登録・管理を行うクラス。

    AutoCAD COM には依存しない。すべての操作はファイルシステムのみで完結する。
    """

    START_MARKER: str = ";; <LispManager_Start>"
    END_MARKER: str = ";; <LispManager_End>"

    # クラス変数として1度だけコンパイル
    _COMMAND_PATTERN: re.Pattern = re.compile(
        r"\(\s*defun\s+c:([a-zA-Z_][a-zA-Z0-9_-]*)", re.IGNORECASE
    )
    _DISABLED_PATTERN: re.Pattern = re.compile(
        r"^;;\s*\(load\s+\"([^\"]+)\"\)", re.IGNORECASE
    )

    def __init__(self, repo_path: str) -> None:
        self._repo_dir = Path(repo_path)
        self._repo_dir.mkdir(parents=True, exist_ok=True)
        self._acaddoc_path = self._repo_dir / "acaddoc.lsp"
        self._launcher_lisp: str | None = None
        logger.debug("LispManager 初期化: repo=%s", self._repo_dir)

        # 起動時に acaddoc.lsp を最新状態に同期する
        # （存在しない場合は新規作成、既存の場合も TRUSTEDPATHS 行などを最新化）
        existed = self._acaddoc_path.exists()
        self._write_acaddoc(self._read_disabled())
        if not existed:
            logger.info("acaddoc.lsp を新規作成しました: %s", self._acaddoc_path)
        else:
            logger.debug("acaddoc.lsp を更新しました: %s", self._acaddoc_path)

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def get_repo_dir(self) -> Path:
        """リポジトリフォルダのパスを返す。"""
        return self._repo_dir

    def get_acaddoc_path(self) -> Path:
        """acaddoc.lsp のパスを返す。"""
        return self._acaddoc_path

    def register(self, src_path: str) -> OperationResult:
        """LISP ファイルをリポジトリにコピーし、acaddoc.lsp に登録する。

        同名ファイルが存在する場合は連番リネームする（例: file_2.lsp）。
        """
        src = Path(src_path)

        if not src.exists():
            return OperationResult.fail(f"ファイルが見つかりません: {src.name}")
        if src.suffix.lower() != ".lsp":
            return OperationResult.fail(f".lsp ファイルではありません: {src.name}")

        dest = self._resolve_dest(src)
        try:
            shutil.copy2(src, dest)
        except OSError as e:
            logger.error("ファイルのコピーに失敗しました: %s → %s: %s", src, dest, e)
            return OperationResult.fail(
                f"{src.name} のコピーに失敗しました。",
                detail=str(e),
            )

        result = self._write_acaddoc(self._read_disabled())
        if not result.success:
            return result

        logger.info("LISP を登録しました: %s → %s", src.name, dest.name)
        return OperationResult.ok(
            f"{dest.name} を登録しました。",
            detail=f"コピー先: {dest}",
        )

    def remove(self, path: str) -> OperationResult:
        """LISP ファイルを削除し、acaddoc.lsp を更新する。"""
        target = Path(path)
        try:
            target.unlink()
        except FileNotFoundError:
            return OperationResult.fail(f"ファイルが見つかりません: {target.name}")
        except OSError as e:
            logger.error("ファイルの削除に失敗しました: %s: %s", target, e)
            return OperationResult.fail(
                f"{target.name} の削除に失敗しました。",
                detail=str(e),
            )

        # 削除されたファイルの stem を無効リストからも除外してから再生成
        disabled = self._read_disabled()
        disabled.discard(target.stem)
        result = self._write_acaddoc(disabled)
        if not result.success:
            return result

        logger.info("LISP を削除しました: %s", target.name)
        return OperationResult.ok(f"{target.name} を削除しました。")

    def toggle(self, stem: str, enabled: bool) -> OperationResult:
        """指定した LISP の有効/無効を切り替える。"""
        disabled = self._read_disabled()
        if enabled:
            disabled.discard(stem)
        else:
            disabled.add(stem)

        result = self._write_acaddoc(disabled)
        if not result.success:
            return result

        state = "有効" if enabled else "無効"
        logger.info("LISP を%sにしました: %s", state, stem)
        return OperationResult.ok(f"{stem} を{state}にしました。")

    def update_launcher(self, python_exe: str, script_path: str | None = None) -> None:
        """AutoCAD コマンド `lisp_manager` で管理ツールを起動するランチャーを登録する。

        acaddoc.lsp に (defun c:lisp_manager ...) をインラインで埋め込む。
        script_path が None の場合は EXE モード（python_exe = EXE パス）として扱う。
        スペースを含むパスも正しく処理する。
        """
        py_lisp = python_exe.replace("\\", "\\\\")
        if script_path is not None:
            # スクリプトモード: startapp "python.exe" "\"main.py\""
            sc_lisp = script_path.replace("\\", "\\\\")
            params = '"' + '\\"' + sc_lisp + '\\"' + '"'
            self._launcher_lisp = (
                "(defun c:lisp_manager ()\n"
                f'  (startapp "{py_lisp}" {params})\n'
                "  (princ))"
            )
        else:
            # EXE モード: startapp "AutoLISP管理ツール.exe"（params 不要）
            self._launcher_lisp = (
                "(defun c:lisp_manager ()\n"
                f'  (startapp "{py_lisp}")\n'
                "  (princ))"
            )
        self._write_acaddoc(self._read_disabled())
        logger.info("lisp_manager ランチャーを acaddoc.lsp に登録しました")

    def get_commands(self, stem: str) -> list[str]:
        """指定 stem の LISP ファイルからコマンド名一覧を返す。"""
        lsp_file = self._repo_dir / f"{stem}.lsp"
        return self._extract_commands(lsp_file)

    def list_all(self) -> list[LispEntry]:
        """登録済み LISP の一覧を返す。"""
        disabled = self._read_disabled()
        entries: list[LispEntry] = []
        for lsp in self._list_lsp_files():
            entries.append(
                LispEntry(
                    name=lsp.name,
                    path=lsp,
                    commands=self._extract_commands(lsp),
                    enabled=lsp.stem not in disabled,
                )
            )
        return entries

    def cleanup(self) -> OperationResult:
        """リポジトリ内の LISP ファイルをすべて削除し、acaddoc.lsp の管理範囲も削除する。

        マーカー外にユーザーが書いたコードは保持する。
        バックアップファイル (.bak) およびツールが生成した Palettes フォルダも削除する。
        """
        # 1) LISP ファイルを全削除
        delete_errors: list[str] = []
        for lsp in self._list_lsp_files():
            try:
                lsp.unlink()
                logger.info("LISP ファイルを削除しました: %s", lsp.name)
            except OSError as e:
                logger.error("LISP ファイルの削除に失敗しました: %s: %s", lsp.name, e)
                delete_errors.append(lsp.name)

        if delete_errors:
            return OperationResult.fail(
                f"一部のファイルを削除できませんでした: {', '.join(delete_errors)}"
            )

        # 2) acaddoc.lsp の管理範囲を削除
        if self._acaddoc_path.exists():
            try:
                lines = self._acaddoc_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            except OSError as e:
                return OperationResult.fail("acaddoc.lsp の読み込みに失敗しました。", detail=str(e))

            start_idx = next(
                (i for i, ln in enumerate(lines) if self.START_MARKER in ln), None
            )
            end_idx = next(
                (i for i, ln in enumerate(lines) if self.END_MARKER in ln), None
            )

            if start_idx is None or end_idx is None:
                # マーカーがない場合はファイルを丸ごと削除
                try:
                    self._acaddoc_path.unlink()
                    logger.info("マーカーなし: acaddoc.lsp を削除しました。")
                except OSError as e:
                    return OperationResult.fail("acaddoc.lsp の削除に失敗しました。", detail=str(e))
            else:
                # マーカー行を含む管理範囲を除去
                new_lines = lines[:start_idx] + lines[end_idx + 1 :]
                remaining = "".join(new_lines).strip()
                try:
                    if remaining:
                        self._acaddoc_path.write_text("".join(new_lines), encoding="utf-8")
                        logger.info("acaddoc.lsp: マーカー範囲を削除しました（ユーザー記述を保持）。")
                    else:
                        # マーカー外に内容がなければファイルごと削除
                        self._acaddoc_path.unlink()
                        logger.info("acaddoc.lsp: 内容が空になったため削除しました。")
                except OSError as e:
                    return OperationResult.fail("acaddoc.lsp の更新に失敗しました。", detail=str(e))

        # 3) バックアップファイル (.bak) を削除
        bak = self._acaddoc_path.with_suffix(".lsp.bak")
        if bak.exists():
            try:
                bak.unlink()
                logger.info("バックアップファイルを削除しました: %s", bak.name)
            except OSError as e:
                logger.warning("バックアップファイルの削除に失敗しました: %s", e)

        # 4) ツールが生成した Palettes フォルダを削除
        palettes_dir = self._repo_dir / "Palettes"
        if palettes_dir.is_dir():
            try:
                shutil.rmtree(palettes_dir)
                logger.info("Palettes フォルダを削除しました。")
            except OSError as e:
                logger.warning("Palettes フォルダの削除に失敗しました: %s", e)

        logger.info("クリーンアップ完了。")
        return OperationResult.ok("設定を元に戻しました。\nLISPファイルとacaddoc.lspの設定をすべて削除しました。")

    # ------------------------------------------------------------------
    # プライベートメソッド
    # ------------------------------------------------------------------

    def _resolve_dest(self, src: Path) -> Path:
        """コピー先パスを決定する。同名ファイルが存在する場合は連番リネームする。"""
        dest = self._repo_dir / src.name
        if dest.exists():
            counter = 2
            while dest.exists():
                dest = self._repo_dir / f"{src.stem}_{counter}{src.suffix}"
                counter += 1
        return dest

    def _list_lsp_files(self) -> list[Path]:
        """リポジトリ内の .lsp ファイル（acaddoc.lsp を除く）を返す。"""
        return [
            p for p in self._repo_dir.glob("*.lsp") if p.name != "acaddoc.lsp"
        ]

    def _read_disabled(self) -> set[str]:
        """acaddoc.lsp 内でコメントアウトされている LISP の stem 集合を返す。"""
        disabled: set[str] = set()
        if not self._acaddoc_path.exists():
            return disabled
        try:
            for line in self._acaddoc_path.read_text(encoding="utf-8", errors="replace").splitlines():
                m = self._DISABLED_PATTERN.match(line.strip())
                if m:
                    disabled.add(m.group(1))
        except OSError as e:
            logger.warning("acaddoc.lsp の読み込みに失敗しました: %s", e)
        return disabled

    # acaddoc.lsp に埋め込む TRUSTEDPATHS 自己登録コード
    # 既にパスが含まれている場合は追加しない（重複防止）。
    # let* は AutoCAD の初期ロード段階で使えない場合があるため setq を使用する。
    # vl-filename-directory は末尾に "\" が付くため、検索前にストリップして比較する。
    _TRUSTED_SELF_REGISTER: str = (
        r'(progn'
        r' (setq _lm_p (vl-filename-directory (findfile "acaddoc.lsp")))'
        r' (setq _lm_tp (getvar "TRUSTEDPATHS"))'
        r' (setq _lm_ps (if (= (substr _lm_p (strlen _lm_p)) "\\") (substr _lm_p 1 (1- (strlen _lm_p))) _lm_p))'
        r' (if (not (vl-string-search (strcase _lm_ps T) (strcase _lm_tp T)))'
        r'  (setvar "TRUSTEDPATHS" (strcat _lm_p ";" _lm_tp)))'
        r' (setq _lm_p nil _lm_tp nil _lm_ps nil) (princ))'
    )

    def _write_acaddoc(self, disabled: set[str]) -> OperationResult:
        """acaddoc.lsp を生成・上書きする（唯一の書き込み口）。

        disabled に含まれる stem の行はコメントアウトする。
        既存ファイルはバックアップしてから上書きする。
        先頭に TRUSTEDPATHS 自己登録コードを埋め込む（セキュリティダイアログ回避）。
        """
        lines: list[str] = [self.START_MARKER, self._TRUSTED_SELF_REGISTER]
        for lsp in self._list_lsp_files():
            load_line = f'(load "{lsp.stem}" nil)'
            if lsp.stem in disabled:
                load_line = f';; (load "{lsp.stem}")'
            lines.append(load_line)
        if self._launcher_lisp:
            lines.append(self._launcher_lisp)
        lines.append(self.END_MARKER)
        content = "\n".join(lines) + "\n"

        # バックアップ（1世代のみ保持）
        if self._acaddoc_path.exists():
            try:
                shutil.copy2(self._acaddoc_path, self._acaddoc_path.with_suffix(".lsp.bak"))
            except OSError as e:
                logger.warning("バックアップの作成に失敗しました: %s", e)

        try:
            self._acaddoc_path.write_text(content, encoding="utf-8")
        except OSError as e:
            logger.error("acaddoc.lsp の書き込みに失敗しました: %s", e)
            return OperationResult.fail("acaddoc.lsp の書き込みに失敗しました。", detail=str(e))

        return OperationResult.ok("acaddoc.lsp を更新しました。")

    def _extract_commands(self, file_path: Path) -> list[str]:
        """LISP ファイルから `(defun c:コマンド名` パターンを抽出する。"""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("コマンド抽出のためのファイル読み込みに失敗しました (%s): %s", file_path.name, e)
            return []
        matches = self._COMMAND_PATTERN.findall(content)
        return sorted(set(matches))
