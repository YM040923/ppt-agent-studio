import asyncio

from ppt_agent_studio.planning.outline import FallbackOutlinePlanner, LLMOutlinePlanner


class FakeChatClient:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def complete(self, messages, temperature=0.2):
        self.calls.append({"messages": list(messages), "temperature": temperature})
        return self.response


def test_llm_outline_planner_parses_json_response():
    chat_client = FakeChatClient(
        """
        ```json
        {
          "deck_title": "AI Strategy",
          "slides": [
            {"title": "AI Strategy", "prototype_hint": "cover"},
            {"title": "Operating Model", "bullets": ["Focus", "Sequence"]}
          ]
        }
        ```
        """
    )
    planner = LLMOutlinePlanner(chat_client=chat_client)

    async def run():
        return await planner.create_outline("Make a board AI strategy deck")

    outline = asyncio.run(run())

    assert outline["deck_title"] == "AI Strategy"
    assert outline["slides"][1]["title"] == "Operating Model"
    assert chat_client.calls[0]["temperature"] == 0.2
    assert chat_client.calls[0]["messages"][0]["role"] == "system"
    assert "DeckSpec" in chat_client.calls[0]["messages"][0]["content"]
    assert chat_client.calls[0]["messages"][1] == {
        "role": "user",
        "content": "Make a board AI strategy deck",
    }


def test_llm_outline_planner_parses_json_embedded_in_provider_text():
    chat_client = FakeChatClient(
        """
        Sure, here is the requested DeckSpec outline:
        {
          "deck_title": "Market Expansion",
          "slides": [
            {"title": "Market Expansion", "prototype_hint": "cover"}
          ]
        }
        Let me know if you want speaker notes.
        """
    )
    planner = LLMOutlinePlanner(chat_client=chat_client)

    async def run():
        return await planner.create_outline("Make a market expansion deck")

    outline = asyncio.run(run())

    assert outline["deck_title"] == "Market Expansion"
    assert outline["slides"][0]["title"] == "Market Expansion"


def test_llm_outline_planner_adds_theme_when_model_omits_it():
    chat_client = FakeChatClient(
        """
        {
          "deck_title": "AI Transformation",
          "slides": [
            {"title": "AI Transformation", "prototype_hint": "cover"}
          ]
        }
        """
    )
    planner = LLMOutlinePlanner(chat_client=chat_client)

    async def run():
        return await planner.create_outline("帮我做一个关于 AI 转型的 PPT，目标受众是高层管理者，风格麦肯锡")

    outline = asyncio.run(run())

    assert outline["theme"] == {
        "name": "executive-consulting",
        "background": "#EEF2F7",
        "slide_background": "#FFFFFF",
        "text": "#111827",
        "accent": "#2563EB",
    }


def test_llm_outline_planner_adds_deck_title_when_model_omits_it():
    chat_client = FakeChatClient(
        """
        {
          "slides": [
            {"title": "Opening", "prototype_hint": "cover"}
          ]
        }
        """
    )
    planner = LLMOutlinePlanner(chat_client=chat_client)

    async def run():
        return await planner.create_outline("Make a board AI strategy deck in McKinsey style")

    outline = asyncio.run(run())

    assert outline["deck_title"] == "Board AI Strategy"


def test_llm_outline_planner_falls_back_when_provider_returns_non_json():
    chat_client = FakeChatClient("I can help with that, but here is prose instead of JSON.")
    planner = LLMOutlinePlanner(chat_client=chat_client)

    async def run():
        return await planner.create_outline("Make a 4 page AI strategy deck")

    outline = asyncio.run(run())

    assert outline["deck_title"] == "AI Strategy"
    assert len(outline["slides"]) == 4
    assert outline["slides"][-1]["title"] == "Implementation roadmap"


def test_llm_outline_planner_adds_fallback_slides_when_model_omits_them():
    chat_client = FakeChatClient(
        """
        {
          "deck_title": "Market Expansion",
          "slides": []
        }
        """
    )
    planner = LLMOutlinePlanner(chat_client=chat_client)

    async def run():
        return await planner.create_outline("Make a 4 page market expansion deck")

    outline = asyncio.run(run())

    assert outline["deck_title"] == "Market Expansion"
    assert len(outline["slides"]) == 4
    assert outline["slides"][0]["title"] == "Market Expansion"
    assert outline["slides"][-1]["title"] == "Implementation roadmap"


def test_llm_outline_planner_caps_excessive_model_slides():
    slides_json = ",\n".join(
        f'{{"title": "Slide {index}", "prototype_hint": "content"}}'
        for index in range(1, 36)
    )
    chat_client = FakeChatClient(
        f"""
        {{
          "deck_title": "Oversized Deck",
          "slides": [
            {slides_json}
          ]
        }}
        """
    )
    planner = LLMOutlinePlanner(chat_client=chat_client)

    async def run():
        return await planner.create_outline("Make a 100 page board strategy deck")

    outline = asyncio.run(run())

    assert len(outline["slides"]) == 30
    assert outline["slides"][0]["title"] == "Slide 1"
    assert outline["slides"][-1]["title"] == "Slide 30"


