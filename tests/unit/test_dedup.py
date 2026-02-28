"""Tests for DeduplicationService.

Tests URL normalization, SimHash computation, hamming distance, and near-duplicate detection.
"""

import pytest

from alice.services.dedup import DeduplicationService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dedup() -> DeduplicationService:
    """DeduplicationService instance."""
    return DeduplicationService()


# ---------------------------------------------------------------------------
# TestNormalizeUrl
# ---------------------------------------------------------------------------


class TestNormalizeUrl:
    """URL normalization tests."""

    def test_normalize_url_strips_utm_params(self, dedup: DeduplicationService) -> None:
        """utm_source, utm_medium, etc. are stripped from query string."""
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        normalized = dedup.normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized
        assert "example.com/article" in normalized

    def test_normalize_url_strips_fbclid(self, dedup: DeduplicationService) -> None:
        """fbclid tracking param is stripped."""
        url = "https://example.com/article?fbclid=abc123"
        normalized = dedup.normalize_url(url)
        assert "fbclid" not in normalized
        assert "example.com/article" in normalized

    def test_normalize_url_removes_www(self, dedup: DeduplicationService) -> None:
        """www. prefix is removed from hostname."""
        url = "https://www.example.com/article"
        normalized = dedup.normalize_url(url)
        assert "www." not in normalized
        assert "example.com/article" in normalized

    def test_normalize_url_lowercases_scheme_and_host(self, dedup: DeduplicationService) -> None:
        """Scheme and hostname are lowercased."""
        url = "HTTP://EXAMPLE.COM/path"
        normalized = dedup.normalize_url(url)
        assert normalized.startswith("http://example.com")

    def test_normalize_url_strips_trailing_slash(self, dedup: DeduplicationService) -> None:
        """Trailing slash on path is removed."""
        url = "https://example.com/article/"
        normalized = dedup.normalize_url(url)
        assert not normalized.endswith("/article/")
        assert "article" in normalized

    def test_normalize_url_strips_fragment(self, dedup: DeduplicationService) -> None:
        """Fragment identifier (#section) is removed."""
        url = "https://example.com/article#section"
        normalized = dedup.normalize_url(url)
        assert "#section" not in normalized
        assert "example.com/article" in normalized

    def test_normalize_url_keeps_non_tracking_params(self, dedup: DeduplicationService) -> None:
        """Non-tracking query params (page, sort, etc.) are preserved."""
        url = "https://example.com/article?page=2&sort=desc"
        normalized = dedup.normalize_url(url)
        assert "page=2" in normalized
        assert "sort=desc" in normalized


# ---------------------------------------------------------------------------
# TestComputeSimhash
# ---------------------------------------------------------------------------


