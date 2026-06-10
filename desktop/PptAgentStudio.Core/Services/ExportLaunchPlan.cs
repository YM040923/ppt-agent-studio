namespace PptAgentStudio_App.Services;

public sealed record ExportLaunchPlan(string FileName, string Arguments)
{
    public static ExportLaunchPlan CreateRevealInExplorer(string pptxPath)
    {
        if (string.IsNullOrWhiteSpace(pptxPath))
        {
            throw new ArgumentException("pptx path is required", nameof(pptxPath));
        }

        return new ExportLaunchPlan(
            FileName: "explorer.exe",
            Arguments: $"/select,\"{pptxPath.Trim()}\"");
    }
}
