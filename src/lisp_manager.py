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
    _BUTTON_PATTERN: re.Pattern = re.compile(
        r"^;;;\s*@button\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s+(.+)$", re.MULTILINE
    )
    _DESCRIPTION_PATTERN: re.Pattern = re.compile(
        r"^;;;\s*@description\s+(.+)$", re.MULTILINE
    )
    # サイドカー (.meta) 専用。コンパイル版はコマンド名を復元できないため、
    # 生成時に (defun c:...) から拾った全コマンドをこの形式で書き出しておく。
    _META_COMMAND_PATTERN: re.Pattern = re.compile(
        r"^;;;\s*@command\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s*$", re.MULTILINE
    )

    # ag-help 共通ヘルプシステムのファイル名
    _BUILTIN_FILES: list[str] = ["ag-help.lsp", "ag-help.dcl"]

    # 登録できる LISP ファイルの拡張子。
    # 同一 stem で複数の形式が存在する場合は、この順（先頭優先）で 1 つだけ採用する。
    # コンパイル版を優先するのは、配布物として .fas / .vlx を置いたときに
    # 古い .lsp が残っていても意図せずソース版がロードされないようにするため。
    LISP_EXTENSIONS: tuple[str, ...] = (".vlx", ".fas", ".lsp")

    # ソースとしてテキスト解析できる拡張子（コマンド名・メタデータ抽出の対象）
    _SOURCE_EXTENSIONS: frozenset[str] = frozenset({".lsp"})

    # コンパイル版に添えるメタデータのサイドカー拡張子。
    # .fas / .vlx は文字列テーブルが難読化されていてコマンド名を復元できないため、
    # @description / @button / @command をテキストで別ファイルに持たせる。
    META_SUFFIX: str = ".meta"

    def __init__(self, repo_path: str) -> None:
        self._repo_dir = Path(repo_path)
        self._repo_dir.mkdir(parents=True, exist_ok=True)
        self._acaddoc_path = self._repo_dir / "acaddoc.lsp"
        self._launcher_lisp: str | None = None
        logger.debug("LispManager 初期化: repo=%s", self._repo_dir)

        # 共通ヘルプシステム（ag-help.lsp / ag-help.dcl）をリポジトリに配置
        self._deploy_builtin_files()

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

        ソース版 (.lsp) とコンパイル版 (.fas / .vlx) のどちらも登録できる。
        同名ファイルが存在する場合は連番リネームする（例: file_2.lsp）。
        """
        src = Path(src_path)

        if not src.exists():
            return OperationResult.fail(f"ファイルが見つかりません: {src.name}")
        if src.suffix.lower() not in self.LISP_EXTENSIONS:
            exts = " / ".join(self.LISP_EXTENSIONS)
            return OperationResult.fail(f"{exts} ファイルではありません: {src.name}")

        # 同一 stem の別形式が既に登録済みかを、コピー前に調べておく
        shadowed = self._find_same_stem(src.stem, exclude_suffix=src.suffix.lower())

        dest = self._resolve_dest(src)
        try:
            shutil.copy2(src, dest)
        except OSError as e:
            logger.error("ファイルのコピーに失敗しました: %s → %s: %s", src, dest, e)
            return OperationResult.fail(
                f"{src.name} のコピーに失敗しました。",
                detail=str(e),
            )

        # README ファイルがあれば一緒にコピー（{stem}_README.md として保存）
        self._copy_readme(src, dest.stem)

        # コンパイル版はメタデータのサイドカー（{stem}.meta）を用意する
        meta_note = ""
        if src.suffix.lower() not in self._SOURCE_EXTENSIONS:
            meta_note = self._prepare_meta(src, dest.stem)

        result = self._write_acaddoc(self._read_disabled())
        if not result.success:
            return result

        logger.info("LISP を登録しました: %s → %s", src.name, dest.name)

        # 同一 stem の別形式が残っている場合は、どちらがロードされるかを明示する
        detail = f"コピー先: {dest}"
        if meta_note:
            detail += f"\n{meta_note}"
        if shadowed:
            winner = self._pick_preferred([*shadowed, dest])
            others = ", ".join(sorted(p.name for p in [*shadowed, dest] if p != winner))
            detail += (
                f"\n同名の別形式があるため {winner.name} のみをロードします"
                f"（{others} は無視されます）。"
            )

        return OperationResult.ok(f"{dest.name} を登録しました。", detail=detail)

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

        # サイドカー（メタデータ）も道連れにする
        meta = self._meta_path(target.stem)
        if meta.exists():
            try:
                meta.unlink()
                logger.info("メタデータを削除しました: %s", meta.name)
            except OSError as e:
                logger.warning("メタデータの削除に失敗しました: %s", e)

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
        lsp_file = self._find_by_stem(stem)
        if lsp_file is None:
            return []
        return self._extract_commands(lsp_file)

    def get_load_target(self, stem: str) -> str:
        """指定 stem を (load "...") に渡すときの文字列を返す。

        コンパイル版 (.fas / .vlx) は拡張子付きで返す。
        実体が見つからない場合は stem をそのまま返す（従来動作）。
        """
        path = self._find_by_stem(stem)
        return self._load_target(path) if path is not None else stem

    def list_all(self) -> list[LispEntry]:
        """登録済み LISP の一覧を返す。"""
        disabled = self._read_disabled()
        entries: list[LispEntry] = []
        for lsp in self._list_lsp_files():
            meta = self._extract_metadata(lsp)
            entries.append(
                LispEntry(
                    name=lsp.name,
                    path=lsp,
                    commands=self._extract_commands(lsp),
                    enabled=lsp.stem not in disabled,
                    description=meta["description"],
                    button_labels=meta["button_labels"],
                    readme_file=meta["readme_file"],
                )
            )
        return entries

    def cleanup(self) -> OperationResult:
        """リポジトリ内の LISP ファイルをすべて削除し、acaddoc.lsp の管理範囲も削除する。

        マーカー外にユーザーが書いたコードは保持する。
        バックアップファイル (.bak) およびツールが生成した Palettes フォルダも削除する。
        """
        # 1) LISP ファイルとメタデータを全削除
        #    （同一 stem の重複も残さないよう、絞り込み前の一覧を使う）
        delete_errors: list[str] = []
        targets = [*self._glob_lisp_files(), *self._repo_dir.glob(f"*{self.META_SUFFIX}")]
        for lsp in targets:
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

    def _to_stem(self, load_target: str) -> str:
        """(load "...") に書かれた文字列を stem に正規化する。

        .fas / .vlx は拡張子付きで書かれるため取り除く。
        LISP の拡張子以外は落とさない（stem にドットを含む名前を壊さないため）。
        """
        p = Path(load_target)
        if p.suffix.lower() in self.LISP_EXTENSIONS:
            return p.stem
        return load_target

    def _load_target(self, path: Path) -> str:
        """(load "...") に渡す文字列を返す。

        .lsp は従来どおり拡張子なし（後方互換）。
        .fas / .vlx は拡張子を明示する。拡張子なしだと AutoCAD 側の探索順に
        委ねることになり、同名のソース版が残っていたときにどちらが読まれるか
        分からなくなるため。
        """
        if path.suffix.lower() == ".lsp":
            return path.stem
        return path.name

    def _pick_preferred(self, candidates: list[Path]) -> Path:
        """同一 stem の候補から LISP_EXTENSIONS の優先順で 1 つ選ぶ。"""
        return min(
            candidates,
            key=lambda p: self.LISP_EXTENSIONS.index(p.suffix.lower()),
        )

    def _find_same_stem(
        self, stem: str, exclude_suffix: str | None = None
    ) -> list[Path]:
        """リポジトリ内で同じ stem を持つ LISP ファイルを返す。"""
        found: list[Path] = []
        for ext in self.LISP_EXTENSIONS:
            if exclude_suffix is not None and ext == exclude_suffix:
                continue
            p = self._repo_dir / f"{stem}{ext}"
            if p.exists():
                found.append(p)
        return found

    def _find_by_stem(self, stem: str) -> Path | None:
        """stem から実体のファイルを 1 つ返す（優先順は LISP_EXTENSIONS）。"""
        found = self._find_same_stem(stem)
        return self._pick_preferred(found) if found else None

    def _glob_lisp_files(self) -> list[Path]:
        """リポジトリ内の LISP ファイルを重複排除せずすべて返す。

        acaddoc.lsp と ag-help.* は管理対象外なので除外する。
        一括削除のように「実体をすべて」扱いたい場面で使う。
        """
        exclude_stems = {"acaddoc", "ag-help"}
        found: list[Path] = []
        for ext in self.LISP_EXTENSIONS:
            for p in self._repo_dir.glob(f"*{ext}"):
                if p.stem.lower() in exclude_stems:
                    continue
                found.append(p)
        return found

    def _list_lsp_files(self) -> list[Path]:
        """リポジトリ内の LISP ファイル（.lsp / .fas / .vlx）を返す。

        acaddoc.lsp と ag-help.* は管理対象外なので除外する。
        同一 stem で複数形式が存在する場合は LISP_EXTENSIONS の優先順で 1 つに絞る
        （両方をロード行に出すと二重ロードになるため）。
        """
        by_stem: dict[str, list[Path]] = {}
        for p in self._glob_lisp_files():
            by_stem.setdefault(p.stem, []).append(p)

        result: list[Path] = []
        for stem, candidates in by_stem.items():
            winner = self._pick_preferred(candidates)
            if len(candidates) > 1:
                ignored = ", ".join(
                    sorted(p.name for p in candidates if p != winner)
                )
                logger.warning(
                    "同一 stem に複数形式があります。%s のみロードします（無視: %s）",
                    winner.name, ignored,
                )
            result.append(winner)
        return sorted(result, key=lambda p: p.name.lower())

    def _read_disabled(self) -> set[str]:
        """acaddoc.lsp 内でコメントアウトされている LISP の stem 集合を返す。"""
        disabled: set[str] = set()
        if not self._acaddoc_path.exists():
            return disabled
        try:
            for line in self._acaddoc_path.read_text(encoding="utf-8", errors="replace").splitlines():
                m = self._DISABLED_PATTERN.match(line.strip())
                if m:
                    disabled.add(self._to_stem(m.group(1)))
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

    # ランチャー定義の開始行（update_launcher が生成する形）
    _LAUNCHER_HEAD: str = "(defun c:lisp_manager"

    def _read_existing_launcher(self) -> str | None:
        """既存の acaddoc.lsp からランチャー定義のブロックを取り出す。

        update_launcher() を呼ばないまま _write_acaddoc() すると
        ランチャーが消えてしまうため、その取りこぼしを防ぐ。
        """
        if not self._acaddoc_path.exists():
            return None
        try:
            lines = self._acaddoc_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError:
            return None

        block: list[str] = []
        for line in lines:
            if not block and line.startswith(self._LAUNCHER_HEAD):
                block.append(line)
                continue
            if block:
                block.append(line)
                if line.strip() == "(princ))":
                    return "\n".join(block)
        return None

    def _write_acaddoc(self, disabled: set[str]) -> OperationResult:
        """acaddoc.lsp を生成・上書きする（唯一の書き込み口）。

        disabled に含まれる stem の行はコメントアウトする。
        既存ファイルはバックアップしてから上書きする。
        先頭に TRUSTEDPATHS 自己登録コードを埋め込む（セキュリティダイアログ回避）。
        """
        lines: list[str] = [self.START_MARKER, self._TRUSTED_SELF_REGISTER]
        # 共通ヘルプシステムを最初にロード
        ag_help = self._repo_dir / "ag-help.lsp"
        if ag_help.exists():
            lines.append('(load "ag-help" nil)')
        for lsp in self._list_lsp_files():
            if lsp.stem == "ag-help":
                continue  # 上で既にロード済み
            target = self._load_target(lsp)
            load_line = f'(load "{target}" nil)'
            if lsp.stem in disabled:
                load_line = f';; (load "{target}")'
            lines.append(load_line)
        # update_launcher() を通っていない場合でも、既存の acaddoc.lsp に
        # 書かれているランチャー定義は引き継ぐ（黙って消さない）。
        launcher = self._launcher_lisp or self._read_existing_launcher()
        if launcher:
            lines.append(launcher)
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
        """LISP ファイルから `(defun c:コマンド名` パターンを抽出する。

        コンパイル版 (.fas / .vlx) はバイトコードなのでこのパターンが残らない。
        その場合はサイドカー ({stem}.meta) の @command 行から復元する。
        サイドカーも無ければ空リストを返す（ロード・実行には影響しない）。
        """
        if file_path.suffix.lower() not in self._SOURCE_EXTENSIONS:
            return self._read_meta_commands(file_path.stem)
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("コマンド抽出のためのファイル読み込みに失敗しました (%s): %s", file_path.name, e)
            return []
        matches = self._COMMAND_PATTERN.findall(content)
        return sorted(set(matches))

    def _extract_metadata(self, file_path: Path) -> dict:
        """LISP ファイルから @button, @description メタデータを抽出する。

        @button / @description はコメント行なので、コンパイル版 (.fas / .vlx) には
        残らない。その場合はサイドカー ({stem}.meta) から読む。
        README（{stem}_README.md）は別ファイルなのでコンパイル版でもそのまま使える。
        """
        if file_path.suffix.lower() not in self._SOURCE_EXTENSIONS:
            source: Path | None = self._meta_path(file_path.stem)
            if not source.exists():
                source = None
        else:
            source = file_path

        if source is None:
            return {
                "description": "",
                "button_labels": {},
                "readme_file": f"{file_path.stem}_README.md",
            }

        try:
            content = source.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return {"description": "", "button_labels": {}, "readme_file": ""}

        desc_match = self._DESCRIPTION_PATTERN.search(content)
        description = desc_match.group(1).strip() if desc_match else ""

        button_labels: dict[str, str] = {}
        for m in self._BUTTON_PATTERN.finditer(content):
            button_labels[m.group(1)] = m.group(2).strip()

        return {
            "description": description,
            "button_labels": button_labels,
            "readme_file": f"{file_path.stem}_README.md",
        }

    def _copy_readme(self, src_lsp: Path, dest_stem: str) -> None:
        """LISP ファイルと同じフォルダにある README を {stem}_README.md としてコピーする。"""
        for name in ("README.md", "README.txt"):
            readme_src = src_lsp.parent / name
            if readme_src.exists():
                ext = Path(name).suffix
                readme_dest = self._repo_dir / f"{dest_stem}_README{ext}"
                try:
                    shutil.copy2(readme_src, readme_dest)
                    logger.info("README をコピーしました: %s → %s", readme_src.name, readme_dest.name)
                except OSError as e:
                    logger.warning("README のコピーに失敗しました: %s", e)
                return

    # ------------------------------------------------------------------
    # メタデータのサイドカー（.meta）
    # ------------------------------------------------------------------

    def _meta_path(self, stem: str) -> Path:
        """リポジトリ内のサイドカーのパスを返す。"""
        return self._repo_dir / f"{stem}{self.META_SUFFIX}"

    def _read_meta_commands(self, stem: str) -> list[str]:
        """サイドカーの @command 行からコマンド名一覧を返す。

        @command が無い手書きのサイドカーでも拾えるよう、
        @button 行に書かれたコマンド名もあわせて採用する。
        """
        meta = self._meta_path(stem)
        if not meta.exists():
            return []
        try:
            content = meta.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("メタデータの読み込みに失敗しました (%s): %s", meta.name, e)
            return []

        commands = set(self._META_COMMAND_PATTERN.findall(content))
        commands.update(m.group(1) for m in self._BUTTON_PATTERN.finditer(content))
        return sorted(commands)

    def build_meta_text(self, lsp_path: Path) -> str:
        """ソース .lsp からサイドカー (.meta) の中身を組み立てて返す。

        コンパイルすると @description / @button のコメントも
        (defun c:...) のコマンド名も失われるため、テキストで書き出しておく。
        """
        commands = self._extract_commands(lsp_path)
        meta = self._extract_metadata(lsp_path)

        lines = [
            f";;; {lsp_path.stem}{self.META_SUFFIX}"
            " - AutoLISP管理ツール用メタデータ",
            ";;; コンパイル版 (.fas / .vlx) と一緒に配布してください。",
            f";;; 生成元: {lsp_path.name}",
            ";;;",
        ]
        if meta["description"]:
            lines.append(f";;; @description {meta['description']}")
        lines.extend(f";;; @command {c}" for c in commands)
        lines.extend(
            f";;; @button {cmd} {label}"
            for cmd, label in sorted(meta["button_labels"].items())
        )
        return "\n".join(lines) + "\n"

    def _prepare_meta(self, src: Path, dest_stem: str) -> str:
        """コンパイル版のサイドカーを用意する。処理内容を表す一文を返す。

        1. 配布物に {stem}.meta が同梱されていればそれをコピーする
        2. なければ隣の {stem}.lsp（開発者の手元）から生成する
        3. どちらも無ければ何もしない（コマンド表示なしで動作はする）
        """
        dest_meta = self._meta_path(dest_stem)

        src_meta = src.with_suffix(self.META_SUFFIX)
        if src_meta.exists():
            try:
                shutil.copy2(src_meta, dest_meta)
                logger.info("メタデータをコピーしました: %s", dest_meta.name)
                return f"{src_meta.name} を取り込みました。"
            except OSError as e:
                logger.warning("メタデータのコピーに失敗しました: %s", e)
                return f"{src_meta.name} の取り込みに失敗しました: {e}"

        src_lsp = src.with_suffix(".lsp")
        if src_lsp.exists():
            try:
                dest_meta.write_text(
                    self.build_meta_text(src_lsp), encoding="utf-8"
                )
                logger.info(
                    "メタデータを生成しました: %s ← %s", dest_meta.name, src_lsp.name
                )
                return (
                    f"{src_lsp.name} から {dest_meta.name} を生成しました"
                    "（配布時はこれも一緒に渡してください）。"
                )
            except OSError as e:
                logger.warning("メタデータの生成に失敗しました: %s", e)
                return f"{dest_meta.name} の生成に失敗しました: {e}"

        logger.info(
            "メタデータがないためコマンド名を表示できません: %s", src.name
        )
        return (
            f"{src.stem}{self.META_SUFFIX} が無いため、"
            "コマンド一覧とツールパレットのボタンは作られません。"
        )

    def _deploy_builtin_files(self) -> None:
        """共通ヘルプシステム（ag-help.lsp, ag-help.dcl）をリポジトリに配置する。"""
        import sys
        if getattr(sys, "frozen", False):
            # PyInstaller EXE モード
            base = Path(sys._MEIPASS) / "assets"
        else:
            # スクリプトモード
            base = Path(__file__).parent.parent / "assets"

        for filename in self._BUILTIN_FILES:
            src = base / filename
            dest = self._repo_dir / filename
            if src.exists():
                try:
                    shutil.copy2(src, dest)
                    logger.debug("ビルトインファイルを配置: %s", filename)
                except OSError as e:
                    logger.warning("ビルトインファイルの配置に失敗: %s: %s", filename, e)
