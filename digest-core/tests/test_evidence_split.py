"""
Test evidence splitting with token budget constraints.
"""
import pytest
from unittest.mock import Mock
from digest_core.evidence.split import EvidenceSplitter
from digest_core.llm.schemas import NormalizedMessage


@pytest.fixture
def splitter():
    """Evidence splitter instance."""
    return EvidenceSplitter()


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    messages = []
    
    # Message 1: Long content with multiple paragraphs
    msg1 = Mock(spec=NormalizedMessage)
    msg1.msg_id = "msg-1"
    msg1.conversation_id = "conv-1"
    msg1.text_body = """
    This is the first paragraph with some content.
    
    This is the second paragraph with more content.
    
    This is the third paragraph with even more content.
    """
    messages.append(msg1)
    
    # Message 2: Short content
    msg2 = Mock(spec=NormalizedMessage)
    msg2.msg_id = "msg-2"
    msg2.conversation_id = "conv-2"
    msg2.text_body = "Short message content."
    messages.append(msg2)
    
    # Message 3: Very long content
    msg3 = Mock(spec=NormalizedMessage)
    msg3.msg_id = "msg-3"
    msg3.conversation_id = "conv-3"
    msg3.text_body = "This is a very long message. " * 1000  # Very long content
    messages.append(msg3)
    
    return messages


def test_paragraph_splitting(splitter, sample_messages):
    """Test splitting by paragraphs."""
    msg = sample_messages[0]  # Long content with paragraphs
    
    chunks = splitter._split_message_content(msg, max_tokens=100)
    
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.thread_id == "conv-1"
        assert chunk.msg_id == "msg-1"


def test_sentence_splitting(splitter, sample_messages):
    """Test splitting by sentences when paragraphs are too long."""
    msg = sample_messages[0]  # Long content with paragraphs
    
    chunks = splitter._split_message_content(msg, max_tokens=50)
    
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.thread_id == "conv-1"
        assert chunk.msg_id == "msg-1"


def test_short_content_no_splitting(splitter, sample_messages):
    """Test that short content is not split."""
    msg = sample_messages[1]  # Short content
    
    chunks = splitter._split_message_content(msg, max_tokens=100)
    
    assert len(chunks) == 1
    assert chunks[0].content == "Short message content."


def test_token_estimation(splitter, sample_messages):
    """Test token estimation accuracy."""
    msg = sample_messages[0]  # Long content
    
    # Test paragraph token estimation
    paragraphs = msg.text_body.split('\n\n')
    for paragraph in paragraphs:
        if paragraph.strip():
            tokens = splitter._estimate_tokens(paragraph)
            assert tokens > 0
            assert tokens == int(len(paragraph.split()) * 1.3)


def test_max_chunks_limit(splitter, sample_messages):
    """Test that max_chunks limit is respected."""
    msg = sample_messages[2]  # Very long content
    
    chunks = splitter._split_message_content(msg, max_tokens=50, max_chunks=5)
    
    assert len(chunks) <= 5


def test_token_budget_respect(splitter, sample_messages):
    """Test that total token budget is respected."""
    msg = sample_messages[2]  # Very long content
    
    chunks = splitter._split_message_content(msg, max_tokens=1000)
    
    total_tokens = sum(chunk.token_count for chunk in chunks)
    assert total_tokens <= 1000


def test_empty_content(splitter):
    """Test handling of empty content."""
    msg = Mock(spec=NormalizedMessage)
    msg.msg_id = "msg-empty"
    msg.conversation_id = "conv-empty"
    msg.text_body = ""
    
    chunks = splitter._split_message_content(msg, max_tokens=100)
    
    assert len(chunks) == 0


def test_whitespace_only_content(splitter):
    """Test handling of whitespace-only content."""
    msg = Mock(spec=NormalizedMessage)
    msg.msg_id = "msg-whitespace"
    msg.conversation_id = "conv-whitespace"
    msg.text_body = "   \n\n   \n   "
    
    chunks = splitter._split_message_content(msg, max_tokens=100)
    
    assert len(chunks) == 0


def test_evidence_chunk_creation(splitter, sample_messages):
    """Test evidence chunk creation."""
    msg = sample_messages[0]  # Long content with paragraphs
    
    chunks = splitter._split_message_content(msg, max_tokens=100)
    
    for i, chunk in enumerate(chunks):
        assert chunk.evidence_id.startswith("ev-")
        assert chunk.thread_id == "conv-1"
        assert chunk.msg_id == "msg-1"
        assert chunk.chunk_index == i
        assert chunk.token_count > 0
        assert chunk.content is not None


def test_multiple_messages_splitting(splitter, sample_messages):
    """Test splitting multiple messages."""
    all_chunks = splitter.split_evidence(sample_messages, max_tokens=100)
    
    # Should have chunks from all messages
    msg_ids = set(chunk.msg_id for chunk in all_chunks)
    assert "msg-1" in msg_ids
    assert "msg-2" in msg_ids
    assert "msg-3" in msg_ids


def test_total_token_budget(splitter, sample_messages):
    """Test that total token budget across all messages is respected."""
    all_chunks = splitter.split_evidence(sample_messages, max_tokens=500)
    
    total_tokens = sum(chunk.token_count for chunk in all_chunks)
    assert total_tokens <= 500
