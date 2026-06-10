using System.Xml.Linq;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class PackageManifestTests
{
    [TestMethod]
    public void PackageManifestUsesProjectBranding()
    {
        var manifest = XDocument.Load(FindPackageManifest());
        XNamespace foundation = "http://schemas.microsoft.com/appx/manifest/foundation/windows10";
        XNamespace uap = "http://schemas.microsoft.com/appx/manifest/uap/windows10";

        var identity = manifest.Root?.Element(foundation + "Identity");
        var properties = manifest.Root?.Element(foundation + "Properties");
        var visualElements = manifest.Root?
            .Element(foundation + "Applications")?
            .Element(foundation + "Application")?
            .Element(uap + "VisualElements");

        Assert.AreEqual("YM040923.PptAgentStudio", identity?.Attribute("Name")?.Value);
        Assert.AreEqual("CN=PPT Agent Studio Open Source", identity?.Attribute("Publisher")?.Value);
        Assert.AreEqual("PPT Agent Studio", properties?.Element(foundation + "DisplayName")?.Value);
        Assert.AreEqual("PPT Agent Studio Contributors", properties?.Element(foundation + "PublisherDisplayName")?.Value);
        Assert.AreEqual("PPT Agent Studio", visualElements?.Attribute("DisplayName")?.Value);
        Assert.AreEqual("Presentation-focused AI Agent for Windows", visualElements?.Attribute("Description")?.Value);
    }

    [TestMethod]
    public void AppProjectPackagesAgentSourceUnderBundledRuntimeLayout()
    {
        var project = XDocument.Load(FindAppProject());
        var ns = project.Root?.Name.Namespace ?? XNamespace.None;
        var contentItems = project.Descendants(ns + "Content");

        var agentRuntimeContent = contentItems.SingleOrDefault(element =>
            element.Attribute("Include")?.Value == @"..\..\agent\src\**\*");

        Assert.IsNotNull(agentRuntimeContent);
        Assert.AreEqual(@"AgentRuntime\agent\src\%(RecursiveDir)%(Filename)%(Extension)", agentRuntimeContent.Attribute("Link")?.Value);
        Assert.AreEqual("PreserveNewest", agentRuntimeContent.Attribute("CopyToOutputDirectory")?.Value);
        Assert.AreEqual("PreserveNewest", agentRuntimeContent.Attribute("CopyToPublishDirectory")?.Value);
    }

    [TestMethod]
    public void AppProjectExcludesPythonCacheFilesFromBundledRuntime()
    {
        var project = XDocument.Load(FindAppProject());
        var ns = project.Root?.Name.Namespace ?? XNamespace.None;
        var contentItems = project.Descendants(ns + "Content");

        var agentRuntimeContent = contentItems.SingleOrDefault(element =>
            element.Attribute("Include")?.Value == @"..\..\agent\src\**\*");

        Assert.IsNotNull(agentRuntimeContent);
        Assert.AreEqual(@"..\..\agent\src\**\__pycache__\**;..\..\agent\src\**\*.pyc", agentRuntimeContent.Attribute("Exclude")?.Value);
    }

    [TestMethod]
    public void AppProjectPackagesStagedPythonRuntimeUnderBundledRuntimeLayout()
    {
        var project = XDocument.Load(FindAppProject());
        var ns = project.Root?.Name.Namespace ?? XNamespace.None;
        var contentItems = project.Descendants(ns + "Content");

        var pythonRuntimeContent = contentItems.SingleOrDefault(element =>
            element.Attribute("Include")?.Value == @"AgentRuntime\python\**\*");

        Assert.IsNotNull(pythonRuntimeContent);
        Assert.AreEqual(@"AgentRuntime\python\%(RecursiveDir)%(Filename)%(Extension)", pythonRuntimeContent.Attribute("Link")?.Value);
        Assert.AreEqual("PreserveNewest", pythonRuntimeContent.Attribute("CopyToOutputDirectory")?.Value);
        Assert.AreEqual("PreserveNewest", pythonRuntimeContent.Attribute("CopyToPublishDirectory")?.Value);
    }

    private static string FindPackageManifest()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "desktop", "PptAgentStudio.App", "Package.appxmanifest");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException("Package.appxmanifest was not found.");
    }

    private static string FindAppProject()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "desktop", "PptAgentStudio.App", "PptAgentStudio.App.csproj");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException("PptAgentStudio.App.csproj was not found.");
    }
}
