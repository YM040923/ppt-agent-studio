using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class PreviewPaneStateTests
{
    [TestMethod]
    public void SlideNavigationClampsToAvailableSlides()
    {
        var state = new PreviewPaneState();

        state.SetSlideCount(3);
        state.GoNext();
        state.GoNext();
        state.GoNext();

        Assert.AreEqual(2, state.CurrentSlideIndex);
        Assert.AreEqual("3 / 3", state.PageText);
        Assert.IsFalse(state.CanGoNext);

        state.GoPrevious();
        state.GoPrevious();
        state.GoPrevious();

        Assert.AreEqual(0, state.CurrentSlideIndex);
        Assert.AreEqual("1 / 3", state.PageText);
        Assert.IsFalse(state.CanGoPrevious);
    }

    [TestMethod]
    public void SlideCountChangesClampCurrentSlide()
    {
        var state = new PreviewPaneState();

        state.SetSlideCount(5);
        state.GoNext();
        state.GoNext();
        state.GoNext();
        state.SetSlideCount(2);

        Assert.AreEqual(1, state.CurrentSlideIndex);
        Assert.AreEqual("2 / 2", state.PageText);
    }

    [TestMethod]
    public void ResetSlidePositionReturnsPreviewToFirstSlide()
    {
        var state = new PreviewPaneState();

        state.SetSlideCount(4);
        state.GoNext();
        state.GoNext();

        state.ResetSlidePosition();

        Assert.AreEqual(0, state.CurrentSlideIndex);
        Assert.AreEqual("1 / 4", state.PageText);

        state.SetSlideCount(0);
        state.ResetSlidePosition();

        Assert.AreEqual(0, state.CurrentSlideIndex);
        Assert.AreEqual("0 / 0", state.PageText);
    }

    [TestMethod]
    public void ZoomStaysWithinPreviewBounds()
    {
        var state = new PreviewPaneState();

        for (var index = 0; index < 20; index++)
        {
            state.ZoomIn();
        }

        Assert.AreEqual(200, state.ZoomPercent);
        Assert.AreEqual("200%", state.ZoomText);

        for (var index = 0; index < 30; index++)
        {
            state.ZoomOut();
        }

        Assert.AreEqual(50, state.ZoomPercent);
        Assert.AreEqual("50%", state.ZoomText);

        state.ResetZoom();

        Assert.AreEqual(100, state.ZoomPercent);
        Assert.AreEqual("100%", state.ZoomText);
    }
}