def test_llm_outline_planner_backfills_when_model_returns_too_few_slides():
    chat_client = FakeChatClient(
        """
        {
          "deck_title": "AI Operating Model",
          "slides": [
            {"title": "AI Operating Model", "prototype_hint": "cover"},
            {"title": "Current State", "prototype_hint": "content"}
          ]
        }
        """
    )
    planner = LLMOutlinePlanner(chat_client=chat_client)

    async def run():
        return await planner.create_outline("Make a 5 page AI operating model deck")

    outline = asyncio.run(run())

    assert len(outline["slides"]) == 5
    assert outline["slides"][0]["title"] == "AI Operating Model"
    assert outline["slides"][1]["title"] == "Current State"
    assert outline["slides"][-1]["title"] == "Implementation roadmap"


def test_fallback_outline_planner_derives_clean_prompt_topic():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline("Make a revenue growth deck.")

    outline = asyncio.run(run())

    assert outline["deck_title"] == "Revenue Growth"
    assert len(outline["slides"]) == 3


def test_fallback_outline_planner_derives_clean_english_deck_title():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline("Make a 5 slide board AI strategy deck in McKinsey style")

    outline = asyncio.run(run())

    assert outline["deck_title"] == "Board AI Strategy"
    assert outline["slides"][0]["title"] == "Board AI Strategy"


def test_fallback_outline_planner_starts_multislide_decks_with_executive_summary():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline("Make a 5 slide board AI strategy deck in McKinsey style")

    outline = asyncio.run(run())
    summary = outline["slides"][1]

    assert summary["title"] == "Executive summary"
    assert [point["label"] for point in summary["points"]] == ["Recommendation", "Impact", "Next step"]


def test_fallback_outline_planner_derives_clean_chinese_deck_title():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline(
            "\u5e2e\u6211\u505a\u4e00\u4e2a\u5173\u4e8e AI \u8f6c\u578b\u7684 20 \u9875 PPT"
        )

    outline = asyncio.run(run())

    assert outline["deck_title"] == "AI \u8f6c\u578b"
    assert outline["slides"][0]["title"] == "AI \u8f6c\u578b"


def test_fallback_outline_planner_extracts_audience_and_style_metadata():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline(
            "Make a 6 page AI strategy deck for the executive committee, style McKinsey"
        )

    outline = asyncio.run(run())

    assert outline["metadata"] == {
        "audience": "executive committee",
        "style": "McKinsey",
    }


def test_fallback_outline_planner_extracts_chinese_audience_and_style_metadata():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline(
            "\u76ee\u6807\u53d7\u4f17\u662f\u9ad8\u5c42\u7ba1\u7406\u8005\uff0c\u98ce\u683c\u9ea6\u80af\u9521"
        )

    outline = asyncio.run(run())

    assert outline["metadata"] == {
        "audience": "\u9ad8\u5c42\u7ba1\u7406\u8005",
        "style": "\u9ea6\u80af\u9521",
    }


def test_fallback_outline_planner_derives_executive_theme_from_real_chinese_prompt():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline(
            "\u5e2e\u6211\u505a\u4e00\u4e2a\u5173\u4e8e AI \u8f6c\u578b\u7684 PPT\uff0c"
            "\u76ee\u6807\u53d7\u4f17\u662f\u9ad8\u5c42\u7ba1\u7406\u8005\uff0c"
            "\u98ce\u683c\u9ea6\u80af\u9521"
        )

    outline = asyncio.run(run())

    assert outline["theme"]["name"] == "executive-consulting"
    assert outline["theme"]["accent"] == "#2563EB"


def test_fallback_outline_planner_respects_requested_slide_count():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline("帮我做一个关于 AI 转型的 20 页 PPT，目标受众是高层管理者")

    outline = asyncio.run(run())

    assert len(outline["slides"]) == 20
    assert outline["slides"][0]["prototype_hint"] == "cover"
    assert outline["slides"][-1]["title"] == "Implementation roadmap"


def test_fallback_outline_planner_caps_large_requested_slide_count():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline("Create a 100 page board strategy deck")

    outline = asyncio.run(run())

    assert len(outline["slides"]) == 30


def test_fallback_outline_planner_reads_chinese_number_slide_count():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline("帮我做一个关于 AI 转型的二十页 PPT")

    outline = asyncio.run(run())

    assert len(outline["slides"]) == 20


def test_fallback_outline_planner_reads_real_chinese_digit_slide_count():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline(
            "\u5e2e\u6211\u505a\u4e00\u4e2a\u5173\u4e8e AI \u8f6c\u578b\u7684 20 \u9875 PPT"
        )

    outline = asyncio.run(run())

    assert len(outline["slides"]) == 20


def test_fallback_outline_planner_reads_real_chinese_number_slide_count():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline(
            "\u5e2e\u6211\u505a\u4e00\u4e2a\u5173\u4e8e AI \u8f6c\u578b\u7684\u4e8c\u5341\u9875 PPT"
        )

    outline = asyncio.run(run())

    assert len(outline["slides"]) == 20


def test_fallback_outline_planner_derives_executive_consulting_theme():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline("帮我做一个关于 AI 转型的 PPT，目标受众是高层管理者，风格麦肯锡")

    outline = asyncio.run(run())

    assert outline["theme"] == {
        "name": "executive-consulting",
        "background": "#EEF2F7",
        "slide_background": "#FFFFFF",
        "text": "#111827",
        "accent": "#2563EB",
    }
