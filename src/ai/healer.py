"""
XPath Self-Healing: detects broken XPaths and repairs them.
"""

import re
import json
import logging
from openai import OpenAI
from models.schemas import FieldXPath, FieldHealth, ExtractType
import config

logger = logging.getLogger(__name__)

HEALING_PROMPT_TEMPLATE = '''You are debugging a broken web scraper XPath.

== WHAT WE ARE LOOKING FOR ==
Field name: {field_name}
Description: {field_description}
Data extraction type: {extract_type}
Previously extracted sample values:
{sample_values_formatted}

== WHAT STOPPED WORKING ==
Old XPath (relative to container): {old_xpath}
Old fallback XPath: {old_fallback_xpath}
Container XPath: {container_xpath}
Container XPath still working: {container_works}
The field XPath now returns: empty / null

== CURRENT PAGE HTML ==
(annotated with data-aid attributes on every element)

{annotated_html}

== TASK ==
Find the element in the current HTML that contains the same type
of data described above. The data is still present on the page
but the HTML structure has changed.

Return its data-aid value so we can generate a new XPath.

If the container XPath is also broken, provide a new container_aid too.

Return valid JSON only, no markdown fences, no other text:
{{
  "found": true,
  "aid": "eXX",
  "container_aid": "eXX",
  "container_changed": false,
  "reasoning": "brief explanation of what changed in the page structure"
}}

If the data genuinely no longer exists on the page:
{{
  "found": false,
  "reasoning": "explanation of why the data appears to be missing"
}}'''


class FieldHealthTracker:
    """Tracks extraction success/failure per field across pages."""

    def __init__(self, fields: list[FieldXPath]):
        self._health: dict[str, FieldHealth] = {}
        for field in fields:
            self._health[field.name] = FieldHealth(name=field.name)

    def record(self, field_name: str, value: str | None):
        """Record an extraction result."""
        if field_name not in self._health:
            return
        health = self._health[field_name]
        health.recent_results.append(value)
        if len(health.recent_results) > 10:
            health.recent_results = health.recent_results[-10:]
        if value is not None:
            health.sample_values.append(value)
            if len(health.sample_values) > 5:
                health.sample_values = health.sample_values[-5:]

    def needs_healing(self, field_name: str) -> bool:
        """Check if field needs healing."""
        if field_name not in self._health:
            return False
        health = self._health[field_name]
        if len(health.recent_results) < 3:
            return False

        # Check consecutive failures
        consecutive = 0
        for v in reversed(health.recent_results):
            if v is None:
                consecutive += 1
            else:
                break
        if consecutive >= config.HEAL_CONSECUTIVE_THRESHOLD:
            return True

        # Check failure rate in last 5
        last_5 = health.recent_results[-5:]
        failures = sum(1 for v in last_5 if v is None)
        if failures / len(last_5) > config.HEAL_RATE_THRESHOLD:
            return True

        return False

    def can_heal(self, field_name: str) -> bool:
        """Check if we haven't exceeded max heal attempts."""
        if field_name not in self._health:
            return False
        return self._health[field_name].heal_attempts < config.MAX_HEAL_ATTEMPTS

    def record_heal_attempt(self, field_name: str):
        """Increment heal attempts counter."""
        if field_name in self._health:
            self._health[field_name].heal_attempts += 1

    def reset_health(self, field_name: str):
        """Reset after successful heal."""
        if field_name in self._health:
            self._health[field_name].recent_results = []
            self._health[field_name].heal_attempts = 0

    def get_sample_values(self, field_name: str) -> list[str]:
        """Return stored sample values."""
        if field_name in self._health:
            return self._health[field_name].sample_values
        return []

    def check_cascade(self) -> bool:
        """Check if majority of fields are failing."""
        if not self._health:
            return False
        failing = sum(1 for name in self._health if self.needs_healing(name))
        return failing / len(self._health) > config.CASCADE_THRESHOLD


def try_code_recovery(
    old_xpath: str,
    field: FieldXPath,
    tree,
    container_element=None
) -> str | None:
    """Try to fix broken XPath without AI."""
    context = container_element if container_element is not None else tree

    # Strategy 1: Fuzzy class match
    class_match = re.search(r"contains\(@class,\s*'([^']+)'\)", old_xpath)
    if class_match:
        old_class = class_match.group(1)
        for el in tree.iter():
            if not isinstance(el.tag, str):
                continue
            el_class = el.get("class", "")
            for token in el_class.split():
                if _is_similar(old_class, token):
                    new_xpath = old_xpath.replace(old_class, token)
                    try:
                        results = context.xpath(new_xpath.split("/text()")[0].split("/@")[0])
                        if results:
                            return new_xpath
                    except Exception:
                        continue

    # Strategy 2: Text pattern match
    sample_values = field.sample_value
    if sample_values:
        pattern = _infer_pattern(sample_values)
        if pattern:
            for el in tree.iter():
                if not isinstance(el.tag, str):
                    continue
                text = (el.text or "").strip()
                if text and re.match(pattern, text):
                    # Build simple xpath from this element
                    el_class = el.get("class", "")
                    if el_class:
                        for token in el_class.split():
                            xpath = f".//{el.tag}[contains(@class, '{token}')]"
                            if field.extract == ExtractType.TEXT:
                                xpath += "/text()"
                            elif field.extract == ExtractType.ATTRIBUTE and field.attribute_name:
                                xpath += f"/@{field.attribute_name}"
                            try:
                                results = context.xpath(xpath.split("/text()")[0].split("/@")[0])
                                if len(results) >= 1:
                                    return xpath
                            except Exception:
                                continue

    return None


