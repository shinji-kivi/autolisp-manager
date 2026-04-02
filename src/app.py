"""
app.py - メインウィンドウ（UI 専用）

設計方針:
- LispManager / AcadSync / PaletteSync の公開 API のみを呼び出す
- OperationResult を受け取り、成否に応じて messagebox を出す
- プライベートメソッド・属性に直接アクセスしない
- ウィンドウサイズの変化を config に保存する
"""
from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from acad_sync import AcadSync
from config import AppConfig
from lisp_manager import LispManager
from models import OperationResult
from palette_sync import PaletteSync

logger = logging.getLogger(__name__)

# tkinterdnd2 の DnDWrapper を継承することで drop_target_register / dnd_bind が使えるようになる
# ctk.CTk は tkinter.Tk → tkinter.Misc を継承するが BaseWidget を継承しないため、
# DnDWrapper を直接ミックスインする
try:
    from tkinterdnd2.TkinterDnD import DnDWrapper as _DnDWrapper  # type: ignore[import-untyped]
    _HAS_TKDND = True
except ImportError:
    class _DnDWrapper:  # type: ignore[no-redef]
        pass
    _HAS_TKDND = False


class App(ctk.CTk, _DnDWrapper):
    """AutoLISP 管理ツール メインウィンドウ。"""

    _ACAD_POLL_MS = 10_000       # AutoCAD 起動検知のポーリング間隔（ミリ秒）
    _ACAD_EXIT_REWRITE_MS = 2_000   # AutoCAD 終了後にレジストリを再書き込みするまでの待機（ミリ秒）
    _ACAD_LAUNCH_WAIT_MS = 15_000   # AutoCAD 起動コマンド後、COM 接続を試みるまでの待機（ミリ秒）
    _ACAD_LOAD_RETRY_MS = 5_000     # 図面未オープン時の acaddoc.lsp ロードリトライ間隔（ミリ秒）
    _ACAD_LOAD_RETRY_MAX = 24       # リトライ上限（5秒×24回 = 2分間）

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._manager = LispManager(config.repo_path)
        self._register_launcher()
        self._acad = AcadSync()
        self._palette = PaletteSync()
        self._acad_was_available: bool = False  # ポーリング用: 前回の AutoCAD 状態

        self.title("AutoLISP 管理ツール")
        self.geometry(config.window_geometry)
        self.minsize(480, 350)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ウィンドウアイコン設定
        self._set_icon()

        self._build_ui()
        self._refresh_list()

        # DnD はウィンドウ表示後に初期化（winfo_id 確定後）
        self.after(100, self._setup_dnd)
        # 前回パス変更時に残留したレジストリエントリを起動時にクリーンアップ
        self.after(150, self._cleanup_prev_repo_path)
        # 起動時にレジストリへ TRUSTEDPATHS を書き込む（AutoCAD 未起動時も永続化）
        self.after(200, self._ensure_trusted_path_registry)
        # AutoCAD 起動を監視してパスを自動登録（起動前でも後でも対応）
        self.after(500, self._poll_autocad)
        # AutoCAD が未起動なら起動を促す（1.5 秒後にウィンドウが安定してから）
        self.after(1500, self._prompt_launch_autocad)

    # ------------------------------------------------------------------
    # アイコン設定
    # ------------------------------------------------------------------

    def _set_icon(self) -> None:
        """ウィンドウアイコンを設定する。"""
        try:
            # PyInstaller onefile: sys._MEIPASS に展開される
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
            ico = base / "assets" / "logo.ico"
            if ico.exists():
                self.iconbitmap(str(ico))
                return
            # PNG フォールバック
            png = base / "assets" / "logo.png"
            if png.exists():
                from PIL import Image, ImageTk
                img = Image.open(png)
                photo = ImageTk.PhotoImage(img)
                self.iconphoto(True, photo)
                self._icon_ref = photo  # GC 防止
        except Exception:
            logger.debug("アイコン設定をスキップしました", exc_info=True)

    # ------------------------------------------------------------------
    # DnD 初期化（tkinterdnd2）
    # ------------------------------------------------------------------

    def _setup_dnd(self) -> None:
        """tkinterdnd2 で drag & drop を初期化する。"""
        self._dnd_backend: str | None = None

        if not _HAS_TKDND:
            logger.warning(
                "DnD は利用できません（tkinterdnd2 が見つかりません）。"
                "「＋ LISPを追加」ボタンをご利用ください。"
            )
            return

        try:
            import tkinterdnd2  # type: ignore[import-untyped]
            from tkinterdnd2.TkinterDnD import _require  # type: ignore[import-untyped]

            # プラットフォーム別DLLパスを自動解決して tkdnd パッケージをロード
            _require(self)
            # App が DnDWrapper を継承しているため drop_target_register / dnd_bind が使える
            self.drop_target_register(tkinterdnd2.DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop_tkdnd)
            self._dnd_backend = "tkinterdnd2"
            logger.info("DnD 初期化成功 (tkinterdnd2)")
        except Exception as e:
            logger.warning("tkinterdnd2 初期化失敗: %s", e)
            logger.warning(
                "DnD は利用できません。「＋ LISPを追加」ボタンをご利用ください。"
            )

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # ステータスバー行

        # ---- サイドバー ----
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="LISP Manager",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(30, 20))

        ctk.CTkButton(
            sidebar, text="＋ LISPを追加", command=self._on_add_lisp, height=35
        ).pack(pady=8, padx=20, fill="x")

        ctk.CTkButton(
            sidebar,
            text="LISP保存先を開く",
            fg_color="transparent",
            border_width=1,
            command=self._on_open_folder,
            height=35,
        ).pack(pady=8, padx=20, fill="x")

        ctk.CTkButton(
            sidebar,
            text="AutoCAD を起動",
            fg_color="transparent",
            border_width=1,
            command=self._on_launch_autocad,
            height=35,
        ).pack(pady=8, padx=20, fill="x")

        ctk.CTkButton(
            sidebar,
            text="\u2699 設定",
            fg_color="transparent",
            border_width=1,
            command=self._on_open_settings,
            height=35,
        ).pack(pady=8, padx=20, fill="x")

        ctk.CTkButton(
            sidebar,
            text="アンインストール",
            fg_color="#d35b5b",
            hover_color="#8e3e3e",
            command=self._on_uninstall,
            height=35,
        ).pack(side="bottom", pady=20, padx=20, fill="x")

        # ---- メインコンテンツ（縦横スクロール対応） ----
        self._build_scrollable_content()

        # ---- ステータスバー ----
        self._status_bar = ctk.CTkLabel(
            self,
            text="起動中...",
            text_color="gray60",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self._status_bar.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 4), sticky="ew")

    def _build_scrollable_content(self) -> None:
        """縦スクロール対応のコンテンツエリアを構築する。
        横スクロールはコマンド列のみ（トグル・名前・×は常に表示）。
        """
        wrapper = ctk.CTkFrame(self)
        wrapper.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        wrapper.grid_rowconfigure(1, weight=1)
        wrapper.grid_columnconfigure(0, weight=1)

        # タイトルラベル
        self._content_label = ctk.CTkLabel(
            wrapper,
            text="登録済み LISP 一覧",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._content_label.grid(
            row=0, column=0, columnspan=2, pady=(8, 4)
        )

        # Canvas + 縦スクロールバー（横スクロールは各行のコマンドキャンバスで制御）
        bg = self._resolve_bg(wrapper)
        self._canvas = tk.Canvas(wrapper, highlightthickness=0, bg=bg)
        self._vsb = ctk.CTkScrollbar(wrapper, command=self._canvas.yview)
        # 横スクロールバー：コマンド列キャンバス群を一括スクロール
        self._hsb = ctk.CTkScrollbar(
            wrapper, orientation="horizontal", command=self._scroll_cmd_canvases
        )
        self._canvas.configure(yscrollcommand=self._vsb.set)
        # ※ xscrollcommand は設定しない（メイン Canvas は横スクロールしない）

        self._canvas.grid(row=1, column=0, sticky="nsew")
        self._vsb.grid(row=1, column=1, sticky="ns")
        self._hsb.grid(row=2, column=0, sticky="ew")

        # 内部フレーム（リスト行を配置する先）
        self._content = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._canvas_win = self._canvas.create_window(
            (0, 0), window=self._content, anchor="nw"
        )

        self._content.bind("<Configure>", self._update_scrollregion)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # マウスホイール（Canvas 領域上でのみ有効）
        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._unbind_mousewheel)

        # コマンド列キャンバス一覧（横スクロール同期用）
        self._cmd_canvases: list[tk.Canvas] = []
        # ファイル名ラベル一覧（列幅統一用）
        self._name_labels: list[tuple[ctk.CTkFrame, ctk.CTkLabel]] = []
        # コマンド列共有フォント
        self._cmd_font = ctk.CTkFont(size=12)

    def _set_status(self, message: str) -> None:
        """ステータスバーのテキストを更新する。"""
        try:
            self._status_bar.configure(text=message)
        except Exception:
            pass  # ウィンドウ破棄後など

    @staticmethod
    def _resolve_bg(widget: ctk.CTkBaseClass) -> str:
        """CTk ウィジェットの現在の外観モードに合った背景色を返す。"""
        try:
            fg = widget.cget("fg_color")
            return widget._apply_appearance_mode(fg)
        except Exception:
            return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#f0f0f0"

    def _update_scrollregion(self, event=None) -> None:
        """縦スクロール領域を更新する。コンテンツが canvas に収まる場合はスクロール無効。"""
        content_h = self._content.winfo_reqheight()
        canvas_h = self._canvas.winfo_height()
        canvas_w = self._canvas.winfo_width()
        scroll_h = max(content_h, canvas_h)
        self._canvas.configure(scrollregion=(0, 0, canvas_w, scroll_h))
        if content_h <= canvas_h:
            self._canvas.yview_moveto(0)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Canvas リサイズ時に内部フレームの幅を調整する。"""
        self._canvas.itemconfigure(self._canvas_win, width=event.width)
        self._update_scrollregion()
        # ウィンドウ幅が変わるとコマンド列の表示幅も変わるので再同期
        self.after(30, self._sync_cmd_scrollregions)

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self._canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self._content.winfo_reqheight() > self._canvas.winfo_height():
            self._canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # ------------------------------------------------------------------
    # イベントハンドラ（公開 API のみを呼び出す）
    # ------------------------------------------------------------------

    def _on_add_lisp(self) -> None:
        files = filedialog.askopenfilenames(
            title="追加する LISP ファイルを選択",
            filetypes=[
                ("AutoLISP ファイル", "*.lsp"),
                ("すべてのファイル", "*.*"),
            ],
        )
        if files:
            self._register_files(list(files))

    def _on_drop_tkdnd(self, event) -> None:
        """tkinterdnd2 コールバック（DnDEvent.data にファイルパスが入る）。"""
        try:
            files = self.tk.splitlist(event.data)
            logger.debug("D&D 受信: %s", files)
            lsp_files = [f for f in files if f.lower().endswith(".lsp")]
            if not lsp_files:
                messagebox.showwarning("警告", ".lsp ファイルのみ登録できます。")
                return
            self._register_files(lsp_files)
        except Exception:
            logger.error("D&D コールバックでエラー", exc_info=True)
            messagebox.showerror(
                "エラー",
                "ドラッグ＆ドロップの処理中にエラーが発生しました。\n"
                "「＋ LISPを追加」ボタンをお試しください。",
            )

    def _on_delete_lisp(self, path: str) -> None:
        if not messagebox.askyesno(
            "確認",
            "このLISPをリポジトリから削除しますか？\n"
            "（ファイルはリポジトリフォルダから削除され、次回から読み込まれません）",
        ):
            return
        self._handle_result(self._manager.remove(path))
        self._refresh_list()

    def _on_toggle_lisp(self, stem: str, enabled: bool) -> None:
        result = self._manager.toggle(stem, enabled)
        if not result.success:
            messagebox.showerror("エラー", result.message)
            return
        if enabled:
            # 有効化: AutoCAD が起動中なら即時ロード
            self._acad.load_lisp(stem)
        else:
            # 無効化: AutoCAD が起動中なら定義済みコマンドを即時削除
            commands = self._manager.get_commands(stem)
            self._acad.unload_lisp(commands)

    def _poll_autocad(self) -> None:
        """AutoCAD の起動・終了を定期監視し、パスを自動登録/再設定する。

        - 起動を検知: SupportPath / TRUSTEDPATHS を COM で即時登録
        - 終了を検知: AutoCAD が TRUSTEDPATHS を空で上書きする前に対処するため
          2 秒後にレジストリへ再書き込みを行う
        """
        now_available = self._acad.is_available()
        if now_available and not self._acad_was_available:
            # AutoCAD 起動検知 → COM でパスを即時追加
            result = self._acad.add_paths(str(self._manager.get_repo_dir()))
            if result.success:
                logger.info("AutoCAD を検出 - パスを自動登録しました。")
                self._set_status("AutoCAD を検出 - パスを自動登録しました。")
            else:
                logger.warning("パス自動登録に失敗しました: %s", result.message)
            # acaddoc.lsp をフルパスで即時ロード
            # 起動直後は図面未オープンでスキップされる場合があるためリトライする
            acaddoc_path = str(self._manager.get_acaddoc_path()).replace("\\", "/")
            if not self._acad.load_lisp(acaddoc_path):
                self._schedule_acaddoc_retry(acaddoc_path, self._ACAD_LOAD_RETRY_MAX)
        elif not now_available and self._acad_was_available:
            # AutoCAD 終了検知 → 終了時に TRUSTEDPATHS が空で保存される恐れがあるため
            # 2 秒後にレジストリへ再書き込みして自己修復する
            logger.info("AutoCAD の終了を検出 - 2秒後にレジストリを再設定します。")
            self.after(self._ACAD_EXIT_REWRITE_MS, self._ensure_trusted_path_registry)
        self._acad_was_available = now_available
        self.after(self._ACAD_POLL_MS, self._poll_autocad)

    def _schedule_acaddoc_retry(self, acaddoc_path: str, remaining: int) -> None:
        """図面が開かれるまで acaddoc.lsp のロードをリトライする。

        AutoCAD 起動直後は ActiveDocument が None のためロードがスキップされる。
        5 秒ごとにリトライし、成功するか上限に達したら終了する。
        """
        if remaining <= 0:
            logger.debug("acaddoc.lsp リトライ上限に達しました")
            return
        if not self._acad.is_available():
            return  # AutoCAD が終了していれば中止
        if self._acad.load_lisp(acaddoc_path):
            logger.info("acaddoc.lsp をリトライでロードしました（残り %d 回）", remaining)
            return
        self.after(
            self._ACAD_LOAD_RETRY_MS,
            lambda: self._schedule_acaddoc_retry(acaddoc_path, remaining - 1),
        )

    def _auto_sync_palette(self) -> None:
        """LISP 登録・AutoCAD 検出時にパレットを自動生成・配置する（メッセージなし）。

        出力先の優先順位:
        1. AutoCAD 起動中 → COM で取得した ToolPalettePath
        2. AutoCAD 未起動 → レジストリから取得した ToolPalettePath
        3. どちらも取得できない → リポジトリフォルダ直下
        """
        lisps = self._manager.list_all()
        output_dir = (
            self._acad.get_tool_palette_path()
            or self._acad.get_tool_palette_path_registry()
            or self._manager.get_repo_dir()
        )
        result = self._palette.generate(lisps, output_dir)
        if result.success:
            logger.info("パレットを自動更新しました: %s", output_dir)
        else:
            logger.warning("パレットの自動更新に失敗: %s", result.message)

        # ToolPalettePath に出力先を追加（AutoCAD 起動中のみ有効）
        self._acad.add_tool_palette_path(str(output_dir))
        # パレットをリフレッシュ（AutoCAD 起動中のみ有効）
        self._acad.refresh_tool_palettes()

    def _cleanup_prev_repo_path(self) -> None:
        """config.prev_repo_path に残留パスがあればレジストリから削除して消去する。"""
        prev = self._config.prev_repo_path
        if not prev:
            return
        logger.info("残留パスをレジストリから削除します: %s", prev)
        self._acad.remove_paths_from_registry(prev)
        self._config.prev_repo_path = ""
        self._config.save()

    def _ensure_trusted_path_registry(self) -> None:
        """AutoCAD の起動状態に関わらず SupportPath/TRUSTEDPATHS をレジストリに永続登録する。
        ApplicationPlugins\... を登録し、サブディレクトリ（Tool_LISP 含む）を再帰的に信頼させる。
        """
        repo = str(self._manager.get_repo_dir())
        # ApplicationPlugins\... を登録（Tool_LISP の親ディレクトリ）
        app_plugins = str(Path(repo).parent)
        trusted_path = app_plugins.rstrip("\\") + "\\..."
        updated = self._acad.ensure_trusted_path_registry(trusted_path)

        if updated:
            logger.info("SupportPath/TRUSTEDPATHS をレジストリに永続登録しました: %s", app_plugins)
            self._set_status("信頼済みパスをレジストリに書き込みました。AutoCAD 再起動で有効になります。")
        else:
            logger.debug("SupportPath/TRUSTEDPATHS は既にレジストリに登録済みです: %s", app_plugins)
            self._set_status(f"信頼済みパス: 登録済み ({Path(app_plugins).name})")

    def _auto_add_paths(self) -> None:
        """AutoCAD が起動中であればリポジトリパスを登録する（手動トリガー用）。"""
        if self._acad.is_available():
            result = self._acad.add_paths(str(self._manager.get_repo_dir()))
            if result.success:
                logger.info("AutoCAD 起動中 - パスを自動登録しました。")
            else:
                logger.warning("パス自動登録に失敗しました: %s", result.message)

    def _on_open_folder(self) -> None:
        repo = self._manager.get_repo_dir()
        try:
            os.startfile(repo)
        except OSError as e:
            messagebox.showerror("エラー", f"フォルダを開けませんでした。\n{e}")

    def _prompt_launch_autocad(self) -> None:
        """起動時に AutoCAD が未起動なら起動を促すダイアログを表示する（1回のみ）。"""
        if self._acad.is_available():
            return  # 既に起動中なら不要
        if self._find_autocad_exe() is None:
            return  # AutoCAD が見つからない環境では表示しない
        if messagebox.askyesno(
            "AutoCAD が起動していません",
            "AutoCAD が起動していません。\n今すぐ起動しますか？",
        ):
            self._on_launch_autocad()

    def _on_launch_autocad(self) -> None:
        """AutoCAD を起動する。レジストリ → 固定パスの順で探索する。"""
        import subprocess

        acad_exe = self._find_autocad_exe()
        if acad_exe is None:
            messagebox.showwarning(
                "AutoCAD が見つかりません",
                "AutoCAD のインストールが確認できませんでした。\n"
                "インストール状況を確認してください。",
            )
            return
        try:
            subprocess.Popen(acad_exe)
            logger.info("AutoCAD を起動しました: %s", acad_exe)
            # AutoCAD の起動完了後にパスを自動登録（15秒後に試行）
            self.after(self._ACAD_LAUNCH_WAIT_MS, self._auto_add_paths)
        except OSError as e:
            messagebox.showerror(
                "エラー", f"AutoCAD を起動できませんでした。\n{e}"
            )

    def _find_autocad_exe(self) -> str | None:
        """AutoCAD の実行ファイルパスをレジストリ → 固定パスの順で探す。
        複数バージョンがインストールされている場合は最新バージョンを優先する。
        """
        import winreg

        # 1) レジストリから全バージョンを収集してソート
        # サブキー名は "R24.0", "R24.1", "R25.0" などのリリース番号形式
        candidates: list[tuple[tuple[int, ...], str]] = []
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Autodesk\AutoCAD"
            ) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    sub = winreg.EnumKey(key, i)
                    try:
                        with winreg.OpenKey(key, sub) as skey:
                            install_dir, _ = winreg.QueryValueEx(skey, "")
                            candidate = os.path.join(install_dir, "acad.exe")
                            if os.path.isfile(candidate):
                                # "R24.1" → (24, 1) としてソート可能なタプルに変換
                                ver_str = sub.lstrip("Rr")
                                ver_tuple = tuple(
                                    int(x) for x in ver_str.split(".") if x.isdigit()
                                )
                                candidates.append((ver_tuple, candidate))
                    except OSError:
                        continue
        except OSError:
            pass

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        # 2) 固定パスにフォールバック（新しい年から順に探す）
        import datetime
        for year in range(datetime.date.today().year + 1, 2019, -1):
            for base in [
                r"C:\Program Files\Autodesk",
                r"C:\Program Files (x86)\Autodesk",
            ]:
                candidate = os.path.join(base, f"AutoCAD {year}", "acad.exe")
                if os.path.isfile(candidate):
                    return candidate

        return None

    def _register_launcher(self) -> None:
        """EXE / スクリプト両対応で lisp_manager ランチャーを acaddoc.lsp に登録する。"""
        if getattr(sys, "frozen", False):
            # PyInstaller EXE として起動中: EXE パスを直接渡す
            self._manager.update_launcher(sys.executable)
        else:
            # Python スクリプトとして起動中
            # pythonw.exe があればコンソールウィンドウを非表示にする
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            launcher_exe = str(pythonw) if pythonw.exists() else sys.executable
            self._manager.update_launcher(
                launcher_exe,
                str(Path(__file__).parent / "main.py"),
            )

    def _on_open_settings(self) -> None:
        _SettingsDialog(self, self._config, self._on_settings_saved)

    def _on_settings_saved(self, new_repo_path: str) -> None:
        """設定ダイアログで「保存」が押されたときの処理。"""
        old_repo_path = self._config.repo_path
        self._config.repo_path = new_repo_path

        # 古いパスを prev_repo_path に保存してから先にセーブ
        # （クリーンアップ中にクラッシュしても次回起動時に再試行できる）
        if old_repo_path != new_repo_path:
            self._config.prev_repo_path = old_repo_path
        self._config.save()

        # 古いパスをレジストリ（および起動中の AutoCAD）から削除
        if old_repo_path != new_repo_path:
            self._acad.remove_paths_from_registry(old_repo_path)
            self._acad.remove_paths(old_repo_path)
            self._config.prev_repo_path = ""
            self._config.save()

        self._manager = LispManager(self._config.repo_path)
        self._register_launcher()
        # 新しいパスを TRUSTEDPATHS / SupportPath に登録
        self._ensure_trusted_path_registry()
        acad_result = self._acad.add_paths(new_repo_path)
        if not acad_result.success:
            logger.warning(acad_result.detail or acad_result.message)
        self._refresh_list()

    def _on_uninstall(self) -> None:
        """システムのアンインストーラーを起動する。

        インストーラー経由でインストールされていない場合はエラーを表示する。
        """
        import subprocess
        import winreg

        if not messagebox.askyesno(
            "アンインストール",
            "AutoLISP管理ツールをアンインストールしますか？\n\n"
            "登録済み LISP ファイルと AutoCAD の設定もすべて削除されます。",
        ):
            return

        app_id = "{9F3A2B1C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}"
        reg_path = f"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_id}_is1"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
                uninstall_str, _ = winreg.QueryValueEx(key, "UninstallString")
            subprocess.Popen(uninstall_str)
            self.destroy()
        except FileNotFoundError:
            messagebox.showerror(
                "エラー",
                "アンインストーラーが見つかりません。\n"
                "「設定」→「アプリ」からアンインストールしてください。",
            )

    def _on_close(self) -> None:
        """ウィンドウを閉じる前にジオメトリを設定に保存する。"""
        self._config.window_geometry = self.geometry()
        self._config.save()
        logger.debug(
            "ウィンドウジオメトリを保存しました: %s",
            self._config.window_geometry,
        )
        self.destroy()

    # ------------------------------------------------------------------
    # リスト更新
    # ------------------------------------------------------------------

    def _refresh_list(self) -> None:
        """登録済み LISP 一覧を再描画する。"""
        for widget in self._content.winfo_children():
            widget.destroy()
        self._cmd_canvases = []   # コマンド列キャンバスをリセット
        self._name_labels = []    # ファイル名ラベルをリセット

        lisps = self._manager.list_all()

        if not lisps:
            ctk.CTkLabel(
                self._content,
                text=(
                    "登録されているLISPはありません。\n"
                    "「＋ LISPを追加」またはドラッグ&ドロップで登録してください。"
                ),
                text_color="gray",
            ).pack(pady=60)
            return

        # コマンドテキストの色（外観モードに応じて）
        cmd_color = "#9a9a9a" if ctk.get_appearance_mode() == "Dark" else "#707070"

        for lisp in lisps:
            row = ctk.CTkFrame(
                self._content, fg_color=("gray95", "gray15")
            )
            row.pack(fill="x", pady=4, padx=5)

            # 内部は grid レイアウト: col2（コマンド列）のみ横に伸縮
            row.grid_columnconfigure(2, weight=1)

            # Col 0: 有効/無効トグルスイッチ
            var = ctk.BooleanVar(value=lisp.enabled)
            ctk.CTkSwitch(
                row,
                text="",
                width=40,          # text="" なのにデフォルト 100px 確保されるのを防ぐ
                variable=var,
                command=lambda s=lisp.path.stem, v=var: self._on_toggle_lisp(
                    s, v.get()
                ),
            ).grid(row=0, column=0, padx=(10, 6), pady=6, sticky="w")

            # Col 1: ファイル名（列幅統一のためラベルを保持）
            name_lbl = ctk.CTkLabel(
                row, text=lisp.name, font=ctk.CTkFont(weight="bold")
            )
            name_lbl.grid(row=0, column=1, padx=(0, 5), sticky="w")
            self._name_labels.append((row, name_lbl))

            # ファイル説明（@description メタデータがあれば表示）
            if lisp.description:
                ctk.CTkLabel(
                    row, text=lisp.description,
                    text_color="gray60",
                    font=ctk.CTkFont(size=11),
                ).grid(row=1, column=1, columnspan=2, padx=(0, 5), sticky="w")

            # Col 2: コマンド一覧（横スクロール可能なキャンバス）
            cmd_text = (
                f"コマンド: {', '.join(lisp.commands)}"
                if lisp.commands
                else "（コマンド定義なし）"
            )
            cmd_bg = self._resolve_bg(row)
            cmd_canvas = tk.Canvas(
                row, highlightthickness=0, bd=0, bg=cmd_bg, height=1,
            )
            cmd_canvas.grid(row=0, column=2, sticky="nsew", padx=(20, 0))
            cmd_canvas.create_text(
                4, 0,
                text=cmd_text,
                anchor="w",
                fill=cmd_color,
                tags="cmd",
                font=self._cmd_font,
            )
            self._cmd_canvases.append(cmd_canvas)

            # Col 3: 削除ボタン
            ctk.CTkButton(
                row,
                text="\u2715",
                width=30,
                height=25,
                fg_color="transparent",
                hover_color="#d35b5b",
                text_color="gray",
                command=lambda p=str(lisp.path): self._on_delete_lisp(p),
            ).grid(row=0, column=3, padx=10, sticky="e")

        # コマンド列の scrollregion を統一（レイアウト確定後）
        self.after(50, self._sync_cmd_scrollregions)

    def _scroll_cmd_canvases(self, *args) -> None:
        """横スクロールバーの操作を全コマンド列キャンバスに伝播する。"""
        for c in self._cmd_canvases:
            c.xview(*args)
        # スクロールバーの位置を更新
        if self._cmd_canvases:
            lo, hi = self._cmd_canvases[0].xview()
            self._hsb.set(lo, hi)

    def _sync_cmd_scrollregions(self) -> None:
        """全コマンド列キャンバスの scrollregion を最大テキスト幅で統一する。

        - テキスト幅の最大値を求め、全キャンバスに同じ scrollregion を設定
        - テキストをキャンバス高さの中央に縦配置
        - これにより横スクロールバー 1 本で全行を同期スクロールできる
        """
        if not self._cmd_canvases:
            return
        self.update_idletasks()

        # ファイル名列の幅を全行で統一（コマンド列の開始 x を揃える）
        if self._name_labels:
            max_name_w = max(lbl.winfo_reqwidth() for _, lbl in self._name_labels)
            for row_frame, _ in self._name_labels:
                row_frame.grid_columnconfigure(1, minsize=max_name_w + 5)
            self.update_idletasks()  # 幅変更をレイアウトに反映

        # 全キャンバスのテキスト幅の最大値を取得
        max_text_w = 0
        for c in self._cmd_canvases:
            bbox = c.bbox("cmd")
            if bbox:
                max_text_w = max(max_text_w, bbox[2] + 4)  # 右マージン 4px

        # 全キャンバスに統一 scrollregion を設定し、テキストを縦中央に配置
        for c in self._cmd_canvases:
            h = max(c.winfo_height(), 1)
            visible_w = c.winfo_width()
            # テキストを縦中央に移動（anchor="w" なので y が垂直中心）
            items = c.find_withtag("cmd")
            if items:
                c.coords(items[0], 4, h // 2)
            # scrollregion: テキスト幅か表示幅の大きい方
            c.configure(scrollregion=(0, 0, max(max_text_w, visible_w), h))

        # スクロールバー位置を更新
        lo, hi = self._cmd_canvases[0].xview()
        self._hsb.set(lo, hi)

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------

    def _register_files(self, file_paths: list[str]) -> None:
        """ファイルパスのリストを受け取り LISP 登録を行う共通処理。"""
        errors: list[str] = []
        success_count = 0
        for f in file_paths:
            result = self._manager.register(f)
            if result.success:
                success_count += 1
                acad_result = self._acad.add_paths(
                    str(self._manager.get_repo_dir())
                )
                if not acad_result.success:
                    logger.warning(acad_result.detail or acad_result.message)
                # AutoCAD が起動中かつドキュメントが開いていれば即時ロード
                stem = os.path.splitext(os.path.basename(f))[0]
                self._acad.load_lisp(stem)
            else:
                errors.append(result.message)

        if errors:
            messagebox.showerror("エラー", "\n".join(errors))
        elif success_count > 0:
            messagebox.showinfo(
                "完了",
                f"{success_count} 件の LISP を登録しました。\n"
                "AutoCAD を起動すると自動ロードされます。",
            )
        self._refresh_list()

    def _handle_result(self, result: OperationResult) -> None:
        """OperationResult に応じて messagebox を表示する。"""
        if result.success:
            messagebox.showinfo("完了", result.message)
        else:
            messagebox.showerror("エラー", result.message)


# ----------------------------------------------------------------------
# 設定ダイアログ
# ----------------------------------------------------------------------


class _SettingsDialog(ctk.CTkToplevel):
    """リポジトリパスを変更するモーダルダイアログ。"""

    def __init__(
        self,
        parent: ctk.CTk,
        config: AppConfig,
        on_save: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self.title("\u2699 設定")
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()

        self._on_save = on_save
        self._path_var = ctk.StringVar(value=config.repo_path)

        # ---- LISPリポジトリフォルダ ----
        ctk.CTkLabel(
            self,
            text="LISPリポジトリフォルダ",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=20, pady=(20, 4))

        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkEntry(
            path_frame,
            textvariable=self._path_var,
            width=320,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            path_frame,
            text="参照...",
            command=self._browse,
            width=72,
            height=32,
        ).pack(side="left")

        ctk.CTkLabel(
            self,
            text=(
                "AutoCAD が起動中の場合、新しいフォルダが "
                "TRUSTEDPATHS に自動登録されます。"
            ),
            text_color="gray60",
            font=ctk.CTkFont(size=11),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # ---- ボタン行 ----
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btn_frame,
            text="キャンセル",
            fg_color="transparent",
            border_width=1,
            command=self.destroy,
            width=100,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame,
            text="保存",
            command=self._save,
            width=100,
        ).pack(side="right")

    def _browse(self) -> None:
        path = filedialog.askdirectory(
            title="LISPリポジトリフォルダを選択",
            initialdir=self._path_var.get(),
        )
        if path:
            self._path_var.set(path)

    def _save(self) -> None:
        self._on_save(self._path_var.get())
        self.destroy()
