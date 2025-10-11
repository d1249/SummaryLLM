"""
Conversation thread building from normalized messages.
"""
from collections import defaultdict
from typing import List, Dict, NamedTuple
from datetime import datetime
import structlog

from digest_core.ingest.ews import NormalizedMessage

logger = structlog.get_logger()


class ConversationThread(NamedTuple):
    """A conversation thread containing multiple messages."""
    conversation_id: str
    messages: List[NormalizedMessage]
    latest_message_time: datetime
    participant_count: int
    message_count: int


class ThreadBuilder:
    """Build conversation threads from normalized messages."""
    
    def __init__(self):
        self.max_thread_age_hours = 48  # Threads older than this are considered stale
        self.max_messages_per_thread = 50  # Limit thread size
    
    def build_threads(self, messages: List[NormalizedMessage]) -> List[ConversationThread]:
        """Build conversation threads from normalized messages."""
        logger.info("Building conversation threads", message_count=len(messages))
        
        # Deduplicate messages by msg_id first
        seen_ids = set()
        unique_messages = []
        for msg in messages:
            if msg.msg_id not in seen_ids:
                seen_ids.add(msg.msg_id)
                unique_messages.append(msg)
        
        if len(unique_messages) < len(messages):
            logger.info("Deduplicated messages", 
                       original=len(messages), 
                       unique=len(unique_messages))
        
        # Group messages by conversation_id or normalized subject
        conversation_groups = defaultdict(list)
        
        for msg in unique_messages:
            if msg.conversation_id:
                conversation_groups[msg.conversation_id].append(msg)
            else:
                # Fallback: use normalized subject as thread key
                norm_subject = self._normalize_subject(msg.subject)
                if norm_subject:
                    thread_id = f"subj_{hash(norm_subject)}"
                    conversation_groups[thread_id].append(msg)
                else:
                    # Messages without conversation_id or subject are single-message threads
                    single_thread_id = f"single_{msg.msg_id}"
                    conversation_groups[single_thread_id].append(msg)
        
        logger.info("Grouped messages", thread_count=len(conversation_groups))
        
        # Build thread objects
        threads = []
        for conv_id, conv_messages in conversation_groups.items():
            try:
                thread = self._build_single_thread(conv_id, conv_messages)
                if thread:
                    threads.append(thread)
            except Exception as e:
                logger.warning("Failed to build thread", conversation_id=conv_id, error=str(e))
                continue
        
        # Sort threads by latest message time (most recent first)
        threads.sort(key=lambda t: t.latest_message_time, reverse=True)
        
        logger.info("Thread building completed", threads_created=len(threads))
        
        return threads
    
    def _build_single_thread(self, conversation_id: str, messages: List[NormalizedMessage]) -> ConversationThread:
        """Build a single conversation thread."""
        if not messages:
            return None
        
        # Sort messages by datetime_received
        messages.sort(key=lambda m: m.datetime_received)
        
        # Limit thread size
        if len(messages) > self.max_messages_per_thread:
            logger.warning(
                "Thread too large, truncating",
                conversation_id=conversation_id,
                original_count=len(messages),
                truncated_count=self.max_messages_per_thread
            )
            messages = messages[-self.max_messages_per_thread:]
        
        # Get latest message time
        latest_time = max(msg.datetime_received for msg in messages)
        
        # Count unique participants
        participants = set()
        for msg in messages:
            participants.add(msg.sender_email)
            participants.update(msg.to_recipients)
            participants.update(msg.cc_recipients)
        
        # Remove empty participants
        participants.discard("")
        
        return ConversationThread(
            conversation_id=conversation_id,
            messages=messages,
            latest_message_time=latest_time,
            participant_count=len(participants),
            message_count=len(messages)
        )
    
    def filter_recent_threads(self, threads: List[ConversationThread], hours: int = 24) -> List[ConversationThread]:
        """Filter threads to only include recent activity."""
        from datetime import datetime, timezone, timedelta
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent_threads = [
            thread for thread in threads
            if thread.latest_message_time >= cutoff_time
        ]
        
        logger.info(
            "Filtered recent threads",
            original_count=len(threads),
            recent_count=len(recent_threads),
            hours=hours
        )
        
        return recent_threads
    
    def prioritize_threads(self, threads: List[ConversationThread]) -> List[ConversationThread]:
        """Prioritize threads based on relevance heuristics."""
        def thread_priority(thread: ConversationThread) -> float:
            """Calculate priority score for a thread."""
            score = 0.0
            
            # Recent activity gets higher priority
            from datetime import datetime, timezone
            hours_ago = (datetime.now(timezone.utc) - thread.latest_message_time).total_seconds() / 3600
            if hours_ago < 1:
                score += 10.0
            elif hours_ago < 6:
                score += 5.0
            elif hours_ago < 24:
                score += 2.0
            
            # More participants might indicate importance
            if thread.participant_count > 5:
                score += 2.0
            elif thread.participant_count > 2:
                score += 1.0
            
            # Longer conversations might be more important
            if thread.message_count > 10:
                score += 1.0
            elif thread.message_count > 5:
                score += 0.5
            
            return score
        
        # Sort by priority (highest first)
        prioritized_threads = sorted(threads, key=thread_priority, reverse=True)
        
        logger.info("Threads prioritized", thread_count=len(prioritized_threads))
        
        return prioritized_threads
    
    def _normalize_subject(self, subject: str) -> str:
        """Normalize subject for threading (remove Re:, Fwd:, etc.)."""
        import re
        if not subject:
            return ""
        
        # Remove common prefixes
        normalized = subject.strip()
        prefixes = [r'^Re:\s*', r'^RE:\s*', r'^Fwd:\s*', r'^FW:\s*', 
                   r'^Fw:\s*', r'^\[.*?\]\s*']
        
        for prefix in prefixes:
            normalized = re.sub(prefix, '', normalized, flags=re.IGNORECASE)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized.lower()
