<!-- f696db6b-77ad-4218-bf20-26d7ea14cf9e 1c23be93-08a3-4dcc-b53f-96a41fd38d88 -->
# Hierarchical Digest Mode Implementation

## 1. Создание схемы ThreadSummary

**digest-core/src/digest_core/llm/schemas.py**

Добавить модель для per-thread summary:

```python
class ThreadAction(BaseModel):
    """Action item from thread summary."""
    title: str = Field(max_length=100)
    evidence_id: str
    quote: str = Field(min_length=10, max_length=150)
    who_must_act: str = Field(description="user/sender/team")
    
class ThreadDeadline(BaseModel):
    """Deadline from thread summary."""
    title: str
    date_time: str
    evidence_id: str
    quote: str = Field(min_length=10, max_length=150)

class ThreadSummary(BaseModel):
    """Per-thread mini-summary output."""
    thread_id: str
    summary: str = Field(max_length=300, description="Brief summary ≤90 tokens")
    pending_actions: List[ThreadAction] = Field(default_factory=list)
    deadlines: List[ThreadDeadline] = Field(default_factory=list)
    who_must_act: List[str] = Field(default_factory=list, description="user/others")
    open_questions: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
```

## 2. Создание промпта thread_summarize

**digest-core/prompts/thread_summarize.v1.j2** (новый файл)

```jinja2
SYSTEM:
Ты — ассистент для краткого суммаризации email-треда. Извлеки действия, дедлайны и ключевые вопросы.

RULES:
- Summary ≤ 90 токенов
- Каждое действие/дедлайн с evidence_id и короткой цитатой (≤150 символов)
- who_must_act: "user" если обращение к пользователю, "sender" если к отправителю, "team" если общее
- Не домысливай, только факты из evidence

INPUT:
Thread ID: {{ thread_id }}
Chunks ({{ chunk_count }}):
{{ chunks }}

OUTPUT (JSON):
{
  "thread_id": "{{ thread_id }}",
  "summary": "Brief summary...",
  "pending_actions": [
    {
      "title": "Action title",
      "evidence_id": "ev_123",
      "quote": "Short quote from evidence",
      "who_must_act": "user"
    }
  ],
  "deadlines": [
    {
      "title": "Deadline title",
      "date_time": "2024-12-15T14:00:00",
      "evidence_id": "ev_456",
      "quote": "Quote about deadline"
    }
  ],
  "who_must_act": ["user"],
  "open_questions": ["Question 1?"],
  "evidence_ids": ["ev_123", "ev_456"]
}
```

## 3. Обновление конфигурации

**digest-core/src/digest_core/config.py**

Добавить HierarchicalConfig:

```python
class HierarchicalConfig(BaseModel):
    """Configuration for hierarchical digest mode."""
    enable: bool = Field(default=True, description="Enable hierarchical mode")
    min_threads: int = Field(default=30, description="Min threads to activate")
    min_emails: int = Field(default=150, description="Min emails to activate")
    
    per_thread_max_chunks_in: int = Field(default=8)
    summary_max_tokens: int = Field(default=90)
    parallel_pool: int = Field(default=8)
    timeout_sec: int = Field(default=20)
    degrade_on_timeout: str = Field(default="best_2_chunks")
    
    final_input_token_cap: int = Field(default=4000)
    max_latency_increase_pct: int = Field(default=50)
    target_latency_increase_pct: int = Field(default=30)
    max_cost_increase_per_email_pct: int = Field(default=40)

class Config(BaseSettings):
    # ... existing fields ...
    hierarchical: HierarchicalConfig = Field(default_factory=HierarchicalConfig)
```

**digest-core/configs/config.example.yaml**

```yaml
hierarchical:
  enable: true
  min_threads: 30
  min_emails: 150
  per_thread_max_chunks_in: 8
  summary_max_tokens: 90
  parallel_pool: 8
  timeout_sec: 20
  final_input_token_cap: 4000
  max_latency_increase_pct: 50
```

## 4. Создание модуля hierarchical processing

**digest-core/src/digest_core/hierarchical/__init__.py** (новый модуль)

```python
from .processor import HierarchicalProcessor
__all__ = ['HierarchicalProcessor']
```

**digest-core/src/digest_core/hierarchical/processor.py** (новый файл)

Основная логика:

