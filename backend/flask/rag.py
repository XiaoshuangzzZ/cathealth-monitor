# -*- coding: utf-8 -*-
"""Lightweight retrieval-augmented generation (RAG) for CatHealth.

Why not embeddings/vector DB?
- The backend deliberately avoids torch and large ML dependencies (Render build
  size and memory constraints). A curated knowledge base plus bilingual keyword
  and n-gram retrieval is cheap, deterministic and runs in pure Python.
- The retrieved excerpts are injected into the DeepSeek system prompt. If the
  knowledge base does not cover a question, the model is instructed to say so
  instead of inventing an answer.
"""

import json
import os
import re

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_KNOWLEDGE_DIR = os.path.join(_BASE_DIR, 'knowledge')
_STOOL_PATH = os.path.join(_KNOWLEDGE_DIR, 'stool_profiles.json')
_RAG_PATH = os.path.join(_KNOWLEDGE_DIR, 'cat_health_rag.json')

_LATIN_RE = re.compile(r"[a-zà-ÿ][a-zà-ÿ\-]{1,}")
_CJK_RE = re.compile(r"[一-鿿]")
_SPACE_RE = re.compile(r"\s+")

# Very common stool words appear in many documents; giving them full keyword
# weight makes every stool profile match every stool question. Keep them useful
# but let specific terms (constipation, blood, soft stool, etc.) dominate.
_GENERIC_KEYWORDS = {
    '大便', '便便', '粪便', '糞便', '排便', 'stool', 'poop', 'feces', 'faeces',
    'fezes', '颜色', '顏色', 'color', 'colour', 'cor', '质地', '質地', 'texture',
    'textura', '形状', '形狀', 'shape', 'forma', '含水量', 'water content',
    'conteúdo de água', 'conteudo de agua', '频率', 'frequency', 'frequência',
}

_DOCS = []
AVAILABLE = False


def _normalize(text):
    return _SPACE_RE.sub(' ', str(text or '').lower()).strip()


def _tokens(text):
    text = _normalize(text)
    words = set(_LATIN_RE.findall(text))
    cjk = _CJK_RE.findall(text)
    bigrams = {cjk[index] + cjk[index + 1] for index in range(len(cjk) - 1)}
    return words | bigrams


def _make_profile_docs(stool_data):
    shared = stool_data.get('shared', {})
    sources_map = stool_data.get('sources', {})
    docs = []

    for class_id, profile in stool_data.get('profiles', {}).items():
        names = profile.get('name', {})
        textures = profile.get('texture', {})
        colors = profile.get('color', {})
        shapes = profile.get('shape', {})
        cause_groups = profile.get('causes', {})
        urgency = profile.get('urgency', {})
        vet_advice = profile.get('vet_advice', {})
        care = profile.get('care', {})
        prevention = profile.get('prevention', {})
        risk = profile.get('risk_label', {})

        keywords = []
        for mapping in (names, textures, colors, shapes, urgency, risk):
            for value in mapping.values():
                if value:
                    keywords.append(str(value))
        for lang_values in cause_groups.values():
            if isinstance(lang_values, list):
                keywords.extend(str(item) for item in lang_values if item)
        # Add language-specific search terms that owners commonly type.
        for value in names.values():
            if value:
                keywords.append(value)
        if profile.get('key') == 'constipation':
            keywords += ['便秘', '乾硬', '干硬', '拉不出', '没拉屎', '沒拉屎', '不拉屎',
                         'hard stool', 'constipation', 'straining', 'constipação',
                         'constipacao', 'prisão de ventre', 'prisao de ventre',
                         'fezes duras', '排便困难', '排便困難']
        elif profile.get('key') == 'diarrhea':
            keywords += ['拉稀', '腹瀉', '腹泻', '水樣', '水样', 'diarrhea', 'diarrhoea',
                         'diarreia', 'watery stool', '拉肚子', '軟便', '软便']
        elif profile.get('key') == 'soft_stool':
            keywords += ['軟便', '软便', '糊状', '糊狀', 'soft stool', 'fezes moles',
                         'mushy stool']
        elif profile.get('key') == 'normal':
            keywords += ['正常', 'normal', 'healthy stool', 'fezes normais']
        elif profile.get('key') == 'no_waste':
            keywords += ['未检测到', '未檢測到', '没看到', '沒看到', 'no waste',
                         'not detected', 'não detetado', 'nao detetado']

        content_en_parts = [
            f"Typical texture: {textures.get('en', '')}",
            f"Typical colour: {colors.get('en', '')}",
            f"Typical shape: {shapes.get('en', '')}",
            f"Possible causes: {', '.join(cause_groups.get('en', []))}",
            f"Urgency: {urgency.get('en', '')}",
            f"Vet advice: {vet_advice.get('en', '')}",
            f"Supportive care: {care.get('en', '')}",
            f"Prevention: {prevention.get('en', '')}",
            f"Red flags: {', '.join(shared.get('red_flags', {}).get('en', []))}",
        ]
        content_zh_parts = [
            f"典型质地：{textures.get('zh-CN', '')}",
            f"典型颜色：{colors.get('zh-CN', '')}",
            f"典型形状：{shapes.get('zh-CN', '')}",
            f"可能原因：{'、'.join(cause_groups.get('zh-CN', []))}",
            f"就医时机：{urgency.get('zh-CN', '')}",
            f"就医建议：{vet_advice.get('zh-CN', '')}",
            f"护理：{care.get('zh-CN', '')}",
            f"预防：{prevention.get('zh-CN', '')}",
            f"危险信号：{'、'.join(shared.get('red_flags', {}).get('zh-CN', []))}",
        ]

        source_names = [sources_map[s]['name'] for s in profile.get('sources', []) if s in sources_map]
        url = next((sources_map[s]['url'] for s in profile.get('sources', []) if s in sources_map), '')

        docs.append({
            'id': 'stool_' + str(profile.get('key') or class_id),
            'title': names.get('en') or names.get('zh-CN') or 'Stool profile',
            'keywords': [k.lower() for k in keywords if k],
            'content_en': '\n'.join(part for part in content_en_parts if part.split(':', 1)[-1].strip()),
            'content_zh': '\n'.join(part for part in content_zh_parts if part.split('：', 1)[-1].strip()),
            'source': '; '.join(source_names) or 'CatHealth knowledge base',
            'url': url,
        })

    return docs


