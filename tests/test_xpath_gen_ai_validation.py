import json
import unittest

from lxml import etree

from ai.xpath_gen import generate_xpath
from models.schemas import (
    AttrClassification,
    ClassifiedAttribute,
    ClassifiedClassToken,
    ClassifiedElement,
    ExtractType,
    FieldInfo,
)


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str):
        self._content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str):
        self.chat = _FakeChat(content)


class TestAiXPathValidation(unittest.TestCase):
    def test_ai_xpath_validation_uses_fallback_when_primary_misses_target(self):
        html = """
        <html>
          <body>
            <div class="root">
              <span>wrong</span>
              <span>target</span>
            </div>
          </body>
        </html>
        """
        tree = etree.HTML(html)
        target = tree.xpath("//span")[1]

        classified = ClassifiedElement(
            tag="span",
            text_sample="target",
            attributes=[ClassifiedAttribute(attr_name="class", attr_value="", classification=AttrClassification.UNKNOWN)],
            class_tokens=[ClassifiedClassToken(token="x", classification=AttrClassification.RANDOM)],
            ancestor_chain=[],
            prev_sibling=None,
            next_sibling=None,
        )
        field_info = FieldInfo(
            name="title",
            aid="f1",
            extract=ExtractType.TEXT,
            attribute_name=None,
            description="title text",
        )

        ai_payload = json.dumps(
            {
                "xpath": ".//span[1]",
                "strategy": "bad primary",
                "confidence": 0.9,
                "fallback_xpath": ".//span[2]",
                "attributes_used": [],
            }
        )
        client = _FakeClient(ai_payload)

        result = generate_xpath(
            element=target,
            classified=classified,
            field_info=field_info,
            tree=tree,
            container_element=None,
            container_xpath=None,
            client=client,
        )

        self.assertEqual(result.xpath, ".//span[2]")
        self.assertEqual(result.confidence, 0.75)

    def test_ai_prompt_includes_target_dom_context(self):
        html = """
        <html>
          <body>
            <div id="content" class="page main">
              <article class="item css-abcd1234">
                <h2>target title</h2>
                <p>desc</p>
              </article>
              <article class="item">
                <h2>other title</h2>
              </article>
            </div>
          </body>
        </html>
        """
        tree = etree.HTML(html)
        target = tree.xpath("//h2")[0]

        classified = ClassifiedElement(
            tag="h2",
            text_sample="target title",
            attributes=[],
            class_tokens=[],
            ancestor_chain=[],
            prev_sibling=None,
            next_sibling=None,
        )
        field_info = FieldInfo(
            name="title",
            aid="f1",
            extract=ExtractType.TEXT,
            attribute_name=None,
            description="title text",
        )

        ai_payload = json.dumps(
            {
                "xpath": ".//h2[1]",
                "strategy": "ok",
                "confidence": 0.9,
                "fallback_xpath": None,
                "attributes_used": [],
            }
        )
        client = _FakeClient(ai_payload)

        _ = generate_xpath(
            element=target,
            classified=classified,
            field_info=field_info,
            tree=tree,
            container_element=None,
            container_xpath=None,
            client=client,
        )

        prompt = client.chat.completions.last_kwargs["messages"][0]["content"]
        self.assertIn("== TARGET DOM CONTEXT ==", prompt)
        self.assertIn("h2", prompt)
        self.assertIn("id=\"content\"", prompt)

    def test_ai_xpath_validation_rejects_too_broad_xpath_in_container(self):
        html = """
        <html>
          <body>
            <div class="item">
              <span>wrong</span>
              <span>target</span>
            </div>
          </body>
        </html>
        """
        tree = etree.HTML(html)
        container = tree.xpath("//div[@class='item']")[0]
        target = container.xpath(".//span")[1]

        classified = ClassifiedElement(
            tag="span",
            text_sample="target",
            attributes=[],
            class_tokens=[],
            ancestor_chain=[],
            prev_sibling=None,
            next_sibling=None,
        )
        field_info = FieldInfo(
            name="title",
            aid="f1",
            extract=ExtractType.TEXT,
            attribute_name=None,
            description="title text",
        )

        ai_payload = json.dumps(
            {
                "xpath": ".//span",
                "strategy": "too broad primary",
                "confidence": 0.7,
                "fallback_xpath": ".//span[2]",
                "attributes_used": [],
            }
        )
        client = _FakeClient(ai_payload)

        result = generate_xpath(
            element=target,
            classified=classified,
            field_info=field_info,
            tree=tree,
            container_element=container,
            container_xpath="//div[@class='item']",
            client=client,
        )

        self.assertEqual(result.xpath, ".//span[2]")


if __name__ == "__main__":
    unittest.main()
