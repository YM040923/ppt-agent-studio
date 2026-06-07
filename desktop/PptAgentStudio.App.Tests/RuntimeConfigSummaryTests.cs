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
                "has_api_key": true,
                "has_extra_headers": true,
                "endpoint_kind": "cloud",
                "source": {
                  "base_url": "environment",
                  "api_key": "env_file",
                  "model": "environment",
                  "extra_headers": "environment"
                }
              },
              "runtime": {
                "name": "ppt-agent-studio",
                "version": "0.1.0"
              },
              "planner": {
                "requested": "llm",
                "active": "llm"
              },
              "artifacts": {
                "directory": "E:\\MyProjects\\ppt-agent-studio\\artifacts\\decks"
              },
              "env_file": {
                "path": "E:\\MyProjects\\ppt-agent-studio\\.env.local",
                "exists": true
              }
            }
            """);

        var summary = RuntimeConfigSummary.FromPayload(document.RootElement);

        Assert.AreEqual("https://provider.example/v1", summary.BaseUrl);
        Assert.AreEqual("gpt-compatible-model", summary.Model);
        Assert.IsTrue(summary.HasApiKey);
        Assert.IsTrue(summary.HasExtraHeaders);
        Assert.AreEqual("cloud", summary.EndpointKind);
        Assert.AreEqual("base_url: environment, api_key: env_file, model: environment, extra_headers: environment", summary.ConfigSource);
        Assert.AreEqual("ppt-agent-studio", summary.RuntimeName);
        Assert.AreEqual("0.1.0", summary.RuntimeVersion);
        Assert.AreEqual("llm", summary.PlannerRequested);
        Assert.AreEqual("llm", summary.PlannerActive);
        Assert.AreEqual(@"E:\MyProjects\ppt-agent-studio\artifacts\decks", summary.ArtifactDirectory);
        Assert.AreEqual(@"E:\MyProjects\ppt-agent-studio\.env.local", summary.EnvFilePath);
        Assert.IsTrue(summary.EnvFileExists);
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
            HasExtraHeaders: true,
            ArtifactDirectory: @"E:\MyProjects\ppt-agent-studio\artifacts\decks",
            EnvFilePath: @"E:\MyProjects\ppt-agent-studio\.env.local",
            EnvFileExists: true,
            RuntimeName: "ppt-agent-studio",
            RuntimeVersion: "0.1.0",
            EndpointKind: "cloud",
            ConfigSource: "base_url: environment, api_key: env_file, model: environment, extra_headers: environment");

        var status = summary.ToStatusText();

        Assert.AreEqual(
            "Local Agent runtime ready. Model: gpt-compatible-model at https://provider.example/v1. API key configured. Extra headers configured. Planner: llm.",
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
            HasExtraHeaders: false,
            ArtifactDirectory: @"E:\MyProjects\ppt-agent-studio\artifacts\decks",
            EnvFilePath: @"E:\MyProjects\ppt-agent-studio\.env.local",
            EnvFileExists: false);

        var status = summary.ToStatusText();

        Assert.AreEqual(
            "Local Agent runtime ready. Model: gpt-4.1-mini at https://api.openai.com/v1. API key missing. Planner: fallback (requested llm).",
            status);
    }

    [TestMethod]
    public void ToSettingsTextShowsUnavailableConfigSourceForOlderRuntimePayloads()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "llm": {
                "base_url": "https://provider.example/v1",
                "model": "gpt-compatible-model",
                "has_api_key": true,
                "has_extra_headers": false,
                "endpoint_kind": "cloud"
              },
              "planner": {
                "requested": "fallback",
                "active": "fallback"
              }
            }
            """);

        var summary = RuntimeConfigSummary.FromPayload(document.RootElement);

        StringAssert.Contains(summary.ToSettingsText(), "Config source: unavailable");
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
            HasExtraHeaders: true,
            ArtifactDirectory: @"E:\MyProjects\ppt-agent-studio\artifacts\decks",
            EnvFilePath: @"E:\MyProjects\ppt-agent-studio\.env.local",
            EnvFileExists: true,
            RuntimeName: "ppt-agent-studio",
            RuntimeVersion: "0.1.0",
            EndpointKind: "cloud",
            ConfigSource: "base_url: environment, api_key: env_file, model: environment, extra_headers: environment");

        var settingsText = summary.ToSettingsText();

        Assert.AreEqual(
            """
            Runtime: ppt-agent-studio 0.1.0
            Endpoint: https://provider.example/v1
            Endpoint type: cloud
            Model: gpt-compatible-model
            Planner: llm
            Config source: base_url: environment, api_key: env_file, model: environment, extra_headers: environment
            PPTX directory: E:\MyProjects\ppt-agent-studio\artifacts\decks
            Env file: E:\MyProjects\ppt-agent-studio\.env.local (found)
            API key: configured
            Extra headers: configured
            """.ReplaceLineEndings(),
            settingsText);
        Assert.IsFalse(settingsText.Contains("secret", StringComparison.OrdinalIgnoreCase));
    }
}
