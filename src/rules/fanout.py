"""Fan-out 分類 + 每組五條原型 prompt（T1.10；規格 §4.6 / §4.7）。

來源：
  - 分類 8 類與觸發訊號：規格 v2 §4.6；
    理論基礎 https://searchengineland.com/guide/query-fan-out（Google 8 類）
    詞表主要來源 https://moz.com/blog/10-fan-outs-for-prompt-research-whiteboard-friday
  - 5 原型：規格 v2 §4.7；理論基礎
    https://www.semrush.com/blog/chatgpt-topic-authority-study/
  - ≤13 詞形狀約束 + branded 標記實證：
    https://moz.com/blog/50k-fan-outs-reveal-about-brands
  - 排除不實作（規格 §4.6）：翻譯類（權重 0）、entailment/clarification
    （需 LLM 推理——ADR-003 無 LLM）

分類：多命中按 §4.6 表序取第一（comparison → transact → attribute →
perspective → follow_up → recency → tutorial），其餘 semantic（定義類預設）。
recency 年份以 2024–2039 逐字詞界比對（ASCII 邊界下「2026新款」可命中）。

原型：topic 先清洗（剝問句外殼），再套 5 模板；
形狀約束 EN ≤13 詞 / ZH ≤26 字，超過不生成該條；
prompt 含品牌詞 → 標 branded（量的是準確度不是可見度，數據不可混看）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rules._signals import classify_first_match, compile_english
from rules.cjk_norm import contains_cjk, match_form

FANOUT_TYPES = (
    "comparison",
    "transact",
    "attribute",
    "perspective",
    "follow_up",
    "recency",
    "tutorial",
    "semantic",
)

_YEARS = tuple(str(year) for year in range(2024, 2040))

_LEVELS = (
    (
        "comparison",
        compile_english(("vs", "versus", "compare", "alternatives to")),
        ("比較", "邊個好", "邊間好", "定係"),
    ),
    (
        "transact",
        compile_english(("buy", "where to buy", "discount", "coupon", "book")),
        ("邊度買", "點買", "優惠", "預約"),
    ),
    (
        "attribute",
        compile_english(("price", "cost", "how much", "size", "specs", "warranty")),
        ("幾錢", "價錢", "規格", "尺寸", "保養"),
    ),
    (
        "perspective",
        compile_english(("worth it", "review", "rating", "reliable")),
        ("好唔好", "值唔值得", "評價", "有冇伏"),
    ),
    (
        "follow_up",
        compile_english(("after", "how long does", "how often")),
        ("之後", "點算", "幾時", "幾耐"),
    ),
    (
        "recency",
        compile_english(("latest", "new", *_YEARS)),
        ("最新", "新款"),
    ),
    (
        "tutorial",
        compile_english(("how to", "how do", "step by step")),
        ("點樣", "如何", "教學", "入門"),
    ),
)


def classify_fanout(keyword: str) -> str:
    """單一問句/關鍵字 → 8 類 fan-out 之一（semantic 為預設）。"""
    return classify_first_match(keyword, _LEVELS, default="semantic")


TEMPLATE_ORDER = ("definition", "comparison", "alternatives", "use_case", "buying")

EN_TEMPLATES = {
    "definition": "What is {topic}?",
    "comparison": "How does {topic} compare to alternatives?",
    "alternatives": "What are the best alternatives to {topic}?",
    "use_case": "Who is {topic} best for?",
    "buying": "Where can I buy {topic} and how much does it cost?",
}
EN_COMPARISON_WITH_RIVAL = "Which is better, {topic} or {rival}?"

ZH_TEMPLATES = {
    "definition": "{topic}係咩？",
    "comparison": "{topic}同其他選擇比較邊個好？",
    "alternatives": "{topic}有咩替代方案？",
    "use_case": "{topic}適合邊類人？",
    "buying": "{topic}邊度買？幾錢？",
}

MAX_EN_WORDS = 13
MAX_ZH_CHARS = 26

_EN_PREFIX_RE = re.compile(
    r"^(?:what is|what does|how much does|how much do|how long does|how to"
    r"|which|who|why|does|do|is|are)(?![a-z0-9])\s*"
)
_EN_SUFFIX_RE = re.compile(r"\s*(?<![a-z0-9])(?:do|does|cost|charge|take|work|last)$")
_EN_ARTICLE_RE = re.compile(r"^(?:an|a|the)(?![a-z0-9])\s*")

_ZH_PREFIX_RE = re.compile(r"^(?:什麼是|如何|點樣|點解|邊個|邊間)")
_ZH_SUFFIX_RE = re.compile(r"(?:係咩|係甚麼|嗎|呢|咩|？|\?)$")


def clean_topic(hub: str) -> str:
    """剝問句外殼（規格 §4.7）：剝前綴 → 剝尾助動詞/常見動詞 → 剝首冠詞。

    EN 詞表照抄規格；ZH 殼（什麼是/如何/…係咩）為簡版補充，
    與 questions.py 標記一致。非問句 hub 原樣通過。
    """
    text = match_form(hub)
    for pattern in (_EN_PREFIX_RE, _ZH_PREFIX_RE, _EN_SUFFIX_RE, _ZH_SUFFIX_RE, _EN_ARTICLE_RE):
        while True:
            stripped = pattern.sub("", text, count=1).strip()
            if stripped == text:
                break
            text = stripped
    return match_form(text)


@dataclass(frozen=True)
class Prototype:
    template: str
    prompt: str
    branded: bool
    lang: str


def _zh_char_count(text: str) -> int:
    return len([char for char in text if not char.isspace()])


def build_prototypes(
    topic: str,
    brands: tuple[str, ...] = (),
    competitors: tuple[str, ...] = (),
) -> list[Prototype]:
    """cluster hub → 5 條原型 prompt（形狀超限的條目不生成）。

    lang 自動判定：清洗後 topic 含 CJK → ZH 模板，否則 EN。
    EN comparison 有對手名時用 "Which is better, X or Y?" 變體（規格 §4.7）；
    ZH 模板規格無對手變體，一律用原版。
    """
    cleaned = clean_topic(topic)
    if not cleaned:
        return []
    use_zh = contains_cjk(cleaned)
    templates = ZH_TEMPLATES if use_zh else EN_TEMPLATES
    rival = next((c for c in competitors if c.strip()), "")
    lowered_brands = [b.lower() for b in brands if b.strip()]
    prototypes: list[Prototype] = []
    for name in TEMPLATE_ORDER:
        if name == "comparison" and not use_zh and rival:
            prompt = EN_COMPARISON_WITH_RIVAL.format(topic=cleaned, rival=rival)
        else:
            prompt = templates[name].format(topic=cleaned)
        if use_zh:
            fits = _zh_char_count(prompt) <= MAX_ZH_CHARS
        else:
            fits = len(prompt.split()) <= MAX_EN_WORDS
        if not fits:
            continue
        prototypes.append(
            Prototype(
                template=name,
                prompt=prompt,
                branded=any(brand in prompt.lower() for brand in lowered_brands),
                lang="zh" if use_zh else "en",
            )
        )
    return prototypes
