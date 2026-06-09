using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record AgentRuntimeEvent(
    int Seq,
    string Type,
    string SessionId,
    string? DeckId,
    int? DeckRevision,
    JsonElement Payload);

public static class AgentRuntimeEventParser
{
    public static AgentRuntimeEvent Parse(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        return new AgentRuntimeEvent(
            Seq: root.GetProperty("seq").GetInt32(),
            Type: root.GetProperty("type").GetString() ?? "",
            SessionId: root.GetProperty("session_id").GetString() ?? "",
            DeckId: ReadOptionalString(root, "deck_id"),
            DeckRevision: ReadOptionalInt(root, "deck_revision"),
            Payload: root.GetProperty("payload").Clone());
    }

    private static string? ReadOptionalString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString()
            : null;
    }

    private static int? ReadOptionalInt(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out var property)
            || property.ValueKind != JsonValueKind.Number
            || !property.TryGetInt32(out var value))
        {
            return null;
        }

        return value;
    }
}
