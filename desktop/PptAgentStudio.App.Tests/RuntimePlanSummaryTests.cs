using System.Text.Json;
using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class RuntimePlanSummaryTests
{
    [TestMethod]
    public void FromPayloadReadsDeckPlanSummary()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "plan": {
                "title": "AI Strategy",
                "slide_count": 3,
                "steps": [
                  { "title": "Research context", "status": "pending" },
                  { "title": "Structure story", "status": "pending" },
                  { "title": "Draft 3 slides", "status": "pending" },
                  { "title": "Render preview", "status": "pending" }
                ]
              }
            }
            """);

        var summary = RuntimePlanSummary.FromPayload(document.RootElement);

        Assert.AreEqual("AI Strategy", summary.Title);
        Assert.AreEqual(3, summary.SlideCount);
        CollectionAssert.AreEqual(
            new[] { "Research context", "Structure story", "Draft 3 slides" },
            summary.FirstSteps.ToArray());
    }

    [TestMethod]
    public void ToChatMessageShowsCompactPlan()
    {
        var summary = new RuntimePlanSummary(
            Title: "AI Strategy",
            SlideCount: 3,
            FirstSteps: ["Research context", "Structure story", "Draft 3 slides"]);

        Assert.AreEqual(
            "Plan ready: AI Strategy (3 slides). Next: Research context, Structure story, Draft 3 slides.",
            summary.ToChatMessage());
    }
}
