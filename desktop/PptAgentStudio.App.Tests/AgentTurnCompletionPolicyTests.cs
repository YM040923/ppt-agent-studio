using System.Text.Json;
using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class AgentTurnCompletionPolicyTests
{
    [TestMethod]
    public void ErrorEventEndsTurn()
    {
        using var document = JsonDocument.Parse("""{"message":"Runtime error"}""");

        Assert.IsTrue(AgentTurnCompletionPolicy.ShouldEndTurn("error", document.RootElement));
    }

    [TestMethod]
    public void PreviewReadyDoesNotEndTurn()
    {
        using var document = JsonDocument.Parse("""{"html":"<!doctype html>"}""");

        Assert.IsFalse(AgentTurnCompletionPolicy.ShouldEndTurn("preview.ready", document.RootElement));
    }

    [TestMethod]
    public void PptxReadyDoesNotEndTurnBeforeCompletedPlan()
    {
        using var document = JsonDocument.Parse("""{"path":"artifacts/decks/deck-r1.pptx"}""");

        Assert.IsFalse(AgentTurnCompletionPolicy.ShouldEndTurn("pptx.ready", document.RootElement));
    }

    [TestMethod]
    public void RunningPlanDoesNotEndTurn()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "plan": {
                "status": "running"
              }
            }
            """);

        Assert.IsFalse(AgentTurnCompletionPolicy.ShouldEndTurn("plan.updated", document.RootElement));
    }

    [TestMethod]
    public void CompletedPlanEndsTurn()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "plan": {
                "status": "completed"
              }
            }
            """);

        Assert.IsTrue(AgentTurnCompletionPolicy.ShouldEndTurn("plan.updated", document.RootElement));
    }
}
