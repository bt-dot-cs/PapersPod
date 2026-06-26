"""
Extract references from an anchor paper's PDF via the Claude document API.
"""

import base64
import json
import logging
from typing import Optional

import httpx
import anthropic

from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from core.models import Paper

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
You are a reference extraction assistant. The document provided is a research paper PDF.

Extract every entry from the bibliography / references section.
Return a JSON array where each element is:
{
  "title": "exact paper title as printed",
  "authors": ["Last, First", ...],
  "year": 2024
}

Rules:
- Include only papers with a recoverable title.
- authors: first author only is fine if the list is long.
- year: integer; omit the key if unknown.
- Return ONLY the raw JSON array — no markdown fences, no commentary.
- If the references section is missing or unreadable, return an empty array: []
"""


async def extract_references(anchor: Paper) -> list[dict]:
    """Fetch the anchor PDF and extract its reference list via Claude.

    Returns a list of dicts with 'title' (required), 'authors', 'year' keys.
    Cost: ~$0.03–0.08 per PDF depending on length.
    """
    if not anchor.pdf_url:
        logger.warning("PDFExtractor: no pdf_url on anchor '%s'", anchor.title[:60])
        return []

    logger.info("PDFExtractor: fetching PDF from %s", anchor.pdf_url)
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http:
            response = await http.get(anchor.pdf_url)
            response.raise_for_status()
            pdf_bytes = response.content
    except Exception as exc:
        logger.warning("PDFExtractor: failed to fetch PDF: %s", exc)
        return []

    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    logger.info("PDFExtractor: PDF fetched (%d bytes), sending to Claude", len(pdf_bytes))

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": _EXTRACTION_PROMPT,
                    },
                ],
            }],
        )
    except Exception as exc:
        logger.warning("PDFExtractor: Claude API call failed: %s", exc)
        return []

    raw = resp.content[0].text.strip()
    logger.info("PDFExtractor: Claude responded (%d chars)", len(raw))

    try:
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        refs = json.loads(raw)
        if not isinstance(refs, list):
            raise ValueError("Expected JSON array")
        logger.info("PDFExtractor: extracted %d references", len(refs))
        return refs
    except Exception as exc:
        logger.warning(
            "PDFExtractor: failed to parse Claude response: %s — raw: %.200s", exc, raw
        )
        return []
