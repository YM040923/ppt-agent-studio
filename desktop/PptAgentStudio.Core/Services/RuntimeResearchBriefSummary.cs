using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimeResearchBriefSummary(
    string Topic,
    string Audience,
    IReadOnlyList<string> Constraints,
    IReadOnlyList<string> Questions)
{
    public bool HasBrief =>
        !string.IsNullOrWhiteSpace(Topic)
        || !string.IsNullOrWhiteSpace(Audience)
        || Constraints.Count > 0
        || Questions.Count > 0;

    public static RuntimeResearchBriefSummary FromPayload(JsonElement payload)
    {
        if (!payload.TryGetProperty("research_brief", out var brief)
            || brief.ValueKind != JsonValueKind.Object)
        {
            return new RuntimeResearchBriefSummary("", "", [], []);
        }

        return new RuntimeResearchBriefSummary(
            Topic: ReadString(brief, "topic"),
            Audience: ReadString(brief, "audience"),
            Constraints: ReadStringList(brief, "constraints"),
            Questions: ReadStringList(brief, "questions"));
    }

    public string ToChatMessage()
    {
        if (!HasBrief)
        {
            return "";
        }

        var topic = string.IsNullOrWhiteSpace(Topic) ? "deck context" : Topic;
        var audience = string.IsNullOrWhiteSpace(Audience) ? "" : $" for {Audience}";
        var constraints = Constraints.Count == 0 ? "" : $" **Constraints:** {string.Join(", ", Constraints)}.";
        var questions = Questions.Count == 0 ? "" : $" **Questions:** {string.Join("; ", Questions)}";
        return $"**Research brief:** {topic}{audience}.{constraints}{questions}";
    }

    private static string ReadString(JsonElement source, string propertyName)
    {
        if (source.TryGetProperty(propertyName, out var property)
            && property.ValueKind == JsonValueKind.String)
        {
            return property.GetString()?.Trim() ?? "";
        }

        return "";
    }

    private static IReadOnlyList<string> ReadStringList(JsonElement source, string propertyName)
    {
        if (!source.TryGetProperty(propertyName, out var property)
            || property.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        var values = new List<string>();
        foreach (var item in property.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.String)
            {
                continue;
            }

            var text = item.GetString()?.Trim();
            if (!string.IsNullOrWhiteSpace(text))
            {
                values.Add(text);
            }
        }

        return values;
    }
}
