"""
Unit tests for NormalizedMessage sender compatibility.
"""
import pytest
from datetime import datetime, timezone
from digest_core.ingest.ews import NormalizedMessage


class TestNormalizedMessageSender:
    """Test NormalizedMessage sender field compatibility."""
    
    def test_sender_property_with_from_email(self):
        """Test that sender property returns from_email when available."""
        msg = NormalizedMessage(
            msg_id="test-001",
            conversation_id="conv-001",
            datetime_received=datetime.now(timezone.utc),
            sender_email="old@example.com",
            subject="Test Subject",
            text_body="Test body",
            to_recipients=["user@example.com"],
            cc_recipients=[],
            importance="Normal",
            is_flagged=False,
            has_attachments=False,
            attachment_types=[],
            # Canonical fields
            from_email="new@example.com",
            from_name="Test User",
            to_emails=["user@example.com"],
            cc_emails=[],
            message_id="test-001",
            body_norm="Test body",
            received_at=datetime.now(timezone.utc)
        )
        
        assert msg.sender == "new@example.com"
    
    def test_sender_property_fallback_to_sender_email(self):
        """Test that sender property falls back to sender_email when from_email is empty."""
        msg = NormalizedMessage(
            msg_id="test-002",
            conversation_id="conv-002",
            datetime_received=datetime.now(timezone.utc),
            sender_email="fallback@example.com",
            subject="Test Subject",
            text_body="Test body",
            to_recipients=["user@example.com"],
            cc_recipients=[],
            importance="Normal",
            is_flagged=False,
            has_attachments=False,
            attachment_types=[],
            # Canonical fields with empty from_email
            from_email="",
            from_name=None,
            to_emails=["user@example.com"],
            cc_emails=[],
            message_id="test-002",
            body_norm="Test body",
            received_at=datetime.now(timezone.utc)
        )
        
        assert msg.sender == "fallback@example.com"
    
    def test_sender_property_empty_when_both_missing(self):
        """Test that sender property returns empty string when both from_email and sender_email are empty."""
        msg = NormalizedMessage(
            msg_id="test-003",
            conversation_id="conv-003",
            datetime_received=datetime.now(timezone.utc),
            sender_email="",
            subject="Test Subject",
            text_body="Test body",
            to_recipients=["user@example.com"],
            cc_recipients=[],
            importance="Normal",
            is_flagged=False,
            has_attachments=False,
            attachment_types=[],
            # Canonical fields with empty from_email
            from_email="",
            from_name=None,
            to_emails=["user@example.com"],
            cc_emails=[],
            message_id="test-003",
            body_norm="Test body",
            received_at=datetime.now(timezone.utc)
        )
        
        assert msg.sender == ""
    
    def test_sender_property_with_none_values(self):
        """Test that sender property handles None values gracefully."""
        msg = NormalizedMessage(
            msg_id="test-004",
            conversation_id="conv-004",
            datetime_received=datetime.now(timezone.utc),
            sender_email=None,
            subject="Test Subject",
            text_body="Test body",
            to_recipients=["user@example.com"],
            cc_recipients=[],
            importance="Normal",
            is_flagged=False,
            has_attachments=False,
            attachment_types=[],
            # Canonical fields with None from_email
            from_email=None,
            from_name=None,
            to_emails=["user@example.com"],
            cc_emails=[],
            message_id="test-004",
            body_norm="Test body",
            received_at=datetime.now(timezone.utc)
        )
        
        assert msg.sender == ""
    
    def test_canonical_fields_populated(self):
        """Test that canonical fields are properly populated."""
        now = datetime.now(timezone.utc)
        
        msg = NormalizedMessage(
            msg_id="test-005",
            conversation_id="conv-005",
            datetime_received=now,
            sender_email="sender@example.com",
            subject="Test Subject",
            text_body="Test body",
            to_recipients=["user1@example.com", "user2@example.com"],
            cc_recipients=["cc@example.com"],
            importance="High",
            is_flagged=True,
            has_attachments=True,
            attachment_types=["pdf", "docx"],
            # Canonical fields
            from_email="sender@example.com",
            from_name="Sender Name",
            to_emails=["user1@example.com", "user2@example.com"],
            cc_emails=["cc@example.com"],
            message_id="test-005",
            body_norm="Test body",
            received_at=now
        )
        
        # Test canonical fields
        assert msg.from_email == "sender@example.com"
        assert msg.from_name == "Sender Name"
        assert msg.to_emails == ["user1@example.com", "user2@example.com"]
        assert msg.cc_emails == ["cc@example.com"]
        assert msg.message_id == "test-005"
        assert msg.body_norm == "Test body"
        assert msg.received_at == msg.datetime_received
        
        # Test backward compatibility
        assert msg.sender == "sender@example.com"
