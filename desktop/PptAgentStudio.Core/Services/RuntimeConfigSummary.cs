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
    bool EnvFileExists = false,
    string RuntimeName = "ppt-agent-studio",
    string RuntimeVersion = "",
    string EndpointKind = "cloud",
    string ConfigSource = "")
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
        var runtimeName = "ppt-agent-studio";
        var runtimeVersion = "";
        if (payload.TryGetProperty("runtime", out var runtime))
        {
            if (runtime.TryGetProperty("name", out var name))
            {
                runtimeName = name.GetString() ?? runtimeName;
            }

            if (runtime.TryGetProperty("version", out var version))
            {
                runtimeVersion = version.GetString() ?? "";
            }
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
            EnvFileExists: envFileExists,
            RuntimeName: runtimeName,
            RuntimeVersion: runtimeVersion,
            EndpointKind: ReadEndpointKind(llm),
            ConfigSource: ReadConfigSource(llm));
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
        var lines = new List<string>();
        if (!string.IsNullOrWhiteSpace(RuntimeVersion))
        {
            var runtimeName = string.IsNullOrWhiteSpace(RuntimeName) ? "ppt-agent-studio" : RuntimeName;
            lines.Add($"Runtime: {runtimeName} {RuntimeVersion}");
        }

        lines.AddRange(
            [
                $"Endpoint: {BaseUrl}",
                $"Endpoint type: {EndpointKind}",
                $"Model: {Model}",
                $"Planner: {plannerActive}",
                $"Config source: {ConfigSource}",
                $"PPTX directory: {ArtifactDirectory}",
                $"Env file: {EnvFilePath} ({envFileState})",
                $"API key: {keyState}",
                $"Extra headers: {extraHeadersState}"
            ]);
        return string.Join(Environment.NewLine, lines);
    }

    private static string ReadPlannerValue(bool hasPlanner, JsonElement planner, string propertyName)
    {
        if (!hasPlanner || !planner.TryGetProperty(propertyName, out var value))
        {
            return "fallback";
        }

        return value.GetString() ?? "fallback";
    }

    private static string ReadEndpointKind(JsonElement llm)
    {
        if (!llm.TryGetProperty("endpoint_kind", out var value))
        {
            return "cloud";
        }

        return string.IsNullOrWhiteSpace(value.GetString()) ? "cloud" : value.GetString()!;
    }

    private static string ReadConfigSource(JsonElement llm)
    {
        if (!llm.TryGetProperty("source", out var source) || source.ValueKind != JsonValueKind.Object)
        {
            return "unknown";
        }

        var parts = new List<string>();
        foreach (var name in new[] { "base_url", "api_key", "model", "extra_headers" })
        {
            if (source.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String)
            {
                parts.Add($"{name}: {value.GetString()}");
            }
        }

        return parts.Count == 0 ? "unknown" : string.Join(", ", parts);
    }
}
