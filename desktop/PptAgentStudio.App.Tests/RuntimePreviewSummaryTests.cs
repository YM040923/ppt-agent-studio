using System.Text.Json;
using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class RuntimePreviewSummaryTests
{
    [TestMethod]
    public void FromPayloadReadsPreviewDeckMetadata()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "deck_title": "Board AI Strategy",
              "slide_count": 5
            }
            """);

        var summary = RuntimePreviewSummary.FromPayload(document.RootElement);

        Assert.AreEqual("Board AI Strategy", summary.Title);
        Assert.AreEqual(5, summary.SlideCount);
    }

    [TestMethod]
    public void ToChatMessageShowsPreviewSlideCount()
    {
        var summary = new RuntimePreviewSummary("Board AI Strategy", 5);

        Assert.AreEqual(
            "Preview updated: Board AI Strategy (5 slides).",
            summary.ToChatMessage());
    }

    [TestMethod]
    public void ToStatusTextIncludesRevisionWhenAvailable()
    {
        var summary = new RuntimePreviewSummary("Board AI Strategy", 5);

        Assert.AreEqual(
            "Preview ready at revision 2: 5 slides.",
            summary.ToStatusText(2));
    }

    [TestMethod]
    public void MissingMetadataFallsBackToGenericPreviewText()
    {
        using var document = JsonDocument.Parse("""{}""");

        var summary = RuntimePreviewSummary.FromPayload(document.RootElement);

        Assert.AreEqual("", summary.Title);
        Assert.AreEqual(0, summary.SlideCount);
        Assert.AreEqual("Preview updated from the local Agent runtime.", summary.ToChatMessage());
        Assert.AreEqual("Preview ready.", summary.ToStatusText(null));
    }
}
