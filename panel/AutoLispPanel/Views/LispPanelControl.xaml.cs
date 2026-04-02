using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using AcadApp = Autodesk.AutoCAD.ApplicationServices.Application;
using WpfButton = System.Windows.Controls.Button;
using AutoLispPanel.Core;
using AutoLispPanel.Models;

namespace AutoLispPanel.Views;

// 基底クラスは XAML 側が宣言済みのため、ここでは IDisposable のみ追加
public partial class LispPanelControl : IDisposable
{
    private FileSystemWatcher? _watcher;
    private string? _acaddocPath;

    public LispPanelControl()
    {
        InitializeComponent();
        Loaded += OnLoaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        Refresh();
        StartWatcher();
    }

    private void Refresh()
    {
        _acaddocPath = ConfigReader.GetAcaddocPath();

        if (_acaddocPath == null)
        {
            GroupList.ItemsSource = null;
            StatusText.Text = "設定ファイルが見つかりません";
            return;
        }

        var groups = LispScanner.ScanGrouped(_acaddocPath);
        GroupList.ItemsSource = groups;
        var totalCommands = groups.Sum(g => g.Commands.Count);
        StatusText.Text = $"{groups.Count} ファイル / {totalCommands} コマンド";
    }

    private void StartWatcher()
    {
        _watcher?.Dispose();
        _watcher = null;

        if (_acaddocPath == null || !File.Exists(_acaddocPath))
            return;

        var dir = Path.GetDirectoryName(_acaddocPath)!;
        var file = Path.GetFileName(_acaddocPath);

        _watcher = new FileSystemWatcher(dir, file)
        {
            NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.Size,
            EnableRaisingEvents = true
        };

        _watcher.Changed += (_, _) => Dispatcher.BeginInvoke(Refresh);
        _watcher.Created += (_, _) => Dispatcher.BeginInvoke(Refresh);
    }

    private void OnCommandButtonClick(object sender, RoutedEventArgs e)
    {
        if (sender is not WpfButton btn) return;
        if (btn.DataContext is not LispCommand cmd) return;

        var doc = AcadApp.DocumentManager.MdiActiveDocument;
        if (doc == null) return;

        doc.SendStringToExecute(cmd.CommandName + " ", true, false, false);
    }

    private void OnRefreshClick(object sender, RoutedEventArgs e)
    {
        Refresh();
        StartWatcher();
    }

    public void Dispose()
    {
        _watcher?.Dispose();
    }
}
