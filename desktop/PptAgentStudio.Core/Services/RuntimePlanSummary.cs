using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimePlanSummary(
    string Title,
    int SlideCount,
    IReadOnlyList<string> FirstSteps,
    string ActiveStepTitle = "",
    string Status = "pending")
{
    public static RuntimePlanSummary FromPayload(JsonElement payload)
    {
        if (!payload.TryGetProperty("plan", out var plan))
        {
            return new RuntimePlanSummary("Deck plan", 0, []);
        }

        var title = plan.TryGetProperty("title", out var titleValue)
            ? titleValue.GetString() ?? "Deck plan"
            : "Deck plan";
        var slideCount = plan.TryGetProperty("slide_count", out var slideCountValue)
            ? slideCountValue.GetInt32()
            : 0;
        var planStatus = plan.TryGetProperty("status", out var statusValue)
            ? statusValue.GetString() ?? "pending"
            : "pending";
        var steps = new List<string>();
        var activeStepTitle = "";
        if (plan.TryGetProperty("steps", out var stepsValue) && stepsValue.ValueKind == JsonValueKind.Array)
        {
            foreach (var step in stepsValue.EnumerateArray())
            {
                var stepTitleText = step.TryGetProperty("title", out var stepTitle)
                    ? stepTitle.GetString()
                    : null;
                if (string.IsNullOrWhiteSpace(stepTitleText))
                {
                    continue;
                }

                if (steps.Count < 3)
                {
                    steps.Add(stepTitleText);
                }

                if (string.IsNullOrWhiteSpace(activeStepTitle)
                    && step.TryGetProperty("status", out var status)
                    && string.Equals(status.GetString(), "running", StringComparison.OrdinalIgnoreCase))
                {
                    activeStepTitle = stepTitleText;
                }
            }
        }

        return new RuntimePlanSummary(title, slideCount, steps, activeStepTitle, planStatus);
    }

    public string ToChatMessage()
    {
        var slideText = SlideCount == 1 ? "1 slide" : $"{SlideCount} slides";
        if (string.Equals(Status, "completed", StringComparison.OrdinalIgnoreCase))
        {
            return $"Plan completed: {Title} ({slideText}).";
        }

        var activeStep = string.IsNullOrWhiteSpace(ActiveStepTitle) ? "" : $" Active: {ActiveStepTitle}.";
        var nextSteps = FirstSteps.Count == 0 ? "" : $" Next: {string.Join(", ", FirstSteps)}.";
        return $"Plan ready: {Title} ({slideText}).{activeStep}{nextSteps}";
    }
}
