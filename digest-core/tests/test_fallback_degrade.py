"""
Tests for LLM degradation fallback.
"""
import pytest
from digest_core.llm.degrade import extractive_fallback
from digest_core.evidence.split import EvidenceChunk


def test_extractive_fallback_creates_digest():
    """Test that extractive fallback creates a valid digest."""
    chunks = [
        EvidenceChunk(
            evidence_id="ev_1",
            content="Прошу согласовать отчет",
            conversation_id="conv1",
            source_ref={"msg_id": "msg1"},
            priority_score=2.0,
            addressed_to_me=True,
            signals={"action_verbs": ["прошу", "согласовать"], "dates": []},
            message_metadata={},
            token_count=10,
            user_aliases_matched=[]
        ),
        EvidenceChunk(
            evidence_id="ev_2",
            content="Дедлайн до 15 января",
            conversation_id="conv2",
            source_ref={"msg_id": "msg2"},
            priority_score=1.5,
            addressed_to_me=False,
            signals={"action_verbs": [], "dates": ["до 15 января"]},
            message_metadata={},
            token_count=10,
            user_aliases_matched=[]
        ),
    ]
    
    digest = extractive_fallback(chunks, "2025-10-14", "test_trace", reason="test")
    
    assert digest.schema_version == "2.0"
    assert digest.prompt_version == "extractive_fallback"
    assert digest.digest_date == "2025-10-14"
    assert digest.trace_id == "test_trace"
    
    # Should have extracted items
    assert len(digest.my_actions) > 0 or len(digest.others_actions) > 0 or len(digest.deadlines_meetings) > 0


def test_extractive_fallback_limits_items():
    """Test that extractive fallback limits items."""
    # Create many chunks
    chunks = [
        EvidenceChunk(
            evidence_id=f"ev_{i}",
            content=f"Прошу выполнить задачу {i}",
            conversation_id=f"conv{i}",
            source_ref={"msg_id": f"msg{i}"},
            priority_score=2.0,
            addressed_to_me=True,
            signals={"action_verbs": ["прошу"], "dates": []},
            message_metadata={},
            token_count=10,
            user_aliases_matched=[]
        )
        for i in range(20)
    ]
    
    digest = extractive_fallback(chunks, "2025-10-14", "test_trace")
    
    # Should limit to 5 my_actions
    assert len(digest.my_actions) <= 5

