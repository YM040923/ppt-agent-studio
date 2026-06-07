namespace PptAgentStudio_App.Services;

public sealed class AgentWorkspaceIdentity
{
    private readonly string _baseDeckId;
    private int _deckSerial = 1;

    public AgentWorkspaceIdentity(string sessionId = "desktop-session", string deckId = "desktop-deck")
    {
        SessionId = string.IsNullOrWhiteSpace(sessionId) ? "desktop-session" : sessionId.Trim();
        _baseDeckId = string.IsNullOrWhiteSpace(deckId) ? "desktop-deck" : deckId.Trim();
        DeckId = _baseDeckId;
    }

    public string SessionId { get; }

    public string DeckId { get; private set; }

    public void StartNewDeck()
    {
        _deckSerial += 1;
        DeckId = $"{_baseDeckId}-{_deckSerial}";
    }
}
