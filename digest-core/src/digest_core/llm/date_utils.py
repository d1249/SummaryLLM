"""
Date normalization utilities for digest generation.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
import pytz

try:
    import dateutil.parser
except ImportError:
    dateutil = None


def normalize_date_to_tz(
    date_str: str, 
    base_datetime: datetime, 
    tz_name: str = "America/Sao_Paulo"
) -> Dict[str, Optional[str]]:
    """
    Normalize date string to ISO-8601 with timezone.
    
    Args:
        date_str: Date string to normalize
        base_datetime: Current datetime for relative calculations
        tz_name: Target timezone name
    
    Returns:
        {
            "normalized": "2024-12-15T15:00:00-03:00",
            "label": "today" | "tomorrow" | None
        }
    """
    if not date_str:
        return {"normalized": None, "label": None}
    
    try:
        tz = pytz.timezone(tz_name)
        base_dt = base_datetime.astimezone(tz)
        
        # Parse date_str
        if dateutil:
            parsed_date = dateutil.parser.parse(date_str)
            # If naive, localize to target timezone
            if parsed_date.tzinfo is None:
                parsed_date = tz.localize(parsed_date)
            else:
                # Convert to target timezone
                parsed_date = parsed_date.astimezone(tz)
        else:
            # Fallback: try ISO format
            try:
                parsed_date = datetime.fromisoformat(date_str)
                if parsed_date.tzinfo is None:
                    parsed_date = tz.localize(parsed_date)
                else:
                    parsed_date = parsed_date.astimezone(tz)
            except ValueError:
                return {"normalized": None, "label": None}
        
        # Check if today/tomorrow
        label = None
        if parsed_date.date() == base_dt.date():
            label = "today"
        elif parsed_date.date() == (base_dt + timedelta(days=1)).date():
            label = "tomorrow"
        elif parsed_date.date() == (base_dt - timedelta(days=1)).date():
            label = "yesterday"
        
        return {
            "normalized": parsed_date.isoformat(),
            "label": label
        }
        
    except Exception as e:
        # Return as-is if parsing fails
        return {"normalized": date_str, "label": None}


def get_current_datetime_in_tz(tz_name: str = "America/Sao_Paulo") -> str:
    """
    Get current datetime in specified timezone as ISO-8601 string.
    
    Args:
        tz_name: Timezone name
    
    Returns:
        ISO-8601 formatted datetime string
    """
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    return now.isoformat()

