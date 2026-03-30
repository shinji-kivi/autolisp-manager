using Autodesk.AutoCAD.Runtime;
using AcadApp = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: ExtensionApplication(typeof(AutoLispPanel.App))]

namespace AutoLispPanel;

public class App : IExtensionApplication
{
    public void Initialize()
    {
        AcadApp.Idle += OnFirstIdle;
    }

    private void OnFirstIdle(object? sender, EventArgs e)
    {
        AcadApp.Idle -= OnFirstIdle;
        PaletteManager.Show();
        RibbonHelper.CreateTab();
    }

    public void Terminate()
    {
        PaletteManager.Close();
    }
}
