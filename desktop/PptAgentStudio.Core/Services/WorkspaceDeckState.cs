namespace PptAgentStudio_App.Services;

public sealed class WorkspaceDeckState
{
    public string LastPptxPath { get; private set; } = "";

    public bool CanExport => !string.IsNullOrWhiteSpace(LastPptxPath);

    public void RecordPptx(string? path)
    {
        LastPptxPath = string.IsNullOrWhiteSpace(path) ? "" : path;
    }

    public void Reset()
    {
        LastPptxPath = "";
    }
}
