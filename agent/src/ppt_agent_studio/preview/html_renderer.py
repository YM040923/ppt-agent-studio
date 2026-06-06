from __future__ import annotations

from html import escape

from ppt_agent_studio.deck.spec import DeckSpec


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
