"""Tests for Jinja2 prompt templates."""

import jinja2
import pytest

from alice.prompts import PromptManager


@pytest.fixture
def pm():
    """Create a PromptManager pointing to the actual prompts directory."""
    return PromptManager()


def test_gatekeeper_template_renders(pm):
    """Test gatekeeper template renders with required variables."""
    result = pm.render_gatekeeper(
        title="The Transformer Architecture Explained",
        text="This paper presents a novel attention mechanism...",
        source="arxiv",
    )
    assert "passed" in result  # JSON format instruction
    assert "true/false" in result or "confidence" in result
    assert "The Transformer Architecture Explained" in result


def test_understanding_template_renders(pm):
    """Test understanding template renders with all fields."""
    result = pm.render_understanding(
        title="Understanding Attention in Transformers",
        text="Attention mechanisms allow models to focus...",
        language="en",
    )
    assert "summary" in result
    assert "key_points" in result
    assert "domains" in result
    assert "estimated_read_time" in result
    assert "JSON" in result  # should contain JSON format instruction


def test_understanding_template_chinese_instruction(pm):
    """Test understanding template handles Chinese language flag."""
    result = pm.render_understanding(
        title="注意力机制", text="注意力机制允许模型关注...", language="zh"
    )
    assert "Chinese" in result  # should indicate Chinese output


def test_quality_score_template_renders(pm):
    """Test quality score template renders with score fields."""
    result = pm.render_quality_score(
        title="Test Article", summary="This explains X", key_points=["Point 1", "Point 2"]
    )
    assert "score" in result
    assert "reasoning" in result
    assert "1.0-10.0" in result or "1-10" in result


def test_push_reason_template_renders(pm):
    """Test push reason template renders with user profile."""
    result = pm.render_push_reason(
        title="Latest Advances in LLMs",
        summary="This paper presents new RLHF techniques",
        key_points=["RLHF improves alignment", "Constitutional AI"],
        domains=["machine learning", "AI safety"],
        user_profile="Researcher focused on LLM training and alignment",
    )
    assert "Latest Advances in LLMs" in result
    assert "machine learning" in result


def test_all_templates_exist(pm):
    """Test all 5 required templates exist."""
    for template_name in ["gatekeeper", "understanding", "quality_score", "push_reason", "push_enrichment"]:
        result = pm.render(
            template_name,
            title="test",
            text="test",
            summary="test",
            key_points=[],
            domains=[],
            source="",
            card_type="deep_knowledge",
        )
        assert result is not None
        assert len(result) > 10


def test_template_render_with_unknown_raises():
    """Test that unknown template raises error."""
    pm = PromptManager()
    with pytest.raises(jinja2.TemplateNotFound):
        pm.render("nonexistent_template")


def test_push_enrichment_template_time_sensitive(pm):
    """Test push enrichment template renders for time_sensitive content."""
    result = pm.render_push_enrichment(
        title="vLLM v0.5.0 Released",
        summary="vLLM releases major version with 30% throughput improvement",
        key_points=["30% faster", "New scheduler"],
        domains=["AI", "infrastructure"],
        card_type="time_sensitive",
        language="English",
    )
    assert "what" in result
    assert "impact" in result
    assert "push_reason" in result
    assert "time-sensitive" in result.lower()


def test_push_enrichment_template_deep_knowledge(pm):
    """Test push enrichment template renders for deep_knowledge content."""
    result = pm.render_push_enrichment(
        title="Understanding Transformers",
        summary="A deep dive into transformer architecture",
        key_points=["Self-attention", "Multi-head attention"],
        domains=["machine learning"],
        card_type="deep_knowledge",
    )
    assert "push_reason" in result
    assert "reading_advice" in result


def test_push_enrichment_template_thought_provoking(pm):
    """Test push enrichment template renders for thought_provoking content."""
    result = pm.render_push_enrichment(
        title="The Future of AI Ethics",
        summary="An essay on responsible AI development",
        key_points=["Ethics frameworks"],
        domains=["AI ethics"],
        card_type="thought_provoking",
    )
    assert "push_reason" in result
    # thought_provoking should NOT require reading_advice or what/impact
    assert "what" not in result.lower().split("push_reason")[0]