def heal_xpath(
    field: FieldXPath,
    sample_values: list[str],
    annotated_html: str,
    container_xpath: str | None,
    container_works: bool,
    client: OpenAI
) -> dict | None:
    """Use AI to find the element in updated HTML."""
    sample_str = "\n".join(f"  - {v}" for v in sample_values) if sample_values else "  (no samples)"

    prompt = HEALING_PROMPT_TEMPLATE.format(
        field_name=field.name,
        field_description=field.description,
        extract_type=field.extract.value,
        sample_values_formatted=sample_str,
        old_xpath=field.xpath,
        old_fallback_xpath=field.fallback_xpath or "None",
        container_xpath=container_xpath or "None",
        container_works=str(container_works),
        annotated_html=annotated_html
    )

    try:
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        data = json.loads(content)
        if data.get("found"):
            return {
                "aid": data["aid"],
                "container_aid": data.get("container_aid"),
                "container_changed": data.get("container_changed", False)
            }
        else:
            logger.warning(f"Healing: field {field.name} not found - {data.get('reasoning')}")
            return None
    except Exception as e:
        logger.error(f"AI healing failed: {e}")
        return None


def perform_healing(
    field: FieldXPath,
    health_tracker: FieldHealthTracker,
    tree,
    annotated_html: str,
    container_element,
    container_xpath: str,
    client: OpenAI,
    classified_element_fn
) -> FieldXPath | None:
    """Full healing pipeline for one field."""
    health_tracker.record_heal_attempt(field.name)

    # 1. Try code recovery
    new_xpath = try_code_recovery(field.xpath, field, tree, container_element)
    if new_xpath:
        # Validate
        try:
            context = container_element if container_element is not None else tree
            base_xpath = new_xpath.split("/text()")[0].split("/@")[0]
            results = context.xpath(base_xpath)
            if results:
                health_tracker.reset_health(field.name)
                return FieldXPath(
                    name=field.name,
                    description=field.description,
                    xpath=new_xpath,
                    fallback_xpath=field.fallback_xpath,
                    confidence=0.7,
                    extract=field.extract,
                    attribute_name=field.attribute_name,
                    sample_value=field.sample_value
                )
        except Exception:
            pass

    # 2. Try AI healing
    sample_values = health_tracker.get_sample_values(field.name)
    container_works = container_element is not None and _test_container(container_xpath, tree)

    heal_result = heal_xpath(field, sample_values, annotated_html, container_xpath, container_works, client)
    if heal_result:
        from preprocessing.annotator import resolve_aid
        element = resolve_aid(tree, heal_result["aid"])
        if element is not None:
            # Classify and generate new xpath
            from preprocessing.annotator import get_sibling_elements
            siblings = get_sibling_elements(element, container_element) if container_element is not None else []
            classified = classified_element_fn(element, siblings, tree)

            from ai.xpath_gen import generate_xpath
            from models.schemas import FieldInfo
            fi = FieldInfo(
                name=field.name,
                aid=heal_result["aid"],
                extract=field.extract,
                attribute_name=field.attribute_name,
                description=field.description
            )
            xpath_result = generate_xpath(element, classified, fi, tree, container_element, container_xpath, client)

            # Validate
            try:
                context = container_element if container_element is not None else tree
                base_xpath = xpath_result.xpath.split("/text()")[0].split("/@")[0]
                results = context.xpath(base_xpath)
                if results:
                    health_tracker.reset_health(field.name)
                    return FieldXPath(
                        name=field.name,
                        description=field.description,
                        xpath=xpath_result.xpath,
                        fallback_xpath=xpath_result.fallback_xpath,
                        confidence=xpath_result.confidence,
                        extract=field.extract,
                        attribute_name=field.attribute_name,
                        sample_value=field.sample_value
                    )
            except Exception:
                pass

    logger.warning(f"Healing failed for field: {field.name}")
    return None


def validate_healed_xpath(
    xpath: str,
    field: FieldXPath,
    tree,
    container_element=None,
    sample_pages: list = None
) -> bool:
    """Validate that healed XPath extracts reasonable data."""
    context = container_element if container_element is not None else tree
    try:
        results = context.xpath(xpath)
        if not results:
            return False

        # Get first value
        value = results[0]
        if hasattr(value, 'text_content'):
            value = value.text_content().strip()
        else:
            value = str(value).strip()

        if not value:
            return False

        # Type consistency check
        if field.sample_value:
            if re.match(r'[\$\€\¥\£\₹]\s*\d+', field.sample_value):
                if not re.match(r'[\$\€\¥\£\₹]\s*\d+', value):
                    return False
            if field.sample_value.startswith(("http", "/")):
                if not value.startswith(("http", "/")):
                    return False

        return True
    except Exception:
        return False


def _is_similar(a: str, b: str) -> bool:
    """Check if two strings are similar (substring or small edit distance)."""
    if a in b or b in a:
        return True
    if abs(len(a) - len(b)) > 3:
        return False
    # Simple character-level comparison
    matches = sum(1 for ca, cb in zip(a, b) if ca == cb)
    return matches >= min(len(a), len(b)) - 2


def _infer_pattern(sample: str) -> str | None:
    """Infer regex pattern from sample value."""
    if re.match(r'[\$\€\¥\£\₹]\s*\d+', sample):
        return r'[\$\€\¥\£\₹]\s*\d+'
    if re.match(r'\d+\.\d{2}', sample):
        return r'\d+\.\d{2}'
    if sample.startswith(("http://", "https://", "/")):
        return r'https?://|/'
    if re.match(r'[\w.+-]+@[\w-]+\.[\w.]+', sample):
        return r'[\w.+-]+@[\w-]+\.[\w.]+'
    return None


def _test_container(container_xpath: str, tree) -> bool:
    """Test if container xpath still works."""
    try:
        results = tree.xpath(container_xpath)
        return len(results) > 0
    except Exception:
        return False
