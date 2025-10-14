"""
LLM Gateway client for processing evidence chunks with retry logic.
"""
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import httpx
import tenacity
import structlog
import pytz
from jinja2 import Environment, FileSystemLoader

def minimal_json_cleanup(text: str) -> str:
    """
    Minimal JSON cleanup - only removes markdown blocks and trims.
    
    Args:
        text: Raw text that may contain JSON
    
    Returns:
        Cleaned text
    """
    import re
    
    # Remove markdown code blocks
    text = re.sub(r'```\s*json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    # Trim to last closing brace if present
    if '}' in text:
        last_brace = text.rfind('}')
        text = text[:last_brace + 1]
    
    return text

try:
    from jsonschema import validate, ValidationError
except ImportError:
    ValidationError = Exception
    validate = None

from digest_core.config import LLMConfig
from digest_core.evidence.split import EvidenceChunk
from digest_core.llm.schemas import Digest, EnhancedDigest, EnhancedDigestV3
from digest_core.llm.date_utils import get_current_datetime_in_tz
from digest_core.llm.degrade import extractive_fallback
from digest_core.observability.metrics import MetricsCollector

logger = structlog.get_logger()


class LLMGateway:
    """Client for LLM Gateway API with retry logic and schema validation."""
    
    def __init__(
        self,
        config: LLMConfig,
        enable_degrade: bool = True,
        degrade_mode: str = "extractive",
        metrics: MetricsCollector = None
    ):
        self.config = config
        self.enable_degrade = enable_degrade
        self.degrade_mode = degrade_mode
        self.metrics = metrics
        self.last_latency_ms = 0
        self.client = httpx.Client(
            timeout=httpx.Timeout(self.config.timeout_s),
            headers=self.config.headers
        )
    
    def extract_actions(self, evidence: List[EvidenceChunk], prompt_template: str, trace_id: str) -> Dict[str, Any]:
        """Extract actions from evidence using LLM with retry logic and quality retry."""
        logger.info("Starting LLM action extraction", 
                   evidence_count=len(evidence), 
                   trace_id=trace_id)
        
        # Prepare evidence text
        evidence_text = self._prepare_evidence_text(evidence)
        
        # Prepare messages
        messages = [
            {
                "role": "system",
                "content": prompt_template
            },
            {
                "role": "user", 
                "content": evidence_text
            }
        ]
        
        # Make request with retry logic
        response_data = self._make_request_with_retry(messages, trace_id, None)
        
        # Validate response
        validated_response = self._validate_response(response_data.get("data", {}), evidence)

        # If empty result but we have promising evidence, perform one quality retry
        if not validated_response.get("sections"):
            has_positive = any(ec.priority_score >= 1.5 for ec in evidence)
            if has_positive:
                logger.info("Quality retry: empty sections but positive signals present", trace_id=trace_id)
                quality_hint = "\n\nIMPORTANT: If there are actionable requests or deadlines, return items accordingly. Return strict JSON per schema only."
                messages[0]["content"] = messages[0]["content"] + quality_hint
                response_data = self._make_request_with_retry(messages, trace_id, None)
                validated_response = self._validate_response(response_data.get("data", {}), evidence)
        
        logger.info("LLM action extraction completed", 
                   sections_count=len(validated_response.get("sections", [])),
                   trace_id=trace_id)
        
        # Attach meta if available
        if "meta" in response_data:
            validated_response["_meta"] = response_data["meta"]
        return validated_response
    
    def _prepare_evidence_text(self, evidence: List[EvidenceChunk]) -> str:
        """Prepare evidence text for LLM processing with rich metadata."""
        evidence_parts = []
        
        for i, chunk in enumerate(evidence):
            # Extract metadata with safe defaults
            metadata = chunk.message_metadata if hasattr(chunk, 'message_metadata') else {}
            sender = metadata.get('from', 'N/A')
            to_list = metadata.get('to', [])
            cc_list = metadata.get('cc', [])
            subject = metadata.get('subject', 'N/A')
            received_at = metadata.get('received_at', 'N/A')
            importance = metadata.get('importance', 'Normal')
            is_flagged = metadata.get('is_flagged', False)
            has_attachments = metadata.get('has_attachments', False)
            attachment_types = metadata.get('attachment_types', [])
            
            # Format recipients
            to_str = ', '.join(to_list[:3]) if to_list else 'N/A'
            if len(to_list) > 3:
                to_str += f' (+{len(to_list) - 3} more)'
            
            cc_str = ', '.join(cc_list[:3]) if cc_list else 'N/A'
            if len(cc_list) > 3:
                cc_str += f' (+{len(cc_list) - 3} more)'
            
            # Truncate subject if too long
            subject_trunc = subject[:80] + '...' if len(subject) > 80 else subject
            
            # Format attachments
            attachments_str = ', '.join(attachment_types) if attachment_types else 'none'
            
            # Extract AddressedToMe info
            addressed_to_me = getattr(chunk, 'addressed_to_me', False)
            aliases_matched = getattr(chunk, 'user_aliases_matched', [])
            aliases_str = ', '.join(aliases_matched) if aliases_matched else 'none'
            
            # Extract signals
            chunk_signals = getattr(chunk, 'signals', {})
            action_verbs = chunk_signals.get('action_verbs', [])
            dates = chunk_signals.get('dates', [])
            contains_question = chunk_signals.get('contains_question', False)
            sender_rank = chunk_signals.get('sender_rank', 1)
            
            # Format signals
            action_verbs_str = ', '.join(action_verbs[:5]) if action_verbs else 'none'
            if len(action_verbs) > 5:
                action_verbs_str += f' (+{len(action_verbs) - 5})'
            
            dates_str = ', '.join(dates[:3]) if dates else 'none'
            if len(dates) > 3:
                dates_str += f' (+{len(dates) - 3})'
            
            # Get message_id and conversation_id from source_ref
            msg_id = chunk.source_ref.get('msg_id', 'N/A')
            conv_id = chunk.source_ref.get('conversation_id', 'N/A')
            
            # Build evidence header
            part = f"""Evidence {i+1} (ID: {chunk.evidence_id}, Msg: {msg_id}, Thread: {conv_id})
From: {sender} | To: {to_str} | Cc: {cc_str}
Subject: {subject_trunc}
ReceivedAt: {received_at} | Importance: {importance} | Flag: {is_flagged} | HasAttachments: {attachments_str}
AddressedToMe: {addressed_to_me} (aliases: {aliases_str})
Signals: action_verbs=[{action_verbs_str}]; dates=[{dates_str}]; contains_question={contains_question}; sender_rank={sender_rank}; attachments=[{attachments_str}]
---
{chunk.content}

"""
            evidence_parts.append(part)
        
        evidence_combined = "\n".join(evidence_parts)
        
        return evidence_combined
    
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(2),  # Retry once on JSON errors
        wait=tenacity.wait_fixed(1),  # 1 second wait between retries
        retry=tenacity.retry_if_exception_type(ValueError)  # Only retry on JSON validation errors
    )
    def _make_request_with_retry(self, messages: List[Dict[str, str]], trace_id: str, digest_date: str = None) -> Dict[str, Any]:
        """Make request to LLM Gateway with retry logic for invalid JSON."""
        start_time = time.time()
        
        # Initialize token counters before try block to avoid UnboundLocalError in finally
        tokens_in = None
        tokens_out = None
        
        try:
            # Prepare request payload
            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": 0.1,  # Low temperature for consistent output
                "max_tokens": 2000,  # Reasonable limit for response
                "response_format": {"type": "json_object"},  # Force JSON output
            }
            
            # Add authorization header
            headers = self.config.headers.copy()
            headers["Authorization"] = f"Bearer {self.config.get_token()}"
            
            # Make request
            response = self.client.post(
                self.config.endpoint,
                json=payload,
                headers=headers
            )
            
            # Calculate latency
            self.last_latency_ms = int((time.time() - start_time) * 1000)
            
            # Check response status
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            # Extract content from response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content:
                logger.warning("Empty LLM response")
                return {
                    "trace_id": trace_id,
                    "latency_ms": self.last_latency_ms,
                    "data": {"sections": []}
                }
            
            # Try to parse JSON with minimal cleanup
            try:
                # Clean markdown blocks
                content_cleaned = minimal_json_cleanup(content)
                
                # Try to parse JSON
                try:
                    parsed_content = json.loads(content_cleaned)
                    
                except json.JSONDecodeError as parse_err:
                    error_msg = str(parse_err)
                    preview = content[:300] if len(content) > 300 else content
                    
                    # Record JSON error metric
                    if self.metrics:
                        self.metrics.record_llm_json_error()
                    
                    logger.error(
                        "Invalid JSON in LLM response",
                        error=error_msg,
                        preview=preview
                    )
                    
                    # Check if strict mode is enabled
                    if self.config.strict_json:
                        # In strict mode, add hint and raise to trigger retry
                        if "IMPORTANT: Return ONLY valid JSON" not in messages[0]["content"]:
                            messages[0]["content"] = messages[0]["content"] + "\n\nIMPORTANT: Return ONLY valid JSON per schema. No markdown, no code blocks."
                        raise ValueError(f"Invalid JSON in strict mode: {error_msg}")
                    else:
                        # Always raise to trigger fallback mechanism
                        raise ValueError(f"Invalid JSON from LLM: {error_msg}")
                        
            except ValueError as validation_err:
                # Re-raise validation errors to trigger retry or fallback
                raise
            except Exception as unexpected_err:
                logger.error("Unexpected LLM parsing error",
                            error=str(unexpected_err),
                            trace_id=trace_id)
                raise
            # Common header variants
            header_keys_in = [
                "x-llm-tokens-in", "x-tokens-in", "x-usage-tokens-in"
            ]
            header_keys_out = [
                "x-llm-tokens-out", "x-tokens-out", "x-usage-tokens-out"
            ]
            for k in header_keys_in:
                if k in response.headers:
                    try:
                        tokens_in = int(response.headers[k])
                        break
                    except Exception:
                        pass
            for k in header_keys_out:
                if k in response.headers:
                    try:
                        tokens_out = int(response.headers[k])
                        break
                    except Exception:
                        pass
            # Body usage fallback
            usage = result.get("usage") or {}
            if tokens_in is None:
                tokens_in = usage.get("prompt_tokens")
            if tokens_out is None:
                tokens_out = usage.get("completion_tokens")

            logger.info("LLM request successful", 
                       latency_ms=self.last_latency_ms,
                       tokens_in=tokens_in or 0, 
                       tokens_out=tokens_out or 0,
                       trace_id=trace_id)
            
            return {
                "trace_id": trace_id,
                "latency_ms": self.last_latency_ms,
                "data": parsed_content,
                "meta": {"tokens_in": tokens_in or 0, "tokens_out": tokens_out or 0}
            }
            
        except httpx.HTTPStatusError as e:
            logger.error("LLM request failed with HTTP error", 
                        status_code=e.response.status_code,
                        error=str(e),
                        trace_id=trace_id)
            raise

    def _validate_response(self, response_data: Dict[str, Any], evidence: List[EvidenceChunk]) -> Dict[str, Any]:
        """Validate LLM response against schema."""
        try:
            # Check if response has sections
            if "sections" not in response_data:
                logger.warning("No sections in LLM response")
                return {"sections": []}
            
            # Validate each section and item
            validated_sections = []
            for section in response_data["sections"]:
                validated_section = self._validate_section(section, evidence)
                if validated_section:
                    validated_sections.append(validated_section)
            
            return {"sections": validated_sections}
            
        except Exception as e:
            logger.error("Response validation failed", error=str(e))
            return {"sections": []}
    
    def _validate_section(self, section: Dict[str, Any], evidence: List[EvidenceChunk]) -> Optional[Dict[str, Any]]:
        """Validate a section and its items."""
        if not isinstance(section, dict) or "title" not in section or "items" not in section:
            return None
        
        validated_items = []
        for item in section.get("items", []):
            validated_item = self._validate_item(item, evidence)
            if validated_item:
                validated_items.append(validated_item)
        
        return {
            "title": section["title"],
            "items": validated_items
        }
    
    def _validate_item(self, item: Dict[str, Any], evidence: List[EvidenceChunk]) -> Optional[Dict[str, Any]]:
        """Validate an item against schema."""
        required_fields = ["title", "evidence_id", "confidence", "source_ref"]
        
        for field in required_fields:
            if field not in item:
                logger.warning(f"Missing required field in item: {field}")
                return None
        
        # Validate evidence_id exists in our evidence
        evidence_id = item["evidence_id"]
        if not any(chunk.evidence_id == evidence_id for chunk in evidence):
            logger.warning(f"Invalid evidence_id: {evidence_id}")
            return None
        
        # Validate confidence is a number between 0 and 1
        confidence = item["confidence"]
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            logger.warning(f"Invalid confidence value: {confidence}")
            return None
        
        # Validate source_ref structure
        source_ref = item["source_ref"]
        if not isinstance(source_ref, dict) or "type" not in source_ref:
            logger.warning("Invalid source_ref structure")
            return None
        
        return {
            "title": item["title"],
            "due": item.get("due"),
            "evidence_id": evidence_id,
            "confidence": confidence,
            "source_ref": source_ref
        }
    
    def summarize_digest(self, digest_data: Digest, prompt_template: str, trace_id: str) -> str:
        """Generate markdown summary of digest."""
        logger.info("Starting LLM digest summarization", trace_id=trace_id)
        
        # Prepare digest text
        digest_text = self._prepare_digest_text(digest_data)
        
        # Prepare messages
        messages = [
            {
                "role": "system",
                "content": prompt_template
            },
            {
                "role": "user",
                "content": digest_text
            }
        ]
        
        # Make request
        response_data = self._make_request_with_retry(messages, trace_id, digest_data.digest_date)
        
        # Extract markdown content
        content = response_data["data"].get("choices", [{}])[0].get("message", {}).get("content", "")
        
        logger.info("LLM digest summarization completed", trace_id=trace_id)
        
        return content
    
    def _prepare_digest_text(self, digest_data: Digest) -> str:
        """Prepare digest data for summarization."""
        text_parts = [
            f"Digest Date: {digest_data.digest_date}",
            f"Trace ID: {digest_data.trace_id}",
            ""
        ]
        
        for section in digest_data.sections:
            text_parts.append(f"## {section.title}")
            for item in section.items:
                text_parts.append(f"- {item.title}")
                if item.due:
                    text_parts.append(f"  Due: {item.due}")
                text_parts.append(f"  Evidence ID: {item.evidence_id}")
                text_parts.append(f"  Confidence: {item.confidence}")
            text_parts.append("")
        
        return "\n".join(text_parts)

    def _get_simplified_prompt(self, original_prompt: str) -> str:
        """
        Create a simplified version of the prompt for retry attempts.

        Args:
            original_prompt: Original complex prompt

        Returns:
            Simplified prompt with clearer instructions
        """
        # Extract just the core instructions and examples
        simplified = """Ты — ассистент для суммаризации email-треда.

ВАЖНО: Верни ТОЛЬКО валидный JSON без markdown:
{
  "thread_id": "ID",
  "summary": "Краткое описание (максимум 600 символов)",
  "pending_actions": [{"title": "Действие", "evidence_id": "id", "quote": "Цитата (максимум 300 символов)", "who_must_act": "user"}],
  "deadlines": [{"title": "Дедлайн", "date_time": "2024-12-15T14:00:00", "evidence_id": "id", "quote": "Цитата"}],
  "who_must_act": ["user"],
  "open_questions": ["Вопрос?"],
  "evidence_ids": ["id1", "id2"]
}

Правила:
- Максимум 600 символов для summary
- Максимум 300 символов для quote
- Обрезай по границе предложения если нужно

ПРИМЕР ПРАВИЛЬНОГО ВЫВОДА:
{
  "thread_id": "test",
  "summary": "Короткое описание треда",
  "pending_actions": [
    {
      "title": "Проверить отчет",
      "evidence_id": "ev_123",
      "quote": "Пожалуйста, проверьте отчет Q4.",
      "who_must_act": "user"
    }
  ],
  "deadlines": [],
  "who_must_act": ["user"],
  "open_questions": [],
  "evidence_ids": ["ev_123"]
}"""

        return simplified

    def get_request_stats(self) -> Dict[str, Any]:
        """Get request statistics."""
        return {
            "last_latency_ms": self.last_latency_ms,
            "endpoint": self.config.endpoint,
            "model": self.config.model,
            "timeout_s": self.config.timeout_s
        }
    
    def process_digest(
        self,
        evidence: List[EvidenceChunk],
        digest_date: str,
        trace_id: str, 
        prompt_version: str = "mvp.5",
        custom_input: str = None
    ) -> Dict[str, Any]:
        """
        Process evidence with enhanced v2 prompt and validation.
        With degradation fallback on LLM failures.
        
        Args:
            evidence: List of evidence chunks
            digest_date: Date of the digest
            trace_id: Trace ID for logging
            prompt_version: Version of prompt to use (default: "v2")
            custom_input: Custom input text (for hierarchical mode, replaces evidence)
        
        Returns:
            Dict with digest, trace_id, meta information, and partial flag
        """
        logger.info("Processing digest with enhanced prompt", 
                   evidence_count=len(evidence) if not custom_input else 0,
                   custom_input=bool(custom_input),
                   prompt_version=prompt_version,
                   trace_id=trace_id)
        
        try:
            return self._process_digest_internal(evidence, digest_date, trace_id, prompt_version, custom_input)
            
        except Exception as llm_err:
            logger.error("LLM digest processing failed",
                        error=str(llm_err),
                        trace_id=trace_id)
            
            if not self.enable_degrade or custom_input:
                # Don't degrade hierarchical mode (custom_input) or if degrade disabled
                raise
            
            # Determine reason for degradation
            reason = "llm_json_error" if "JSON" in str(llm_err) else "llm_processing_failed"
            
            # Record degradation metric
            if self.metrics:
                self.metrics.record_degradation(reason)
            
            # Use extractive fallback
            logger.warning("Using extractive fallback for digest", trace_id=trace_id, reason=reason)
            fallback_digest = extractive_fallback(
                evidence,
                digest_date,
                trace_id,
                reason=reason
            )
            
            return {
                "trace_id": trace_id,
                "digest": fallback_digest,
                "meta": {},
                "partial": True,
                "reason": reason
            }
    
    def _process_digest_internal(
        self,
        evidence: List[EvidenceChunk], 
        digest_date: str, 
        trace_id: str, 
        prompt_version: str = "mvp.5",
        custom_input: str = None
    ) -> Dict[str, Any]:
        """Internal digest processing without fallback logic."""
        
        # Use custom_input if provided (hierarchical mode), else prepare evidence text
        if custom_input:
            evidence_text = custom_input
        else:
            evidence_text = self._prepare_evidence_text(evidence)
        
        # Get current datetime in target timezone
        tz_name = "America/Sao_Paulo"
        current_datetime = get_current_datetime_in_tz(tz_name)
        
        # Load and render prompt
        prompts_dir = Path("prompts")
        env = Environment(loader=FileSystemLoader(prompts_dir))
        template = env.get_template(f"summarize.{prompt_version}.j2")
        
        rendered_prompt = template.render(
            digest_date=digest_date,
            trace_id=trace_id,
            current_datetime=current_datetime,
            evidence=evidence_text,
            evidence_count=len(evidence)
        )
        
        # Prepare messages
        messages = [
            {"role": "user", "content": rendered_prompt}
        ]
        
        # Call LLM with retry
        response_data = self._make_request_with_retry(messages, trace_id, digest_date)
        
        # Parse response (JSON + optional Markdown)
        parsed = self._parse_enhanced_response(response_data.get("data", ""))
        
        # Validate with jsonschema
        if validate is not None:
            validated = self._validate_enhanced_schema(parsed)
        else:
            logger.warning("jsonschema not available, skipping validation")
            validated = parsed
        
        # Convert to Pydantic model - use V3 for mvp.5, otherwise V2
        try:
            if prompt_version in ["mvp.5", "mvp5"]:
                digest = EnhancedDigestV3(**validated)
            else:
                digest = EnhancedDigest(**validated)
        except Exception as e:
            logger.error("Failed to parse digest", error=str(e), prompt_version=prompt_version)
            raise ValueError(f"Invalid digest structure: {e}")
        
        logger.info("Digest processing completed",
                   my_actions=len(digest.my_actions),
                   others_actions=len(digest.others_actions),
                   deadlines=len(digest.deadlines_meetings),
                   trace_id=trace_id)
        
        return {
            "trace_id": trace_id,
            "digest": digest,
            "meta": response_data.get("meta", {})
        }
    
    def _parse_enhanced_response(self, response_text) -> Dict[str, Any]:
        """
        Parse response that may contain JSON + Markdown.
        
        Args:
            response_text: Raw response from LLM (str or dict)
        
        Returns:
            Parsed dict with JSON data and optional markdown_summary
        """
        # If already a dict (parsed by gateway), return as is
        if isinstance(response_text, dict):
            return response_text
        
        if not response_text:
            raise ValueError("Empty response from LLM")
        
        text = response_text.strip()
        
        # Try to extract JSON (may be followed by markdown)
        lines = text.split('\n')
        
        brace_count = 0
        in_json = False
        json_lines = []
        markdown_lines = []
        
        for i, line in enumerate(lines):
            if not in_json and line.strip().startswith('{'):
                in_json = True
            
            if in_json:
                json_lines.append(line)
                brace_count += line.count('{') - line.count('}')
                
                if brace_count == 0:
                    # JSON ended
                    markdown_lines = lines[i+1:]
                    break
        
        # Parse JSON
        if not json_lines:
            raise ValueError("No JSON found in response")
        
        json_str = '\n'.join(json_lines)
        try:
            # Minimal cleanup before parsing
            json_cleaned = minimal_json_cleanup(json_str)
            parsed = json.loads(json_cleaned)
            
        except json.JSONDecodeError as parse_err:
            error_msg = str(parse_err)
            preview = json_str[:300] if len(json_str) > 300 else json_str
            
            # Record JSON error metric
            if self.metrics:
                self.metrics.record_llm_json_error()
            
            logger.error(
                "Invalid JSON in enhanced response",
                error=error_msg,
                json_preview=preview
            )
            
            # Raise error to trigger fallback mechanism
            raise ValueError(f"Invalid JSON in enhanced response: {error_msg}")
        
        # Add markdown if present
        if markdown_lines:
            markdown_text = '\n'.join(markdown_lines).strip()
            if markdown_text and 'markdown_summary' not in parsed:
                parsed['markdown_summary'] = markdown_text
        
        return parsed
    
    def _validate_enhanced_schema(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate response against enhanced schema using jsonschema.
        
        Args:
            response_data: Parsed response data
        
        Returns:
            Validated response data
        
        Raises:
            ValueError: If validation fails
        """
        # Define JSON schema (supports both V2 and V3)
        action_item_schema = {
            "type": "object",
            "required": ["title", "description", "evidence_id", "quote", "confidence"],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "description": {"type": "string"},
                "evidence_id": {"type": "string", "minLength": 1},
                "quote": {"type": "string", "minLength": 10},
                "due_date": {"type": ["string", "null"]},
                "due_date_normalized": {"type": ["string", "null"]},
                "due_date_label": {"type": ["string", "null"]},
                "actors": {"type": "array", "items": {"type": "string"}},
                "owners": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "string", "enum": ["High", "Medium", "Low"]},
                "response_channel": {"type": ["string", "null"]}
            }
        }
        
        schema = {
            "type": "object",
            "required": ["schema_version", "digest_date", "trace_id"],
            "properties": {
                "schema_version": {"type": "string"},
                "prompt_version": {"type": "string"},
                "digest_date": {"type": "string"},
                "trace_id": {"type": "string"},
                "timezone": {"type": "string"},
                "my_actions": {
                    "type": "array",
                    "items": action_item_schema
                },
                "others_actions": {
                    "type": "array",
                    "items": action_item_schema
                },
                "deadlines_meetings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["title", "evidence_id", "quote", "date_time"],
                        "properties": {
                            "title": {"type": "string"},
                            "evidence_id": {"type": "string"},
                            "quote": {"type": "string", "minLength": 10},
                            "date_time": {"type": "string"},
                            "date_label": {"type": ["string", "null"]},
                            "location": {"type": ["string", "null"]},
                            "participants": {"type": "array"}
                        }
                    }
                },
                "risks_blockers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["title", "evidence_id", "quote", "severity", "impact"],
                        "properties": {
                            "title": {"type": "string"},
                            "evidence_id": {"type": "string"},
                            "quote": {"type": "string", "minLength": 10},
                            "severity": {"type": "string"},
                            "impact": {"type": "string"},
                            "owners": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                "fyi": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["title", "evidence_id", "quote"],
                        "properties": {
                            "title": {"type": "string"},
                            "evidence_id": {"type": "string"},
                            "quote": {"type": "string", "minLength": 10},
                            "category": {"type": ["string", "null"]}
                        }
                    }
                },
                "markdown_summary": {"type": ["string", "null"]}
            }
        }
        
        try:
            validate(instance=response_data, schema=schema)
            logger.info("Enhanced schema validation passed")
            return response_data
        except ValidationError as e:
            logger.error("Schema validation failed", error=str(e), path=list(e.path))
            raise ValueError(f"Invalid response schema: {e.message}")
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
