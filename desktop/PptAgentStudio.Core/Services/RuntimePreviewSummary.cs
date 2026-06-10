using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimePreviewSummary(string Title, int SlideCount, string ThemeName = "")
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

        return new RuntimePreviewSummary(title, slideCount, ReadString(payload, "theme_name"));
    }

    public string ToChatMessage()
    {
        var detailText = FormatDetails();
        if (!string.IsNullOrWhiteSpace(Title) && !string.IsNullOrWhiteSpace(detailText))
        {
            return $"**Preview updated:** {Title} ({detailText}).";
        }

        if (!string.IsNullOrWhiteSpace(Title))
        {
            return $"**Preview updated:** {Title}.";
        }

        if (!string.IsNullOrWhiteSpace(detailText))
        {
            return $"**Preview updated:** {detailText}.";
        }

        return "**Preview updated** from the local Agent runtime.";
    }

    public string ToStatusText(int? deckRevision)
    {
        var revisionText = deckRevision is null ? "" : $" at revision {deckRevision}";
        var detailText = FormatDetails();
        if (!string.IsNullOrWhiteSpace(detailText))
        {
            return $"Preview ready{revisionText}: {detailText}.";
        }

        return $"Preview ready{revisionText}.";
    }

    private string FormatDetails()
    {
        var slideText = FormatSlideCount();
        var themeText = string.IsNullOrWhiteSpace(ThemeName) ? "" : $"theme {ThemeName}";
        if (!string.IsNullOrWhiteSpace(slideText) && !string.IsNullOrWhiteSpace(themeText))
        {
            return $"{slideText}, {themeText}";
        }

        return string.IsNullOrWhiteSpace(slideText) ? themeText : slideText;
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
