using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimeConfigSummary(string BaseUrl, string Model, bool HasApiKey)
{
    public static RuntimeConfigSummary FromPayload(JsonElement payload)
    {
        var llm = payload.GetProperty("llm");
        return new RuntimeConfigSummary(
            BaseUrl: llm.GetProperty("base_url").GetString() ?? "",
            Model: llm.GetProperty("model").GetString() ?? "",
            HasApiKey: llm.TryGetProperty("has_api_key", out var hasApiKey) && hasApiKey.GetBoolean());
    }

    public string ToStatusText()
    {
        var keyState = HasApiKey ? "API key configured." : "API key missing.";
        return $"Local Agent runtime ready. Model: {Model} at {BaseUrl}. {keyState}";
    }
}
