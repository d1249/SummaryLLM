"""
Timezone utilities with metrics and rate-limited logging.

Ensures all datetime objects are timezone-aware and provides UTC conversion.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional
from collections import defaultdict
import time
import structlog

logger = structlog.get_logger()


class RateLimitedLogger:
    """Rate-limited logger to reduce log chatter for repeated warnings."""
    
    def __init__(self, cooldown_seconds: int = 60):
        self.cooldown_seconds = cooldown_seconds
        self.last_log_time = defaultdict(float)
        self.suppressed_count = defaultdict(int)
    
    def log_if_allowed(self, key: str, log_func, *args, **kwargs):
        """Log message only if cooldown period has passed."""
        now = time.time()
        last_time = self.last_log_time[key]
        
        if now - last_time >= self.cooldown_seconds:
            # Log any suppressed messages
            if self.suppressed_count[key] > 0:
                logger.info(
                    f"Suppressed {self.suppressed_count[key]} similar messages in last {self.cooldown_seconds}s",
                    message_key=key
                )
                self.suppressed_count[key] = 0
            
            # Log the actual message
            log_func(*args, **kwargs)
            self.last_log_time[key] = now
        else:
            # Increment suppressed counter
            self.suppressed_count[key] += 1


# Global rate limiter for timezone warnings
_tz_logger = RateLimitedLogger(cooldown_seconds=60)


def ensure_aware(dt: datetime, mailbox_tz: str, metrics=None) -> datetime:
    """
    Ensure datetime is timezone-aware.
    
    If datetime is naive, it will be localized to mailbox_tz.
    If datetime is aware, it will be returned as-is (not converted).
    
    Args:
        dt: Datetime object (naive or aware)
        mailbox_tz: Mailbox timezone (e.g., "Europe/Moscow", "America/Sao_Paulo")
        metrics: Optional MetricsCollector instance for recording tz_naive_total
    
    Returns:
        Timezone-aware datetime
    
    Raises:
        ValueError: If datetime is None
    """
    if dt is None:
        raise ValueError("Cannot ensure timezone awareness for None datetime")
    
    # Already timezone-aware - return as-is
    if dt.tzinfo is not None:
        return dt
    
    # Naive datetime - localize to mailbox timezone
    mailbox_zone = ZoneInfo(mailbox_tz)
    
    # Record metric
    if metrics:
        metrics.record_tz_naive()
    
    # Rate-limited warning
    _tz_logger.log_if_allowed(
        "naive_datetime",
        logger.warning,
        "Naive datetime auto-localized to mailbox timezone",
        dt=dt.isoformat(),
        mailbox_tz=mailbox_tz
    )
    
    # Localize to mailbox timezone
    return dt.replace(tzinfo=mailbox_zone)


def to_utc(dt: datetime) -> datetime:
    """
    Convert datetime to UTC timezone.
    
    Args:
        dt: Timezone-aware datetime
    
    Returns:
        Datetime in UTC timezone
    
    Raises:
        ValueError: If datetime is naive (no timezone info)
    """
    if dt is None:
        raise ValueError("Cannot convert None datetime to UTC")
    
    if dt.tzinfo is None:
        raise ValueError(
            f"Cannot convert naive datetime to UTC: {dt}. "
            "Use ensure_aware() first to localize to a timezone."
        )
    
    # Convert to UTC
    return dt.astimezone(timezone.utc)


def ensure_aware_and_utc(dt: datetime, mailbox_tz: str, metrics=None) -> datetime:
    """
    Convenience function to ensure awareness and convert to UTC in one step.
    
    Args:
        dt: Datetime object (naive or aware)
        mailbox_tz: Mailbox timezone for naive datetimes
        metrics: Optional MetricsCollector instance
    
    Returns:
        Timezone-aware datetime in UTC
    """
    aware_dt = ensure_aware(dt, mailbox_tz, metrics=metrics)
    return to_utc(aware_dt)


def get_suppressed_stats() -> dict:
    """Get statistics on suppressed log messages."""
    return {
        "suppressed_counts": dict(_tz_logger.suppressed_count),
        "last_log_times": dict(_tz_logger.last_log_time)
    }

