"""
main.py - アプリケーション エントリーポイント

起動方法:
    python main.py
"""
import ctypes
import logging
import sys

import customtkinter as ctk

from app import App
from config import AppConfig

# ミューテックスハンドルをモジュールレベルで保持（GC 対策）
_mutex_handle = None


def _setup_logging() -> None:
    import os
    from pathlib import Path

    log_path = Path(os.environ.get("APPDATA", "~")) / ".lisp_manager.log"
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    # コンソールが使える場合（開発環境）は標準エラーにも出力
    if not getattr(sys, "frozen", False):
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def _ensure_single_instance() -> bool:
    """既に起動中なら既存ウィンドウをフォアグラウンドにして False を返す。"""
    global _mutex_handle
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(
        None, False, "Local\\AutoLISP_Manager_SingleInstance"
    )
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        try:
            import win32con
            import win32gui

            hwnd = win32gui.FindWindow(None, "AutoLISP 管理ツール")
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return False
    return True


def _run_uninstall() -> None:
    """アンインストール時のクリーンアップ処理。

    レジストリの TRUSTEDPATHS / SupportPath からリポジトリパスを削除し、
    acaddoc.lsp の管理範囲を除去する。GUI は表示しない。
    """
    import os as _os
    from acad_sync import AcadSync
    from lisp_manager import LispManager

    config = AppConfig.load()
    repo = config.repo_path

    # レジストリから削除
    acad = AcadSync()
    acad.remove_paths_from_registry(repo)

    # acaddoc.lsp の管理範囲を除去
    try:
        manager = LispManager(repo)
        manager.cleanup()
    except Exception:
        pass

    logging.getLogger(__name__).info("アンインストールクリーンアップ完了: %s", repo)
    _os._exit(0)


if __name__ == "__main__":
    _setup_logging()

    if "--uninstall" in sys.argv:
        _run_uninstall()

    if not _ensure_single_instance():
        # os._exit() でプロセスを即終了する。
        # sys.exit() だと PyInstaller onefile ブートローダーの後片付けが走り
        # 「Failed to remove temporary directory」ダイアログが出るため。
        import os as _os
        _os._exit(0)

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    config = AppConfig.load()
    app = App(config)
    app.mainloop()
