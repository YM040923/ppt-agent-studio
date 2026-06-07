using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class AgentWorkspaceIdentityTests
{
    [TestMethod]
    public void StartsWithStableSessionAndDeckIds()
    {
        var identity = new AgentWorkspaceIdentity("desktop-session", "desktop-deck");

        Assert.AreEqual("desktop-session", identity.SessionId);
        Assert.AreEqual("desktop-deck", identity.DeckId);
    }

    [TestMethod]
    public void StartNewDeckKeepsSessionAndAdvancesDeckId()
    {
        var identity = new AgentWorkspaceIdentity("desktop-session", "desktop-deck");

        identity.StartNewDeck();
        var firstNewDeckId = identity.DeckId;
        identity.StartNewDeck();

        Assert.AreEqual("desktop-session", identity.SessionId);
        Assert.AreEqual("desktop-deck-2", firstNewDeckId);
        Assert.AreEqual("desktop-deck-3", identity.DeckId);
    }
}
