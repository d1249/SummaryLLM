"""
Timezone normalization utilities.

Ensures all datetime objects are timezone-aware.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import structlog

logger = structlog.get_logger()


def ensure_tz_aware(
    dt: datetime,
    mailbox_tz: str,
    *,
    fail_on_naive: bool = True
) -> datetime:
    """
    Ensure datetime is timezone-aware.
    
    If datetime is naive, it will be localized to mailbox_tz.
    If datetime is aware, it will be converted to mailbox_tz.
    
    Args:
        dt: Datetime object (naive or aware)
        mailbox_tz: Mailbox timezone (e.g., "Europe/Moscow")
        fail_on_naive: If True, raise ValueError on naive datetime
    
    Returns:
        Timezone-aware datetime in mailbox_tz
    
    Raises:
        ValueError: If datetime is naive and fail_on_naive=True
    """
    if dt is None:
        return None
    
    mailbox_zone = ZoneInfo(mailbox_tz)
    
    if dt.tzinfo is None:
        # Naive datetime
        if fail_on_naive:
            raise ValueError(
                f"Naive datetime encountered: {dt}. "
                f"Configure fail_on_naive=False to auto-localize to {mailbox_tz}"
            )
        
        logger.warning(
            "Naive datetime auto-localized to mailbox timezone",
            dt=dt.isoformat(),
            mailbox_tz=mailbox_tz
        )
        
        # Localize to mailbox timezone
        return dt.replace(tzinfo=mailbox_zone)
    
    else:
        # Already aware, convert to mailbox timezone
        return dt.astimezone(mailbox_zone)


def normalize_email_dates(
    email_data: dict,
    mailbox_tz: str,
    *,
    fail_on_naive: bool = True
) -> dict:
    """
    Normalize all datetime fields in email data.
    
    Args:
        email_data: Email data dictionary
        mailbox_tz: Mailbox timezone
        fail_on_naive: If True, raise on naive datetime
    
    Returns:
        Email data with normalized datetimes
    """
    date_fields = ['sent', 'received', 'last_modified', 'datetime_received']
    
    for field in date_fields:
        if field in email_data and email_data[field]:
            dt = email_data[field]
            if isinstance(dt, datetime):
                email_data[field] = ensure_tz_aware(dt, mailbox_tz, fail_on_naive=fail_on_naive)
    
    return email_data


def get_current_tz_aware(tz_name: str) -> datetime:
    """
    Get current datetime in specified timezone.
    
    Args:
        tz_name: Timezone name (e.g., "America/Sao_Paulo")
    
    Returns:
        Current datetime in specified timezone
    """
    return datetime.now(ZoneInfo(tz_name))

