using System.Text.Json;
using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class RuntimeToolSummaryTests
{
    [TestMethod]
    public void FromPayloadCreatesSafeToolProgressMessage()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "tool_name": "pptx.export",
              "status": "completed",
              "summary": "Exported editable PPTX artifact.",
              "secret": "should-not-appear"
            }
            """);

        var summary = RuntimeToolSummary.FromPayload(document.RootElement);

        Assert.AreEqual("pptx.export", summary.ToolName);
        Assert.AreEqual("completed", summary.Status);
        Assert.AreEqual("Exported editable PPTX artifact.", summary.Summary);
        Assert.AreEqual("**Tool completed:** pptx.export. Exported editable PPTX artifact.", summary.ToChatMessage());
        Assert.IsFalse(summary.ToChatMessage().Contains("secret", StringComparison.OrdinalIgnoreCase));
    }

    [TestMethod]
    public void FromPayloadFallsBackForMissingSummary()
    {
        using var document = JsonDocument.Parse("""{"tool_name":"preview.render_html"}""");

        var summary = RuntimeToolSummary.FromPayload(document.RootElement);

        Assert.AreEqual("preview.render_html", summary.ToolName);
        Assert.AreEqual("completed", summary.Status);
        Assert.AreEqual("**Tool completed:** preview.render_html.", summary.ToChatMessage());
    }
}
