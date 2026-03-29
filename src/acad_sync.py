"""
acad_sync.py - AutoCAD COM API 連携

責務:
- 起動中の AutoCAD インスタンスへの接続
- SupportPath・TRUSTEDPATHS へのリポジトリパスの追加・削除
- ToolPalettePath の取得・追加

AutoCAD が起動していない場合でも安全に動作する（is_available() で確認可能）。
"""
from __future__ import annotations

import logging
from pathlib import Path

from models import OperationResult

logger = logging.getLogger(__name__)



def _normalize(path: str) -> str:
    """Windows パスをスラッシュ区切り・小文字に正規化する（比較用）。"""
    return path.replace("\\", "/").rstrip("/").lower()


def _dedup_prepend(path: str, norm: str, semicolon_list: str) -> str:
    """セミコロン区切りリストから path の重複を全て除去し、先頭に1つ追加して返す。

    既存の重複エントリをクリーンアップしながら path が確実に1つだけ存在する
    状態にする。リストが変化しない場合は元の文字列をそのまま返す（変更検知用）。
    """
    parts = [p for p in semicolon_list.split(";") if p.strip() and _normalize(p) != norm]
    parts.insert(0, path)
    return ";".join(parts)


class AcadSync:
    """AutoCAD COM API を通じたパス設定の更新を担うクラス。"""

    def is_available(self) -> bool:
        """AutoCAD が起動中かどうかを返す。"""
        return self._get_app() is not None

    def add_paths(self, repo_path: str) -> OperationResult:
        """リポジトリフォルダを SupportPath と TRUSTEDPATHS に追加する。"""
        acad = self._get_app()
        if acad is None:
            return OperationResult.fail(
                "AutoCAD が起動していないため、パスを自動登録できませんでした。\n"
                "次回 AutoCAD 起動後に「AutoCADと同期」を実行してください。"
            )

        try:
            pref = acad.Preferences.Files
            norm = _normalize(repo_path)

            # SupportPath（重複除去してから先頭に追加）
            current_support = pref.SupportPath or ""
            new_support = _dedup_prepend(repo_path, norm, current_support)
            if new_support != current_support:
                pref.SupportPath = new_support
                logger.info("SupportPath を更新しました: %s", repo_path)
            else:
                logger.debug("SupportPath に既に登録済み: %s", repo_path)

            # TRUSTEDPATHS
            self._add_trusted_path(acad, repo_path, norm)

            return OperationResult.ok("AutoCAD のパス設定を更新しました。")
        except Exception as e:
            logger.error("AutoCAD パス追加中にエラーが発生しました: %s", e)
            return OperationResult.fail(
                "AutoCAD のパス設定の更新に失敗しました。",
                detail=str(e),
            )
        finally:
            del acad

    def remove_paths(self, repo_path: str) -> OperationResult:
        """リポジトリフォルダを SupportPath と TRUSTEDPATHS から削除する。"""
        acad = self._get_app()
        if acad is None:
            return OperationResult.fail(
                "AutoCAD が起動していないため、パスを自動削除できませんでした。\n"
                "AutoCAD 起動後に手動で削除してください。"
            )

        try:
            pref = acad.Preferences.Files
            norm = _normalize(repo_path)

            # SupportPath
            current_support = pref.SupportPath or ""
            new_support = ";".join(
                p for p in current_support.split(";") if _normalize(p) != norm
            )
            pref.SupportPath = new_support

            # TRUSTEDPATHS
            self._remove_trusted_path(acad, repo_path, norm)

            logger.info("AutoCAD パスから削除しました: %s", repo_path)
            return OperationResult.ok("AutoCAD のパス設定から削除しました。")
        except Exception as e:
            logger.error("AutoCAD パス削除中にエラーが発生しました: %s", e)
            return OperationResult.fail(
                "AutoCAD のパス設定の削除に失敗しました。",
                detail=str(e),
            )
        finally:
            del acad

    def load_lisp(self, stem: str) -> bool:
        """起動中の AutoCAD に LISP を即時ロードする。

        AutoCAD が起動中かつアクティブドキュメントがある場合のみ実行する。
        Returns True if the load command was sent, False if skipped (no document).
        """
        acad = self._get_app()
        if acad is None:
            return False
        try:
            doc = acad.ActiveDocument
            if doc is None:
                logger.debug("アクティブドキュメントなし: LISP の即時ロードをスキップ")
                return False
            # SendCommand はコマンドラインへの入力と同等
            doc.SendCommand(f'(progn (load "{stem}" nil) (princ))\n')
            logger.info("AutoCAD に LISP を即時ロードしました: %s", stem)
            return True
        except Exception as e:
            logger.warning("LISP の即時ロードに失敗しました (%s): %s", stem, e)
            return False
        finally:
            del acad

    def unload_lisp(self, commands: list[str]) -> None:
        """起動中の AutoCAD から LISP コマンドを即時削除する。

        (unintern (read "c:CMD")) でシンボルテーブルからコマンドを除去する。
        AutoCAD が起動中かつアクティブドキュメントがある場合のみ実行する。
        """
        if not commands:
            return
        acad = self._get_app()
        if acad is None:
            return
        try:
            doc = acad.ActiveDocument
            if doc is None:
                return
            for cmd in commands:
                doc.SendCommand(f'(setq c:{cmd} nil) \n')
            logger.info("AutoCAD から LISP コマンドを無効化しました: %s", commands)
        except Exception as e:
            logger.warning("LISP のアンロードに失敗しました: %s", e)
        finally:
            del acad

    def get_tool_palette_path_registry(self) -> Path | None:
        """レジストリから ToolPalettePath を取得する（AutoCAD 未起動時用）。"""
        import winreg
        import os

        base = r"Software\Autodesk\AutoCAD"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as acad_key:
                num_vers = winreg.QueryInfoKey(acad_key)[0]
                for vi in range(num_vers):
                    ver = winreg.EnumKey(acad_key, vi)
                    with winreg.OpenKey(acad_key, ver) as ver_key:
                        num_prods = winreg.QueryInfoKey(ver_key)[0]
                        for pi in range(num_prods):
                            prod = winreg.EnumKey(ver_key, pi)
                            profiles_path = f"{base}\\{ver}\\{prod}\\Profiles"
                            try:
                                with winreg.OpenKey(
                                    winreg.HKEY_CURRENT_USER, profiles_path
                                ) as prof_key:
                                    for pri in range(winreg.QueryInfoKey(prof_key)[0]):
                                        prof = winreg.EnumKey(prof_key, pri)
                                        gen_path = f"{profiles_path}\\{prof}\\General"
                                        try:
                                            with winreg.OpenKey(
                                                winreg.HKEY_CURRENT_USER, gen_path
                                            ) as gk:
                                                try:
                                                    val, _ = winreg.QueryValueEx(
                                                        gk, "ToolPalettePath"
                                                    )
                                                    if val:
                                                        first = val.split(";")[0].strip()
                                                        if first:
                                                            p = Path(
                                                                os.path.expandvars(first)
                                                            )
                                                            logger.debug(
                                                                "ToolPalettePath (registry): %s", p
                                                            )
                                                            return p
                                                except FileNotFoundError:
                                                    pass
                                        except OSError:
                                            pass
                            except OSError:
                                pass
        except OSError as e:
            logger.warning("ToolPalettePath のレジストリ取得に失敗: %s", e)
        return None

    def refresh_tool_palettes(self) -> None:
        """ツールパレットを閉じて再度開き、.atc の変更を AutoCAD に即時反映する。

        AutoCAD が起動中でアクティブドキュメントがある場合のみ実行する。
        起動していない場合は次回 AutoCAD 起動時に自動反映される。
        """
        acad = self._get_app()
        if acad is None:
            logger.debug("AutoCAD 未起動: パレット再読み込みをスキップ")
            return
        try:
            doc = acad.ActiveDocument
            if doc is None:
                logger.debug("アクティブドキュメントなし: パレット再読み込みをスキップ")
                return
            # パレットを閉じて再度開くことで .atc の変更を即時反映する
            # （_ToolPalettesClose / _ToolPalettes は AutoCAD 2027 で動作確認済み）
            doc.SendCommand("_ToolPalettesClose\n")
            doc.SendCommand("_ToolPalettes\n")
            logger.info("ツールパレットを再読み込みしました")
        except Exception as e:
            logger.warning("ツールパレットの再読み込みに失敗しました: %s", e)
        finally:
            del acad

    def get_tool_palette_path(self) -> Path | None:
        """AutoCAD のツールパレットフォルダパスを取得する。

        AutoCAD が起動していない場合は None を返す。
        """
        acad = self._get_app()
        if acad is None:
            return None
        try:
            tp_path = acad.Preferences.Files.ToolPalettePath
            if tp_path:
                first = tp_path.split(";")[0].strip()
                if first:
                    p = Path(first)
                    logger.debug("ToolPalettePath 取得: %s", p)
                    return p
        except Exception as e:
            logger.warning("ToolPalettePath の取得に失敗: %s", e)
        finally:
            del acad
        return None

    def add_tool_palette_path(self, palette_dir: str) -> OperationResult:
        """ToolPalettePath にパレットフォルダを追加する。"""
        acad = self._get_app()
        if acad is None:
            return OperationResult.fail(
                "AutoCAD が起動していません。"
            )

        try:
            pref = acad.Preferences.Files
            norm = _normalize(palette_dir)
            current_tp = pref.ToolPalettePath or ""

            if not self._path_in_list(norm, current_tp):
                new_tp = f"{palette_dir};{current_tp}" if current_tp else palette_dir
                pref.ToolPalettePath = new_tp
                logger.info("ToolPalettePath に追加しました: %s", palette_dir)

            return OperationResult.ok("ToolPalettePath を更新しました。")
        except Exception as e:
            logger.warning("ToolPalettePath の更新に失敗: %s", e)
            return OperationResult.fail(
                "ToolPalettePath の更新に失敗しました。",
                detail=str(e),
            )
        finally:
            del acad

    # ------------------------------------------------------------------
    # レジストリ操作（AutoCAD 未起動時用）
    # ------------------------------------------------------------------

    def remove_paths_from_registry(self, repo_path: str) -> None:
        """レジストリから指定パスを TRUSTEDPATHS / SupportPath から削除する（AutoCAD 未起動時用）。"""
        self._remove_path_from_registry(repo_path)

    def ensure_trusted_path_registry(self, repo_path: str) -> bool:
        """レジストリへ TRUSTEDPATHS / SupportPath を直接書き込む（AutoCAD 未起動時用）。

        Returns True if at least one profile was updated.
        """
        norm = _normalize(repo_path)
        return self._add_trusted_path_registry(repo_path, norm)

    # ------------------------------------------------------------------
    # プライベートメソッド
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_path(path: str) -> str:
        """パスを比較用に正規化する（公開ラッパー）。"""
        return _normalize(path)

    @staticmethod
    def _path_in_list(norm_path: str, semicolon_list: str) -> bool:
        """セミコロン区切りのパスリスト内に、正規化済みパスが含まれるか判定する。"""
        for p in semicolon_list.split(";"):
            if _normalize(p) == norm_path:
                return True
        return False

    def _add_trusted_path(self, acad, repo_path: str, norm: str) -> None:
        """TRUSTEDPATHS システム変数にパスを追加する。

        COM で失敗した場合はレジストリへの直接書き込みにフォールバックする。
        重複除去してから先頭に追加することで既存の重複もクリーンアップする。
        """
        # Method 1: GetSystemVariable / SetSystemVariable
        try:
            old_tp = str(acad.GetSystemVariable("TRUSTEDPATHS") or "")
            new_tp = _dedup_prepend(repo_path, norm, old_tp)
            if new_tp != old_tp:
                acad.SetSystemVariable("TRUSTEDPATHS", new_tp)
                logger.info(
                    "TRUSTEDPATHS を更新しました (SetSystemVariable): %s",
                    repo_path,
                )
            return
        except Exception as e:
            logger.warning("SetSystemVariable 失敗、フォールバックへ: %s", e)

        # Method 2: Preferences.Files.TrustedPaths
        try:
            pref = acad.Preferences.Files
            old_tp = str(pref.TrustedPaths or "")
            new_tp = _dedup_prepend(repo_path, norm, old_tp)
            if new_tp != old_tp:
                pref.TrustedPaths = new_tp
                logger.info(
                    "TRUSTEDPATHS を更新しました (Preferences.Files): %s",
                    repo_path,
                )
            return
        except Exception as e:
            logger.warning("Preferences.Files.TrustedPaths 失敗: %s", e)

        # Method 3: SendCommand で LISP 経由（AutoCAD 2027+ で COM API が非対応の場合）
        # ※ファイル経由だと TRUSTEDPATHS 外でセキュリティダイアログが出るため直接送信する
        try:
            doc = acad.ActiveDocument
            if doc is not None:
                lisp_path = repo_path.replace("\\", "\\\\")
                doc.SendCommand(
                    f'(progn (if (not (vl-string-search (strcase "{lisp_path}" T)'
                    f' (strcase (getvar "TRUSTEDPATHS") T)))'
                    f' (setvar "TRUSTEDPATHS" (strcat "{lisp_path};" (getvar "TRUSTEDPATHS"))))'
                    f' (princ))\n'
                )
                logger.info(
                    "TRUSTEDPATHS を更新しました (SendCommand): %s", repo_path
                )
                return
        except Exception as e:
            logger.warning("SendCommand による TRUSTEDPATHS 更新失敗: %s", e)

        # Method 4: レジストリへの直接書き込み（COM が使えない場合）
        if self._add_trusted_path_registry(repo_path, norm):
            logger.info(
                "TRUSTEDPATHS をレジストリに書き込みました（AutoCAD 再起動後に有効）: %s",
                repo_path,
            )
        else:
            logger.warning(
                "TRUSTEDPATHS の更新に失敗しました（手動設定が必要）: %s", repo_path
            )

    def _remove_path_from_registry(self, repo_path: str) -> None:
        """レジストリの TRUSTEDPATHS と ACAD（SupportPath）から指定パスを削除する。"""
        import winreg

        norm = _normalize(repo_path)
        try:
            base = r"Software\Autodesk\AutoCAD"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as acad_key:
                for vi in range(winreg.QueryInfoKey(acad_key)[0]):
                    ver = winreg.EnumKey(acad_key, vi)
                    with winreg.OpenKey(acad_key, ver) as ver_key:
                        for pi in range(winreg.QueryInfoKey(ver_key)[0]):
                            prod = winreg.EnumKey(ver_key, pi)
                            profiles_path = f"{base}\\{ver}\\{prod}\\Profiles"
                            try:
                                with winreg.OpenKey(
                                    winreg.HKEY_CURRENT_USER, profiles_path
                                ) as prof_key:
                                    for pri in range(winreg.QueryInfoKey(prof_key)[0]):
                                        prof = winreg.EnumKey(prof_key, pri)
                                        for subkey in ("General", "Variables"):
                                            sub_path = f"{profiles_path}\\{prof}\\{subkey}"
                                            try:
                                                with winreg.OpenKey(
                                                    winreg.HKEY_CURRENT_USER,
                                                    sub_path,
                                                    access=winreg.KEY_READ | winreg.KEY_WRITE,
                                                ) as sk:
                                                    key_names = ("TRUSTEDPATHS", "ACAD") if subkey == "General" else ("TRUSTEDPATHS",)
                                                    for key_name in key_names:
                                                        try:
                                                            val, vtype = winreg.QueryValueEx(sk, key_name)
                                                            new_val = ";".join(
                                                                p for p in val.split(";")
                                                                if _normalize(p) != norm
                                                            )
                                                            if new_val != val:
                                                                winreg.SetValueEx(sk, key_name, 0, vtype, new_val)
                                                                logger.info(
                                                                    "レジストリから削除 [%s\\%s] %s: %s",
                                                                    subkey, key_name, prof, repo_path,
                                                                )
                                                        except FileNotFoundError:
                                                            pass
                                            except OSError:
                                                pass
                            except OSError:
                                pass
        except OSError as e:
            logger.warning("レジストリからのパス削除に失敗しました: %s", e)

    def _add_trusted_path_registry(self, repo_path: str, norm: str) -> bool:
        """レジストリを直接書き換えて TRUSTEDPATHS と ACAD（SupportPath）にパスを追加する。

        HKCU\\Software\\Autodesk\\AutoCAD 以下のすべてのプロファイルを対象とする。
        - TRUSTEDPATHS: REG_SZ（セミコロン区切り）
        - ACAD: REG_EXPAND_SZ（セミコロン区切り・SupportPath）
        Returns True if at least one profile was updated.
        """
        import winreg

        updated = False
        try:
            base = r"Software\Autodesk\AutoCAD"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as acad_key:
                num_vers = winreg.QueryInfoKey(acad_key)[0]
                for vi in range(num_vers):
                    ver = winreg.EnumKey(acad_key, vi)
                    with winreg.OpenKey(acad_key, ver) as ver_key:
                        num_prods = winreg.QueryInfoKey(ver_key)[0]
                        for pi in range(num_prods):
                            prod = winreg.EnumKey(ver_key, pi)
                            profiles_path = f"{base}\\{ver}\\{prod}\\Profiles"
                            try:
                                with winreg.OpenKey(
                                    winreg.HKEY_CURRENT_USER, profiles_path
                                ) as prof_key:
                                    num_profs = winreg.QueryInfoKey(prof_key)[0]
                                    for pri in range(num_profs):
                                        prof = winreg.EnumKey(prof_key, pri)
                                        changed = False

                                        # General\TRUSTEDPATHS と ACAD（SupportPath）
                                        gen_path = f"{profiles_path}\\{prof}\\General"
                                        try:
                                            with winreg.OpenKey(
                                                winreg.HKEY_CURRENT_USER,
                                                gen_path,
                                                access=winreg.KEY_READ | winreg.KEY_WRITE,
                                            ) as gen_key:
                                                # TRUSTEDPATHS (REG_SZ)
                                                try:
                                                    current_tp, _ = winreg.QueryValueEx(
                                                        gen_key, "TRUSTEDPATHS"
                                                    )
                                                except FileNotFoundError:
                                                    current_tp = ""
                                                new_tp = _dedup_prepend(repo_path, norm, current_tp)
                                                if new_tp != current_tp:
                                                    winreg.SetValueEx(
                                                        gen_key, "TRUSTEDPATHS", 0,
                                                        winreg.REG_SZ, new_tp,
                                                    )
                                                    changed = True

                                                # ACAD = SupportPath (REG_EXPAND_SZ)
                                                try:
                                                    current_acad, acad_type = winreg.QueryValueEx(
                                                        gen_key, "ACAD"
                                                    )
                                                except FileNotFoundError:
                                                    current_acad, acad_type = "", winreg.REG_EXPAND_SZ
                                                new_acad = _dedup_prepend(repo_path, norm, current_acad)
                                                if new_acad != current_acad:
                                                    winreg.SetValueEx(
                                                        gen_key, "ACAD", 0,
                                                        acad_type, new_acad,
                                                    )
                                                    changed = True
                                        except OSError:
                                            pass

                                        # Variables\TRUSTEDPATHS
                                        # AutoCAD はこのキーを実行時値の永続化に使用しており、
                                        # Options ダイアログはこちらを表示する。
                                        var_path = f"{profiles_path}\\{prof}\\Variables"
                                        try:
                                            with winreg.CreateKeyEx(
                                                winreg.HKEY_CURRENT_USER,
                                                var_path,
                                                access=winreg.KEY_READ | winreg.KEY_WRITE,
                                            ) as var_key:
                                                try:
                                                    current_vtp, _ = winreg.QueryValueEx(
                                                        var_key, "TRUSTEDPATHS"
                                                    )
                                                except FileNotFoundError:
                                                    current_vtp = ""
                                                new_vtp = _dedup_prepend(repo_path, norm, current_vtp)
                                                if new_vtp != current_vtp:
                                                    winreg.SetValueEx(
                                                        var_key, "TRUSTEDPATHS", 0,
                                                        winreg.REG_SZ, new_vtp,
                                                    )
                                                    changed = True
                                        except OSError:
                                            pass

                                        if changed:
                                            logger.info(
                                                "SupportPath/TRUSTEDPATHS をレジストリに追加 [%s/%s/%s]",
                                                ver, prod, prof,
                                            )
                                            updated = True
                            except OSError:
                                pass
        except OSError as e:
            logger.warning("AutoCAD レジストリへのアクセスに失敗しました: %s", e)
        return updated

    def _remove_trusted_path(self, acad, repo_path: str, norm: str) -> None:
        """TRUSTEDPATHS システム変数からパスを削除する。"""
        try:
            old_tp = str(acad.GetSystemVariable("TRUSTEDPATHS") or "")
            new_tp = ";".join(
                p for p in old_tp.split(";") if _normalize(p) != norm
            )
            acad.SetSystemVariable("TRUSTEDPATHS", new_tp)
            logger.info(
                "TRUSTEDPATHS から削除しました (SetSystemVariable): %s",
                repo_path,
            )
            return
        except Exception as e:
            logger.warning("SetSystemVariable 失敗、フォールバックへ: %s", e)

        try:
            pref = acad.Preferences.Files
            old_tp = str(pref.TrustedPaths or "")
            new_tp = ";".join(
                p for p in old_tp.split(";") if _normalize(p) != norm
            )
            pref.TrustedPaths = new_tp
            logger.info(
                "TRUSTEDPATHS から削除しました (Preferences.Files): %s",
                repo_path,
            )
        except Exception as e:
            logger.warning("TRUSTEDPATHS の削除に失敗しました: %s", e)

    def _get_app(self):  # type: ignore[return]
        """起動中の AutoCAD インスタンスを取得する。

        GetActiveObject で接続を試み、失敗した場合は None を返す。
        汎用 ProgID で接続できない場合はバージョン付き ProgID を順に試す。
        """
        try:
            import win32com.client
        except ImportError:
            logger.warning("pywin32 がインストールされていません")
            return None

        # 汎用 → バージョン付きの順に試行（新しいバージョンを優先）
        prog_ids = ["AutoCAD.Application"]
        prog_ids.extend(f"AutoCAD.Application.{v}" for v in range(26, 23, -1))

        for prog_id in prog_ids:
            try:
                acad = win32com.client.GetActiveObject(prog_id)
                _ = acad.Visible
                return acad
            except Exception:
                continue
        return None
