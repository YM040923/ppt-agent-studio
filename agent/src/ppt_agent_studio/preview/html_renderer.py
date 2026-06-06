from __future__ import annotations

from html import escape

from ppt_agent_studio.deck.spec import DeckSpec


def render_preview_document(deck: DeckSpec) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        "<style>\n"
        "body { margin: 0; background: #f3f3f3; font-family: Segoe UI, sans-serif; }\n"
        ".deck { padding: 24px; }\n"
        ".deck-header { color: #555; font-size: 13px; margin-bottom: 12px; }\n"
        ".slide { aspect-ratio: 16 / 9; background: #fff; border-radius: 8px; box-shadow: 0 12px 32px rgba(0,0,0,.14); box-sizing: border-box; margin: 0 0 18px; padding: 42px; }\n"
        ".page-number { color: #777; font-size: 13px; }\n"
        "h1 { font-size: 34px; margin: 34px 0 12px; }\n"
        "p { color: #444; font-size: 18px; line-height: 1.45; }\n"
        ".point { border-top: 1px solid #ddd; padding-top: 12px; }\n"
        ".point strong { display: block; font-size: 18px; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{render_preview_html(deck)}\n"
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
    title = escape(str(slide.get("title") or f"Slide {index}"))
    layout = escape(str(slide.get("layout") or "content"))
    blocks = slide.get("blocks") if isinstance(slide.get("blocks"), list) else []
    body = "\n".join(_render_block(block) for block in blocks if isinstance(block, dict))
    return (
        f'<section class="slide slide-{layout}" data-slide-index="{index}">\n'
        f'<div class="page-number">{index:02d}</div>\n'
        f"<h1>{title}</h1>\n"
        f'<div class="content">{body}</div>\n'
        "</section>"
    )


def _render_block(block: dict[str, object]) -> str:
    block_type = str(block.get("type") or "text")
    if block_type == "point":
        label = escape(str(block.get("label") or ""))
        body = escape(str(block.get("body") or ""))
        return f'<article class="point"><strong>{label}</strong><p>{body}</p></article>'
    text = escape(str(block.get("text") or ""))
    return f'<p class="block block-{escape(block_type)}">{text}</p>'
