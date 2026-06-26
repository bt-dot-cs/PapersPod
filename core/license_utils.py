def normalize_license(raw: str) -> str:
    """Normalize a license URL or string to a canonical identifier.

    Returns one of:
      cc-by, cc0, cc-by-sa, cc-by-nc, cc-by-nd, cc-by-nc-sa, cc-by-nc-nd,
      arxiv-nonexclusive, restricted, unknown
    """
    if not raw:
        return "unknown"
    s = raw.lower().strip().rstrip("/")

    if "cc0" in s or "publicdomain/zero" in s or "public-domain" in s:
        return "cc0"

    # Check most-specific CC variants before shorter substrings
    if "by-nc-nd" in s or "by_nc_nd" in s:
        return "cc-by-nc-nd"
    if "by-nc-sa" in s or "by_nc_sa" in s:
        return "cc-by-nc-sa"
    if "by-nc" in s or "by_nc" in s:
        return "cc-by-nc"
    if "by-nd" in s or "by_nd" in s:
        return "cc-by-nd"
    if "by-sa" in s or "by_sa" in s:
        return "cc-by-sa"
    if ("creativecommons" in s and "by" in s) or s in ("cc-by", "cc by", "cc_by"):
        return "cc-by"

    # arXiv perpetual non-exclusive distribution license (not CC, not commercial-safe)
    if "arxiv.org/licenses/nonexclusive-distrib" in s:
        return "arxiv-nonexclusive"

    return "unknown"


# Licenses safe for commercial derivative works (CC BY + CC0 only)
COMMERCIAL_SAFE: frozenset[str] = frozenset({"cc-by", "cc0"})


def is_commercial_safe(license_str: str | None) -> bool:
    """Return True only if the license explicitly permits commercial derivative use."""
    return license_str in COMMERCIAL_SAFE
