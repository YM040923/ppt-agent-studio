namespace PptAgentStudio_App.Services;

public static class ChatInputPolicy
{
    public static bool CanSend(string inputText, bool isSending)
    {
        return !isSending && !string.IsNullOrWhiteSpace(inputText);
    }
}
