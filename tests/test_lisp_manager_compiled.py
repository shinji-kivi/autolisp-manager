"""
test_lisp_manager_compiled.py
コンパイル版 (.fas / .vlx) 対応まわりの回帰テスト。

依存を増やさないよう標準ライブラリの unittest だけで書いてある。
実行:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lisp_manager import LispManager  # noqa: E402

# テスト用のごく短いソース LISP
SAMPLE_LSP = """;;; @description テスト用
;;; @button FOO テスト実行
(defun c:FOO () (princ))
(defun c:FOO-HELP () (princ))
"""


class CompiledLispSupportTest(unittest.TestCase):
    """.lsp / .fas / .vlx の登録・一覧・ロード行生成を検証する。"""

    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="lispmgr_test_"))
        self._repo = self._tmp / "repo"
        self._src = self._tmp / "src"
        self._src.mkdir(parents=True)
        self._mgr = LispManager(str(self._repo))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # ヘルパー
    # ------------------------------------------------------------------

    def _make_src(self, name: str, content: str = SAMPLE_LSP) -> str:
        """テスト用のソースファイルを作り、そのパスを返す。"""
        p = self._src / name
        p.write_text(content, encoding="utf-8")
        return str(p)

    def _acaddoc_lines(self) -> list[str]:
        return self._mgr.get_acaddoc_path().read_text(encoding="utf-8").splitlines()

    def _load_lines(self) -> list[str]:
        """acaddoc.lsp 内の (load ...) 行だけを返す（ag-help は除く）。"""
        return [
            ln for ln in self._acaddoc_lines()
            if "(load " in ln and '"ag-help"' not in ln
        ]

    # ------------------------------------------------------------------
    # 登録可否
    # ------------------------------------------------------------------

    def test_register_accepts_lsp_fas_vlx(self) -> None:
        for name in ("a.lsp", "b.fas", "c.vlx"):
            with self.subTest(name=name):
                result = self._mgr.register(self._make_src(name))
                self.assertTrue(result.success, result.message)
                self.assertTrue((self._repo / name).exists())

    def test_register_accepts_uppercase_extension(self) -> None:
        result = self._mgr.register(self._make_src("D.FAS"))
        self.assertTrue(result.success, result.message)

    def test_register_rejects_other_extensions(self) -> None:
        for name in ("note.txt", "script.dcl", "tool.arx"):
            with self.subTest(name=name):
                result = self._mgr.register(self._make_src(name))
                self.assertFalse(result.success)
                self.assertFalse((self._repo / name).exists())

    # ------------------------------------------------------------------
    # ロード行の生成
    # ------------------------------------------------------------------

    def test_lsp_load_line_has_no_extension(self) -> None:
        """.lsp は従来どおり拡張子なしでロードする（後方互換）。"""
        self._mgr.register(self._make_src("MYTOOL.lsp"))
        self.assertIn('(load "MYTOOL" nil)', self._load_lines())

    def test_compiled_load_line_has_explicit_extension(self) -> None:
        """.fas / .vlx は拡張子を明示する（探索順に委ねないため）。"""
        self._mgr.register(self._make_src("FASTOOL.fas"))
        self._mgr.register(self._make_src("VLXTOOL.vlx"))
        lines = self._load_lines()
        self.assertIn('(load "FASTOOL.fas" nil)', lines)
        self.assertIn('(load "VLXTOOL.vlx" nil)', lines)

    # ------------------------------------------------------------------
    # 同一 stem の併存（二重ロード防止）
    # ------------------------------------------------------------------

    def test_same_stem_loads_only_once(self) -> None:
        """.lsp と .fas が両方あってもロード行は 1 本だけ。"""
        self._mgr.register(self._make_src("DUP.lsp"))
        self._mgr.register(self._make_src("DUP.fas"))
        dup_lines = [ln for ln in self._load_lines() if "DUP" in ln]
        self.assertEqual(len(dup_lines), 1, dup_lines)

    def test_compiled_wins_over_source(self) -> None:
        """併存時はコンパイル版が優先される。"""
        self._mgr.register(self._make_src("DUP.lsp"))
        self._mgr.register(self._make_src("DUP.fas"))
        self.assertIn('(load "DUP.fas" nil)', self._load_lines())

    def test_vlx_wins_over_fas(self) -> None:
        self._mgr.register(self._make_src("DUP.fas"))
        self._mgr.register(self._make_src("DUP.vlx"))
        self.assertIn('(load "DUP.vlx" nil)', self._load_lines())

    def test_register_reports_shadowed_file(self) -> None:
        """併存したことがユーザーに伝わる（detail に無視される側が出る）。"""
        self._mgr.register(self._make_src("DUP.lsp"))
        result = self._mgr.register(self._make_src("DUP.fas"))
        self.assertTrue(result.success)
        self.assertIn("DUP.lsp", result.detail)

    def test_list_all_has_one_entry_per_stem(self) -> None:
        self._mgr.register(self._make_src("DUP.lsp"))
        self._mgr.register(self._make_src("DUP.fas"))
        stems = [e.path.stem for e in self._mgr.list_all()]
        self.assertEqual(stems.count("DUP"), 1, stems)

    # ------------------------------------------------------------------
    # 有効/無効の往復（拡張子付きロード行でも状態が保持されること）
    # ------------------------------------------------------------------

    def test_toggle_roundtrip_for_compiled(self) -> None:
        self._mgr.register(self._make_src("FASTOOL.fas"))

        self._mgr.toggle("FASTOOL", False)
        self.assertIn(';; (load "FASTOOL.fas")', self._load_lines())
        self.assertFalse(self._entry("FASTOOL").enabled)

        # 無効のまま再書き込みしても無効が維持される（stem 正規化が効いているか）
        self._mgr.register(self._make_src("OTHER.lsp"))
        self.assertIn(';; (load "FASTOOL.fas")', self._load_lines())
        self.assertFalse(self._entry("FASTOOL").enabled)

        self._mgr.toggle("FASTOOL", True)
        self.assertIn('(load "FASTOOL.fas" nil)', self._load_lines())
        self.assertTrue(self._entry("FASTOOL").enabled)

    def test_toggle_roundtrip_for_source(self) -> None:
        self._mgr.register(self._make_src("MYTOOL.lsp"))
        self._mgr.toggle("MYTOOL", False)
        self.assertIn(';; (load "MYTOOL")', self._load_lines())
        self.assertFalse(self._entry("MYTOOL").enabled)

    def _entry(self, stem: str):
        for e in self._mgr.list_all():
            if e.path.stem == stem:
                return e
        self.fail(f"エントリが見つかりません: {stem}")

    # ------------------------------------------------------------------
    # 即時ロード用のターゲット文字列
    # ------------------------------------------------------------------

    def test_get_load_target(self) -> None:
        self._mgr.register(self._make_src("MYTOOL.lsp"))
        self._mgr.register(self._make_src("FASTOOL.fas"))
        self.assertEqual(self._mgr.get_load_target("MYTOOL"), "MYTOOL")
        self.assertEqual(self._mgr.get_load_target("FASTOOL"), "FASTOOL.fas")
        # 未登録の stem はそのまま返す（従来動作）
        self.assertEqual(self._mgr.get_load_target("NOPE"), "NOPE")

    # ------------------------------------------------------------------
    # メタデータ抽出
    # ------------------------------------------------------------------

    def test_commands_extracted_from_source(self) -> None:
        self._mgr.register(self._make_src("MYTOOL.lsp"))
        self.assertEqual(self._mgr.get_commands("MYTOOL"), ["FOO", "FOO-HELP"])

    def test_commands_empty_for_compiled_without_meta(self) -> None:
        """サイドカーが無いコンパイル版は空を返す（例外は出さない）。"""
        self._mgr.register(self._make_src("FASTOOL.fas"))
        self.assertEqual(self._mgr.get_commands("FASTOOL"), [])

    def test_readme_name_kept_for_compiled(self) -> None:
        """README は別ファイルなのでコンパイル版でも参照名が残る。"""
        self._mgr.register(self._make_src("FASTOOL.fas"))
        self.assertEqual(
            self._entry("FASTOOL").readme_file, "FASTOOL_README.md"
        )

    def test_readme_copied_alongside_compiled(self) -> None:
        (self._src / "README.md").write_text("# help", encoding="utf-8")
        self._mgr.register(self._make_src("FASTOOL.fas"))
        self.assertTrue((self._repo / "FASTOOL_README.md").exists())

    # ------------------------------------------------------------------
    # メタデータのサイドカー (.meta)
    # ------------------------------------------------------------------

    def test_meta_generated_from_sibling_source(self) -> None:
        """.fas の隣に .lsp があれば .meta を自動生成する（開発者の手元）。"""
        self._make_src("FASTOOL.lsp")          # 隣に置くだけで登録はしない
        self._mgr.register(self._make_src("FASTOOL.fas"))

        meta = self._repo / "FASTOOL.meta"
        self.assertTrue(meta.exists())
        body = meta.read_text(encoding="utf-8")
        self.assertIn(";;; @command FOO", body)
        self.assertIn(";;; @command FOO-HELP", body)
        self.assertIn(";;; @description テスト用", body)
        self.assertIn(";;; @button FOO テスト実行", body)

    def test_meta_restores_commands_and_metadata(self) -> None:
        """.meta があればコマンド一覧と @description / @button が復活する。"""
        self._make_src("FASTOOL.lsp")
        self._mgr.register(self._make_src("FASTOOL.fas"))

        self.assertEqual(self._mgr.get_commands("FASTOOL"), ["FOO", "FOO-HELP"])
        entry = self._entry("FASTOOL")
        self.assertEqual(entry.description, "テスト用")
        self.assertEqual(entry.button_labels, {"FOO": "テスト実行"})

    def test_meta_copied_when_shipped_alongside(self) -> None:
        """配布物に .meta が同梱されていればそれを取り込む（受け取り側）。"""
        (self._src / "SHIPPED.meta").write_text(
            ";;; @description 配布された説明\n"
            ";;; @command SHIPCMD\n"
            ";;; @button SHIPCMD 配布ボタン\n",
            encoding="utf-8",
        )
        self._mgr.register(self._make_src("SHIPPED.fas"))

        self.assertTrue((self._repo / "SHIPPED.meta").exists())
        self.assertEqual(self._mgr.get_commands("SHIPPED"), ["SHIPCMD"])
        entry = self._entry("SHIPPED")
        self.assertEqual(entry.description, "配布された説明")
        self.assertEqual(entry.button_labels, {"SHIPCMD": "配布ボタン"})

    def test_shipped_meta_wins_over_sibling_source(self) -> None:
        """同梱の .meta があれば、隣の .lsp からは生成し直さない。"""
        self._make_src("BOTH.lsp")
        (self._src / "BOTH.meta").write_text(
            ";;; @command SHIPPED_ONLY\n", encoding="utf-8"
        )
        self._mgr.register(self._make_src("BOTH.fas"))
        self.assertEqual(self._mgr.get_commands("BOTH"), ["SHIPPED_ONLY"])

    def test_meta_accepts_button_only_sidecar(self) -> None:
        """@command を書いていない手書き .meta でも @button から拾える。"""
        (self._src / "HAND.meta").write_text(
            ";;; @button HANDCMD 手書き\n", encoding="utf-8"
        )
        self._mgr.register(self._make_src("HAND.fas"))
        self.assertEqual(self._mgr.get_commands("HAND"), ["HANDCMD"])

    def test_source_registration_makes_no_meta(self) -> None:
        """.lsp の登録ではサイドカーを作らない（従来どおり本体から読む）。"""
        self._mgr.register(self._make_src("PLAIN.lsp"))
        self.assertFalse((self._repo / "PLAIN.meta").exists())

    def test_remove_deletes_meta(self) -> None:
        self._make_src("FASTOOL.lsp")
        self._mgr.register(self._make_src("FASTOOL.fas"))
        self.assertTrue((self._repo / "FASTOOL.meta").exists())

        self._mgr.remove(str(self._repo / "FASTOOL.fas"))
        self.assertFalse((self._repo / "FASTOOL.meta").exists())

    def test_register_reports_missing_meta(self) -> None:
        """サイドカーが用意できないことがユーザーに伝わる。"""
        result = self._mgr.register(self._make_src("BARE.fas"))
        self.assertTrue(result.success)
        self.assertIn("BARE.meta", result.detail)

    # ------------------------------------------------------------------
    # stem 正規化のエッジケース
    # ------------------------------------------------------------------

    def test_to_stem_keeps_dotted_names(self) -> None:
        """ドットを含む stem を LISP 以外の拡張子として削らない。"""
        self.assertEqual(self._mgr._to_stem("v1.2tool"), "v1.2tool")
        self.assertEqual(self._mgr._to_stem("v1.2tool.fas"), "v1.2tool")
        self.assertEqual(self._mgr._to_stem("MYTOOL"), "MYTOOL")

    # ------------------------------------------------------------------
    # ランチャー定義の保全
    # ------------------------------------------------------------------

    def test_launcher_survives_new_manager_instance(self) -> None:
        """update_launcher を通らない再生成でランチャーを消さない。

        GUI を経由せず LispManager を直接使ったとき、acaddoc.lsp から
        (defun c:lisp_manager ...) が黙って消える事故を防ぐ。
        """
        self._mgr.update_launcher(r"C:\tools\LispManager.exe")
        self.assertIn("(defun c:lisp_manager", self._acaddoc_text())

        # 新しいインスタンス（= update_launcher 未実行）で再生成させる
        fresh = LispManager(str(self._repo))
        fresh.register(self._make_src("MYTOOL.lsp"))

        text = self._acaddoc_text()
        self.assertIn("(defun c:lisp_manager", text)
        self.assertIn(r"C:\\tools\\LispManager.exe", text)
        self.assertEqual(text.count("(defun c:lisp_manager"), 1)

    def _acaddoc_text(self) -> str:
        return self._mgr.get_acaddoc_path().read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # 一括削除
    # ------------------------------------------------------------------

    def test_cleanup_removes_compiled_files(self) -> None:
        self._make_src("FASTOOL.lsp")
        self._mgr.register(self._make_src("MYTOOL.lsp"))
        self._mgr.register(self._make_src("FASTOOL.fas"))
        self._mgr.register(self._make_src("VLXTOOL.vlx"))
        result = self._mgr.cleanup()
        self.assertTrue(result.success, result.message)
        for name in ("MYTOOL.lsp", "FASTOOL.fas", "VLXTOOL.vlx", "FASTOOL.meta"):
            self.assertFalse((self._repo / name).exists(), name)

    def test_cleanup_removes_shadowed_duplicate(self) -> None:
        """同一 stem で重複していた側も消し残さない。"""
        self._mgr.register(self._make_src("DUP.lsp"))
        self._mgr.register(self._make_src("DUP.fas"))
        result = self._mgr.cleanup()
        self.assertTrue(result.success, result.message)
        self.assertFalse((self._repo / "DUP.lsp").exists())
        self.assertFalse((self._repo / "DUP.fas").exists())


if __name__ == "__main__":
    unittest.main()
