using System.IO;
using System.Text.Json;

namespace AutoLispPanel.Core;

public static class ConfigReader
{
    private static readonly string ConfigPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        ".lisp_manager_config.json");

    /// <summary>
    /// repo_path を返す。設定ファイルが存在しないか読めない場合は null。
    /// </summary>
    public static string? GetRepoPath()
    {
        if (!File.Exists(ConfigPath))
            return null;

        try
        {
            var json = File.ReadAllText(ConfigPath);
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("repo_path", out var prop))
                return prop.GetString();
        }
        catch
        {
            // 読み取り失敗は無視
        }

        return null;
    }

    /// <summary>
    /// acaddoc.lsp のフルパスを返す。repo_path が取得できない場合は null。
    /// </summary>
    public static string? GetAcaddocPath()
    {
        var repo = GetRepoPath();
        if (repo == null) return null;
        return Path.Combine(repo, "acaddoc.lsp");
    }
}
