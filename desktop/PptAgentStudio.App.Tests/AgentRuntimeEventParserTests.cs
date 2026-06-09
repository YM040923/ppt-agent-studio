using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class AgentRuntimeEventParserTests
{
    [TestMethod]
    public void ParseReadsRuntimeEventEnvelope()
    {
        var runtimeEvent = AgentRuntimeEventParser.Parse(
            """
            {
              "seq": 7,
              "type": "preview.ready",
              "session_id": "session_001",
              "deck_id": "deck_001",
              "deck_revision": 4,
              "payload": { "html": "<!doctype html>" }
            }
            """);

        Assert.AreEqual(7, runtimeEvent.Seq);
        Assert.AreEqual("preview.ready", runtimeEvent.Type);
        Assert.AreEqual("session_001", runtimeEvent.SessionId);
        Assert.AreEqual("deck_001", runtimeEvent.DeckId);
        Assert.AreEqual(4, runtimeEvent.DeckRevision);
        Assert.AreEqual("<!doctype html>", runtimeEvent.Payload.GetProperty("html").GetString());
    }

    [TestMethod]
    public void ParseTreatsNullDeckRevisionAsMissing()
    {
        var runtimeEvent = AgentRuntimeEventParser.Parse(
            """
            {
              "seq": 8,
              "type": "plan.updated",
              "session_id": "session_001",
              "deck_id": "deck_001",
              "deck_revision": null,
              "payload": { "plan": { "status": "running" } }
            }
            """);

        Assert.IsNull(runtimeEvent.DeckRevision);
        Assert.AreEqual("running", runtimeEvent.Payload.GetProperty("plan").GetProperty("status").GetString());
    }

    [TestMethod]
    public void RequirePayloadReturnsPayloadForExpectedEventType()
    {
        var runtimeEvent = AgentRuntimeEventParser.Parse(
            """
            {
              "seq": 9,
              "type": "runtime.tools",
              "session_id": "session_001",
              "payload": { "tools": [ { "name": "pptx.export" } ] }
            }
            """);

        var payload = runtimeEvent.RequirePayload("runtime.tools");

        Assert.AreEqual("pptx.export", payload.GetProperty("tools")[0].GetProperty("name").GetString());
    }

    [TestMethod]
    public void RequirePayloadSurfacesRuntimeErrorMessage()
    {
        var runtimeEvent = AgentRuntimeEventParser.Parse(
            """
            {
              "seq": 10,
              "type": "error",
              "session_id": "session_001",
              "payload": { "message": "Invalid runtime configuration: OPENAI_EXTRA_HEADERS must be a JSON object" }
            }
            """);

        try
        {
            _ = runtimeEvent.RequirePayload("runtime.config");
        }
        catch (InvalidOperationException error)
        {
            Assert.AreEqual("Invalid runtime configuration: OPENAI_EXTRA_HEADERS must be a JSON object", error.Message);
            return;
        }

        Assert.Fail("Expected runtime error message to be surfaced.");
    }
}