```python
class HierarchicalProcessor:
    """Process digest hierarchically: per-thread summaries → final aggregation."""
    
    def __init__(self, config: HierarchicalConfig, llm_gateway: LLMGateway):
        self.config = config
        self.llm_gateway = llm_gateway
        self.metrics = HierarchicalMetrics()
    
    def should_use_hierarchical(self, threads: List, emails: List) -> bool:
        """Determine if hierarchical mode should be used."""
        return (len(threads) >= self.config.min_threads or 
                len(emails) >= self.config.min_emails)
    
    def process_hierarchical(
        self, 
        threads: List[ConversationThread],
        all_chunks: List[EvidenceChunk],
        digest_date: str,
        trace_id: str
    ) -> EnhancedDigest:
        """
        Process threads hierarchically:
        1. Per-thread summarization (parallel)
        2. Final aggregation to EnhancedDigest v2
        """
        logger.info("Starting hierarchical processing",
                   threads=len(threads),
                   hierarchical_mode=True)
        
        # Step 1: Group chunks by thread
        thread_chunks = self._group_chunks_by_thread(threads, all_chunks)
        
        # Step 2: Filter threads for summarization (skip small threads)
        threads_to_summarize = self._filter_threads_for_summarization(thread_chunks)
        
        # Step 3: Parallel per-thread summarization
        thread_summaries = self._summarize_threads_parallel(threads_to_summarize)
        
        # Step 4: Prepare final aggregator input (thread summaries + small thread chunks)
        aggregator_input = self._prepare_aggregator_input(
            thread_summaries, 
            thread_chunks,
            threads_to_summarize
        )
        
        # Step 5: Final aggregation to EnhancedDigest v2
        digest = self._final_aggregation(aggregator_input, digest_date, trace_id)
        
        # Update metrics
        self._update_metrics(thread_summaries, aggregator_input, digest)
        
        return digest
    
    def _filter_threads_for_summarization(self, thread_chunks: Dict) -> Dict:
        """Skip threads with < 3 chunks (dynamic filtering)."""
        filtered = {}
        for thread_id, chunks in thread_chunks.items():
            if len(chunks) >= 3:
                # Take up to per_thread_max_chunks_in
                filtered[thread_id] = chunks[:self.config.per_thread_max_chunks_in]
            # else: skip thread_summarize, chunks go directly to aggregator
        
        logger.info("Filtered threads for summarization",
                   total=len(thread_chunks),
                   to_summarize=len(filtered))
        return filtered
    
    def _summarize_threads_parallel(self, threads_to_summarize: Dict) -> List[ThreadSummary]:
        """Parallel per-thread summarization with timeout and degradation."""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
        
        summaries = []
        
        with ThreadPoolExecutor(max_workers=self.config.parallel_pool) as executor:
            futures = {}
            for thread_id, chunks in threads_to_summarize.items():
                future = executor.submit(
                    self._summarize_single_thread, 
                    thread_id, 
                    chunks
                )
                futures[future] = thread_id
            
            for future in as_completed(futures, timeout=self.config.timeout_sec):
                thread_id = futures[future]
                try:
                    summary = future.result(timeout=self.config.timeout_sec)
                    summaries.append(summary)
                    self.metrics.threads_summarized += 1
                except TimeoutError:
                    logger.warning("Thread summarization timeout, degrading",
                                 thread_id=thread_id)
                    # Degrade: take best 2 chunks
                    degraded = self._degrade_thread_summary(thread_id, chunks[:2])
                    summaries.append(degraded)
                except Exception as e:
                    logger.error("Thread summarization failed",
                               thread_id=thread_id, error=str(e))
        
        return summaries
    
    def _summarize_single_thread(
        self, 
        thread_id: str, 
        chunks: List[EvidenceChunk]
    ) -> ThreadSummary:
        """Summarize single thread using LLM."""
        # Prepare chunks text
        chunks_text = self._prepare_thread_chunks_text(chunks)
        
        # Load prompt
        from pathlib import Path
        from jinja2 import Environment, FileSystemLoader
        
        env = Environment(loader=FileSystemLoader(Path("prompts")))
        template = env.get_template("thread_summarize.v1.j2")
        
        rendered = template.render(
            thread_id=thread_id,
            chunk_count=len(chunks),
            chunks=chunks_text
        )
        
        # Call LLM
        messages = [{"role": "user", "content": rendered}]
        response = self.llm_gateway._make_request_with_retry(messages, thread_id)
        
        # Parse and validate
        parsed = json.loads(response.get("data", "{}"))
        summary = ThreadSummary(**parsed)
        
        # Track tokens
        self.metrics.per_thread_tokens.append(len(chunks_text.split()) * 1.3)
        
        return summary
    
    def _prepare_aggregator_input(
        self,
        thread_summaries: List[ThreadSummary],
        all_thread_chunks: Dict,
        summarized_threads: Dict
    ) -> str:
        """
        Prepare final aggregator input:
        - Thread summaries (for large threads)
        - Direct chunks (for small threads < 3 chunks)
        - Thread headers (From/Subject/Recency)
        """
        parts = []
        
        # Add thread summaries (large threads)
        for summary in thread_summaries:
            parts.append(f"Thread: {summary.thread_id}")
            parts.append(f"Summary: {summary.summary}")
            if summary.pending_actions:
                parts.append(f"Actions: {len(summary.pending_actions)}")
                for action in summary.pending_actions:
                    parts.append(f"  - {action.title} (ev: {action.evidence_id}, quote: {action.quote})")
            if summary.deadlines:
                parts.append(f"Deadlines: {len(summary.deadlines)}")
                for dl in summary.deadlines:
                    parts.append(f"  - {dl.title} at {dl.date_time} (ev: {dl.evidence_id})")
            parts.append("")
        
        # Add direct chunks from small threads
        for thread_id, chunks in all_thread_chunks.items():
            if thread_id not in summarized_threads and len(chunks) < 3:
                parts.append(f"Thread: {thread_id} (direct chunks)")
                for chunk in chunks:
                    parts.append(f"Evidence {chunk.evidence_id}:")
                    parts.append(chunk.content[:200])  # Truncate
                parts.append("")
        
        input_text = "\n".join(parts)
        
        # Apply token cap with shrink logic
        if len(input_text.split()) * 1.3 > self.config.final_input_token_cap:
            input_text = self._shrink_aggregator_input(input_text, thread_summaries)
        
        self.metrics.final_input_tokens = int(len(input_text.split()) * 1.3)
        
        return input_text
    
    def _shrink_aggregator_input(self, input_text: str, summaries: List[ThreadSummary]) -> str:
        """
        Shrink aggregator input to fit token cap.
        Priority: keep threads with AddressedToMe/deadlines, cut others.
        """
        # Implement shrink logic similar to ContextSelector
        # ... (prioritize threads with deadlines, AddressedToMe signals)
        return input_text  # Placeholder
    
    def _final_aggregation(
        self,
        aggregator_input: str,
        digest_date: str,
        trace_id: str
    ) -> EnhancedDigest:
        """Final aggregation to EnhancedDigest v2."""
        # Use existing process_digest with v2 prompt
        # Input is now thread summaries instead of raw chunks
        
        result = self.llm_gateway.process_digest(
            evidence=[],  # Empty, we use custom input
            digest_date=digest_date,
            trace_id=trace_id,
            prompt_version="v2",
            custom_input=aggregator_input  # Pass thread summaries
        )
        
        return result["digest"]
```

