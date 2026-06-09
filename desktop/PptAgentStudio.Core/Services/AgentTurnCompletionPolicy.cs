using System.Text.Json;

namespace PptAgentStudio_App.Services;

public static class AgentTurnCompletionPolicy
{
    public static bool ShouldEndTurn(string eventType, JsonElement payload)
    {
        if (string.Equals(eventType, "error", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (!string.Equals(eventType, "plan.updated", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (!payload.TryGetProperty("plan", out var plan)
            || !plan.TryGetProperty("status", out var status))
        {
            return false;
        }

        var statusText = status.GetString();
        return string.Equals(statusText, "completed", StringComparison.OrdinalIgnoreCase)
            || string.Equals(statusText, "failed", StringComparison.OrdinalIgnoreCase);
    }
}
