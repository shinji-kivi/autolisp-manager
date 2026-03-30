using System.IO;
using Autodesk.Windows;

namespace AutoLispPanel;

public static class RibbonHelper
{
    private const string TabId = "AutoLispPanel_Tab";

    public static void CreateTab()
    {
        var ribbon = ComponentManager.Ribbon;
        if (ribbon == null) return;

        // 既に作成済みなら何もしない
        foreach (var t in ribbon.Tabs)
            if (t.Id == TabId) return;

        var tab = new RibbonTab
        {
            Title = "LISP",
            Id = TabId,
            IsContextualTab = false
        };

        var panel = new RibbonPanelSource { Title = "Manager" };

        // パネルトグルボタン
        var toggleBtn = new RibbonButton
        {
            Text = "LISP Manager",
            ShowText = true,
            Size = RibbonItemSize.Large,
            LargeImage = IconHelper.CreateLarge(),
            Image = IconHelper.CreateSmall(),
            Orientation = System.Windows.Controls.Orientation.Vertical,
            CommandHandler = new PanelToggleCommand()
        };
        panel.Items.Add(toggleBtn);

        panel.Items.Add(new RibbonSeparator());

        // 管理ツール起動ボタン
        var launchBtn = new RibbonButton
        {
            Text = "管理ツール",
            ShowText = true,
            Size = RibbonItemSize.Large,
            LargeImage = IconHelper.CreateLaunchLarge(),
            Image = IconHelper.CreateLaunchSmall(),
            Orientation = System.Windows.Controls.Orientation.Vertical,
            CommandHandler = new LaunchManagerCommand()
        };
        panel.Items.Add(launchBtn);

        var ribbonPanel = new RibbonPanel { Source = panel };
        tab.Panels.Add(ribbonPanel);
        ribbon.Tabs.Add(tab);
        tab.IsActive = false;
    }

    // パネルの表示/非表示を切り替える
    private class PanelToggleCommand : System.Windows.Input.ICommand
    {
        public event EventHandler? CanExecuteChanged;
        public bool CanExecute(object? parameter) => true;
        public void Execute(object? parameter) => PaletteManager.Toggle();
    }

    // AutoLISP管理ツール.exe を起動する
    private class LaunchManagerCommand : System.Windows.Input.ICommand
    {
        public event EventHandler? CanExecuteChanged;
        public bool CanExecute(object? parameter) => true;
        public void Execute(object? parameter)
        {
            var exePath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "AutoLISP管理ツール",
                "AutoLISP管理ツール.exe");
            if (File.Exists(exePath))
                System.Diagnostics.Process.Start(
                    new System.Diagnostics.ProcessStartInfo(exePath) { UseShellExecute = true });
        }
    }
}
