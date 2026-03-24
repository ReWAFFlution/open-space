using Content.Shared.Administration.Logs;
using Content.Shared.Database; // OpenSpace-Edit
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;
using Robust.Shared.Utility; // OpenSpace-Edit

namespace Content.Client.Administration.UI.CustomControls;

public sealed class AdminLogLabel : RichTextLabel
{
    public AdminLogLabel(ref SharedAdminLog log, HSeparator separator)
    {
        Log = log;
        Separator = separator;
        // OpenSpace-Edit Start
        var impactColor = GetImpactColor(log.Impact);
        var impactText = $"[color={impactColor}]█[/color]";

        var formatted = new FormattedMessage();
        formatted.AddMarkupOrThrow($"{impactText} [bold]{log.Date:HH:mm:ss}[/bold]: {log.Message}");

        SetMessage(formatted);
        // OpenSpace-Edit End
        OnVisibilityChanged += VisibilityChanged;
    }

    public new SharedAdminLog Log { get; }

    public HSeparator Separator { get; }

    private void VisibilityChanged(Control control)
    {
        Separator.Visible = Visible;
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);

        OnVisibilityChanged -= VisibilityChanged;
    }
    // OpenSpace-Edit Start
    private static string GetImpactColor(LogImpact impact) => impact switch
    {
        LogImpact.Extreme => "red",
        LogImpact.High => "orange",
        LogImpact.Medium => "yellow",
        LogImpact.Low => "lightgreen",
        _ => "gray"
    };
    // OpenSpace-Edit End
}
