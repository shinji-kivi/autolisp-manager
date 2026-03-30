using Autodesk.AutoCAD.Runtime;

namespace AutoLispPanel;

public class Commands
{
    [CommandMethod("LISPMANAGERPANEL")]
    public void ShowPanel()
    {
        PaletteManager.Show();
    }
}