def _load():
    global _DOCS, AVAILABLE

    docs = []
    try:
        with open(_RAG_PATH, 'r', encoding='utf-8') as handle:
            rag_data = json.load(handle)
        for item in rag_data.get('docs', []):
            content_en = str(item.get('content_en', '')).strip()
            content_zh = str(item.get('content_zh', '')).strip()
            if not (content_en or content_zh):
                continue
            docs.append({
                'id': item.get('id', ''),
                'title': item.get('title', ''),
                'keywords': [str(k).lower() for k in item.get('keywords', []) if k],
                'content_en': content_en,
                'content_zh': content_zh,
                'source': item.get('source', ''),
                'url': item.get('url', ''),
            })
    except Exception as error:  # pragma: no cover
        print(f"[RAG] Failed to load {_RAG_PATH}: {error}")

    try:
        with open(_STOOL_PATH, 'r', encoding='utf-8') as handle:
            stool_data = json.load(handle)
        docs.extend(_make_profile_docs(stool_data))
    except Exception as error:  # pragma: no cover
        print(f"[RAG] Failed to load {_STOOL_PATH}: {error}")

    _DOCS = docs
    AVAILABLE = bool(docs)
    print(f"[RAG] Loaded {len(docs)} knowledge documents")
    return docs


_load()


def _score(doc, query, query_tokens, doc_tokens):
    score = 0.0
    for keyword in doc.get('keywords', []):
        keyword = keyword.strip().lower()
        if not keyword:
            continue
        if keyword in query:
            if keyword in _GENERIC_KEYWORDS:
                score += 1.5
            else:
                score += 5.0 + min(len(keyword), 12) * 0.4

    score += len(query_tokens & doc_tokens) * 0.6

    title = _normalize(doc.get('title', ''))
    if title and title in query:
        score += 4.0

    return score


def retrieve(query, language='zh-CN', top_k=4, min_score=3.0):
    """Return the most relevant knowledge documents for a query."""
    if not _DOCS:
        return []

    normalized = _normalize(query)
    if len(normalized) < 2:
        return []

    query_tokens = _tokens(normalized)
    scored = []
    for doc in _DOCS:
        doc_text = ' '.join([
            doc.get('title', ''),
            ' '.join(doc.get('keywords', [])),
            doc.get('content_en', ''),
            doc.get('content_zh', ''),
        ])
        doc_tokens = _tokens(doc_text)
        score = _score(doc, normalized, query_tokens, doc_tokens)
        if score >= min_score:
            scored.append((score, doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc for _, doc in scored[:max(1, top_k)]]


def context_from_docs(docs, language='zh-CN', max_chars=4200):
    """Build a compact, language-appropriate context block for the LLM."""
    if not docs:
        return ''

    use_chinese = language in ('zh-CN', 'zh-TW')
    blocks = []
    total = 0

    for index, doc in enumerate(docs, start=1):
        content = doc.get('content_zh' if use_chinese else 'content_en', '').strip()
        if not content:
            content = doc.get('content_en') or doc.get('content_zh') or ''
        block = f"[{index}] {doc.get('title', '')}\n{content}\nSource: {doc.get('source', '')}"
        if total + len(block) > max_chars:
            break
        blocks.append(block)
        total += len(block)

    return '\n\n'.join(blocks)


def build_context(query, language='zh-CN', top_k=4):
    return context_from_docs(retrieve(query, language, top_k=top_k), language)


def status():
    return {
        'available': AVAILABLE,
        'documents': len(_DOCS),
        'ids': [doc.get('id') for doc in _DOCS],
    }
