using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimeToolSummary(string ToolName, string Status, string Summary)
{
    public static RuntimeToolSummary FromPayload(JsonElement payload)
    {
        var toolName = ReadString(payload, "tool_name", "tool");
        var status = ReadString(payload, "status", "completed");
        var summary = ReadString(payload, "summary", "");

        return new RuntimeToolSummary(toolName, status, summary);
    }

    public string ToChatMessage()
    {
        var statusText = string.Equals(Status, "completed", StringComparison.OrdinalIgnoreCase)
            ? "completed"
            : Status;
        var prefix = $"**Tool {statusText}:** {ToolName}.";
        return string.IsNullOrWhiteSpace(Summary)
            ? prefix
            : $"{prefix} {Summary}";
    }

    private static string ReadString(JsonElement payload, string propertyName, string fallback)
    {
        if (payload.TryGetProperty(propertyName, out var property)
            && property.ValueKind == JsonValueKind.String)
        {
            var value = property.GetString();
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value;
            }
        }

        return fallback;
    }
}