## 5. Обновление LLM Gateway

**digest-core/src/digest_core/llm/gateway.py**

Обновить `process_digest()` для поддержки custom_input:

```python
def process_digest(
    self, 
    evidence: List[EvidenceChunk], 
    digest_date: str, 
    trace_id: str, 
    prompt_version: str = "v2",
    custom_input: str = None  # NEW: for hierarchical mode
) -> Dict[str, Any]:
    """Process evidence with enhanced v2 prompt and validation."""
    
    # Use custom_input if provided (hierarchical mode)
    if custom_input:
        evidence_text = custom_input
    else:
        evidence_text = self._prepare_evidence_text(evidence)
    
    # ... rest unchanged ...
```

## 6. Создание метрик

**digest-core/src/digest_core/hierarchical/metrics.py** (новый файл)

```python
class HierarchicalMetrics:
    """Metrics for hierarchical processing."""
    
    def __init__(self):
        self.threads_summarized = 0
        self.threads_skipped_small = 0
        self.per_thread_tokens = []
        self.final_input_tokens = 0
        self.parallel_time_ms = 0
        self.total_time_ms = 0
    
    def to_dict(self) -> Dict:
        return {
            "threads_summarized": self.threads_summarized,
            "threads_skipped_small": self.threads_skipped_small,
            "per_thread_avg_tokens": (
                sum(self.per_thread_tokens) / len(self.per_thread_tokens)
                if self.per_thread_tokens else 0
            ),
            "final_input_tokens": self.final_input_tokens,
            "parallel_time_ms": self.parallel_time_ms,
            "total_time_ms": self.total_time_ms
        }
```

## 7. Интеграция в run.py

**digest-core/src/digest_core/run.py**

Обновить для использования hierarchical режима:

