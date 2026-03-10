"""
config.py - アプリケーション設定の読み書き
JSON ファイルへ永続化する。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_REPO = str(
    Path(os.environ.get("APPDATA", "")) / "Autodesk" / "Support" / "Tool_LISP"
)
_CONFIG_PATH = Path(os.environ.get("APPDATA", "")) / ".lisp_manager_config.json"


@dataclass
class AppConfig:
    """アプリケーション設定。"""
    repo_path: str = _DEFAULT_REPO
    window_geometry: str = "900x600"
    prev_repo_path: str = ""  # 前回のリポジトリパス（起動時クリーンアップ用）

    # ------------------------------------------------------------------
    # クラスメソッド
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> "AppConfig":
        """設定ファイルから読み込む。ファイルが存在しない場合はデフォルト値を返す。"""
        if not _CONFIG_PATH.exists():
            logger.debug("設定ファイルが見つかりません。デフォルト設定を使用します。")
            return cls()

        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                data: dict = json.load(f)
            cfg = cls()
            cfg.repo_path = data.get("repo_path", _DEFAULT_REPO)
            cfg.window_geometry = data.get("window_geometry", "900x600")
            cfg.prev_repo_path = data.get("prev_repo_path", "")
            logger.debug("設定ファイルを読み込みました: %s", _CONFIG_PATH)
            return cfg
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("設定ファイルの読み込みに失敗しました（デフォルト使用）: %s", e)
            return cls()

    def save(self) -> None:
        """設定ファイルへ書き込む。"""
        try:
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
            logger.debug("設定ファイルを保存しました: %s", _CONFIG_PATH)
        except OSError as e:
            logger.error("設定ファイルの保存に失敗しました: %s", e)
