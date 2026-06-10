using PptAgentStudio_App.Services;
using System.Text;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class EnvFileTemplateWriterTests
{
    [TestMethod]
    public void CreateFromExampleRejectsBlankPath()
    {
        Assert.ThrowsExactly<ArgumentException>(() => EnvFileTemplateWriter.CreateFromExample(" "));
    }

    [TestMethod]
    public void CreateFromExampleCopiesSiblingExampleWhenEnvFileIsMissing()
    {
        var root = CreateTempDirectory();
        var examplePath = Path.Combine(root, ".env.example");
        var envPath = Path.Combine(root, ".env.local");
        File.WriteAllText(examplePath, "OPENAI_API_KEY=replace-with-your-api-key", Encoding.UTF8);

        var result = EnvFileTemplateWriter.CreateFromExample(envPath);

        Assert.IsTrue(result.Created);
        Assert.AreEqual(envPath, result.EnvFilePath);
        Assert.AreEqual("OPENAI_API_KEY=replace-with-your-api-key", File.ReadAllText(envPath, Encoding.UTF8));
    }

    [TestMethod]
    public void CreateFromExampleDoesNotOverwriteExistingEnvFile()
    {
        var root = CreateTempDirectory();
        var envPath = Path.Combine(root, ".env.local");
        File.WriteAllText(envPath, "OPENAI_API_KEY=already-set", Encoding.UTF8);

        var result = EnvFileTemplateWriter.CreateFromExample(envPath);

        Assert.IsFalse(result.Created);
        Assert.AreEqual("OPENAI_API_KEY=already-set", File.ReadAllText(envPath, Encoding.UTF8));
    }

    private static string CreateTempDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "ppt-agent-studio-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(path);
        return path;
    }
}
