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

            var commands = ExtractCommands(lispPath);
            foreach (var cmd in commands)
                result.Add(new LispCommand(cmd, Path.GetFileName(lispPath)));
        }

        return result;
    }

    private static IEnumerable<string> ExtractCommands(string lispPath)
    {
        string content;
        try
        {
            content = File.ReadAllText(lispPath);
        }
        catch
        {
            yield break;
        }

        foreach (Match m in DefunRe.Matches(content))
            yield return m.Groups[1].Value.ToUpperInvariant();
    }
}
