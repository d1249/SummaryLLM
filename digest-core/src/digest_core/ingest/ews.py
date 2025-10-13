"""
Exchange Web Services (EWS) email ingestion with NTLM authentication.
"""
import structlog
from datetime import datetime, timezone, timedelta
from typing import List, NamedTuple, Optional
from pathlib import Path
import pytz
from exchangelib import (
    Credentials, Account, DELEGATE, Configuration, NTLM, 
    Message, Folder, Q, EWSDateTime
)
from exchangelib.protocol import BaseProtocol
import tenacity
import ssl

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
    
    # Class-level flags to track global SSL patching (thread-safety consideration)
    _ssl_verification_disabled = False
    _original_request = None
    
    def __init__(self, config: EWSConfig):
        self.config = config
        self.account: Optional[Account] = None
        self._setup_ssl_context()
        
    def _setup_ssl_context(self):
        """Setup SSL context based on configuration.
        
        Three modes:
        1. verify_ssl=false: Disable all SSL verification (TESTING ONLY!)
        2. verify_ca specified: Use custom CA certificate
        3. Default: Use system CA certificates
        
        Warning:
            Setting verify_ssl=false disables SSL verification globally
            for all EWS connections in this process. Use only for testing!
        """
        # Create SSL context once
        self.ssl_context = ssl.create_default_context()
        
        if not self.config.verify_ssl:
            # Полностью отключаем SSL verification для тестирования
            self.ssl_context.check_hostname = False  # Не проверяем hostname
            self.ssl_context.verify_mode = ssl.CERT_NONE  # Не проверяем сертификат
            logger.warning(
                "SSL verification disabled (verify_ssl=false)",
                extra={"security_warning": "Use only for testing!"}
            )
        elif self.config.verify_ca:
            # Use custom CA certificate
            try:
                self.ssl_context.load_verify_locations(self.config.verify_ca)
                logger.info("SSL context configured with corporate CA", 
                          ca_path=self.config.verify_ca)
            except FileNotFoundError as e:
                logger.error("Corporate CA certificate not found",
                           ca_path=self.config.verify_ca,
                           error=str(e))
                raise
        else:
            # Use default system CA
            logger.warning("Using system CA certificates for SSL verification")
        
    def _connect(self) -> Account:
        """Establish EWS connection with NTLM authentication."""
        if self.account is not None:
            return self.account
            
        logger.info("Connecting to EWS", endpoint=self.config.endpoint)
        
        # Create credentials with NTLM username (login@domain)
        ntlm_username = self.config.get_ntlm_username()
        credentials = Credentials(
            username=ntlm_username,
            password=self.config.get_password()
        )
        
        logger.debug("Using NTLM authentication", username=ntlm_username)
        
        # Set SSL context (thread-safe assignment)
        BaseProtocol.SSL_CONTEXT = self.ssl_context
        
        # Handle SSL verification disabling (with proper guards)
        if not self.config.verify_ssl and not self.__class__._ssl_verification_disabled:
            self._disable_ssl_verification()

        # Create configuration with NTLM auth and explicit service endpoint
        config_obj = Configuration(
            service_endpoint=self.config.endpoint,
            credentials=credentials,
            auth_type=NTLM,
        )
        
        # Create account with explicit settings
        self.account = Account(
            primary_smtp_address=self.config.user_upn,
            config=config_obj,
            autodiscover=False,  # Explicitly disable autodiscover
            access_type=DELEGATE
        )
        
        logger.info("EWS connection established", 
                   endpoint=self.config.endpoint,
                   user="[[REDACTED]]",  # Маскируем email в логах
                   auth_type="NTLM")
        return self.account
    
    @classmethod
    def _disable_ssl_verification(cls):
        """Disable SSL verification globally (use with caution!).
        
        Warning:
            This method monkey-patches requests.Session.request globally
            for all HTTP requests. It should only be called once per process.
        
        Side effects:
            - Disables urllib3 SSL warnings globally
            - Patches requests.Session.request to use verify=False
            - Sets class-level flag _ssl_verification_disabled
        """
        if cls._ssl_verification_disabled:
            logger.debug("SSL verification already disabled, skipping")
            return
            
        # Suppress SSL warnings globally
        import urllib3
        import requests
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Monkey-patch requests.Session.request (only once)
        if cls._original_request is None:
            cls._original_request = requests.Session.request
            
        def patched_request(self, method, url, **kwargs):
            """Patched version of Session.request that disables SSL verification."""
            kwargs['verify'] = False
            return cls._original_request(self, method, url, **kwargs)
        
        requests.Session.request = patched_request
        cls._ssl_verification_disabled = True
        
        logger.critical(
            "SSL verification disabled globally for all HTTP requests",
            extra={"security_risk": "HIGH", "testing_only": True}
        )
    
    @classmethod
    def restore_ssl_verification(cls):
        """Restore original SSL verification (cleanup method).
        
        This method should be called when SSL verification needs to be re-enabled,
        typically in test cleanup or when transitioning from testing to production.
        """
        if not cls._ssl_verification_disabled:
            logger.debug("SSL verification not disabled, nothing to restore")
            return
            
        if cls._original_request is not None:
            import requests
            requests.Session.request = cls._original_request
            cls._ssl_verification_disabled = False
            logger.info("SSL verification restored to original state")
        else:
            logger.warning("Cannot restore SSL verification: original method not saved")
    
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
    def _fetch_messages_with_retry(self, folder: Folder, start_date: datetime, end_date: datetime) -> List[Message]:
        """Fetch messages with retry logic."""
        try:
            # Create EWS datetime objects
            start_ews = EWSDateTime.from_datetime(start_date)
            end_ews = EWSDateTime.from_datetime(end_date)
            
            # Create filter for last 24 hours
            filter_query = Q(
                datetime_received__gte=start_ews,
                datetime_received__lte=end_ews
            )
            
            # Fetch messages with pagination
            messages = []
            offset = 0
            
            while True:
                # Use folder.filter() with pagination
                page = folder.filter(filter_query)[offset:offset + self.config.page_size]
                page_list = list(page)
                
                if not page_list:
                    break
                    
                messages.extend(page_list)
                offset += self.config.page_size
                
                logger.debug("Fetched page", page_size=len(page_list), total=len(messages))
                
                # Safety check to prevent infinite loops
                if len(page_list) < self.config.page_size:
                    break
            
            return messages
            
        except Exception as e:
            logger.warning("EWS fetch failed, retrying", error=str(e))
            raise
    
    def _normalize_message(self, msg: Message) -> NormalizedMessage:
        """Normalize EWS message to our format."""
        # Get message ID (prefer InternetMessageId, fallback to EWS ID)
        msg_id = getattr(msg, 'internet_message_id', None) or str(msg.id)
        if msg_id and msg_id.startswith('<') and msg_id.endswith('>'):
            msg_id = msg_id[1:-1]  # Remove angle brackets
        msg_id = (msg_id or "").lower()
        
        # Normalize conversation ID
        conversation_id = getattr(msg, 'conversation_id', None) or ""
        if conversation_id:
            conversation_id = conversation_id.encode('utf-8', errors='ignore').decode('utf-8')
        
        # Get sender email address
        sender_email = ""
        if msg.sender and hasattr(msg.sender, 'email_address') and msg.sender.email_address:
            sender_email = msg.sender.email_address.lower()
        
        # Get recipients
        to_recipients = []
        if hasattr(msg, 'to_recipients') and msg.to_recipients:
            to_recipients = [
                r.email_address.lower() 
                for r in msg.to_recipients 
                if hasattr(r, 'email_address') and r.email_address
            ]
        
        cc_recipients = []
        if hasattr(msg, 'cc_recipients') and msg.cc_recipients:
            cc_recipients = [
                r.email_address.lower() 
                for r in msg.cc_recipients 
                if hasattr(r, 'email_address') and r.email_address
            ]
        
        # Get text body (prefer text_body, fallback to body)
        text_body = ""
        if hasattr(msg, 'text_body') and msg.text_body:
            text_body = msg.text_body
        elif hasattr(msg, 'body') and msg.body:
            text_body = str(msg.body)
        
        # Convert datetime to UTC if needed
        datetime_received = msg.datetime_received
        if datetime_received.tzinfo is None:
            datetime_received = datetime_received.replace(tzinfo=timezone.utc)
        elif datetime_received.tzinfo != timezone.utc:
            datetime_received = datetime_received.astimezone(timezone.utc)
        
        return NormalizedMessage(
            msg_id=msg_id,
            conversation_id=conversation_id,
            datetime_received=datetime_received,
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
        
        # Check SyncState/Watermark for incremental processing
        watermark = self._load_sync_state()
        if watermark:
            try:
                start_date = datetime.fromisoformat(watermark)
                logger.info("Using watermark for incremental window", start=start_date.isoformat())
            except Exception:
                logger.warning("Invalid watermark format, doing full fetch", watermark=watermark)
        # Fetch with retry over the computed window
        raw_messages = self._fetch_messages_with_retry(account.inbox, start_date, end_date)
        
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
        
        # Update SyncState with latest timestamp
        self._update_sync_state(end_date)
        
        return normalized_messages
    
    def _load_sync_state(self) -> Optional[str]:
        """Load SyncState/watermark (ISO timestamp) from file."""
        sync_state_path = Path(self.config.sync_state_path)
        if not sync_state_path.exists():
            logger.info("No SyncState file found, will perform full fetch")
            return None
        
        try:
            with open(sync_state_path, 'r') as f:
                sync_state = f.read().strip()
            logger.info("SyncState loaded", path=str(sync_state_path))
            return sync_state
        except Exception as e:
            logger.warning("Failed to load SyncState", path=str(sync_state_path), error=str(e))
            return None
    
    # Note: Real EWS SyncFolderItems can be added later; MVP uses timestamp watermark
    
    def _update_sync_state(self, last_processed: datetime) -> None:
        """Update timestamp watermark for incremental processing."""
        sync_state_path = Path(self.config.sync_state_path)
        sync_state_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(sync_state_path, 'w') as f:
                f.write(last_processed.isoformat())
            
            logger.debug("SyncState updated", 
                        path=str(sync_state_path),
                        timestamp=last_processed.isoformat())
        except Exception as e:
            logger.warning("Failed to update SyncState", 
                          path=str(sync_state_path),
                          error=str(e))