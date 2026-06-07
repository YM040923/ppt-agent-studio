namespace PptAgentStudio_App.Services;

public sealed class PreviewPaneState
{
    private const int MinimumZoomPercent = 50;
    private const int MaximumZoomPercent = 200;
    private const int ZoomStepPercent = 10;

    public int SlideCount { get; private set; }

    public int CurrentSlideIndex { get; private set; }

    public int ZoomPercent { get; private set; } = 100;

    public bool CanGoPrevious => CurrentSlideIndex > 0;

    public bool CanGoNext => SlideCount > 0 && CurrentSlideIndex < SlideCount - 1;

    public string PageText => SlideCount == 0 ? "0 / 0" : $"{CurrentSlideIndex + 1} / {SlideCount}";

    public string ZoomText => $"{ZoomPercent}%";

    public void SetSlideCount(int slideCount)
    {
        SlideCount = Math.Max(0, slideCount);
        CurrentSlideIndex = ClampSlideIndex(CurrentSlideIndex);
    }

    public void GoPrevious()
    {
        CurrentSlideIndex = ClampSlideIndex(CurrentSlideIndex - 1);
    }

    public void GoNext()
    {
        CurrentSlideIndex = ClampSlideIndex(CurrentSlideIndex + 1);
    }

    public void ResetSlidePosition()
    {
        CurrentSlideIndex = ClampSlideIndex(0);
    }

    public void ZoomIn()
    {
        ZoomPercent = Math.Min(MaximumZoomPercent, ZoomPercent + ZoomStepPercent);
    }

    public void ZoomOut()
    {
        ZoomPercent = Math.Max(MinimumZoomPercent, ZoomPercent - ZoomStepPercent);
    }

    public void ResetZoom()
    {
        ZoomPercent = 100;
    }

    private int ClampSlideIndex(int index)
    {
        if (SlideCount <= 0)
        {
            return 0;
        }

        return Math.Clamp(index, 0, SlideCount - 1);
    }
}
