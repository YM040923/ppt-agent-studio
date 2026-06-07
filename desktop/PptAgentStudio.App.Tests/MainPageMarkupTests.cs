using System.Xml.Linq;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class MainPageMarkupTests
{
    [TestMethod]
    public void ChatInputUpdatesBindingWhileUserTypes()
    {
        var page = XDocument.Load(FindMainPageXaml());
        XNamespace xaml = "http://schemas.microsoft.com/winfx/2006/xaml/presentation";
        var input = page
            .Descendants(xaml + "TextBox")
            .Single(element => element.Attribute("PlaceholderText")?.Value == "Ask for a board-ready deck...");

        var textBinding = input.Attribute("Text")?.Value ?? "";

        StringAssert.Contains(textBinding, "UpdateSourceTrigger=PropertyChanged");
    }

    [TestMethod]
    public void ViewModelDisplaysResearchBriefPlanUpdates()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "RuntimeResearchBriefSummary.FromPayload");
        StringAssert.Contains(source, "researchSummary.HasBrief");
        StringAssert.Contains(source, "researchSummary.ToChatMessage()");
    }

    private static string FindMainPageXaml()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "desktop", "PptAgentStudio.App", "MainPage.xaml");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException("MainPage.xaml was not found.");
    }

    private static string FindMainPageViewModel()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "desktop", "PptAgentStudio.App", "ViewModels", "MainPageViewModel.cs");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException("MainPageViewModel.cs was not found.");
    }
}
