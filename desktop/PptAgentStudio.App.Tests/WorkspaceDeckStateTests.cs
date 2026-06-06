using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class WorkspaceDeckStateTests
{
    [TestMethod]
    public void ExportIsUnavailableUntilPptxIsRecorded()
    {
        var state = new WorkspaceDeckState();

        Assert.IsFalse(state.CanExport);
        Assert.AreEqual("", state.LastPptxPath);

        state.RecordPptx(@"E:\MyProjects\ppt-agent-studio\artifacts\decks\deck-r1.pptx");

        Assert.IsTrue(state.CanExport);
        Assert.AreEqual(@"E:\MyProjects\ppt-agent-studio\artifacts\decks\deck-r1.pptx", state.LastPptxPath);
    }

    [TestMethod]
    public void ResetClearsExportState()
    {
        var state = new WorkspaceDeckState();
        state.RecordPptx(@"E:\deck.pptx");

        state.Reset();

        Assert.IsFalse(state.CanExport);
        Assert.AreEqual("", state.LastPptxPath);
    }
}
