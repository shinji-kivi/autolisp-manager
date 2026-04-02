namespace AutoLispPanel.Models;

public record LispGroup(
    string FileName,
    string DisplayName,
    List<LispCommand> Commands);
