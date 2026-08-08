import re
import math
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent
ECG_KNOWLEDGE_FILE = BASE_DIR / "ecg_knowledge.txt"
PURC_KNOWLEDGE_FILE = BASE_DIR / "purc_knowledge.txt"

# Below this score, a query is treated as having no relevant knowledge-base match at all
# (prevents forcing 5 low/no-relevance filler docs into the LLM prompt for off-topic questions).
MIN_RELEVANCE_SCORE = 5.0

STOPWORDS = {
    'the', 'and', 'for', 'that', 'with', 'this', 'from', 'your', 'are', 'not',
    'can', 'only', 'have', 'will', 'when', 'which', 'into', 'more', 'but',
    'also', 'use', 'uses', 'using', 'has', 'its', 'our', 'help', 'support',
    'customer', 'service', 'power', 'utility', 'system', 'data', 'may', 'within',
    'during', 'across', 'over', 'under', 'all', 'any', 'some', 'about', 'then',
    'than', 'such', 'each', 'each', 'is', 'what', 'how', 'does', 'did', 'you',
    'want', 'need', 'please', 'would', 'could', 'get', 'good',
}


def tokenize(text: str) -> Counter[str]:
    tokens = re.findall(r"[a-zA-Z]{2,}", text.lower())
    return Counter([t for t in tokens if t not in STOPWORDS])


def _load_knowledge_sections(file_path: Path, section_marker: str, id_prefix: str, source_label: str) -> list[dict]:
    """Load '--- {section_marker}: name ---' delimited sections from a knowledge text file."""
    if not file_path.exists():
        return []

    raw = file_path.read_text(encoding='utf-8', errors='ignore')
    sections = []
    current = {'id': f'{id_prefix}_general', 'text': ''}
    marker_re = re.compile(rf'^--- {re.escape(section_marker)}:\s*(\w+)')

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = marker_re.match(line)
        if m:
            if current['text']:
                sections.append(current)
            current = {'id': f"{id_prefix}_{m.group(1)}", 'text': ''}
            continue
        current['text'] += (' ' + line if current['text'] else line)

    if current['text']:
        sections.append(current)

    cleaned = []
    for section in sections:
        text = re.sub(r'\s+', ' ', section['text']).strip()
        if len(text) < 30:
            continue
        cleaned.append({
            'id': section['id'],
            'text': text,
            'source': source_label,
            'tokens': tokenize(text),
        })

    return cleaned


DOCS = (
    _load_knowledge_sections(ECG_KNOWLEDGE_FILE, "ECG_SECTION", "ecg", "ecg_website")
    + _load_knowledge_sections(PURC_KNOWLEDGE_FILE, "PURC_SECTION", "purc", "purc_website")
)


def _compute_idf(docs: list[dict]) -> dict[str, float]:
    """Inverse document frequency: rare terms score higher than common ones."""
    N = len(docs)
    if N == 0:
        return {}
    df: dict[str, int] = {}
    for doc in docs:
        for term in doc['tokens']:
            df[term] = df.get(term, 0) + 1
    return {term: math.log((N + 1) / (count + 1)) + 1.0 for term, count in df.items()}


IDF = _compute_idf(DOCS)


def _score(query_tokens: Counter[str], doc: dict) -> float:
    """TF-IDF score: term overlap weighted by how rare each term is across the corpus."""
    total = 0.0
    for token, query_tf in query_tokens.items():
        doc_tf = doc['tokens'].get(token, 0)
        if doc_tf > 0:
            tf = min(query_tf, doc_tf)
            total += tf * IDF.get(token, 1.0)
    return total


def retrieve_relevant_docs(query: str, top_n: int = 3) -> list[dict]:
    if not DOCS:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    scored = []
    for doc in DOCS:
        score = _score(query_tokens, doc)
        if score >= MIN_RELEVANCE_SCORE:
            scored.append((score, doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            'id': doc['id'],
            'text': doc['text'][:800],
            'source': doc.get('source', 'unknown'),
        }
        for _, doc in scored[:top_n]
    ]
