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

    [TestMethod]
    public void CommandBarExposesDemoDeckShortcut()
    {
        var page = XDocument.Load(FindMainPageXaml());
        XNamespace xaml = "http://schemas.microsoft.com/winfx/2006/xaml/presentation";
        var button = page
            .Descendants(xaml + "AppBarButton")
            .Single(element => element.Attribute("Label")?.Value == "Demo Deck");

        StringAssert.Contains(button.Attribute("Command")?.Value ?? "", "GenerateDemoCommand");
    }

    [TestMethod]
    public void ViewModelGeneratesDemoDeckFromDefaultPrompt()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "private const string DemoPrompt");
        StringAssert.Contains(source, "Make a 5 slide board AI strategy deck");
        StringAssert.Contains(source, "await Send()");
    }

    [TestMethod]
    public void NewDeckStartsFreshRuntimeDeckIdentity()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "await _agentClient.StartNewDeckAsync()");
    }

    [TestMethod]
    public void AgentSessionClientSendsRuntimeSessionReset()
    {
        var source = File.ReadAllText(FindAgentSessionClient());

        StringAssert.Contains(source, "type = \"session.reset\"");
        StringAssert.Contains(source, "ResetCurrentDeckAsync");
        StringAssert.Contains(source, "CancelAfter(TimeSpan.FromSeconds(1))");
        StringAssert.Contains(source, "_identity.StartNewDeck()");
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

    private static string FindAgentSessionClient()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "desktop", "PptAgentStudio.App", "Services", "AgentSessionClient.cs");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException("AgentSessionClient.cs was not found.");
    }
}
