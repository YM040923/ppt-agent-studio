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
    public void CreateLaunchPlanUsesPythonModuleAndAgentSourcePath()
    {
        var plan = RuntimeSidecarLaunchPlan.Create(
            pythonExecutable: "python",
            agentSourceRoot: @"E:\Repo\agent\src",
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
