using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using System.Collections.ObjectModel;

namespace PptAgentStudio_App.ViewModels;

public sealed class ChatMessageItem
{
    public string Role { get; init; } = "";

    public string Content { get; init; } = "";
}

public partial class MainPageViewModel : ObservableObject
{
    [ObservableProperty]
    public partial string SessionStatus { get; set; } = "Local Agent runtime not connected";

    [ObservableProperty]
    public partial string InputText { get; set; } = "";

    public ObservableCollection<ChatMessageItem> Messages { get; } =
    [
        new()
        {
            Role = "Assistant",
            Content = "Tell me the topic, audience, slide count, and style. I will turn it into a DeckSpec and keep the preview in sync."
        }
    ];

    public string PreviewHtml { get; } = """
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

    [RelayCommand]
    private void Send()
    {
        var text = InputText.Trim();
        if (text.Length == 0)
        {
            return;
        }

        Messages.Add(new ChatMessageItem { Role = "You", Content = text });
        Messages.Add(new ChatMessageItem { Role = "Assistant", Content = "The first Agent runtime skeleton is ready. WebSocket streaming will attach here next." });
        InputText = "";
    }
}
