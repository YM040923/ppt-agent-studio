using System.Text.Json;
using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class RuntimeConfigSummaryTests
{
    [TestMethod]
    public void FromPayloadReadsRedactedRuntimeConfig()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "llm": {
                "base_url": "https://provider.example/v1",
                "model": "gpt-compatible-model",
                "has_api_key": true
              },
              "planner": {
                "requested": "llm",
                "active": "llm"
              },
              "artifacts": {
                "directory": "E:\\MyProjects\\ppt-agent-studio\\artifacts\\decks"
              }
            }
            """);

        var summary = RuntimeConfigSummary.FromPayload(document.RootElement);

        Assert.AreEqual("https://provider.example/v1", summary.BaseUrl);
        Assert.AreEqual("gpt-compatible-model", summary.Model);
        Assert.IsTrue(summary.HasApiKey);
        Assert.AreEqual("llm", summary.PlannerRequested);
        Assert.AreEqual("llm", summary.PlannerActive);
        Assert.AreEqual(@"E:\MyProjects\ppt-agent-studio\artifacts\decks", summary.ArtifactDirectory);
    }

    [TestMethod]
    public void ToStatusTextShowsModelAndNeverKeyValue()
    {
        var summary = new RuntimeConfigSummary(
            BaseUrl: "https://provider.example/v1",
            Model: "gpt-compatible-model",
            HasApiKey: true,
            PlannerRequested: "llm",
            PlannerActive: "llm",
            ArtifactDirectory: @"E:\MyProjects\ppt-agent-studio\artifacts\decks");

        var status = summary.ToStatusText();

        Assert.AreEqual(
            "Local Agent runtime ready. Model: gpt-compatible-model at https://provider.example/v1. API key configured. Planner: llm.",
            status);
        Assert.IsFalse(status.Contains("secret", StringComparison.OrdinalIgnoreCase));
    }

    [TestMethod]
    public void ToStatusTextWarnsWhenApiKeyIsMissing()
    {
        var summary = new RuntimeConfigSummary(
            BaseUrl: "https://api.openai.com/v1",
            Model: "gpt-4.1-mini",
            HasApiKey: false,
            PlannerRequested: "llm",
            PlannerActive: "fallback",
            ArtifactDirectory: @"E:\MyProjects\ppt-agent-studio\artifacts\decks");

        var status = summary.ToStatusText();

        Assert.AreEqual(
            "Local Agent runtime ready. Model: gpt-4.1-mini at https://api.openai.com/v1. API key missing. Planner: fallback (requested llm).",
            status);
    }

    [TestMethod]
    public void ToSettingsTextShowsRuntimeConfigurationWithoutSecrets()
    {
        var summary = new RuntimeConfigSummary(
            BaseUrl: "https://provider.example/v1",
            Model: "gpt-compatible-model",
            HasApiKey: true,
            PlannerRequested: "llm",
            PlannerActive: "llm",
            ArtifactDirectory: @"E:\MyProjects\ppt-agent-studio\artifacts\decks");

        var settingsText = summary.ToSettingsText();

        Assert.AreEqual(
            """
            Endpoint: https://provider.example/v1
            Model: gpt-compatible-model
            Planner: llm
            PPTX directory: E:\MyProjects\ppt-agent-studio\artifacts\decks
            API key: configured
            """.ReplaceLineEndings(),
            settingsText);
        Assert.IsFalse(settingsText.Contains("secret", StringComparison.OrdinalIgnoreCase));
    }
}
