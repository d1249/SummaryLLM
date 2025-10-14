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

try:
    from json_repair import repair_json
except ImportError:
    # Fallback if json-repair not available
    def repair_json(text: str) -> str:
        return text

def extract_json_from_text(text: str) -> str:
    """
    Extract JSON from text using regex patterns as last resort.

    Args:
        text: Text that may contain JSON

    Returns:
        Extracted JSON string or original text
    """
    import re

    # Try to find JSON object/array
    patterns = [
        r'\{.*\}',  # Object
        r'\[.*\]',  # Array
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            # Try to parse this match as JSON
            try:
                json.loads(match)
                return match
            except:
                continue

    return text

def advanced_json_repair(text: str) -> str:
    """
    Advanced JSON repair that handles common LLM JSON issues.

    Args:
        text: Raw text that should contain JSON

    Returns:
        Repaired JSON string
    """
    import re

    # 1. Remove markdown code blocks if present
    text = re.sub(r'```\s*json\s*', '', text)
    text = re.sub(r'```\s*$', '', text)

    # 2. Fix unterminated strings (common issue)
    # Find strings that start but don't end properly
    lines = text.split('\n')
    fixed_lines = []
    in_string = False
    string_char = None

    for line in lines:
        if not in_string:
            # Look for start of string
            string_match = re.search(r'(["\'])(.*)$', line)
            if string_match:
                string_char = string_match.group(1)
                content = string_match.group(2)
                # Check if string ends on this line
                if content.count(string_char) % 2 == 1:  # Odd number means unterminated
                    line = line + string_char  # Close the string
                    in_string = False
                else:
                    in_string = True
            fixed_lines.append(line)
        else:
            # We're in a string, look for its end
            if string_char in line:
                in_string = False
            fixed_lines.append(line)

    text = '\n'.join(fixed_lines)

    # 3. Fix missing commas between objects in arrays
    # Pattern: } { -> },
    text = re.sub(r'}\s*{', '}, {', text)

    # 4. Fix trailing commas before closing brackets/braces
    text = re.sub(r',(\s*[}\]])', r'\1', text)

    # 5. Fix missing closing braces/brackets at end
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')

    if open_braces > 0:
        text += '}' * open_braces
    if open_brackets > 0:
        text += ']' * open_brackets

    return text

try:
    from jsonschema import validate, ValidationError
except ImportError:
    ValidationError = Exception
    validate = None

from digest_core.config import LLMConfig
from digest_core.evidence.split import EvidenceChunk
from digest_core.llm.schemas import Digest, EnhancedDigest
from digest_core.llm.date_utils import get_current_datetime_in_tz

logger = structlog.get_logger()


class LLMGateway:
    """Client for LLM Gateway API with retry logic and schema validation."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
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
        response_data = self._make_request_with_retry(messages, trace_id, digest_date)
        
        # Validate response
        validated_response = self._validate_response(response_data.get("data", {}), evidence)

        # If empty result but we have promising evidence, perform one quality retry
        if not validated_response.get("sections"):
            has_positive = any(ec.priority_score >= 1.5 for ec in evidence)
            if has_positive:
                logger.info("Quality retry: empty sections but positive signals present", trace_id=trace_id)
                quality_hint = "\n\nIMPORTANT: If there are actionable requests or deadlines, return items accordingly. Return strict JSON per schema only."
                messages[0]["content"] = messages[0]["content"] + quality_hint
                response_data = self._make_request_with_retry(messages, trace_id, digest_date)
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
        
        return "\n".join(evidence_parts)
    
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(2),  # Retry once on JSON errors
        wait=tenacity.wait_fixed(1),  # 1 second wait between retries
        retry=tenacity.retry_if_exception_type(ValueError)  # Only retry on JSON validation errors
    )
    def _make_request_with_retry(self, messages: List[Dict[str, str]], trace_id: str, digest_date: str = None) -> Dict[str, Any]:
        """Make request to LLM Gateway with retry logic for invalid JSON."""
        start_time = time.time()
        
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
            
            # Try to parse JSON (handle markdown code blocks)
            try:
                # Strip markdown code blocks if present
                content_stripped = content.strip()
                if content_stripped.startswith("```"):
                    # Extract JSON from markdown code block
                    lines = content_stripped.split("\n")
                    # Remove first line (```json or ```)
                    lines = lines[1:]
                    # Remove last line if it's ```
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    content_stripped = "\n".join(lines).strip()
                
                # Try to parse JSON first
                try:
                    parsed_content = json.loads(content_stripped)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Invalid JSON in LLM response, attempting repair",
                        error=str(e),
                        content_preview=content[:500] if len(content) > 500 else content
                    )
                    # Try to repair JSON using advanced repair
                    try:
                        # First try with advanced repair
                        advanced_repaired = advanced_json_repair(content_stripped)
                        parsed_content = json.loads(advanced_repaired)
                        logger.info("JSON successfully repaired with advanced repair", original_error=str(e))
                    except Exception as advanced_error:
                        logger.warning(
                            "Advanced JSON repair failed, trying json-repair library",
                            advanced_error=str(advanced_error)
                        )
                try:
                    # Fallback to json-repair library
                    repaired_json = repair_json(content_stripped)
                    parsed_content = json.loads(repaired_json)
                    logger.info("JSON successfully repaired with json-repair library", original_error=str(e))
                except Exception as library_error:
                    logger.warning(
                        "JSON repair failed, trying regex extraction",
                        library_error=str(library_error)
                    )
                    try:
                        # Last resort: extract JSON with regex
                        extracted_json = extract_json_from_text(content_stripped)
                        if extracted_json != content_stripped:
                            parsed_content = json.loads(extracted_json)
                            logger.info("JSON successfully extracted with regex", original_error=str(e))
                        else:
                            raise ValueError("No valid JSON found")
                    except Exception as extract_error:
                        logger.error(
                            "All JSON repair methods failed, creating fallback digest",
                            extract_error=str(extract_error),
                            content_preview=content[:300] if len(content) > 300 else content
                        )
                        # Last resort: create empty digest instead of failing completely
                        parsed_content = {
                            "schema_version": "2.0",
                            "prompt_version": "v2",
                            "digest_date": digest_date,
                            "trace_id": trace_id,
                            "timezone": "America/Sao_Paulo",
                            "my_actions": [],
                            "others_actions": [],
                            "deadlines_meetings": [],
                            "risks_blockers": [],
                            "fyi": []
                        }
                # Add retry instruction to system message
                if "IMPORTANT: Return ONLY valid JSON" not in messages[0]["content"]:
                    messages[0]["content"] = messages[0]["content"] + "\n\nIMPORTANT: Return ONLY valid JSON per schema. No markdown, no code blocks, no additional text."

                # On second retry, use simplified prompt
                if hasattr(self, '_retry_count'):
                    self._retry_count = getattr(self, '_retry_count', 0) + 1
                else:
                    self._retry_count = 1

                if self._retry_count >= 2:
                    # Use simplified prompt for final retry
                    messages[0]["content"] = self._get_simplified_prompt(messages[0]["content"])
                    logger.info("Using simplified prompt for retry", retry_count=self._retry_count)

                raise ValueError("Invalid JSON response")
            except Exception as e:
                logger.error("LLM request failed",
                            error=str(e),
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
                       tokens_in=tokens_in, tokens_out=tokens_out,
                       trace_id=trace_id)
            
            return {
                "trace_id": trace_id,
                "latency_ms": self.last_latency_ms,
                "data": parsed_content,
                "meta": {"tokens_in": tokens_in, "tokens_out": tokens_out}
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
            "owners_masked": item.get("owners_masked", []),
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
        response_data = self._make_request_with_retry(messages, trace_id, digest_date)
        
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
        prompt_version: str = "v2",
        custom_input: str = None
    ) -> Dict[str, Any]:
        """
        Process evidence with enhanced v2 prompt and validation.
        
        Args:
            evidence: List of evidence chunks
            digest_date: Date of the digest
            trace_id: Trace ID for logging
            prompt_version: Version of prompt to use (default: "v2")
            custom_input: Custom input text (for hierarchical mode, replaces evidence)
        
        Returns:
            Dict with digest, trace_id, and meta information
        """
        logger.info("Processing digest with enhanced prompt", 
                   evidence_count=len(evidence) if not custom_input else 0,
                   custom_input=bool(custom_input),
                   prompt_version=prompt_version,
                   trace_id=trace_id)
        
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
        
        # Convert to Pydantic model
        try:
            digest = EnhancedDigest(**validated)
        except Exception as e:
            logger.error("Failed to parse as EnhancedDigest", error=str(e))
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
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in response, attempting repair", error=str(e), json_preview=json_str[:500])
            try:
                # First try with advanced repair
                advanced_repaired = advanced_json_repair(json_str)
                parsed = json.loads(advanced_repaired)
                logger.info("JSON successfully repaired with advanced repair", original_error=str(e))
            except Exception as advanced_error:
                logger.warning(
                    "Advanced JSON repair failed, trying json-repair library",
                    advanced_error=str(advanced_error)
                )
                try:
                    # Fallback to json-repair library
                    repaired_json = repair_json(json_str)
                    parsed = json.loads(repaired_json)
                    logger.info("JSON successfully repaired with json-repair library", original_error=str(e))
                except Exception as library_error:
                    logger.warning(
                        "JSON repair failed, trying regex extraction",
                        library_error=str(library_error)
                    )
                    try:
                        # Last resort: extract JSON with regex
                        extracted_json = extract_json_from_text(json_str)
                        if extracted_json != json_str:
                            parsed = json.loads(extracted_json)
                            logger.info("JSON successfully extracted with regex", original_error=str(e))
                        else:
                            raise ValueError("No valid JSON found")
                    except Exception as extract_error:
                        logger.error(
                            "All JSON repair methods failed for thread summary, creating fallback",
                            extract_error=str(extract_error),
                            json_preview=json_str[:300] if len(json_str) > 300 else json_str
                        )
                        # Last resort: create empty thread summary instead of failing completely
                        parsed = {
                            "thread_id": thread_id,
                            "summary": "Thread summary extraction failed",
                            "pending_actions": [],
                            "deadlines": [],
                            "who_must_act": [],
                            "open_questions": [],
                            "evidence_ids": [c.evidence_id for c in chunks[:3]]  # Use first 3 evidence IDs
                        }
        
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
        # Define JSON schema
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
                            "impact": {"type": "string"}
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
