using System.IO;

namespace PptAgentStudio_App.Services;

public sealed record EnvFileLaunchPlan(string FileName, string Arguments)
{
    public static EnvFileLaunchPlan CreateOpenEnvLocation(string envFilePath, bool envFileExists)
    {
        if (string.IsNullOrWhiteSpace(envFilePath))
        {
            throw new ArgumentException("env file path is required", nameof(envFilePath));
        }

        var trimmedPath = envFilePath.Trim();
        if (envFileExists)
        {
            return new EnvFileLaunchPlan(
                FileName: "explorer.exe",
                Arguments: $"/select,\"{trimmedPath}\"");
        }

        var folderPath = Path.GetDirectoryName(trimmedPath);
        if (string.IsNullOrWhiteSpace(folderPath))
        {
            throw new ArgumentException("env file path must include a folder", nameof(envFilePath));
        }

        return new EnvFileLaunchPlan(
            FileName: "explorer.exe",
            Arguments: $"\"{folderPath}\"");
    }
}
