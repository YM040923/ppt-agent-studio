using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class PreviewInteractionScriptsTests
{
    [TestMethod]
    public void InitializeScriptReusesEmbeddedPreviewApiWhenAvailable()
    {
        var script = PreviewInteractionScripts.Initialize;

        StringAssert.Contains(script, "if (!window.pptAgentPreview)");
        StringAssert.Contains(script, "document.querySelectorAll('.slide')");
        StringAssert.Contains(script, "window.pptAgentPreview.showSlide(0)");
        StringAssert.Contains(script, "showSlideById(slideId)");
        StringAssert.Contains(script, "slide.dataset.slideId");
        StringAssert.Contains(script, "return window.pptAgentPreview.slideCount");
    }
}
