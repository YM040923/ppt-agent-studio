using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimePreviewSummary(string Title, int SlideCount)
{
    public static RuntimePreviewSummary FromPayload(JsonElement payload)
    {
        var title = ReadString(payload, "deck_title");
        if (string.IsNullOrWhiteSpace(title))
        {
            title = ReadString(payload, "title");
        }

        var slideCount = 0;
        if (payload.TryGetProperty("slide_count", out var slideCountValue)
            && slideCountValue.ValueKind == JsonValueKind.Number
            && slideCountValue.TryGetInt32(out var parsedSlideCount)
            && parsedSlideCount > 0)
        {
            slideCount = parsedSlideCount;
        }

        return new RuntimePreviewSummary(title, slideCount);
    }

    public string ToChatMessage()
    {
        var slideText = FormatSlideCount();
        if (!string.IsNullOrWhiteSpace(Title) && !string.IsNullOrWhiteSpace(slideText))
        {
            return $"**Preview updated:** {Title} ({slideText}).";
        }

        if (!string.IsNullOrWhiteSpace(Title))
        {
            return $"**Preview updated:** {Title}.";
        }

        if (!string.IsNullOrWhiteSpace(slideText))
        {
            return $"**Preview updated:** {slideText}.";
        }

        return "**Preview updated** from the local Agent runtime.";
    }

    public string ToStatusText(int? deckRevision)
    {
        var revisionText = deckRevision is null ? "" : $" at revision {deckRevision}";
        var slideText = FormatSlideCount();
        if (!string.IsNullOrWhiteSpace(slideText))
        {
            return $"Preview ready{revisionText}: {slideText}.";
        }

        return $"Preview ready{revisionText}.";
    }

    private string FormatSlideCount()
    {
        return SlideCount <= 0
            ? ""
            : SlideCount == 1 ? "1 slide" : $"{SlideCount} slides";
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
