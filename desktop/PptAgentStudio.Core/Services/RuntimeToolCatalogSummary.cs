using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimeToolCatalogSummary(IReadOnlyList<string> ToolNames)
{
    public int ToolCount => ToolNames.Count;

    public static RuntimeToolCatalogSummary FromPayload(JsonElement payload)
    {
        var toolNames = new List<string>();
        if (payload.TryGetProperty("tools", out var tools) && tools.ValueKind == JsonValueKind.Array)
        {
            foreach (var tool in tools.EnumerateArray())
            {
                if (tool.TryGetProperty("name", out var name) && name.ValueKind == JsonValueKind.String)
                {
                    var toolName = name.GetString();
                    if (!string.IsNullOrWhiteSpace(toolName))
                    {
                        toolNames.Add(toolName);
                    }
                }
            }
        }

        return new RuntimeToolCatalogSummary(toolNames);
    }

    public string ToSettingsText()
    {
        if (ToolNames.Count == 0)
        {
            return "Tools: 0";
        }

        return string.Join(
            Environment.NewLine,
            [
                $"Tools: {ToolNames.Count}",
                .. ToolNames.Select(toolName => $"- {toolName}")
            ]);
    }
}
