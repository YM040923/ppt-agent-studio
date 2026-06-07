using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimeConfigSummary(
    string BaseUrl,
    string Model,
    bool HasApiKey,
    string PlannerRequested,
    string PlannerActive,
    string ArtifactDirectory = "")
{
    public static RuntimeConfigSummary FromPayload(JsonElement payload)
    {
        var llm = payload.GetProperty("llm");
        var hasPlanner = payload.TryGetProperty("planner", out var planner);
        var artifactDirectory = "";
        if (payload.TryGetProperty("artifacts", out var artifacts)
            && artifacts.TryGetProperty("directory", out var directory))
        {
            artifactDirectory = directory.GetString() ?? "";
        }

        return new RuntimeConfigSummary(
            BaseUrl: llm.GetProperty("base_url").GetString() ?? "",
            Model: llm.GetProperty("model").GetString() ?? "",
            HasApiKey: llm.TryGetProperty("has_api_key", out var hasApiKey) && hasApiKey.GetBoolean(),
            PlannerRequested: ReadPlannerValue(hasPlanner, planner, "requested"),
            PlannerActive: ReadPlannerValue(hasPlanner, planner, "active"),
            ArtifactDirectory: artifactDirectory);
    }

    public string ToStatusText()
    {
        var keyState = HasApiKey ? "API key configured." : "API key missing.";
        var plannerRequested = string.IsNullOrWhiteSpace(PlannerRequested) ? "fallback" : PlannerRequested;
        var plannerActive = string.IsNullOrWhiteSpace(PlannerActive) ? "fallback" : PlannerActive;
        var plannerState = plannerRequested == plannerActive
            ? $"Planner: {plannerActive}."
            : $"Planner: {plannerActive} (requested {plannerRequested}).";
        return $"Local Agent runtime ready. Model: {Model} at {BaseUrl}. {keyState} {plannerState}";
    }

    public string ToSettingsText()
    {
        var keyState = HasApiKey ? "configured" : "missing";
        var plannerActive = string.IsNullOrWhiteSpace(PlannerActive) ? "fallback" : PlannerActive;
        return $"""
            Endpoint: {BaseUrl}
            Model: {Model}
            Planner: {plannerActive}
            PPTX directory: {ArtifactDirectory}
            API key: {keyState}
            """.ReplaceLineEndings();
    }

    private static string ReadPlannerValue(bool hasPlanner, JsonElement planner, string propertyName)
    {
        if (!hasPlanner || !planner.TryGetProperty(propertyName, out var value))
        {
            return "fallback";
        }

        return value.GetString() ?? "fallback";
    }
}
