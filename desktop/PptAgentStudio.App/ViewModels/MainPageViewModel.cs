using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PptAgentStudio_App.Services;
using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;

namespace PptAgentStudio_App.ViewModels;

public sealed class ChatMessageItem
{
    public string Role { get; init; } = "";

    public string Content { get; init; } = "";
}

public partial class MainPageViewModel : ObservableObject
{
    private readonly AgentSessionClient _agentClient = new();
    private readonly RuntimeSidecarService _sidecar = new();
    private readonly WorkspaceDeckState _workspaceDeckState = new();

    [ObservableProperty]
    public partial string SessionStatus { get; set; } = "Local Agent runtime not connected";

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(SendCommand))]
    public partial string InputText { get; set; } = "";

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(SendCommand))]
    [NotifyCanExecuteChangedFor(nameof(GenerateDemoCommand))]
    public partial bool IsSending { get; set; }

    [ObservableProperty]
    public partial string PreviewHtml { get; set; } = InitialPreviewHtml;

    public RuntimeConfigSummary? RuntimeConfig { get; private set; }

    public ObservableCollection<ChatMessageItem> Messages { get; } =
    [
        CreateInitialMessage()
    ];

    private const string InitialPreviewHtml = """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <style>
            body { margin: 0; background: #f3f3f3; font-family: Segoe UI, sans-serif; }
            .deck { padding: 24px; }
            .deck-header { color: #555; font-size: 13px; margin-bottom: 12px; }
            .slide { aspect-ratio: 16 / 9; background: white; border-radius: 8px; box-shadow: 0 12px 32px rgba(0,0,0,.14); margin: 0 0 18px; padding: 42px; box-sizing: border-box; }
            .page-number { color: #777; font-size: 13px; }
            h1 { font-size: 34px; margin: 40px 0 12px; }
            p { color: #444; font-size: 18px; line-height: 1.45; }
          </style>
        </head>
        <body>
          <main class="deck" data-deck-id="sample" data-revision="0">
            <header class="deck-header"><span>Sample Deck</span></header>
            <section class="slide slide-cover">
              <div class="page-number">01</div>
              <h1>Board AI Strategy</h1>
              <p>Live preview placeholder</p>
            </section>
          </main>
        </body>
        </html>
        """;

    private const string DemoPrompt = "Make a 5 slide board AI strategy deck in McKinsey style for senior executives.";

    public async Task InitializeRuntimeAsync()
    {
        SessionStatus = "Starting local Agent runtime...";
        var ready = await _sidecar.EnsureRunningAsync();
        if (!ready)
        {
            SessionStatus = "Local Agent runtime could not be started.";
            return;
        }

        try
        {
            var runtimeConfig = await _agentClient.GetRuntimeConfigAsync();
            RuntimeConfig = runtimeConfig;
            SessionStatus = runtimeConfig.ToStatusText();
        }
        catch (Exception ex)
        {
            SessionStatus = $"Local Agent runtime ready. Config probe failed: {ex.Message}";
        }
    }

    public void StopRuntime()
    {
        _sidecar.Dispose();
    }

    [RelayCommand]
    private async Task NewDeck()
    {
        await _agentClient.StartNewDeckAsync();
        _workspaceDeckState.Reset();
        InputText = "";
        PreviewHtml = InitialPreviewHtml;
        Messages.Clear();
        Messages.Add(CreateInitialMessage());
        SessionStatus = "New deck workspace ready.";
        ExportLatestCommand.NotifyCanExecuteChanged();
    }

    private bool CanExportLatest()
    {
        return _workspaceDeckState.CanExport;
    }

    private bool CanGenerateDemo()
    {
        return !IsSending;
    }

    [RelayCommand(CanExecute = nameof(CanGenerateDemo))]
    private async Task GenerateDemo()
    {
        if (IsSending)
        {
            return;
        }

        InputText = DemoPrompt;
        await Send();
    }

    [RelayCommand(CanExecute = nameof(CanExportLatest))]
    private void ExportLatest()
    {
        var pptxPath = _workspaceDeckState.LastPptxPath;
        if (!File.Exists(pptxPath))
        {
            SessionStatus = $"Latest editable PPTX export was not found: {pptxPath}";
            Messages.Add(new ChatMessageItem
            {
                Role = "Assistant",
                Content = SessionStatus
            });
            return;
        }

        var launchPlan = ExportLaunchPlan.CreateRevealInExplorer(pptxPath);
        Process.Start(new ProcessStartInfo
        {
            FileName = launchPlan.FileName,
            Arguments = launchPlan.Arguments,
            UseShellExecute = false,
        });

        SessionStatus = $"Opened latest editable PPTX location: {pptxPath}";
        Messages.Add(new ChatMessageItem
        {
            Role = "Assistant",
            Content = $"Opened latest editable PPTX location: {pptxPath}"
        });
    }

    private bool CanSend()
    {
        return ChatInputPolicy.CanSend(InputText, IsSending);
    }

    [RelayCommand(CanExecute = nameof(CanSend))]
    private async Task Send()
    {
        var text = InputText.Trim();
        if (!ChatInputPolicy.CanSend(text, IsSending))
        {
            return;
        }

        Messages.Add(new ChatMessageItem { Role = "You", Content = text });
        InputText = "";
        IsSending = true;
        SessionStatus = "Sending request to local Agent runtime...";

        try
        {
            await foreach (var runtimeEvent in _agentClient.SendUserMessageAsync(text))
            {
                ApplyRuntimeEvent(runtimeEvent);
            }
        }
        catch (Exception ex)
        {
            SessionStatus = $"Runtime unavailable: {ex.Message}";
            Messages.Add(new ChatMessageItem
            {
                Role = "Assistant",
                Content = "I could not reach the local Python Agent runtime. Start it with: python -m ppt_agent_studio.runtime.websocket_server --port 8765"
            });
        }
        finally
        {
            IsSending = false;
        }
    }

    private void ApplyRuntimeEvent(AgentRuntimeEvent runtimeEvent)
    {
        switch (runtimeEvent.Type)
        {
            case "plan.updated":
                var planSummary = RuntimePlanSummary.FromPayload(runtimeEvent.Payload);
                var isCompletedPlan = string.Equals(planSummary.Status, "completed", StringComparison.OrdinalIgnoreCase);
                SessionStatus = isCompletedPlan
                    ? $"Agent completed a {planSummary.SlideCount}-slide plan."
                    : $"Agent created a {planSummary.SlideCount}-slide plan.";
                Messages.Add(new ChatMessageItem
                {
                    Role = "Assistant",
                    Content = planSummary.ToChatMessage()
                });
                var researchSummary = RuntimeResearchBriefSummary.FromPayload(runtimeEvent.Payload);
                if (researchSummary.HasBrief)
                {
                    SessionStatus = researchSummary.ToChatMessage();
                    Messages.Add(new ChatMessageItem
                    {
                        Role = "Assistant",
                        Content = researchSummary.ToChatMessage()
                    });
                }
                break;
            case "deck.updated":
                SessionStatus = $"Deck updated at revision {runtimeEvent.DeckRevision}.";
                break;
            case "tool.completed":
                var toolSummary = RuntimeToolSummary.FromPayload(runtimeEvent.Payload);
                SessionStatus = toolSummary.ToChatMessage();
                Messages.Add(new ChatMessageItem
                {
                    Role = "Assistant",
                    Content = SessionStatus
                });
                break;
            case "pptx.ready":
                var path = runtimeEvent.Payload.TryGetProperty("path", out var pptxPath)
                    ? pptxPath.GetString()
                    : null;
                _workspaceDeckState.RecordPptx(path);
                ExportLatestCommand.NotifyCanExecuteChanged();
                SessionStatus = $"PPTX exported at revision {runtimeEvent.DeckRevision}.";
                Messages.Add(new ChatMessageItem
                {
                    Role = "Assistant",
                    Content = string.IsNullOrWhiteSpace(path)
                        ? "Editable PPTX export is ready."
                        : $"Editable PPTX export is ready: {path}"
                });
                break;
            case "preview.ready":
                if (runtimeEvent.Payload.TryGetProperty("html", out var html))
                {
                    PreviewHtml = html.GetString() ?? PreviewHtml;
                }
                SessionStatus = $"Preview ready at revision {runtimeEvent.DeckRevision}.";
                Messages.Add(new ChatMessageItem { Role = "Assistant", Content = "Preview updated from the local Agent runtime." });
                break;
            case "error":
                var message = runtimeEvent.Payload.TryGetProperty("message", out var error)
                    ? error.GetString()
                    : "Runtime error";
                SessionStatus = message ?? "Runtime error";
                Messages.Add(new ChatMessageItem { Role = "Assistant", Content = SessionStatus });
                break;
        }
    }

    private static ChatMessageItem CreateInitialMessage()
    {
        return new ChatMessageItem
        {
            Role = "Assistant",
            Content = "Tell me the topic, audience, slide count, and style. I will turn it into a DeckSpec and keep the preview in sync."
        };
    }
}
