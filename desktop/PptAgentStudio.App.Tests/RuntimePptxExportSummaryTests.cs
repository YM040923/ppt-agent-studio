using System.Text.Json;
using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class RuntimePptxExportSummaryTests
{
    [TestMethod]
    public void FromPayloadReadsPathAndSlideCount()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "path": "E:\\MyProjects\\ppt-agent-studio\\artifacts\\decks\\deck-r1.pptx",
              "slide_count": 2,
              "secret": "should-not-appear"
            }
            """);

        var summary = RuntimePptxExportSummary.FromPayload(document.RootElement);

        Assert.AreEqual(@"E:\MyProjects\ppt-agent-studio\artifacts\decks\deck-r1.pptx", summary.Path);
        Assert.AreEqual(2, summary.SlideCount);
        Assert.AreEqual(
            @"**Editable PPTX export is ready:** 2 slides at `E:\MyProjects\ppt-agent-studio\artifacts\decks\deck-r1.pptx`",
            summary.ToChatMessage());
        Assert.AreEqual("PPTX exported at revision 3: 2 slides.", summary.ToStatusText(3));
        Assert.IsFalse(summary.ToChatMessage().Contains("secret", StringComparison.OrdinalIgnoreCase));
    }

    [TestMethod]
    public void ToChatMessageFallsBackWhenPathOrSlideCountIsMissing()
    {
        using var document = JsonDocument.Parse("""{}""");

        var summary = RuntimePptxExportSummary.FromPayload(document.RootElement);

        Assert.AreEqual("", summary.Path);
        Assert.AreEqual(0, summary.SlideCount);
        Assert.AreEqual("**Editable PPTX export is ready.**", summary.ToChatMessage());
        Assert.AreEqual("PPTX exported.", summary.ToStatusText(null));
    }
}
