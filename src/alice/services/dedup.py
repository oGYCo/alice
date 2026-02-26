"""Content deduplication — URL normalization + SimHash near-duplicate detection."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, cast
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import structlog

# Tracking params to strip during URL normalization
_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "msclkid",
        "ref",
        "referrer",
        "source",
    }
)

# SimHash: number of bits
_SIMHASH_BITS = 64


class _Logger(Protocol):
    def debug(self, event: str, **kwargs: object) -> None: ...
    def info(self, event: str, **kwargs: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))


class DeduplicationService:
    """URL normalization + SimHash-based near-duplicate detection."""

    def normalize_url(self, url: str) -> str:
        """Normalize URL by stripping tracking params, lowercasing scheme/host,
        removing www., and stripping trailing slashes from path.
        """
        parsed = urlparse(url)
        # Lowercase scheme and netloc, strip www.
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # Strip tracking query params
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        clean_params = {k: v for k, v in query_params.items() if k.lower() not in _TRACKING_PARAMS}
        clean_query = urlencode(clean_params, doseq=True)
        # Strip trailing slash from path (unless root)
        path = parsed.path.rstrip("/") or "/"
        normalized = urlunparse(
            (
                parsed.scheme.lower(),
                netloc,
                path,
                parsed.params,
                clean_query,
                "",  # strip fragment
            )
        )
        logger.debug("url_normalized", original=url, normalized=normalized)
        return normalized

    def compute_simhash(self, text: str) -> int:
        """Compute a 64-bit SimHash fingerprint for the given text.

        Algorithm:
        1. Tokenize text into words (lowercase, strip punctuation)
        2. For each token, compute MD5 hash → treat as bit vector
        3. Accumulate weighted bit counts
        4. Final bit = 1 if count > 0, else 0
        """
        if not text:
            return 0
        # Tokenize: lowercase words only
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            return 0
        # Accumulate bit counts
        v = [0] * _SIMHASH_BITS
        for token in tokens:
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)  # noqa: S324
            for i in range(_SIMHASH_BITS):
                bit = (h >> i) & 1
                v[i] += 1 if bit else -1
        # Build fingerprint
        fingerprint = 0
        for i in range(_SIMHASH_BITS):
            if v[i] > 0:
                fingerprint |= 1 << i
        logger.debug("simhash_computed", text_len=len(text), fingerprint=fingerprint)
        return fingerprint

    def hamming_distance(self, a: int, b: int) -> int:
        """Count differing bits between two 64-bit integers (Hamming distance)."""
        xor = a ^ b
        # Count set bits using Brian Kernighan's algorithm
        count = 0
        while xor:
            xor &= xor - 1
            count += 1
        return count

    def is_near_duplicate(
        self, fingerprint_a: int, fingerprint_b: int, *, threshold: int = 3
    ) -> bool:
        """Return True if two SimHash fingerprints are near-duplicates.

        Default threshold: hamming distance ≤ 3 = duplicate.
        """
        return self.hamming_distance(fingerprint_a, fingerprint_b) <= threshold
