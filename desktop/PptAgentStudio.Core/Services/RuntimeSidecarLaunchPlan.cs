using System.Collections.Generic;
using System.IO;

namespace PptAgentStudio_App.Services;

public sealed class RuntimeSidecarLaunchPlan
{
    private RuntimeSidecarLaunchPlan(string fileName, string arguments, Dictionary<string, string> environment)
    {
        FileName = fileName;
        Arguments = arguments;
        Environment = environment;
    }

    public string FileName { get; }

    public string Arguments { get; }

    public IReadOnlyDictionary<string, string> Environment { get; }

    public static RuntimeSidecarLaunchPlan Create(
        string pythonExecutable,
        string agentSourceRoot,
        string artifactDirectory,
        string host,
        int port)
    {
        return new RuntimeSidecarLaunchPlan(
            fileName: pythonExecutable,
            arguments: $"-m ppt_agent_studio.runtime.websocket_server --host {host} --port {port}",
            environment: new Dictionary<string, string>
            {
                ["PYTHONPATH"] = agentSourceRoot,
                ["PPT_AGENT_ARTIFACTS_DIR"] = artifactDirectory,
                ["PYTHONDONTWRITEBYTECODE"] = "1",
            });
    }
}
