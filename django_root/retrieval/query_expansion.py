import logging

logger = logging.getLogger(__name__)

_EXPAND_PROMPT = """\
Erweitere die folgende Suchanfrage um Synonyme und verwandte Fachbegriffe, \
sodass eine Volltextsuche mehr relevante Dokumente findet.

Anfrage: {query}

Antworte ausschließlich mit der erweiterten Suchanfrage als einzelnen Satz oder \
kurzer Phrase – keine Aufzählungen, keine Erklärungen."""


def expand_query(query: str) -> str:
    """Expand *query* with synonyms and related terms via the LLM.

    Returns the expanded query string.  On failure the original query is
    returned unchanged.
    """
    try:
        from llm.client import chat

        expanded = chat(_EXPAND_PROMPT.format(query=query)).strip()
        if expanded:
            logger.debug("Query expanded: %r → %r", query, expanded)
            return expanded
    except Exception:
        logger.warning("Query expansion failed; using original query.")
    return query
