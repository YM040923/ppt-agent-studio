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
              }
            }
            """);

        var summary = RuntimeConfigSummary.FromPayload(document.RootElement);

        Assert.AreEqual("https://provider.example/v1", summary.BaseUrl);
        Assert.AreEqual("gpt-compatible-model", summary.Model);
        Assert.IsTrue(summary.HasApiKey);
    }

    [TestMethod]
    public void ToStatusTextShowsModelAndNeverKeyValue()
    {
        var summary = new RuntimeConfigSummary(
            BaseUrl: "https://provider.example/v1",
            Model: "gpt-compatible-model",
            HasApiKey: true);

        var status = summary.ToStatusText();

        Assert.AreEqual(
            "Local Agent runtime ready. Model: gpt-compatible-model at https://provider.example/v1. API key configured.",
            status);
        Assert.IsFalse(status.Contains("secret", StringComparison.OrdinalIgnoreCase));
    }

    [TestMethod]
    public void ToStatusTextWarnsWhenApiKeyIsMissing()
    {
        var summary = new RuntimeConfigSummary(
            BaseUrl: "https://api.openai.com/v1",
            Model: "gpt-4.1-mini",
            HasApiKey: false);

        var status = summary.ToStatusText();

        Assert.AreEqual(
            "Local Agent runtime ready. Model: gpt-4.1-mini at https://api.openai.com/v1. API key missing.",
            status);
    }
}
