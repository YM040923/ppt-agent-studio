using System;
using System.Collections.Generic;
using System.IO;

namespace PptAgentStudio_App.Services;

public static class RuntimeSidecarLocator
{
    public static string FindAgentSourceRoot(string startDirectory, IReadOnlyDictionary<string, string?> environment)
    {
        if (environment.TryGetValue("PPT_AGENT_RUNTIME_ROOT", out var overrideRoot)
            && !string.IsNullOrWhiteSpace(overrideRoot))
        {
            return Path.Combine(overrideRoot.Trim(), "agent", "src");
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
}
