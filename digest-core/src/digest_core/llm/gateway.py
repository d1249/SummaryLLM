"""
LLM Gateway client for processing evidence chunks with retry logic.
"""
import json
import time
from typing import List, Dict, Any, Optional
import httpx
import tenacity
import structlog

from digest_core.config import LLMConfig
from digest_core.evidence.split import EvidenceChunk
from digest_core.llm.schemas import Digest

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
        response_data = self._make_request_with_retry(messages, trace_id)
        
        # Validate response
        validated_response = self._validate_response(response_data.get("data", {}), evidence)

        # If empty result but we have promising evidence, perform one quality retry
        if not validated_response.get("sections"):
            has_positive = any(ec.priority_score >= 1.5 for ec in evidence)
            if has_positive:
                logger.info("Quality retry: empty sections but positive signals present", trace_id=trace_id)
                quality_hint = "\n\nIMPORTANT: If there are actionable requests or deadlines, return items accordingly. Return strict JSON per schema only."
                messages[0]["content"] = messages[0]["content"] + quality_hint
                response_data = self._make_request_with_retry(messages, trace_id)
                validated_response = self._validate_response(response_data.get("data", {}), evidence)
        
        logger.info("LLM action extraction completed", 
                   sections_count=len(validated_response.get("sections", [])),
                   trace_id=trace_id)
        
        # Attach meta if available
        if "meta" in response_data:
            validated_response["_meta"] = response_data["meta"]
        return validated_response
    
    def _prepare_evidence_text(self, evidence: List[EvidenceChunk]) -> str:
        """Prepare evidence text for LLM processing."""
        evidence_parts = []
        
        for i, chunk in enumerate(evidence):
            part = f"Evidence {i+1} (ID: {chunk.evidence_id}):\n{chunk.content}\n"
            evidence_parts.append(part)
        
        return "\n".join(evidence_parts)
    
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(2),  # Retry once on JSON errors
        wait=tenacity.wait_fixed(1),  # 1 second wait between retries
        retry=tenacity.retry_if_exception_type(ValueError)  # Only retry on JSON validation errors
    )
    def _make_request_with_retry(self, messages: List[Dict[str, str]], trace_id: str) -> Dict[str, Any]:
        """Make request to LLM Gateway with retry logic for invalid JSON."""
        start_time = time.time()
        
        try:
            # Prepare request payload
            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": 0.1,  # Low temperature for consistent output
                "max_tokens": 2000,  # Reasonable limit for response
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
            
            # Try to parse JSON
            try:
                parsed_content = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON in LLM response, retrying", error=str(e))
                # Add retry instruction to system message
                messages[0]["content"] = messages[0]["content"] + "\n\nIMPORTANT: Return strict JSON per schema only. No additional text."
                raise ValueError("Invalid JSON response")
            
            # Try to capture token usage from headers or body
            tokens_in = None
            tokens_out = None
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
        except Exception as e:
            logger.error("LLM request failed", 
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
        response_data = self._make_request_with_retry(messages, trace_id)
        
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
    
    def get_request_stats(self) -> Dict[str, Any]:
        """Get request statistics."""
        return {
            "last_latency_ms": self.last_latency_ms,
            "endpoint": self.config.endpoint,
            "model": self.config.model,
            "timeout_s": self.config.timeout_s
        }
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
