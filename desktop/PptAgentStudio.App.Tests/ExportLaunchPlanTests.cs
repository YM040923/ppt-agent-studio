using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class ExportLaunchPlanTests
{
    [TestMethod]
    public void CreateRevealInExplorerRejectsBlankPath()
    {
        Assert.ThrowsExactly<ArgumentException>(() => ExportLaunchPlan.CreateRevealInExplorer(" "));
    }

    [TestMethod]
    public void CreateRevealInExplorerSelectsPptxPath()
    {
        var plan = ExportLaunchPlan.CreateRevealInExplorer(@"E:\My Projects\ppt-agent-studio\artifacts\decks\deck-r1.pptx");

        Assert.AreEqual("explorer.exe", plan.FileName);
        Assert.AreEqual(
            @"/select,""E:\My Projects\ppt-agent-studio\artifacts\decks\deck-r1.pptx""",
            plan.Arguments);
    }
}
