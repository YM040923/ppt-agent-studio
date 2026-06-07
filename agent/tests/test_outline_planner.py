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


def test_fallback_outline_planner_preserves_prompt_topic():
    planner = FallbackOutlinePlanner()

    async def run():
        return await planner.create_outline("Make a revenue growth deck.")

    outline = asyncio.run(run())

    assert outline["deck_title"] == "Make a revenue growth deck"
    assert len(outline["slides"]) == 3


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
