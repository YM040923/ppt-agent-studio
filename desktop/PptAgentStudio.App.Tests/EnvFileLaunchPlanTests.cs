using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class EnvFileLaunchPlanTests
{
    [TestMethod]
    public void CreateOpenEnvLocationRejectsBlankPath()
    {
        Assert.ThrowsExactly<ArgumentException>(() => EnvFileLaunchPlan.CreateOpenEnvLocation(" ", envFileExists: false));
    }

    [TestMethod]
    public void CreateOpenEnvLocationSelectsExistingEnvFile()
    {
        var plan = EnvFileLaunchPlan.CreateOpenEnvLocation(@"E:\My Projects\ppt-agent-studio\.env.local", envFileExists: true);

        Assert.AreEqual("explorer.exe", plan.FileName);
        Assert.AreEqual(
            @"/select,""E:\My Projects\ppt-agent-studio\.env.local""",
            plan.Arguments);
    }

    [TestMethod]
    public void CreateOpenEnvLocationOpensParentFolderWhenEnvFileIsMissing()
    {
        var plan = EnvFileLaunchPlan.CreateOpenEnvLocation(@"E:\My Projects\ppt-agent-studio\.env.local", envFileExists: false);

        Assert.AreEqual("explorer.exe", plan.FileName);
        Assert.AreEqual(@"""E:\My Projects\ppt-agent-studio""", plan.Arguments);
    }
}
