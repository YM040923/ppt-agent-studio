using System.IO;
using System.Text;

namespace PptAgentStudio_App.Services;

public sealed record EnvFileTemplateResult(string EnvFilePath, bool Created);

public static class EnvFileTemplateWriter
{
    private const string DefaultTemplate = """
        # Copy to .env.local and fill with your local or third-party OpenAI-compatible provider.
        # Never commit .env.local or real API keys.

        OPENAI_BASE_URL=https://your-provider.example/v1
        OPENAI_API_KEY=replace-with-your-api-key
        OPENAI_MODEL=your-compatible-model
        OPENAI_EXTRA_HEADERS=
        PPT_AGENT_PLANNER=fallback
        """;

    public static EnvFileTemplateResult CreateFromExample(string envFilePath)
    {
        if (string.IsNullOrWhiteSpace(envFilePath))
        {
            throw new ArgumentException("env file path is required", nameof(envFilePath));
        }

        var trimmedPath = envFilePath.Trim();
        if (File.Exists(trimmedPath))
        {
            return new EnvFileTemplateResult(trimmedPath, Created: false);
        }

        var folderPath = Path.GetDirectoryName(trimmedPath);
        if (string.IsNullOrWhiteSpace(folderPath))
        {
            throw new ArgumentException("env file path must include a folder", nameof(envFilePath));
        }

        Directory.CreateDirectory(folderPath);
        var examplePath = Path.Combine(folderPath, ".env.example");
        var template = File.Exists(examplePath)
            ? File.ReadAllText(examplePath, Encoding.UTF8)
            : DefaultTemplate;
        File.WriteAllText(trimmedPath, template, Encoding.UTF8);

        return new EnvFileTemplateResult(trimmedPath, Created: true);
    }
}
