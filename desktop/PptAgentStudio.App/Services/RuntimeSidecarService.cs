using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;

namespace PptAgentStudio_App.Services;

public sealed class RuntimeSidecarService : IDisposable
{
    private const string Host = "127.0.0.1";
    private const int Port = 8765;
    private Process? _ownedProcess;

    public async Task<bool> EnsureRunningAsync(CancellationToken cancellationToken = default)
    {
        if (await CanConnectAsync(cancellationToken))
        {
            return true;
        }

        if (!StartOwnedProcess())
        {
            return false;
        }

        for (var i = 0; i < 20; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            await Task.Delay(250, cancellationToken);
            if (await CanConnectAsync(cancellationToken))
            {
                return true;
            }
        }

        return false;
    }

    public void Dispose()
    {
        if (_ownedProcess is { HasExited: false })
        {
            _ownedProcess.Kill(entireProcessTree: true);
        }
        _ownedProcess?.Dispose();
    }

    private static async Task<bool> CanConnectAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var client = new TcpClient();
            await client.ConnectAsync(Host, Port, cancellationToken);
            return true;
        }
        catch
        {
            return false;
        }
    }

    private bool StartOwnedProcess()
    {
        if (_ownedProcess is { HasExited: false })
        {
            return true;
        }

        var env = new Dictionary<string, string?>
        {
            ["PPT_AGENT_RUNTIME_ROOT"] = Environment.GetEnvironmentVariable("PPT_AGENT_RUNTIME_ROOT"),
        };
        var agentSourceRoot = RuntimeSidecarLocator.FindAgentSourceRoot(AppContext.BaseDirectory, env);
        var python = Environment.GetEnvironmentVariable("PPT_AGENT_PYTHON");
        if (string.IsNullOrWhiteSpace(python))
        {
            python = "python";
        }
        var plan = RuntimeSidecarLaunchPlan.Create(python, agentSourceRoot, Host, Port);
        var startInfo = new ProcessStartInfo
        {
            FileName = plan.FileName,
            Arguments = plan.Arguments,
            WorkingDirectory = Path.GetFullPath(Path.Combine(agentSourceRoot, "..", "..")),
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (var item in plan.Environment)
        {
            startInfo.Environment[item.Key] = item.Value;
        }

        try
        {
            _ownedProcess = Process.Start(startInfo);
            return _ownedProcess is not null;
        }
        catch
        {
            return false;
        }
    }
}
