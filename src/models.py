"""
models.py - データモデル定義
LispEntry と OperationResult を提供する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LispEntry:
    """登録済み LISP ファイルを表すデータモデル。"""
    name: str           # ファイル名（例: "my_tool.lsp"）
    path: Path          # フルパス
    commands: list[str] = field(default_factory=list)  # 抽出されたコマンド名
    enabled: bool = True                                # 有効/無効
    description: str = ""                               # @description メタデータ
    button_labels: dict[str, str] = field(default_factory=dict)  # コマンド名→日本語ラベル
    readme_file: str = ""                               # 関連READMEファイル名


@dataclass
class OperationResult:
    """操作の結果を表すデータモデル。UI へフィードバックするために使用する。"""
    success: bool
    message: str   # ユーザー向けの短いメッセージ
    detail: str = ""  # ログ用の詳細情報（省略可）

    @classmethod
    def ok(cls, message: str, detail: str = "") -> "OperationResult":
        return cls(success=True, message=message, detail=detail)

    @classmethod
    def fail(cls, message: str, detail: str = "") -> "OperationResult":
        return cls(success=False, message=message, detail=detail)
