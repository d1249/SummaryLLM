"""
Sample email fixtures for testing.
"""
import json
from datetime import datetime, timezone, timedelta


def create_sample_emails():
    """Create sample email fixtures."""
    emails = []
    
    # Email 1: Urgent action item
    email1 = {
        "msg_id": "msg-001",
        "conversation_id": "conv-001",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "sender": {"email_address": "manager@company.com"},
        "subject": "URGENT: Server Maintenance Required",
        "text_body": """
        Hi Team,
        
        Our production server is experiencing issues and needs immediate attention.
        Please review the logs and schedule maintenance for tonight.
        
        Best regards,
        Manager
        """
    }
    emails.append(email1)
    
    # Email 2: Meeting request
    email2 = {
        "msg_id": "msg-002",
        "conversation_id": "conv-002",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
        "sender": {"email_address": "colleague@company.com"},
        "subject": "Meeting: Q4 Review",
        "text_body": """
        Hello,
        
        Let's schedule a meeting to review Q4 performance.
        Please confirm your availability for next week.
        
        Thanks,
        Colleague
        """
    }
    emails.append(email2)
    
    # Email 3: Out of Office
    email3 = {
        "msg_id": "msg-003",
        "conversation_id": "conv-003",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "sender": {"email_address": "user@company.com"},
        "subject": "Out of Office",
        "text_body": """
        I will be out of office until next Monday.
        For urgent matters, please contact my assistant.
        
        Best regards,
        User
        """
    }
    emails.append(email3)
    
    # Email 4: Long thread
    email4 = {
        "msg_id": "msg-004",
        "conversation_id": "conv-004",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
        "sender": {"email_address": "team@company.com"},
        "subject": "Project Discussion",
        "text_body": """
        This is a long email with multiple paragraphs.
        
        Paragraph 1: We need to discuss the project timeline.
        
        Paragraph 2: The budget has been approved.
        
        Paragraph 3: Please review the attached documents.
        
        Paragraph 4: Let me know if you have any questions.
        
        Paragraph 5: We should schedule a follow-up meeting.
        
        Best regards,
        Team
        """
    }
    emails.append(email4)
    
    # Email 5: DSN (Delivery Status Notification)
    email5 = {
        "msg_id": "msg-005",
        "conversation_id": "conv-005",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
        "sender": {"email_address": "system@company.com"},
        "subject": "Delivery Status Notification",
        "text_body": """
        Delivery Status Notification
        
        Your message could not be delivered.
        Please check the recipient address.
        
        System Administrator
        """
    }
    emails.append(email5)
    
    return emails


def create_config_fixtures():
    """Create sample configuration fixtures."""
    configs = {}
    
    # Calendar day config
    configs["calendar_day"] = {
        "time": {
            "timezone": "UTC",
            "window_type": "calendar_day"
        },
        "ews": {
            "endpoint": "https://mail.company.com/EWS/Exchange.asmx",
            "user_upn": "test@company.com",
            "sync_state_path": "/tmp/test.state"
        },
        "llm": {
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
            "max_retries": 3,
            "timeout": 30
        }
    }
    
    # Rolling 24h config
    configs["rolling_24h"] = {
        "time": {
            "timezone": "UTC",
            "window_type": "rolling_24h"
        },
        "ews": {
            "endpoint": "https://mail.company.com/EWS/Exchange.asmx",
            "user_upn": "test@company.com",
            "sync_state_path": "/tmp/test.state"
        },
        "llm": {
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
            "max_retries": 3,
            "timeout": 30
        }
    }
    
    return configs


if __name__ == "__main__":
    # Generate fixture files
    emails = create_sample_emails()
    configs = create_config_fixtures()
    
    # Save email fixtures
    with open("emails.json", "w") as f:
        json.dump(emails, f, indent=2)
    
    # Save config fixtures
    for name, config in configs.items():
        with open(f"config_{name}.yaml", "w") as f:
            import yaml
            yaml.dump(config, f, default_flow_style=False)
    
    print("Fixture files generated:")
    print("- emails.json")
    print("- config_calendar_day.yaml")
    print("- config_rolling_24h.yaml")
