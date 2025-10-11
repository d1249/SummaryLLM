"""
Exchange Web Services (EWS) email ingestion.
"""
import structlog
from datetime import datetime, timezone, timedelta
from typing import List, NamedTuple, Optional
from pathlib import Path
import pytz
from exchangelib import Credentials, Account, DELEGATE, Configuration, NTLM, Message
from exchangelib.folders import Inbox
from exchangelib.items import Item
import tenacity

from digest_core.config import EWSConfig, TimeConfig

logger = structlog.get_logger()


class NormalizedMessage(NamedTuple):
    """Normalized email message."""
    msg_id: str
    conversation_id: str
    datetime_received: datetime
    sender_email: str
    subject: str
    text_body: str
    to_recipients: List[str]
    cc_recipients: List[str]


class EWSIngest:
    """EWS email ingestion with NTLM authentication."""
    
    def __init__(self, config: EWSConfig):
        self.config = config
        self.account: Optional[Account] = None
        
    def _connect(self) -> Account:
        """Establish EWS connection with NTLM authentication."""
        if self.account is not None:
            return self.account
            
        logger.info("Connecting to EWS", endpoint=self.config.endpoint)
        
        # Create credentials
        credentials = Credentials(
            username=self.config.user_upn,
            password=self.config.get_ews_password()  # Will be resolved by config
        )
        
        # Create configuration
        config_obj = Configuration(
            server=self.config.endpoint,
            credentials=credentials,
            auth_type=NTLM,
            verify_ssl=self.config.verify_ca is not None,
            ca_cert=self.config.verify_ca
        )
        
        # Create account
        self.account = Account(
            primary_smtp_address=self.config.user_upn,
            config=config_obj,
            autodiscover=self.config.autodiscover,
            access_type=DELEGATE
        )
        
        logger.info("EWS connection established")
        return self.account
    
    def _get_time_window(self, digest_date: str, time_config: TimeConfig) -> tuple[datetime, datetime]:
        """Calculate time window for email fetching."""
        user_tz = pytz.timezone(time_config.user_timezone)
        
        if time_config.window == "calendar_day":
            # Calendar day: 00:00:00 to 23:59:59 in user timezone
            start_date = datetime.strptime(digest_date, "%Y-%m-%d").replace(tzinfo=user_tz)
            end_date = start_date.replace(hour=23, minute=59, second=59)
            
            # Convert to UTC
            start_utc = start_date.astimezone(timezone.utc)
            end_utc = end_date.astimezone(timezone.utc)
            
        else:  # rolling_24h
            # Rolling 24 hours from now
            now_utc = datetime.now(timezone.utc)
            end_utc = now_utc
            start_utc = now_utc - timedelta(hours=self.config.lookback_hours)
            
        logger.info(
            "Time window calculated",
            window_type=time_config.window,
            start_utc=start_utc.isoformat(),
            end_utc=end_utc.isoformat()
        )
        
        return start_utc, end_utc
    
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(8),
        wait=tenacity.wait_exponential(multiplier=0.5, max=60),
        retry=tenacity.retry_if_exception_type((ConnectionError, TimeoutError))
    )
    def _fetch_messages_with_retry(self, folder, start_date: datetime, end_date: datetime) -> List[Message]:
        """Fetch messages with retry logic."""
        try:
            # Create filter
            filter_kwargs = {
                'datetime_received__gte': start_date,
                'datetime_received__lte': end_date
            }
            
            # Fetch messages with pagination
            messages = []
            offset = 0
            
            while True:
                page = folder.filter(**filter_kwargs)[offset:offset + self.config.page_size]
                page_list = list(page)
                
                if not page_list:
                    break
                    
                messages.extend(page_list)
                offset += self.config.page_size
                
                logger.debug("Fetched page", page_size=len(page_list), total=len(messages))
            
            return messages
            
        except Exception as e:
            logger.warning("EWS fetch failed, retrying", error=str(e))
            raise
    
    def _normalize_message(self, msg: Message) -> NormalizedMessage:
        """Normalize EWS message to our format."""
        # Get message ID (prefer InternetMessageId, fallback to EWS ID)
        msg_id = getattr(msg, 'internet_message_id', None) or str(msg.id)
        if msg_id.startswith('<') and msg_id.endswith('>'):
            msg_id = msg_id[1:-1]  # Remove angle brackets
        msg_id = msg_id.lower()
        
        # Normalize conversation ID
        conversation_id = getattr(msg, 'conversation_id', None) or ""
        conversation_id = conversation_id.encode('utf-8', errors='ignore').decode('utf-8')
        
        # Get sender email
        sender_email = ""
        if msg.sender and msg.sender.email_address:
            sender_email = msg.sender.email_address.lower()
        
        # Get recipients
        to_recipients = []
        if msg.to_recipients:
            to_recipients = [r.email_address.lower() for r in msg.to_recipients if r.email_address]
        
        cc_recipients = []
        if msg.cc_recipients:
            cc_recipients = [r.email_address.lower() for r in msg.cc_recipients if r.email_address]
        
        # Get text body
        text_body = ""
        if msg.text_body:
            text_body = msg.text_body
        elif msg.body:
            text_body = str(msg.body)
        
        return NormalizedMessage(
            msg_id=msg_id,
            conversation_id=conversation_id,
            datetime_received=msg.datetime_received,
            sender_email=sender_email,
            subject=msg.subject or "",
            text_body=text_body,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients
        )
    
    def fetch_messages(self, digest_date: str, time_config: TimeConfig) -> List[NormalizedMessage]:
        """Fetch and normalize messages for the given date."""
        logger.info("Starting EWS message fetch", digest_date=digest_date)
        
        # Connect to EWS
        account = self._connect()
        
        # Calculate time window
        start_date, end_date = self._get_time_window(digest_date, time_config)
        
        # Fetch messages from Inbox
        inbox = account.inbox
        raw_messages = self._fetch_messages_with_retry(inbox, start_date, end_date)
        
        logger.info("Raw messages fetched", count=len(raw_messages))
        
        # Normalize messages
        normalized_messages = []
        for msg in raw_messages:
            try:
                normalized_msg = self._normalize_message(msg)
                normalized_messages.append(normalized_msg)
            except Exception as e:
                logger.warning("Failed to normalize message", msg_id=str(msg.id), error=str(e))
                continue
        
        logger.info("Messages normalized", count=len(normalized_messages))
        
        # Update sync state (simplified - in real implementation would use SyncState)
        self._update_sync_state(end_date)
        
        return normalized_messages
    
    def _update_sync_state(self, last_processed: datetime) -> None:
        """Update sync state for incremental processing."""
        sync_state_path = Path(self.config.sync_state_path)
        sync_state_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(sync_state_path, 'w') as f:
            f.write(last_processed.isoformat())
        
        logger.debug("Sync state updated", path=str(sync_state_path))
