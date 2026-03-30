using System.Globalization;
using System.IO;
using System.Reflection;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using WpfBrushes = System.Windows.Media.Brushes;
using WpfColor = System.Windows.Media.Color;
using WpfFontFamily = System.Windows.Media.FontFamily;
using WpfPen = System.Windows.Media.Pen;
using WpfPoint = System.Windows.Point;

namespace AutoLispPanel;

public static class IconHelper
{
    private static readonly WpfColor DarkBg   = WpfColor.FromRgb(41,  41,  41);
    private static readonly WpfColor LightGray = WpfColor.FromRgb(200, 200, 200);
    private static readonly WpfColor AccentBlue = WpfColor.FromRgb(70, 160, 230);

    // ---------- バンドル内の logo.png を読み込む ----------

    private static BitmapSource? TryLoadLogo(int size)
    {
        try
        {
            // DLL は bundle/Contents/20XX/ に置かれる → 2階層上がると bundle ルート
            var dllDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)!;
            var bundleDir = Path.GetFullPath(Path.Combine(dllDir, "..", ".."));
            var logoPath = Path.Combine(bundleDir, "logo.png");
            if (!File.Exists(logoPath)) return null;

            var bmp = new BitmapImage();
            bmp.BeginInit();
            bmp.UriSource = new Uri(logoPath);
            bmp.DecodePixelWidth = size;
            bmp.DecodePixelHeight = size;
            bmp.CacheOption = BitmapCacheOption.OnLoad;
            bmp.EndInit();
            bmp.Freeze();
            return bmp;
        }
        catch
        {
            return null;
        }
    }

    // ---------- パネルトグルボタン用アイコン ----------

    public static BitmapSource CreateLarge() =>
        TryLoadLogo(32) ?? CreateLargeDrawn();

    public static BitmapSource CreateSmall() =>
        TryLoadLogo(16) ?? CreateSmallDrawn();

    private static BitmapSource CreateLargeDrawn()
    {
        return Render(32, 32, ctx =>
        {
            ctx.DrawRoundedRectangle(
                new SolidColorBrush(DarkBg),
                new WpfPen(new SolidColorBrush(WpfColor.FromRgb(80, 80, 80)), 1),
                new Rect(0, 0, 32, 32), 4, 4);

            var lText = new FormattedText(
                "L",
                CultureInfo.InvariantCulture,
                System.Windows.FlowDirection.LeftToRight,
                new Typeface(new WpfFontFamily("Arial"), FontStyles.Normal, FontWeights.Black, FontStretches.Normal),
                20,
                new SolidColorBrush(WpfColor.FromRgb(210, 45, 45)),
                96);
            ctx.DrawText(lText, new WpfPoint((32 - lText.Width) / 2, 1));

            var paren = new FormattedText(
                "( )",
                CultureInfo.InvariantCulture,
                System.Windows.FlowDirection.LeftToRight,
                new Typeface(new WpfFontFamily("Consolas"), FontStyles.Normal, FontWeights.Bold, FontStretches.Normal),
                9,
                new SolidColorBrush(LightGray),
                96);
            ctx.DrawText(paren, new WpfPoint((32 - paren.Width) / 2, 21));
        });
    }

    private static BitmapSource CreateSmallDrawn()
    {
        return Render(16, 16, ctx =>
        {
            ctx.DrawRoundedRectangle(
                new SolidColorBrush(DarkBg),
                new WpfPen(new SolidColorBrush(WpfColor.FromRgb(80, 80, 80)), 0.5),
                new Rect(0, 0, 16, 16), 2, 2);

            var lText = new FormattedText(
                "L",
                CultureInfo.InvariantCulture,
                System.Windows.FlowDirection.LeftToRight,
                new Typeface(new WpfFontFamily("Arial"), FontStyles.Normal, FontWeights.Black, FontStretches.Normal),
                11,
                new SolidColorBrush(WpfColor.FromRgb(210, 45, 45)),
                96);
            ctx.DrawText(lText, new WpfPoint((16 - lText.Width) / 2, 0));

            var paren = new FormattedText(
                "()",
                CultureInfo.InvariantCulture,
                System.Windows.FlowDirection.LeftToRight,
                new Typeface(new WpfFontFamily("Consolas"), FontStyles.Normal, FontWeights.Bold, FontStretches.Normal),
                6,
                new SolidColorBrush(LightGray),
                96);
            ctx.DrawText(paren, new WpfPoint((16 - paren.Width) / 2, 10));
        });
    }

    // ---------- 管理ツール起動ボタン用アイコン（ウィンドウ＋矢印） ----------

    public static BitmapSource CreateLaunchLarge()
    {
        return Render(32, 32, ctx =>
        {
            // 背景
            ctx.DrawRoundedRectangle(
                new SolidColorBrush(DarkBg),
                new WpfPen(new SolidColorBrush(WpfColor.FromRgb(80, 80, 80)), 1),
                new Rect(0, 0, 32, 32), 4, 4);

            // ウィンドウ枠
            var framePen = new WpfPen(new SolidColorBrush(LightGray), 1.5);
            ctx.DrawRectangle(null, framePen, new Rect(4, 7, 18, 14));
            // タイトルバー線
            ctx.DrawLine(framePen, new WpfPoint(4, 11), new WpfPoint(22, 11));

            // 起動矢印（右上向き）
            var arrowBrush = new SolidColorBrush(AccentBlue);
            var arrow = new StreamGeometry();
            using (var gc = arrow.Open())
            {
                gc.BeginFigure(new WpfPoint(20, 8), true, true);
                gc.LineTo(new WpfPoint(28, 8), true, false);
                gc.LineTo(new WpfPoint(28, 16), true, false);
                gc.LineTo(new WpfPoint(25, 13), true, false);
                gc.LineTo(new WpfPoint(20, 18), true, false);
                gc.LineTo(new WpfPoint(18, 16), true, false);
                gc.LineTo(new WpfPoint(23, 11), true, false);
            }
            arrow.Freeze();
            ctx.DrawGeometry(arrowBrush, null, arrow);
        });
    }

    public static BitmapSource CreateLaunchSmall()
    {
        return Render(16, 16, ctx =>
        {
            ctx.DrawRoundedRectangle(
                new SolidColorBrush(DarkBg),
                new WpfPen(new SolidColorBrush(WpfColor.FromRgb(80, 80, 80)), 0.5),
                new Rect(0, 0, 16, 16), 2, 2);

            var framePen = new WpfPen(new SolidColorBrush(LightGray), 1);
            ctx.DrawRectangle(null, framePen, new Rect(2, 4, 9, 7));
            ctx.DrawLine(framePen, new WpfPoint(2, 6), new WpfPoint(11, 6));

            var arrow = new StreamGeometry();
            using (var gc = arrow.Open())
            {
                gc.BeginFigure(new WpfPoint(10, 3), true, true);
                gc.LineTo(new WpfPoint(14, 3), true, false);
                gc.LineTo(new WpfPoint(14, 7), true, false);
                gc.LineTo(new WpfPoint(12, 5), true, false);
                gc.LineTo(new WpfPoint(9,  8), true, false);
                gc.LineTo(new WpfPoint(8,  7), true, false);
                gc.LineTo(new WpfPoint(11, 4), true, false);
            }
            arrow.Freeze();
            ctx.DrawGeometry(new SolidColorBrush(AccentBlue), null, arrow);
        });
    }

    // ---------- 共通描画ユーティリティ ----------

    private static BitmapSource Render(int w, int h, Action<DrawingContext> draw)
    {
        var visual = new DrawingVisual();
        using (var ctx = visual.RenderOpen())
            draw(ctx);
        var bmp = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
        bmp.Render(visual);
        bmp.Freeze();
        return bmp;
    }
}
