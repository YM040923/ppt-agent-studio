using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimeConfigSummary(
    string BaseUrl,
    string Model,
    bool HasApiKey,
    string PlannerRequested,
    string PlannerActive,
    bool HasExtraHeaders = false,
    string ArtifactDirectory = "",
    string EnvFilePath = "",
    bool EnvFileExists = false)
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
        var envFilePath = "";
        var envFileExists = false;
        if (payload.TryGetProperty("env_file", out var envFile))
        {
            if (envFile.TryGetProperty("path", out var path))
            {
                envFilePath = path.GetString() ?? "";
            }

            envFileExists = envFile.TryGetProperty("exists", out var exists) && exists.GetBoolean();
        }

        return new RuntimeConfigSummary(
            BaseUrl: llm.GetProperty("base_url").GetString() ?? "",
            Model: llm.GetProperty("model").GetString() ?? "",
            HasApiKey: llm.TryGetProperty("has_api_key", out var hasApiKey) && hasApiKey.GetBoolean(),
            PlannerRequested: ReadPlannerValue(hasPlanner, planner, "requested"),
            PlannerActive: ReadPlannerValue(hasPlanner, planner, "active"),
            HasExtraHeaders: llm.TryGetProperty("has_extra_headers", out var hasExtraHeaders) && hasExtraHeaders.GetBoolean(),
            ArtifactDirectory: artifactDirectory,
            EnvFilePath: envFilePath,
            EnvFileExists: envFileExists);
    }

    public string ToStatusText()
    {
        var keyState = HasApiKey ? "API key configured." : "API key missing.";
        var extraHeadersState = HasExtraHeaders ? " Extra headers configured." : "";
        var plannerRequested = string.IsNullOrWhiteSpace(PlannerRequested) ? "fallback" : PlannerRequested;
        var plannerActive = string.IsNullOrWhiteSpace(PlannerActive) ? "fallback" : PlannerActive;
        var plannerState = plannerRequested == plannerActive
            ? $"Planner: {plannerActive}."
            : $"Planner: {plannerActive} (requested {plannerRequested}).";
        return $"Local Agent runtime ready. Model: {Model} at {BaseUrl}. {keyState}{extraHeadersState} {plannerState}";
    }

    public string ToSettingsText()
    {
        var keyState = HasApiKey ? "configured" : "missing";
        var extraHeadersState = HasExtraHeaders ? "configured" : "not configured";
        var plannerActive = string.IsNullOrWhiteSpace(PlannerActive) ? "fallback" : PlannerActive;
        var envFileState = EnvFileExists ? "found" : "missing";
        return $"""
            Endpoint: {BaseUrl}
            Model: {Model}
            Planner: {plannerActive}
            PPTX directory: {ArtifactDirectory}
            Env file: {EnvFilePath} ({envFileState})
            API key: {keyState}
            Extra headers: {extraHeadersState}
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
