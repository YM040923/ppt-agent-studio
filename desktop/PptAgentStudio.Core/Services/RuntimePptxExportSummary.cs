using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimePptxExportSummary(string Path, int SlideCount)
{
    public static RuntimePptxExportSummary FromPayload(JsonElement payload)
    {
        var path = ReadString(payload, "path");
        var slideCount = 0;
        if (payload.TryGetProperty("slide_count", out var slideCountValue)
            && slideCountValue.ValueKind == JsonValueKind.Number
            && slideCountValue.TryGetInt32(out var parsedSlideCount)
            && parsedSlideCount > 0)
        {
            slideCount = parsedSlideCount;
        }

        return new RuntimePptxExportSummary(path, slideCount);
    }

    public string ToChatMessage()
    {
        var slideText = SlideCount <= 0
            ? ""
            : SlideCount == 1 ? "1 slide" : $"{SlideCount} slides";

        if (!string.IsNullOrWhiteSpace(slideText) && !string.IsNullOrWhiteSpace(Path))
        {
            return $"Editable PPTX export is ready: {slideText} at {Path}";
        }

        if (!string.IsNullOrWhiteSpace(slideText))
        {
            return $"Editable PPTX export is ready: {slideText}.";
        }

        return string.IsNullOrWhiteSpace(Path)
            ? "Editable PPTX export is ready."
            : $"Editable PPTX export is ready: {Path}";
    }

    public string ToStatusText(int? deckRevision)
    {
        var revisionText = deckRevision is null ? "" : $" at revision {deckRevision}";
        var slideText = SlideCount <= 0
            ? ""
            : SlideCount == 1 ? ": 1 slide" : $": {SlideCount} slides";
        return $"PPTX exported{revisionText}{slideText}.";
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
