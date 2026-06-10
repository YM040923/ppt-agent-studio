using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class ChatInputPolicyTests
{
    [TestMethod]
    public void CanSendRequiresNonBlankInput()
    {
        Assert.IsFalse(ChatInputPolicy.CanSend("", isSending: false));
        Assert.IsFalse(ChatInputPolicy.CanSend("   ", isSending: false));
    }

    [TestMethod]
    public void CanSendRejectsInputWhileTurnIsRunning()
    {
        Assert.IsFalse(ChatInputPolicy.CanSend("Make a board deck", isSending: true));
    }

    [TestMethod]
    public void CanSendAllowsInputWhenIdle()
    {
        Assert.IsTrue(ChatInputPolicy.CanSend("Make a board deck", isSending: false));
    }
}
