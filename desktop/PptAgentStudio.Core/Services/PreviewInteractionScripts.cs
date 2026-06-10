namespace PptAgentStudio_App.Services;

public static class PreviewInteractionScripts
{
    public const string Initialize = """
        (() => {
          if (!window.pptAgentPreview) {
            const slides = Array.from(document.querySelectorAll('.slide'));
            const clamp = (value, min, max) => Math.max(min, Math.min(value, max));
            window.pptAgentPreview = {
              slideCount: slides.length,
              currentIndex: 0,
              zoom: 1,
              showSlide(index) {
                const maxIndex = Math.max(slides.length - 1, 0);
                this.currentIndex = clamp(Number(index) || 0, 0, maxIndex);
                slides.forEach((slide, slideIndex) => {
                  slide.style.display = slideIndex === this.currentIndex ? 'block' : 'none';
                });
                window.scrollTo(0, 0);
              },
              showSlideById(slideId) {
                const targetIndex = slides.findIndex((slide) => slide.dataset.slideId === String(slideId));
                if (targetIndex >= 0) {
                  this.showSlide(targetIndex);
                }
                return this.currentIndex;
              },
              setZoom(zoom) {
                this.zoom = clamp(Number(zoom) || 1, 0.5, 2);
                document.body.style.zoom = String(this.zoom);
              }
            };
          }
          window.pptAgentPreview.showSlide(0);
          window.pptAgentPreview.setZoom(1);
          return window.pptAgentPreview.slideCount;
        })()
        """;
}
