from __future__ import annotations

from html import escape
import re

from ppt_agent_studio.deck.spec import DeckSpec


_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def render_preview_document(deck: DeckSpec) -> str:
    preview_background = _theme_color(deck, "background", "#f3f3f3")
    slide_background = _theme_color(deck, "slide_background", "#fff")
    slide_text = _theme_color(deck, "text", "#111827")
    slide_accent = _theme_color(deck, "accent", "#2563EB")
    metadata_tags = _metadata_meta_tags(deck)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"{metadata_tags}"
        "<style>\n"
        ":root { "
        f"--preview-background: {preview_background}; "
        f"--slide-background: {slide_background}; "
        f"--slide-text: {slide_text}; "
        f"--slide-accent: {slide_accent}; "
        "}\n"
        "body { margin: 0; background: var(--preview-background); font-family: Segoe UI, sans-serif; }\n"
        ".deck { padding: 24px; }\n"
        ".deck-header { color: var(--slide-text); font-size: 13px; margin-bottom: 12px; opacity: .72; }\n"
        ".slide { aspect-ratio: 16 / 9; background: var(--slide-background); border-radius: 8px; border-top: 4px solid var(--slide-accent); box-shadow: 0 12px 32px rgba(0,0,0,.14); box-sizing: border-box; color: var(--slide-text); margin: 0 0 18px; padding: 42px; }\n"
        ".page-number { color: var(--slide-accent); font-size: 13px; font-weight: 600; }\n"
        "h1 { font-size: 34px; margin: 34px 0 12px; }\n"
        "p { color: var(--slide-text); font-size: 18px; line-height: 1.45; opacity: .86; }\n"
        ".point { border-top: 1px solid #ddd; padding-top: 12px; }\n"
        ".point strong { display: block; font-size: 18px; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{render_preview_html(deck)}\n"
        f"{_preview_interaction_script()}\n"
        "</body>\n"
        "</html>"
    )


def render_preview_html(deck: DeckSpec) -> str:
    slides = "\n".join(_render_slide(slide.to_dict(), index) for index, slide in enumerate(deck.slides, start=1))
    return (
        f'<main class="deck" data-deck-id="{escape(deck.deck_id)}" data-revision="{deck.revision}">\n'
        f'<header class="deck-header"><span>{escape(deck.title)}</span></header>\n'
        f"{slides}\n"
        "</main>"
    )


def _render_slide(slide: dict[str, object], index: int) -> str:
    slide_id = escape(str(slide.get("slide_id") or f"s{index}"))
    title = escape(str(slide.get("title") or f"Slide {index}"))
    layout = escape(str(slide.get("layout") or "content"))
    blocks = slide.get("blocks") if isinstance(slide.get("blocks"), list) else []
    body = "\n".join(_render_block(block) for block in blocks if isinstance(block, dict))
    speaker_notes = escape(str(slide.get("speaker_notes") or ""))
    notes = f'<aside class="speaker-notes" hidden>{speaker_notes}</aside>\n' if speaker_notes else ""
    return (
        f'<section class="slide slide-{layout}" data-slide-id="{slide_id}" data-slide-index="{index}">\n'
        f'<div class="page-number">{index:02d}</div>\n'
        f"<h1>{title}</h1>\n"
        f'<div class="content">{body}</div>\n'
        f"{notes}"
        "</section>"
    )


def _render_block(block: dict[str, object]) -> str:
    block_type = str(block.get("type") or "text")
    if block_type == "point":
        label = escape(str(block.get("label") or ""))
        body = escape(str(block.get("body") or ""))
        return f'<article class="point"><strong>{label}</strong><p>{body}</p></article>'
    text = escape(str(block.get("text") or ""))
    if text and block_type in {"bullet", "summary_item", "toc_item"}:
        text = f"\u2022 {text}"
    return f'<p class="block block-{escape(block_type)}">{text}</p>'


def _theme_color(deck: DeckSpec, key: str, fallback: str) -> str:
    value = deck.theme.get(key)
    if isinstance(value, str) and _HEX_COLOR.fullmatch(value.strip()):
        return value.strip()
    return fallback


def _metadata_meta_tags(deck: DeckSpec) -> str:
    tags = []
    theme_name = deck.theme.get("name")
    if isinstance(theme_name, str) and theme_name.strip():
        tags.append(f'<meta name="ppt-agent-theme" content="{escape(theme_name.strip())}" />\n')
    for key in ("audience", "style"):
        value = deck.metadata.get(key)
        if isinstance(value, str) and value.strip():
            tags.append(f'<meta name="ppt-agent-{key}" content="{escape(value.strip())}" />\n')
    return "".join(tags)


def _preview_interaction_script() -> str:
    return """
<script>
(() => {
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
  window.pptAgentPreview.showSlide(0);
  window.pptAgentPreview.setZoom(1);
})();
</script>""".strip()
