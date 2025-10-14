"""
Tests for enhanced markdown assembler with v2 schema.
"""
import pytest
from pathlib import Path
import tempfile
from digest_core.llm.schemas import EnhancedDigest, ActionItem, DeadlineMeeting
from digest_core.assemble.markdown import MarkdownAssembler


class TestEnhancedMarkdownAssembler:
    """Test markdown assembler with EnhancedDigest v2."""
    
    def test_write_enhanced_digest_with_actions(self):
        """Test writing enhanced digest with actions to markdown."""
        # Create test digest
        action1 = ActionItem(
            title="Review PR",
            description="Review pull request #123",
            evidence_id="ev_1",
            quote="Please review pull request #123 by end of day.",
            due_date="2024-12-15",
            due_date_normalized="2024-12-15T17:00:00-03:00",
            due_date_label="tomorrow",
            actors=["user"],
            confidence="High",
            response_channel="slack"
        )
        
        digest = EnhancedDigest(
            prompt_version="v2",
            digest_date="2024-12-14",
            trace_id="test_123",
            timezone="America/Sao_Paulo",
            my_actions=[action1],
            others_actions=[],
            deadlines_meetings=[],
            risks_blockers=[],
            fyi=[]
        )
        
        # Write to temp file
        assembler = MarkdownAssembler()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            assembler.write_enhanced_digest(digest, output_path)
            
            # Read and verify
            content = output_path.read_text(encoding='utf-8')
            
            assert "# Дайджест действий - 2024-12-14" in content
            assert "Trace ID: test_123" in content
            assert "Schema version: 2.0" in content
            assert "## Мои действия" in content
            assert "Review PR" in content
            assert "Evidence ev_1" in content
            assert "Please review pull request" in content
            assert "(tomorrow)" in content
            
        finally:
            if output_path.exists():
                output_path.unlink()
    
    def test_write_enhanced_digest_with_deadlines(self):
        """Test writing enhanced digest with deadlines."""
        deadline1 = DeadlineMeeting(
            title="Team standup",
            evidence_id="ev_2",
            quote="Daily standup scheduled for 10 AM tomorrow.",
            date_time="2024-12-15T10:00:00-03:00",
            date_label="tomorrow",
            location="Room 201",
            participants=["Alice", "Bob", "Charlie"]
        )
        
        digest = EnhancedDigest(
            prompt_version="v2",
            digest_date="2024-12-14",
            trace_id="test_456",
            deadlines_meetings=[deadline1],
            my_actions=[],
            others_actions=[],
            risks_blockers=[],
            fyi=[]
        )
        
        assembler = MarkdownAssembler()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            assembler.write_enhanced_digest(digest, output_path)
            
            content = output_path.read_text(encoding='utf-8')
            
            assert "## Дедлайны и встречи" in content
            assert "Team standup" in content
            assert "Room 201" in content
            assert "Alice, Bob, Charlie" in content
            
        finally:
            if output_path.exists():
                output_path.unlink()
    
    def test_write_empty_enhanced_digest(self):
        """Test writing empty enhanced digest."""
        digest = EnhancedDigest(
            prompt_version="v2",
            digest_date="2024-12-14",
            trace_id="test_789",
            my_actions=[],
            others_actions=[],
            deadlines_meetings=[],
            risks_blockers=[],
            fyi=[],
            markdown_summary="## Краткое резюме\n\nДействий не найдено."
        )
        
        assembler = MarkdownAssembler()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            assembler.write_enhanced_digest(digest, output_path)
            
            content = output_path.read_text(encoding='utf-8')
            
            assert "За период релевантных действий не найдено" in content
            assert "Краткое резюме" in content
            
        finally:
            if output_path.exists():
                output_path.unlink()
    
    def test_enhanced_digest_contains_quotes(self):
        """Test that all items in enhanced digest contain quotes."""
        action1 = ActionItem(
            title="Update docs",
            description="Update documentation",
            evidence_id="ev_10",
            quote="Please update the documentation to reflect recent changes.",
            confidence="Medium"
        )
        
        digest = EnhancedDigest(
            prompt_version="v2",
            digest_date="2024-12-14",
            trace_id="test_quotes",
            my_actions=[action1]
        )
        
        assembler = MarkdownAssembler()
        content = assembler._generate_enhanced_markdown(digest)
        
        # Check that quote is present
        assert "**Цитата:**" in content
        assert "Please update the documentation" in content