```python
from digest_core.hierarchical import HierarchicalProcessor

def run_digest(config: Config, trace_id: str = None) -> str:
    # ... steps 1-5 unchanged (ingest, normalize, threads, split, select) ...
    
    # NEW: Check if hierarchical mode should be used
    hierarchical = HierarchicalProcessor(config.hierarchical, llm_gateway)
    
    if hierarchical.should_use_hierarchical(threads, messages):
        logger.info("Using hierarchical mode",
                   threads=len(threads),
                   emails=len(messages))
        
        # Step 6: Hierarchical processing
        digest = hierarchical.process_hierarchical(
            threads=threads,
            all_chunks=evidence_chunks,
            digest_date=digest_date,
            trace_id=trace_id
        )
        
        # Log hierarchical metrics
        h_metrics = hierarchical.metrics.to_dict()
        logger.info("Hierarchical processing completed", **h_metrics)
        
    else:
        logger.info("Using flat mode (below thresholds)")
        
        # Step 6: Flat processing (existing v2 flow)
        result = llm_gateway.process_digest(
            selected_evidence, 
            digest_date, 
            trace_id,
            prompt_version="v2"
        )
        digest = result['digest']
    
    # Step 7: Assemble output (unchanged)
    # ...
```

## 8. Тесты

**digest-core/tests/test_hierarchical.py** (новый файл)

```python
class TestHierarchicalMode:
    def test_threshold_activation(self):
        """Test hierarchical mode activates at correct thresholds."""
        
    def test_small_threads_skipped(self):
        """Test threads < 3 chunks skip summarization."""
        
    def test_thread_summary_structure(self):
        """Test ThreadSummary has required fields with evidence_id and quotes."""
        
    def test_parallel_processing(self):
        """Test parallel thread summarization."""
        
    def test_timeout_degradation(self):
        """Test timeout handling with best_2_chunks degradation."""
        
    def test_final_aggregation_to_enhanced_digest_v2(self):
        """Test final output is EnhancedDigest v2."""
        
    def test_300_emails_coverage(self):
        """Test coverage on 300+ emails dataset."""
        # Generate 300 emails with known actions/deadlines
        # Compare hierarchical vs flat coverage
        # Assert: hierarchical coverage >= flat + 10%
```

**digest-core/tests/fixtures/large_dataset.py** (новый файл)

Создать фикстуры для 300+ писем:

```python
def generate_large_email_dataset(count: int = 300) -> List[NormalizedMessage]:
    """Generate synthetic 300+ email dataset with known actions/deadlines."""
    # Mix of:
    # - Large threads (10-20 messages)
    # - Medium threads (5-10 messages)
    # - Small threads (1-3 messages)
    # - Known action signals
    # - Known deadlines
```

## Acceptance Criteria Validation

Добавить validation tests:

```python
def test_coverage_action_threads_gte_95_percent():
    """Validate: coverage of threads with action-signals >= 95%."""
    
def test_all_items_have_evidence_id_and_quote():
    """Validate: every action/deadline has valid evidence_id + quote."""
    
def test_actor_detection_error_rate_lte_5_percent():
    """Validate: actor errors <= 5% on gold dataset."""
    
def test_date_normalization_accuracy_gte_99_percent():
    """Validate: date normalization correct in >= 99% cases."""
```

## Implementation Order

1. Create schemas (ThreadSummary, ThreadAction, ThreadDeadline)
2. Create thread_summarize.v1.j2 prompt
3. Update config with HierarchicalConfig
4. Create hierarchical/processor.py module
5. Update llm/gateway.py for custom_input support
6. Create hierarchical/metrics.py
7. Update run.py integration
8. Create test fixtures (300+ emails)
9. Create test_hierarchical.py
10. Run tests and validate acceptance criteria


### To-dos

- [ ] Создать ThreadSummary, ThreadAction, ThreadDeadline в schemas.py
- [ ] Создать prompts/thread_summarize.v1.j2 (per-thread mini-summary prompt)
- [ ] Добавить HierarchicalConfig в config.py и config.example.yaml
- [ ] Создать hierarchical/processor.py с HierarchicalProcessor классом
- [ ] Реализовать _summarize_threads_parallel с timeout и degradation
- [ ] Реализовать _prepare_aggregator_input с shrink-логикой
- [ ] Обновить llm/gateway.py::process_digest для поддержки custom_input
- [ ] Создать hierarchical/metrics.py с HierarchicalMetrics
- [ ] Интегрировать hierarchical режим в run.py с проверкой порогов
- [ ] Создать fixtures/large_dataset.py с генератором 300+ писем
- [ ] Создать test_hierarchical.py с тестами на пороги, параллелизм, coverage
- [ ] Добавить тесты валидации acceptance criteria (coverage ≥95%, actor errors ≤5%, dates ≥99%)