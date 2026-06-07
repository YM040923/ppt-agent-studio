using System.Text.Json;
using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class RuntimeResearchBriefSummaryTests
{
    [TestMethod]
    public void FromPayloadReadsSafeResearchBrief()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "research_brief": {
                "topic": "AI strategy",
                "audience": "executive committee",
                "constraints": ["Style: McKinsey", "Slides: 4"],
                "questions": [
                  "Clarify the decision the deck must support.",
                  "Identify the audience's current belief and desired shift.",
                  "List the proof points needed for executive confidence."
                ],
                "api_key": "should-not-appear"
              }
            }
            """);

        var summary = RuntimeResearchBriefSummary.FromPayload(document.RootElement);

        Assert.IsTrue(summary.HasBrief);
        Assert.AreEqual("AI strategy", summary.Topic);
        Assert.AreEqual("executive committee", summary.Audience);
        CollectionAssert.AreEqual(
            new[] { "Style: McKinsey", "Slides: 4" },
            summary.Constraints.ToArray());
        CollectionAssert.AreEqual(
            new[]
            {
                "Clarify the decision the deck must support.",
                "Identify the audience's current belief and desired shift.",
                "List the proof points needed for executive confidence."
            },
            summary.Questions.ToArray());
        Assert.AreEqual(
            "**Research brief:** AI strategy for executive committee. **Constraints:** Style: McKinsey, Slides: 4. **Questions:** Clarify the decision the deck must support.; Identify the audience's current belief and desired shift.; List the proof points needed for executive confidence.",
            summary.ToChatMessage());
        Assert.IsFalse(summary.ToChatMessage().Contains("api_key", StringComparison.OrdinalIgnoreCase));
    }

    [TestMethod]
    public void FromPayloadReturnsEmptySummaryWhenBriefIsMissing()
    {
        using var document = JsonDocument.Parse("""{"plan":{"status":"running"}}""");

        var summary = RuntimeResearchBriefSummary.FromPayload(document.RootElement);

        Assert.IsFalse(summary.HasBrief);
        Assert.AreEqual("", summary.ToChatMessage());
    }
}