class TestComputeSimhash:
    """SimHash fingerprint computation tests."""

    def test_compute_simhash_empty_text_returns_zero(self, dedup: DeduplicationService) -> None:
        """Empty string returns 0."""
        result = dedup.compute_simhash("")
        assert result == 0

    def test_compute_simhash_is_deterministic(self, dedup: DeduplicationService) -> None:
        """Same text produces same hash when called multiple times."""
        text = "The quick brown fox jumps over the lazy dog"
        hash1 = dedup.compute_simhash(text)
        hash2 = dedup.compute_simhash(text)
        assert hash1 == hash2

    def test_compute_simhash_different_texts_differ(self, dedup: DeduplicationService) -> None:
        """Two clearly different texts produce different hashes."""
        text1 = "Alice is an AI secretary application"
        text2 = "Bob is a software engineer"
        hash1 = dedup.compute_simhash(text1)
        hash2 = dedup.compute_simhash(text2)
        assert hash1 != hash2

    def test_compute_simhash_similar_texts_close(self, dedup: DeduplicationService) -> None:
        """Two near-identical texts have hamming distance ≤ 10."""
        text1 = "The quick brown fox jumps over the lazy dog"
        text2 = "The quick brown fox jumps over the lazy dogs"  # one character added

        hash1 = dedup.compute_simhash(text1)
        hash2 = dedup.compute_simhash(text2)
        distance = dedup.hamming_distance(hash1, hash2)
        assert distance <= 15

    def test_compute_simhash_chinese_text_nonzero(self, dedup: DeduplicationService) -> None:
        """Chinese text should produce a non-zero fingerprint via CJK bigrams."""
        text = "人工智能技术正在改变世界"
        result = dedup.compute_simhash(text)
        assert result != 0

    def test_compute_simhash_chinese_different_texts_differ(self, dedup: DeduplicationService) -> None:
        """Two different Chinese texts produce different hashes."""
        text1 = "人工智能技术正在改变世界的每一个角落"
        text2 = "今天天气晴朗适合出门散步和运动"
        hash1 = dedup.compute_simhash(text1)
        hash2 = dedup.compute_simhash(text2)
        assert hash1 != hash2

    def test_compute_simhash_chinese_similar_texts_close(self, dedup: DeduplicationService) -> None:
        """Two near-identical Chinese texts have small hamming distance."""
        text1 = "深度学习模型在自然语言处理中的应用研究"
        text2 = "深度学习模型在自然语言处理中的应用分析"  # 研究→分析
        hash1 = dedup.compute_simhash(text1)
        hash2 = dedup.compute_simhash(text2)
        distance = dedup.hamming_distance(hash1, hash2)
        assert distance <= 15

    def test_compute_simhash_mixed_bilingual(self, dedup: DeduplicationService) -> None:
        """Mixed Chinese-English text produces a non-zero fingerprint."""
        text = "Transformer模型在NLP任务中表现优异"
        result = dedup.compute_simhash(text)
        assert result != 0

    def test_compute_simhash_single_cjk_char(self, dedup: DeduplicationService) -> None:
        """A single CJK character still produces a non-zero fingerprint."""
        result = dedup.compute_simhash("人")
        assert result != 0


# ---------------------------------------------------------------------------
# TestHammingDistance
# ---------------------------------------------------------------------------


class TestHammingDistance:
    """Hamming distance (bit difference) tests."""

    def test_hamming_distance_identical(self, dedup: DeduplicationService) -> None:
        """Identical values have distance 0."""
        x = 0x1234567890ABCDEF
        result = dedup.hamming_distance(x, x)
        assert result == 0

    def test_hamming_distance_one_bit_difference(self, dedup: DeduplicationService) -> None:
        """Exactly one bit difference → distance 1."""
        # 0b0 and 0b1 differ in exactly 1 bit
        result = dedup.hamming_distance(0, 1)
        assert result == 1

    def test_hamming_distance_all_64_bits(self, dedup: DeduplicationService) -> None:
        """All 64 bits different → distance 64."""
        # 0 and 0xFFFFFFFFFFFFFFFF differ in all 64 bits
        result = dedup.hamming_distance(0, 0xFFFFFFFFFFFFFFFF)
        assert result == 64


# ---------------------------------------------------------------------------
# TestIsNearDuplicate
# ---------------------------------------------------------------------------


class TestIsNearDuplicate:
    """Near-duplicate detection tests (hamming distance ≤ threshold)."""

    def test_is_near_duplicate_identical(self, dedup: DeduplicationService) -> None:
        """Same fingerprint → True."""
        x = 0x123456789ABCDEF0
        result = dedup.is_near_duplicate(x, x)
        assert result is True

    def test_is_near_duplicate_far_apart(self, dedup: DeduplicationService) -> None:
        """Very large hamming distance (all 64 bits) → False."""
        # 0 and 0xFFFFFFFFFFFFFFFF differ in 64 bits, default threshold is 3
        result = dedup.is_near_duplicate(0, 0xFFFFFFFFFFFFFFFF)
        assert result is False

    def test_is_near_duplicate_custom_threshold_zero(self, dedup: DeduplicationService) -> None:
        """Threshold of 0 only matches identical fingerprints."""
        # Two values with hamming distance of 1
        a = 0
        b = 1  # hamming_distance = 1
        result = dedup.is_near_duplicate(a, b, threshold=0)
        assert result is False
