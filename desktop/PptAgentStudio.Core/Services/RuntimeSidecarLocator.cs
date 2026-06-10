using System;
using System.Collections.Generic;
using System.IO;

namespace PptAgentStudio_App.Services;

public static class RuntimeSidecarLocator
{
    private const string BundledRuntimeDirectory = "AgentRuntime";

    public static string FindAgentSourceRoot(string startDirectory, IReadOnlyDictionary<string, string?> environment)
    {
        if (environment.TryGetValue("PPT_AGENT_RUNTIME_ROOT", out var overrideRoot)
            && !string.IsNullOrWhiteSpace(overrideRoot))
        {
            return Path.Combine(overrideRoot.Trim(), "agent", "src");
        }

        var bundledAgentSourceRoot = Path.Combine(startDirectory, BundledRuntimeDirectory, "agent", "src");
        if (Directory.Exists(bundledAgentSourceRoot))
        {
            return bundledAgentSourceRoot;
        }

        var current = new DirectoryInfo(startDirectory);
        while (current is not null)
        {
            var candidate = Path.Combine(current.FullName, "agent", "src");
            if (Directory.Exists(candidate))
            {
                return candidate;
            }
            current = current.Parent;
        }

        return Path.Combine(startDirectory, "agent", "src");
    }

    public static string FindPythonExecutable(string startDirectory, IReadOnlyDictionary<string, string?> environment)
    {
        if (environment.TryGetValue("PPT_AGENT_PYTHON", out var overridePython)
            && !string.IsNullOrWhiteSpace(overridePython))
        {
            return overridePython.Trim();
        }

        var bundledPython = Path.Combine(startDirectory, BundledRuntimeDirectory, "python", "python.exe");
        if (File.Exists(bundledPython))
        {
            return bundledPython;
        }

        return "python";
    }

    public static string FindArtifactDirectory(
        string appBaseDirectory,
        string agentSourceRoot,
        string localAppDataDirectory,
        IReadOnlyDictionary<string, string?> environment)
    {
        if (environment.TryGetValue("PPT_AGENT_ARTIFACTS_DIR", out var overrideDirectory)
            && !string.IsNullOrWhiteSpace(overrideDirectory))
        {
            return overrideDirectory.Trim();
        }

        if (IsBundledAgentSourceRoot(appBaseDirectory, agentSourceRoot))
        {
            return Path.Combine(localAppDataDirectory, "PPT Agent Studio", "artifacts", "decks");
        }

        var repositoryRoot = Path.GetFullPath(Path.Combine(agentSourceRoot, "..", ".."));
        return Path.Combine(repositoryRoot, "artifacts", "decks");
    }

    private static bool IsBundledAgentSourceRoot(string appBaseDirectory, string agentSourceRoot)
    {
        var bundledAgentSourceRoot = Path.GetFullPath(Path.Combine(appBaseDirectory, BundledRuntimeDirectory, "agent", "src"));
        var fullAgentSourceRoot = Path.GetFullPath(agentSourceRoot);
        return string.Equals(bundledAgentSourceRoot, fullAgentSourceRoot, StringComparison.OrdinalIgnoreCase);
    }
}
