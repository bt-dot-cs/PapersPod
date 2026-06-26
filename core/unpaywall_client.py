"""Unpaywall license resolver.

Queries Unpaywall for papers with unknown licenses to get the publisher-supplied
CC license identifier. Only called in COMMERCIAL_MODE for papers with a DOI.
"""
import asyncio
import logging
from urllib.parse import quote

import httpx

from core.config import OPENALEX_EMAIL
from core.license_utils import normalize_license
from core.models import Paper

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.unpaywall.org/v2"
_RATE_LIMIT_SECONDS = 1.0

# Licenses that may be resolved to something better via Unpaywall.
# "arxiv-nonexclusive" is the arXiv submission license; the published journal
# version (identified by DOI) may carry a CC license instead.
_RESOLVABLE = frozenset({None, "unknown", "arxiv-nonexclusive"})


async def resolve_licenses(papers: list[Paper]) -> list[Paper]:
    """Resolve unknown licenses for papers with DOIs via the Unpaywall API.

    Mutates paper.license in-place where a CC license can be confirmed.
    Returns the same list unchanged in structure.
    """
    if not OPENALEX_EMAIL:
        logger.warning("Unpaywall: OPENALEX_EMAIL not set — skipping license resolution")
        return papers

    to_resolve = [p for p in papers if p.doi and p.license in _RESOLVABLE]
    if not to_resolve:
        return papers

    logger.info("Unpaywall: resolving %d/%d papers", len(to_resolve), len(papers))

    async with httpx.AsyncClient(timeout=15.0) as client:
        for paper in to_resolve:
            url = f"{_BASE_URL}/{quote(paper.doi, safe='')}?email={OPENALEX_EMAIL}"
            try:
                response = await client.get(url)
                if response.status_code == 404:
                    logger.debug("Unpaywall: DOI not found — %s", paper.doi)
                    await asyncio.sleep(_RATE_LIMIT_SECONDS)
                    continue
                response.raise_for_status()
                data = response.json()

                best_oa = data.get("best_oa_location") or {}
                raw_license = (best_oa.get("license") or "").strip()
                oa_status = data.get("oa_status") or ""

                if raw_license:
                    resolved = normalize_license(raw_license)
                    if resolved not in ("unknown", "arxiv-nonexclusive"):
                        old = paper.license
                        paper.license = resolved
                        logger.info("Unpaywall: %s → %s (was %r)", paper.doi, resolved, old)
                    else:
                        logger.debug("Unpaywall: unrecognized license for %s — %r", paper.doi, raw_license)
                elif oa_status == "bronze":
                    # Free to read but no explicit license — correctly stays unknown
                    logger.debug("Unpaywall: bronze OA (no explicit license) — %s", paper.doi)
                else:
                    logger.debug("Unpaywall: no license for %s (oa_status=%r)", paper.doi, oa_status)

            except Exception as exc:
                logger.warning("Unpaywall: request failed for %s: %s", paper.doi, exc)

            await asyncio.sleep(_RATE_LIMIT_SECONDS)

    return papers
