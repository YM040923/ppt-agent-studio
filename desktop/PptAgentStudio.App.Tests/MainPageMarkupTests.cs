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
    public void SettingsDialogOffersEnvFileLocationAction()
    {
        var viewModelSource = File.ReadAllText(FindMainPageViewModel());
        var pageSource = File.ReadAllText(FindMainPageCodeBehind());

        StringAssert.Contains(pageSource, "PrimaryButtonText = \"Open Env Folder\"");
        StringAssert.Contains(pageSource, "ViewModel.OpenEnvFileLocationCommand");
        StringAssert.Contains(viewModelSource, "OpenEnvFileLocationCommand");
        StringAssert.Contains(viewModelSource, "EnvFileLaunchPlan.CreateOpenEnvLocation");
    }

    [TestMethod]
    public void SettingsDialogOffersEnvFileTemplateAction()
    {
        var viewModelSource = File.ReadAllText(FindMainPageViewModel());
        var pageSource = File.ReadAllText(FindMainPageCodeBehind());

        StringAssert.Contains(pageSource, "SecondaryButtonText = \"Create Env File\"");
        StringAssert.Contains(pageSource, "ViewModel.CreateEnvFileCommand");
        StringAssert.Contains(viewModelSource, "CreateEnvFileCommand");
        StringAssert.Contains(viewModelSource, "EnvFileTemplateWriter.CreateFromExample");
    }

    [TestMethod]
    public void ViewModelNotifiesSettingsTextAfterRuntimeProbe()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "OnPropertyChanged(nameof(SettingsText))");
    }

    [TestMethod]
    public void PreviewHtmlChangesResetPreviewToFirstSlide()
    {
        var source = File.ReadAllText(FindMainPageCodeBehind());
        var previewChangedStart = source.IndexOf("e.PropertyName == nameof(ViewModel.PreviewHtml)", StringComparison.Ordinal);

        Assert.AreNotEqual(-1, previewChangedStart);
        var previewChangedBody = source[previewChangedStart..source.IndexOf("PreviewWebView.NavigateToString", previewChangedStart, StringComparison.Ordinal)];

        StringAssert.Contains(previewChangedBody, "_previewPaneState.ResetSlidePosition()");
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
    public void ViewModelRequiresHtmlBeforePreviewReadyMessage()
    {
        var source = File.ReadAllText(FindMainPageViewModel());
        var previewReadyCase = source.IndexOf("case \"preview.ready\":", StringComparison.Ordinal);
        var nextCase = source.IndexOf("case \"error\":", previewReadyCase, StringComparison.Ordinal);

        Assert.IsGreaterThanOrEqualTo(0, previewReadyCase);
        Assert.IsGreaterThan(previewReadyCase, nextCase);

        var previewReadyBody = source[previewReadyCase..nextCase];
        var missingHtmlGuard = previewReadyBody.IndexOf("string.IsNullOrWhiteSpace(previewHtml)", StringComparison.Ordinal);
        var previewSummary = previewReadyBody.IndexOf("RuntimePreviewSummary.FromPayload", StringComparison.Ordinal);

        StringAssert.Contains(previewReadyBody, "var previewHtml = html.GetString();");
        Assert.IsGreaterThan(-1, missingHtmlGuard);
        Assert.IsGreaterThan(missingHtmlGuard, previewSummary);
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
    public void ViewModelOnlyAddsOpenPptxActionWhenExportPathExists()
    {
        var source = File.ReadAllText(FindMainPageViewModel());

        StringAssert.Contains(source, "!string.IsNullOrWhiteSpace(pptxSummary.Path)");
        StringAssert.Contains(source, "Actions = exportActions");
    }

    [TestMethod]
    public void ViewModelClearsStaleExportWhenDeckUpdates()
    {
        var source = File.ReadAllText(FindMainPageViewModel());
        var deckUpdatedCase = source.IndexOf("case \"deck.updated\":", StringComparison.Ordinal);
        var statusUpdate = source.IndexOf("SessionStatus = $\"Deck updated at revision", deckUpdatedCase, StringComparison.Ordinal);
        var nextCase = source.IndexOf("case \"tool.completed\":", deckUpdatedCase, StringComparison.Ordinal);

        Assert.IsGreaterThanOrEqualTo(0, deckUpdatedCase);
        Assert.IsGreaterThan(deckUpdatedCase, statusUpdate);
        Assert.IsGreaterThan(statusUpdate, nextCase);
        Assert.IsGreaterThan(
            deckUpdatedCase,
            source.IndexOf("_workspaceDeckState.Reset();", deckUpdatedCase, StringComparison.Ordinal));
        Assert.IsGreaterThan(
            deckUpdatedCase,
            source.IndexOf("ExportLatestCommand.NotifyCanExecuteChanged();", deckUpdatedCase, StringComparison.Ordinal));
    }

    [TestMethod]
    public void ViewModelClearsStaleExportWhenSendingNewTurn()
    {
        var source = File.ReadAllText(FindMainPageViewModel());
        var sendStart = source.IndexOf("private async Task Send()", StringComparison.Ordinal);
        var nextMemberStart = source.IndexOf("private void ApplyRuntimeEvent", sendStart, StringComparison.Ordinal);

        Assert.IsGreaterThanOrEqualTo(0, sendStart);
        Assert.IsGreaterThan(sendStart, nextMemberStart);

        var sendBody = source[sendStart..nextMemberStart];
        var userMessage = sendBody.IndexOf("Messages.Add(new ChatMessageItem { Role = \"You\", Content = text });", StringComparison.Ordinal);
        var reset = sendBody.IndexOf("_workspaceDeckState.Reset();", StringComparison.Ordinal);
        var notifyExport = sendBody.IndexOf("ExportLatestCommand.NotifyCanExecuteChanged();", StringComparison.Ordinal);
        var sendState = sendBody.IndexOf("IsSending = true;", StringComparison.Ordinal);

        Assert.IsGreaterThan(userMessage, reset, "The stale export state should clear after the user message is accepted.");
        Assert.IsGreaterThan(reset, notifyExport, "The export command should be refreshed after clearing stale export state.");
        Assert.IsLessThan(sendState, notifyExport, "The stale export command should disappear before the new turn starts sending.");
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
    public void NewDeckCancelsRunningAgentTurnBeforeReset()
    {
        var source = File.ReadAllText(FindMainPageViewModel());
        var newDeckStart = source.IndexOf("private async Task NewDeck()", StringComparison.Ordinal);
        var nextMemberStart = source.IndexOf("private bool CanExportLatest()", newDeckStart, StringComparison.Ordinal);

        Assert.IsGreaterThanOrEqualTo(0, newDeckStart);
        Assert.IsGreaterThan(newDeckStart, nextMemberStart);

        var newDeckBody = source[newDeckStart..nextMemberStart];

        StringAssert.Contains(newDeckBody, "_turnCancellation?.Cancel();");
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
