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
    public void SettingsDialogShowsRuntimeTools()
    {
        var viewModelSource = File.ReadAllText(FindMainPageViewModel());
        var pageSource = File.ReadAllText(FindMainPageCodeBehind());
        var clientSource = File.ReadAllText(FindAgentSessionClient());

        StringAssert.Contains(clientSource, "type = \"runtime.tools\"");
        StringAssert.Contains(viewModelSource, "GetRuntimeToolsAsync");
        StringAssert.Contains(viewModelSource, "RuntimeTools");
        StringAssert.Contains(viewModelSource, "SettingsText");
        StringAssert.Contains(pageSource, "ViewModel.SettingsText");
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
    public void CommandBarExposesCancelShortcut()
    {
        var page = XDocument.Load(FindMainPageXaml());
        XNamespace xaml = "http://schemas.microsoft.com/winfx/2006/xaml/presentation";
        var button = page
            .Descendants(xaml + "AppBarButton")
            .Single(element => element.Attribute("Label")?.Value == "Cancel");

        StringAssert.Contains(button.Attribute("Command")?.Value ?? "", "CancelCommand");
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
    public void ViewModelCanCancelRunningAgentTurn()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "private CancellationTokenSource? _turnCancellation");
        StringAssert.Contains(source, "CancelCommand");
        StringAssert.Contains(source, "_turnCancellation?.Cancel()");
        StringAssert.Contains(source, "SendUserMessageAsync(text, turnCancellation.Token)");
        StringAssert.Contains(source, "Agent turn canceled.");
    }

    [TestMethod]
    public void ViewModelUsesPptxExportSummaryForReadyEvents()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "RuntimePptxExportSummary.FromPayload");
        StringAssert.Contains(source, "pptxSummary.ToChatMessage()");
    }

    [TestMethod]
    public void ViewModelUsesPreviewSummaryForReadyEvents()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "RuntimePreviewSummary.FromPayload");
        StringAssert.Contains(source, "previewSummary.ToChatMessage()");
    }

    [TestMethod]
    public void ChatMessagesCanRenderActionButtons()
    {
        var page = XDocument.Load(FindMainPageXaml());
        XNamespace xaml = "http://schemas.microsoft.com/winfx/2006/xaml/presentation";

        var actions = page
            .Descendants(xaml + "ItemsControl")
            .Single(element => element.Attribute("ItemsSource")?.Value == "{x:Bind Actions}");
        var button = actions
            .Descendants(xaml + "Button")
            .Single(element => element.Attribute("Click")?.Value == "ChatMessageAction_Click");

        Assert.AreEqual("{x:Bind Label}", button.Attribute("Content")?.Value);
        Assert.AreEqual("{x:Bind Kind}", button.Attribute("Tag")?.Value);
    }

    [TestMethod]
    public void ChatMessagesUseMarkdownRenderer()
    {
        var page = XDocument.Load(FindMainPageXaml());
        XNamespace markdown = "using:CommunityToolkit.WinUI.UI.Controls";

        var markdownBlock = page
            .Descendants(markdown + "MarkdownTextBlock")
            .Single();

        Assert.AreEqual("{x:Bind Content}", markdownBlock.Attribute("Text")?.Value);
    }

    [TestMethod]
    public void DesktopAppReferencesMarkdownControlPackage()
    {
        var project = XDocument.Load(FindDesktopAppProject());
        var packageReferences = project
            .Descendants("PackageReference")
            .Select(element => element.Attribute("Include")?.Value)
            .ToArray();

        CollectionAssert.Contains(packageReferences, "CommunityToolkit.WinUI.UI.Controls.Markdown");
    }

    [TestMethod]
    public void ViewModelAddsOpenPptxActionToExportReadyMessage()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "new ChatMessageAction");
        StringAssert.Contains(source, "Open PPTX");
        StringAssert.Contains(source, "open_pptx");
    }

    [TestMethod]
    public void InitialMessageOffersDemoDeckAction()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "Label = \"Demo Deck\"");
        StringAssert.Contains(source, "Kind = \"demo_deck\"");
    }

    [TestMethod]
    public void ChatMessageActionHandlerRoutesOpenPptxToExportCommand()
    {
        var source = File.ReadAllText(FindMainPageCodeBehind());

        StringAssert.Contains(source, "ChatMessageAction_Click");
        StringAssert.Contains(source, "ViewModel.ExportLatestCommand.Execute(null)");
        StringAssert.Contains(source, "ViewModel.GenerateDemoCommand.Execute(null)");
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

    [TestMethod]
    public void ViewModelIgnoresStaleDeckEvents()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "_agentClient.AcceptsDeckEvent(runtimeEvent.DeckId)");
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

    private static string FindDesktopAppProject()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "desktop", "PptAgentStudio.App", "PptAgentStudio.App.csproj");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException("PptAgentStudio.App.csproj was not found.");
    }

    private static string FindMainPageCodeBehind()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "desktop", "PptAgentStudio.App", "MainPage.xaml.cs");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException("MainPage.xaml.cs was not found.");
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
