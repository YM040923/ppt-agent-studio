using System.Text.Json;

namespace PptAgentStudio_App.Services;

public sealed record RuntimePlanSummary(string Title, int SlideCount, IReadOnlyList<string> FirstSteps)
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
        var steps = new List<string>();
        if (plan.TryGetProperty("steps", out var stepsValue) && stepsValue.ValueKind == JsonValueKind.Array)
        {
            foreach (var step in stepsValue.EnumerateArray())
            {
                if (steps.Count == 3)
                {
                    break;
                }

                if (step.TryGetProperty("title", out var stepTitle))
                {
                    var value = stepTitle.GetString();
                    if (!string.IsNullOrWhiteSpace(value))
                    {
                        steps.Add(value);
                    }
                }
            }
        }

        return new RuntimePlanSummary(title, slideCount, steps);
    }

    public string ToChatMessage()
    {
        var slideText = SlideCount == 1 ? "1 slide" : $"{SlideCount} slides";
        var nextSteps = FirstSteps.Count == 0 ? "" : $" Next: {string.Join(", ", FirstSteps)}.";
        return $"Plan ready: {Title} ({slideText}).{nextSteps}";
    }
}
