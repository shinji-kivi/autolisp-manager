using System.Windows.Forms;
using System.Windows.Forms.Integration;
using Autodesk.AutoCAD.Windows;
using AutoLispPanel.Views;

namespace AutoLispPanel;

public static class PaletteManager
{
    private static PaletteSet? _paletteSet;
    private static LispPanelControl? _wpfControl;

    public static void Show()
    {
        if (_paletteSet == null)
        {
            _wpfControl = new LispPanelControl();

            var host = new ElementHost
            {
                Child = _wpfControl,
                Dock = DockStyle.Fill
            };

            _paletteSet = new PaletteSet(
                "LISP Manager",
                new Guid("C3D4E5F6-A7B8-9012-CDEF-123456789ABC"))
            {
                Size = new System.Drawing.Size(240, 400),
                Visible = true
            };
            _paletteSet.Add("コマンド一覧", host);
        }

        _paletteSet.Visible = true;
    }

    public static void Toggle()
    {
        if (_paletteSet == null)
        {
            Show();
            return;
        }
        _paletteSet.Visible = !_paletteSet.Visible;
    }

    public static void Close()
    {
        _wpfControl?.Dispose();
        _paletteSet?.Dispose();
        _paletteSet = null;
        _wpfControl = null;
    }
}
