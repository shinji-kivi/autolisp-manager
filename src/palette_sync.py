"""
palette_sync.py - AutoCAD ツールパレット (.atc) ファイルの生成

責務:
- 登録済み LISP の一覧から AutoCAD ツールパレット XML を生成する
- 出力先ディレクトリは引数で受け取る（ハードコードしない）

AutoCAD のツールパレット (.atc) ファイルは XML 形式で、
各ツールには一意の GUID (ItemID) が必要。
Command Tool の ComClass CLSID は AutoCAD 内部の固定値を使用する。
"""
from __future__ import annotations

import logging
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from models import LispEntry, OperationResult

logger = logging.getLogger(__name__)

# AutoCAD の Command Tool 用 StockTool CLSID
# （AutoCAD 内部で定義された CommandTool のクラス ID）
_COMMAND_TOOL_CLSID = "{2AF2E430-41CA-4F03-88FB-1F9B4E05B519}"

_PALETTE_GUID = "{D7B9B404-E6E0-4E1B-9A3F-0E7C8C5D3F2E}"
_PALETTE_NAME = "LISP"
_OUTPUT_FILENAME = "LISP.atc"

# AutoCAD がパレットに割り当てた外部 GUID（Palettes/*.atc のファイル名部分）
# この GUID を使って .xpg（パレットグループ定義ファイル）を生成する
# ※ LISP.xpg を「パレットをカスタマイズ」→ LISP グループ右クリック →「読み込み」で
#    インポートすると "LISP" グループが再構成される
_PALETTE_EXTERNAL_GUID = "{E15260D5-6FAF-4DC1-BB7F-6D30D3C79957}"
_XPG_FILENAME = "LISP.xpg"


def _make_guid() -> str:
    """新しいランダム GUID を生成する。"""
    return "{" + str(uuid.uuid4()).upper() + "}"


class PaletteSync:
    """ツールパレット (.atc) ファイルを生成するクラス。"""

    def _write_xpg(self, output_dir: Path) -> None:
        """LISP パレットグループを定義する .xpg ファイルを生成する。

        AutoCAD のカスタマイズダイアログで
        「LISP グループ右クリック → 読み込み」によって
        "LISP" グループを再構成できる。
        """
        xpg_content = (
            "<ToolPaletteGroupExport>"
            "<ToolPaletteGroups>"
            "<ToolPaletteGroup>"
            f"<Name>{_PALETTE_NAME}</Name>"
            "<CustomData/>"
            "<ActivePaletteIndex>0</ActivePaletteIndex>"
            "<Contents>"
            f'<ToolPalette ID="{_PALETTE_EXTERNAL_GUID}"/>'
            "</Contents>"
            "</ToolPaletteGroup>"
            "</ToolPaletteGroups>"
            "</ToolPaletteGroupExport>"
        )
        xpg_path = output_dir / _XPG_FILENAME
        try:
            xpg_path.write_text(xpg_content, encoding="utf-8")
            logger.debug("xpg ファイルを生成しました: %s", xpg_path)
        except OSError as e:
            logger.warning("xpg ファイルの書き込みに失敗しました: %s", e)

    def generate(
        self, lisps: list[LispEntry], output_dir: Path
    ) -> OperationResult:
        """有効な LISP のコマンドをボタンとしてパレットファイルを生成する。

        Args:
            lisps: LispEntry のリスト（enabled フラグを考慮して有効なもののみ書き出す）
            output_dir: .atc ファイルの出力先ディレクトリ
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return OperationResult.fail(
                "出力フォルダの作成に失敗しました。", detail=str(e)
            )

        # ---------- XML 構築 ----------
        root = ET.Element("Catalog")
        # Palette 定義
        palette_el = ET.SubElement(
            root,
            "Palette",
            {
                "Name": _PALETTE_NAME,
                "GUID": _PALETTE_GUID,
            },
        )

        items_el = ET.SubElement(palette_el, "Items")
        added = 0

        for lisp in lisps:
            if not lisp.enabled:
                continue
            for cmd in lisp.commands:
                tool_guid = _make_guid()

                item_el = ET.SubElement(
                    items_el,
                    "Tool",
                    {"GUID": tool_guid},
                )

                # StockTool 参照（Command Tool タイプ）
                ET.SubElement(
                    item_el, "StockToolRef", {"idValue": _COMMAND_TOOL_CLSID}
                )

                # ツールプロパティ（日本語ラベルがあればボタン名に使用）
                props_el = ET.SubElement(item_el, "Properties")
                label = lisp.button_labels.get(cmd, cmd)
                ET.SubElement(props_el, "Name").text = label
                desc_parts = [f"{lisp.name} ({cmd})"]
                if lisp.description:
                    desc_parts.append(lisp.description)
                ET.SubElement(props_el, "Description").text = (
                    " - ".join(desc_parts)
                )
                ET.SubElement(props_el, "Macro").text = f"^C^C{cmd} "

                added += 1

        output_path = output_dir / _OUTPUT_FILENAME
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        try:
            tree.write(output_path, encoding="utf-16", xml_declaration=True)
        except OSError as e:
            logger.error("パレットファイルの書き込みに失敗しました: %s", e)
            return OperationResult.fail(
                "パレットファイルの書き込みに失敗しました。",
                detail=str(e),
            )

        logger.info(
            "パレットファイルを生成しました: %s (%d コマンド)",
            output_path,
            added,
        )

        # ---------- .xpg 生成（パレットグループ再構成用） ----------
        self._write_xpg(output_dir)

        if added == 0:
            return OperationResult.ok(
                "有効なコマンドが見つかりませんでした。\n"
                "LISP ファイルに (defun c:コマンド名 ...) が含まれているか確認してください。",
                detail=str(output_path),
            )

        return OperationResult.ok(
            f"ツールパレットを生成しました。（{added} コマンド）\n"
            f"出力先: {output_path}\n\n"
            "AutoCAD を再起動するとパレットが更新されます。\n"
            "LISP グループが消えた場合は LISP.xpg を\n"
            "「グループ右クリック」→「読み込み」でインポートしてください。",
            detail=str(output_path),
        )
