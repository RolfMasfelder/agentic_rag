"""Reusable prompt templates for LLM interactions.

Each function returns a list of message dicts ready to pass to ``llm.client.chat``
or ``llm.client.chat_stream``.
"""

from __future__ import annotations


def summarize(text: str, language: str = "Deutsch", max_words: int = 200) -> list[dict]:
    """Summarize *text* in up to *max_words* words."""
    return [
        {
            "role": "system",
            "content": (
                f"Du bist ein präziser Textzusammenfasser. "
                f"Fasse den folgenden Text auf {language} in maximal {max_words} Wörtern zusammen. "
                "Behalte alle wichtigen Fakten und Kernaussagen."
            ),
        },
        {"role": "user", "content": text},
    ]


def analyze(text: str, question: str, language: str = "Deutsch") -> list[dict]:
    """Answer *question* based solely on *text*."""
    return [
        {
            "role": "system",
            "content": (
                f"Du bist ein Dokumentenanalyst. Beantworte die Frage ausschließlich "
                f"auf Basis des bereitgestellten Texts. Antworte auf {language}. "
                "Falls die Antwort nicht im Text enthalten ist, sage das klar."
            ),
        },
        {
            "role": "user",
            "content": f"Text:\n{text}\n\nFrage: {question}",
        },
    ]


def retrieval_augmented(query: str, context_chunks: list[str], language: str = "Deutsch") -> list[dict]:
    """Generate a RAG answer from *query* and retrieved *context_chunks*."""
    context = "\n\n---\n\n".join(context_chunks)
    return [
        {
            "role": "system",
            "content": (
                f"Du bist ein hilfreicher Assistent. Beantworte die Frage auf {language} "
                "ausschließlich auf Grundlage der bereitgestellten Kontextabschnitte. "
                "Zitiere relevante Stellen wenn möglich. "
                "Falls der Kontext keine ausreichende Antwort erlaubt, weise darauf hin."
            ),
        },
        {
            "role": "user",
            "content": f"Kontext:\n{context}\n\nFrage: {query}",
        },
    ]


def extract_keywords(text: str, max_keywords: int = 10) -> list[dict]:
    """Extract up to *max_keywords* keywords from *text* as a JSON list."""
    return [
        {
            "role": "system",
            "content": (
                f"Extrahiere die {max_keywords} wichtigsten Schlüsselbegriffe aus dem folgenden Text. "
                "Antworte ausschließlich mit einem JSON-Array von Strings, z.B.: "
                '["Begriff1", "Begriff2"]'
            ),
        },
        {"role": "user", "content": text},
    ]


def compare_documents(text_a: str, text_b: str, language: str = "Deutsch") -> list[dict]:
    """Compare two texts and highlight similarities and differences."""
    return [
        {
            "role": "system",
            "content": (
                f"Vergleiche die folgenden zwei Texte auf {language}. "
                "Beschreibe Gemeinsamkeiten und Unterschiede strukturiert."
            ),
        },
        {
            "role": "user",
            "content": f"Text A:\n{text_a}\n\nText B:\n{text_b}",
        },
    ]
