using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class RuntimeSidecarLocatorTests
{
    [TestMethod]
    public void FindAgentSourceRootUsesEnvironmentOverride()
    {
        var env = new Dictionary<string, string?>
        {
            ["PPT_AGENT_RUNTIME_ROOT"] = @"E:\AgentRuntime"
        };

        var root = RuntimeSidecarLocator.FindAgentSourceRoot(@"E:\Other", env);

        Assert.AreEqual(@"E:\AgentRuntime\agent\src", root);
    }

    [TestMethod]
    public void FindAgentSourceRootPrefersBundledRuntimeNextToApp()
    {
        var temp = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        var appOutput = Path.Combine(temp, "app");
        var bundledAgentSrc = Path.Combine(appOutput, "AgentRuntime", "agent", "src");
        var repoAgentSrc = Path.Combine(temp, "agent", "src");
        Directory.CreateDirectory(appOutput);
        Directory.CreateDirectory(bundledAgentSrc);
        Directory.CreateDirectory(repoAgentSrc);

        try
        {
            var root = RuntimeSidecarLocator.FindAgentSourceRoot(appOutput, new Dictionary<string, string?>());

            Assert.AreEqual(bundledAgentSrc, root);
        }
        finally
        {
            Directory.Delete(temp, recursive: true);
        }
    }

    [TestMethod]
    public void FindAgentSourceRootWalksUpToRepoRoot()
    {
        var temp = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        var appOutput = Path.Combine(temp, "desktop", "PptAgentStudio.App", "bin", "Debug");
        var agentSrc = Path.Combine(temp, "agent", "src");
        Directory.CreateDirectory(appOutput);
        Directory.CreateDirectory(agentSrc);

        try
        {
            var root = RuntimeSidecarLocator.FindAgentSourceRoot(appOutput, new Dictionary<string, string?>());

            Assert.AreEqual(agentSrc, root);
        }
        finally
        {
            Directory.Delete(temp, recursive: true);
        }
    }

    [TestMethod]
    public void FindPythonExecutableUsesEnvironmentOverride()
    {
        var env = new Dictionary<string, string?>
        {
            ["PPT_AGENT_PYTHON"] = @"E:\Python\python.exe"
        };

        var python = RuntimeSidecarLocator.FindPythonExecutable(@"E:\App", env);

        Assert.AreEqual(@"E:\Python\python.exe", python);
    }

    [TestMethod]
    public void FindPythonExecutablePrefersBundledRuntimePython()
    {
        var temp = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        var appOutput = Path.Combine(temp, "app");
        var bundledPython = Path.Combine(appOutput, "AgentRuntime", "python", "python.exe");
        Directory.CreateDirectory(Path.GetDirectoryName(bundledPython)!);
        File.WriteAllText(bundledPython, "");

        try
        {
            var python = RuntimeSidecarLocator.FindPythonExecutable(appOutput, new Dictionary<string, string?>());

            Assert.AreEqual(bundledPython, python);
        }
        finally
        {
            Directory.Delete(temp, recursive: true);
        }
    }

    [TestMethod]
    public void FindArtifactDirectoryUsesEnvironmentOverride()
    {
        var env = new Dictionary<string, string?>
        {
            ["PPT_AGENT_ARTIFACTS_DIR"] = @"E:\Decks"
        };

        var directory = RuntimeSidecarLocator.FindArtifactDirectory(
            appBaseDirectory: @"E:\App",
            agentSourceRoot: @"E:\Repo\agent\src",
            localAppDataDirectory: @"C:\Users\Ada\AppData\Local",
            env);

        Assert.AreEqual(@"E:\Decks", directory);
    }

    [TestMethod]
    public void FindArtifactDirectoryUsesLocalAppDataForBundledRuntime()
    {
        var directory = RuntimeSidecarLocator.FindArtifactDirectory(
            appBaseDirectory: @"C:\Program Files\WindowsApps\PptAgentStudio",
            agentSourceRoot: @"C:\Program Files\WindowsApps\PptAgentStudio\AgentRuntime\agent\src",
            localAppDataDirectory: @"C:\Users\Ada\AppData\Local",
            new Dictionary<string, string?>());

        Assert.AreEqual(@"C:\Users\Ada\AppData\Local\PPT Agent Studio\artifacts\decks", directory);
    }

    [TestMethod]
    public void FindArtifactDirectoryKeepsRepositoryArtifactsForDevelopmentRuntime()
    {
        var directory = RuntimeSidecarLocator.FindArtifactDirectory(
            appBaseDirectory: @"E:\Repo\desktop\PptAgentStudio.App\bin\Debug",
            agentSourceRoot: @"E:\Repo\agent\src",
            localAppDataDirectory: @"C:\Users\Ada\AppData\Local",
            new Dictionary<string, string?>());

        Assert.AreEqual(@"E:\Repo\artifacts\decks", directory);
    }

    [TestMethod]
    public void CreateLaunchPlanUsesPythonModuleAndAgentSourcePath()
    {
        var plan = RuntimeSidecarLaunchPlan.Create(
            pythonExecutable: "python",
            agentSourceRoot: @"E:\Repo\agent\src",
            artifactDirectory: @"E:\Repo\artifacts\decks",
            host: "127.0.0.1",
            port: 8765);

        Assert.AreEqual("python", plan.FileName);
        Assert.AreEqual(@"E:\Repo\agent\src", plan.Environment["PYTHONPATH"]);
        Assert.AreEqual(@"E:\Repo\artifacts\decks", plan.Environment["PPT_AGENT_ARTIFACTS_DIR"]);
        StringAssert.Contains(plan.Arguments, "-m ppt_agent_studio.runtime.websocket_server");
        StringAssert.Contains(plan.Arguments, "--host 127.0.0.1");
        StringAssert.Contains(plan.Arguments, "--port 8765");
    }
}
