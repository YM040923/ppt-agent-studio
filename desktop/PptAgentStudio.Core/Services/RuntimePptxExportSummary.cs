using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimePptxExportSummary(string Path, string Title, int SlideCount, string ThemeName = "")
{
    public static RuntimePptxExportSummary FromPayload(JsonElement payload)
    {
        var path = ReadString(payload, "path");
        var title = ReadString(payload, "deck_title");
        var themeName = ReadString(payload, "theme_name");
        var slideCount = 0;
        if (payload.TryGetProperty("slide_count", out var slideCountValue)
            && slideCountValue.ValueKind == JsonValueKind.Number
            && slideCountValue.TryGetInt32(out var parsedSlideCount)
            && parsedSlideCount > 0)
        {
            slideCount = parsedSlideCount;
        }

        return new RuntimePptxExportSummary(path, title, slideCount, themeName);
    }

    public string ToChatMessage()
    {
        var detailText = DisplayText();

        if (!string.IsNullOrWhiteSpace(detailText) && !string.IsNullOrWhiteSpace(Path))
        {
            return $"**Editable PPTX export is ready:** {detailText} at `{Path}`";
        }

        if (!string.IsNullOrWhiteSpace(detailText))
        {
            return $"**Editable PPTX export is ready:** {detailText}.";
        }

        return string.IsNullOrWhiteSpace(Path)
            ? "**Editable PPTX export is ready.**"
            : $"**Editable PPTX export is ready:** `{Path}`";
    }

    public string ToStatusText(int? deckRevision)
    {
        var revisionText = deckRevision is null ? "" : $" at revision {deckRevision}";
        var displayText = DisplayText();
        var detailText = string.IsNullOrWhiteSpace(displayText) ? "" : $": {displayText}";
        return $"PPTX exported{revisionText}{detailText}.";
    }

    private string DisplayText()
    {
        var details = DetailParts();
        var detailsText = string.Join(", ", details);
        if (string.IsNullOrWhiteSpace(Title))
        {
            return detailsText;
        }

        return string.IsNullOrWhiteSpace(detailsText)
            ? Title
            : $"{Title} ({detailsText})";
    }

    private List<string> DetailParts()
    {
        var details = new List<string>();
        if (SlideCount > 0)
        {
            details.Add(SlideCount == 1 ? "1 slide" : $"{SlideCount} slides");
        }

        if (!string.IsNullOrWhiteSpace(ThemeName))
        {
            details.Add($"theme {ThemeName}");
        }

        return details;
    }

    private static string ReadString(JsonElement payload, string propertyName)
    {
        if (payload.TryGetProperty(propertyName, out var property)
            && property.ValueKind == JsonValueKind.String)
        {
            return property.GetString() ?? "";
        }

        return "";
    }
}
