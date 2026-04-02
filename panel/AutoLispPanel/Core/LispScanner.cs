using System.IO;
using System.Text.RegularExpressions;
using AutoLispPanel.Models;

namespace AutoLispPanel.Core;

public static class LispScanner
{
    // acaddoc.lsp の有効行: (load "stem" nil) または (load "stem")
    private static readonly Regex EnabledLoadRe = new(
        @"^\s*\(load\s+""([^""]+)""",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    // コメントアウト行（無効）
    private static readonly Regex DisabledLoadRe = new(
        @"^\s*;;",
        RegexOptions.Compiled);

    // defun c: パターン
    private static readonly Regex DefunRe = new(
        @"\(\s*defun\s+c:([a-zA-Z_][a-zA-Z0-9_\-]*)",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    // @button メタデータパターン
    private static readonly Regex ButtonRe = new(
        @"^;;;\s*@button\s+([a-zA-Z_][a-zA-Z0-9_\-]*)\s+(.+)$",
        RegexOptions.Multiline | RegexOptions.Compiled);

    // @description メタデータパターン
    private static readonly Regex DescriptionRe = new(
        @"^;;;\s*@description\s+(.+)$",
        RegexOptions.Multiline | RegexOptions.Compiled);

    /// <summary>
    /// acaddoc.lsp を解析し、有効な LISP ファイルのコマンド一覧を返す。
    /// </summary>
    public static List<LispCommand> Scan(string acaddocPath)
    {
        var result = new List<LispCommand>();

        if (!File.Exists(acaddocPath))
            return result;

        var repoDir = Path.GetDirectoryName(acaddocPath)!;
        var lines = File.ReadAllLines(acaddocPath);

        foreach (var line in lines)
        {
            // コメントアウト行はスキップ
            if (DisabledLoadRe.IsMatch(line))
                continue;

            var loadMatch = EnabledLoadRe.Match(line);
            if (!loadMatch.Success)
                continue;

            var stem = loadMatch.Groups[1].Value;
            // stem に .lsp が付いていない場合は追加
            var fileName = stem.EndsWith(".lsp", StringComparison.OrdinalIgnoreCase)
                ? stem
                : stem + ".lsp";

            var lispPath = Path.Combine(repoDir, fileName);
            if (!File.Exists(lispPath))
                continue;

            var content = ReadFileContent(lispPath);
            if (content == null)
                continue;

            var labels = ExtractButtonLabels(content);
            var commands = ExtractCommandsFromContent(content);
            foreach (var cmd in commands)
            {
                var label = labels.TryGetValue(cmd, out var l) ? l : cmd;
                result.Add(new LispCommand(cmd, Path.GetFileName(lispPath), label));
            }
        }

        return result;
    }

    private static string? ReadFileContent(string lispPath)
    {
        try { return File.ReadAllText(lispPath); }
        catch { return null; }
    }

    private static IEnumerable<string> ExtractCommandsFromContent(string content)
    {
        foreach (Match m in DefunRe.Matches(content))
            yield return m.Groups[1].Value.ToUpperInvariant();
    }

    private static Dictionary<string, string> ExtractButtonLabels(string content)
    {
        var labels = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (Match m in ButtonRe.Matches(content))
            labels[m.Groups[1].Value.ToUpperInvariant()] = m.Groups[2].Value.Trim();
        return labels;
    }

    private static string ExtractDescription(string content)
    {
        var m = DescriptionRe.Match(content);
        return m.Success ? m.Groups[1].Value.Trim() : "";
    }

    /// <summary>
    /// acaddoc.lsp を解析し、LISPファイルごとにグループ化したコマンド一覧を返す。
    /// </summary>
    public static List<LispGroup> ScanGrouped(string acaddocPath)
    {
        var result = new List<LispGroup>();

        if (!File.Exists(acaddocPath))
            return result;

        var repoDir = Path.GetDirectoryName(acaddocPath)!;
        var lines = File.ReadAllLines(acaddocPath);

        foreach (var line in lines)
        {
            if (DisabledLoadRe.IsMatch(line))
                continue;

            var loadMatch = EnabledLoadRe.Match(line);
            if (!loadMatch.Success)
                continue;

            var stem = loadMatch.Groups[1].Value;
            var fileName = stem.EndsWith(".lsp", StringComparison.OrdinalIgnoreCase)
                ? stem
                : stem + ".lsp";

            // ag-help.lsp はユーティリティなのでパネルに表示しない
            if (fileName.Equals("ag-help.lsp", StringComparison.OrdinalIgnoreCase))
                continue;

            var lispPath = Path.Combine(repoDir, fileName);
            if (!File.Exists(lispPath))
                continue;

            var content = ReadFileContent(lispPath);
            if (content == null)
                continue;

            var labels = ExtractButtonLabels(content);
            var description = ExtractDescription(content);
            var commands = new List<LispCommand>();

            foreach (var cmd in ExtractCommandsFromContent(content))
            {
                var label = labels.TryGetValue(cmd, out var l) ? l : cmd;
                commands.Add(new LispCommand(cmd, Path.GetFileName(lispPath), label));
            }

            if (commands.Count == 0)
                continue;

            // 表示名: @description があればそれを使い、なければファイル名
            var displayName = string.IsNullOrEmpty(description)
                ? Path.GetFileNameWithoutExtension(lispPath)
                : description;

            result.Add(new LispGroup(Path.GetFileName(lispPath), displayName, commands));
        }

        return result;
    }
}
