# Hierarchical Orchestration Implementation Summary

## Обзор

Реализована система **автоматического иерархического масштабирования** с гарантированным включением обязательных чанков и merge-политикой с citations.

**Ключевые возможности:**
- ✅ Авто-активация: `threads>=60` OR `emails>=300`
- ✅ Must-include: mentions + last_update (до 12 чанков в исключениях)
- ✅ Merge policy: заголовок + 3-5 ключевых цитат
- ✅ Skip LLM если нет evidence (экономия токенов)
- ✅ 4 новых Prometheus метрики

---

## Реализованные компоненты

### 1. Auto-Enable Logic

**HierarchicalConfig** (`digest-core/src/digest_core/config.py`):
```python
class HierarchicalConfig(BaseModel):
    enable: bool = True
    auto_enable: bool = True  # NEW
    min_threads: int = 60     # NEW: was 30
    min_emails: int = 300     # NEW: was 150
    
    per_thread_max_chunks_in: int = 8
    per_thread_max_chunks_exception: int = 12  # NEW
    
    # Must-include chunks (NEW)
    must_include_mentions: bool = True
    must_include_last_update: bool = True
    
    # Merge policy (NEW)
    merge_max_citations: int = 5
    merge_include_title: bool = True
    
    # Optimization (NEW)
    skip_llm_if_no_evidence: bool = True
```

**Trigger Reasons:**
- `auto_threads`: threads >= 60
- `auto_emails`: emails >= 300
- `manual`: вручную enable=true

---

### 2. Must-Include Chunks

**HierarchicalProcessor** (`digest-core/src/digest_core/hierarchical/processor.py`):

```python
def _select_chunks_with_must_include(
    self,
    chunks: List[EvidenceChunk],
    user_aliases: List[str],
    max_chunks: int = 8
) -> List[EvidenceChunk]:
    """
    Select chunks ensuring must-include chunks are present.
    
    Must-include chunks:
    1. Chunks with user mentions (by user_aliases)
    2. Last update chunk (most recent by timestamp)
    
    Exception handling:
    - If must_include_count > max_chunks (8):
      → Extend to per_thread_max_chunks_exception (12)
    
    Returns:
        Selected chunks = must_include + top regular (up to 8 or 12)
    """
```

**Логика:**
1. Найти chunks с упоминаниями user_aliases
2. Найти last update chunk (max по timestamp)
3. Если must_include > 8 → расширить до 12 (exception limit)
4. Выбрать top regular chunks для заполнения оставшихся слотов
5. Вернуть: must_include + regular

**Metrics:**
```python
must_include_chunks_total{chunk_type="mentions"}
must_include_chunks_total{chunk_type="last_update"}
```

---

### 3. Skip LLM Optimization

**В `_summarize_single_thread()`:**
```python
selected_chunks = self._select_chunks_with_must_include(...)

# Skip LLM if no evidence after selection
if not selected_chunks and self.config.skip_llm_if_no_evidence:
    logger.info("Skipping LLM for thread (no evidence)")
    return ThreadSummary(
        thread_id=thread_id,
        key_points=[],
        actions=[],
        deadlines=[]
    )
```

**Сценарии:**
- Тред содержал только спам/подписи
- Все чанки отфильтрованы selection политикой
- Тред вне time window

**Metrics:**
```python
saved_tokens_total{skip_reason="no_evidence"}
saved_tokens_total{skip_reason="empty_selection"}
```

---

### 4. Merge Policy with Citations

**В `_prepare_aggregator_input()`:**
```python
def _extract_key_citations_from_chunks(
    self,
    chunks: List[EvidenceChunk],
    max_citations: int = 5
) -> List[str]:
    """Extract 3-5 key citations from thread chunks."""
    top_chunks = chunks[:max_citations]
    citations = []
    for chunk in top_chunks:
        snippet = chunk.text[:150].strip()
        if len(chunk.text) > 150:
            snippet += "..."
        citation = f"[{chunk.evidence_id}] {snippet}"
        citations.append(citation)
    return citations
```

**Формат aggregator input:**
```
=== Thread: thread123 ===
Summary: Brief thread summary title

Key Citations (5):
  [ev1] Please review the updated proposal by Friday...
  [ev3] User john@example.com mentioned critical deadline...
  [ev5] Decision was made to proceed with option B...
  ...

Summary (full): Detailed thread summary...
```

---

### 5. Prometheus Metrics

**MetricsCollector** (`digest-core/src/digest_core/observability/metrics.py`):

```python
# Counter: hierarchical runs by trigger reason
self.hierarchical_runs_total = Counter(
    'hierarchical_runs_total',
    'Total hierarchical digest runs',
    ['trigger_reason']  # auto_threads, auto_emails, manual
)

# Gauge: average chunks per subsummary
self.avg_subsummary_chunks = Gauge(
    'avg_subsummary_chunks',
    'Average number of chunks per thread subsummary'
)

# Counter: saved tokens by optimization
self.saved_tokens_total = Counter(
    'saved_tokens_total',
    'Total tokens saved by skipping LLM calls',
    ['skip_reason']  # no_evidence, empty_selection
)

# Counter: must-include chunks added
self.must_include_chunks_total = Counter(
    'must_include_chunks_total',
    'Total must-include chunks added',
    ['chunk_type']  # mentions, last_update
)
```

**Методы:**
- `record_hierarchical_run(trigger_reason)`
- `update_avg_subsummary_chunks(avg_chunks)`
- `record_saved_tokens(count, skip_reason)`
- `record_must_include_chunk(chunk_type, count)`

---

### 6. Pipeline Integration

**run.py** (`digest-core/src/digest_core/run.py`):

```python
if use_hierarchical:
    # Determine trigger reason for metrics
    trigger_reason = "manual"
    if config.hierarchical.auto_enable:
        if len(threads) >= config.hierarchical.min_threads:
            trigger_reason = "auto_threads"
        elif len(messages) >= config.hierarchical.min_emails:
            trigger_reason = "auto_emails"
    
    metrics.record_hierarchical_run(trigger_reason)
    
    # Pass user_aliases to processor
    digest = hierarchical_processor.process_hierarchical(
        threads=threads,
        all_chunks=evidence_chunks,
        digest_date=digest_date,
        trace_id=trace_id,
        user_aliases=config.ews.user_aliases  # NEW
    )
    
    # Calculate and record avg subsummary chunks
    if h_metrics.get('threads_summarized', 0) > 0:
        avg_chunks = sum(hierarchical_processor.metrics.per_thread_tokens) / h_metrics['threads_summarized']
        avg_chunks_estimate = avg_chunks / 300  # Tokens to chunks estimate
        metrics.update_avg_subsummary_chunks(avg_chunks_estimate)
```

**Обновления:**
- Передача `user_aliases` в `process_hierarchical()`
- Определение `trigger_reason` для метрик
- Запись метрик: hierarchical_runs_total, avg_subsummary_chunks

---

### 7. Tests

**test_hierarchical_orchestration.py** (`digest-core/tests/test_hierarchical_orchestration.py`):

**Test Classes (6):**
1. **TestAutoEnableThresholds** - Проверка auto-enable логики
   - test_auto_enable_by_threads (≥60)
   - test_auto_enable_by_emails (≥300)
   - test_no_auto_enable_below_thresholds
   - test_disabled_hierarchical

2. **TestMustIncludeChunks** - Гарантия must-include
   - test_must_include_mentions
   - test_must_include_last_update
   - test_exception_limit_with_many_must_include (12 chunks)

3. **TestSkipLLM** - Пропуск LLM оптимизация
   - test_skip_llm_no_evidence
   - test_no_skip_when_disabled

4. **TestMergePolicy** - Merge policy с citations
   - test_extract_key_citations (3-5)
   - test_merge_policy_in_aggregator

5. **TestMailExplosion** - Синтетический mail explosion
   - test_mail_explosion_performance (100 threads, 500 emails)

6. **TestF1Preservation** - F1 для actions/mentions
   - test_actions_not_lost
   - test_mentions_not_lost

**Acceptance Criteria:**
- ✅ Auto-enable: threads>=60 OR emails>=300
- ✅ Must-include: mentions + last_update всегда включены
- ✅ Exception limit: 12 chunks при переполнении
- ✅ Skip LLM: пропуск при отсутствии evidence
- ✅ Merge policy: 3-5 citations
- ✅ Mail explosion: latency < 1s для группировки 100 threads
- ✅ F1: actions/mentions не теряются

---

### 8. Configuration

**config.example.yaml** (`digest-core/configs/config.example.yaml`):

```yaml
hierarchical:
  enable: true
  auto_enable: true         # NEW: Auto-enable based on thresholds
  min_threads: 60           # NEW: Increased from 30
  min_emails: 300           # NEW: Increased from 150
  
  per_thread_max_chunks_in: 8
  per_thread_max_chunks_exception: 12  # NEW: Exception limit
  
  # Must-include chunks (NEW)
  must_include_mentions: true
  must_include_last_update: true
  
  # Merge policy (NEW)
  merge_max_citations: 5
  merge_include_title: true
  
  # Optimization (NEW)
  skip_llm_if_no_evidence: true
  
  # Existing params
  summary_max_tokens: 90
  parallel_pool: 8
  timeout_sec: 20
  degrade_on_timeout: "best_2_chunks"
  final_input_token_cap: 4000
```

---

### 9. Documentation

**HIERARCHICAL_ORCHESTRATION.md** (`docs/development/HIERARCHICAL_ORCHESTRATION.md`):

**Разделы:**
1. Обзор и архитектура
2. Auto-Enable Logic (thresholds, trigger reasons)
3. Must-Include Chunks (mentions + last_update, exception limit)
4. Merge Policy (title + 3-5 citations)
5. Skip LLM Optimization (token savings)
6. Конфигурация (примеры: standard, aggressive, high-quality)
7. Prometheus Metrics + Grafana queries
8. Тестирование и acceptance criteria
9. Pipeline Flow (шаг за шагом)
10. Примеры использования (CLI, logs)
11. Troubleshooting (4 common issues)
12. Roadmap (v1.0, v1.1, v2.0)

---

## Acceptance Criteria (DoD)

### Code ✅
- ✅ HierarchicalConfig: 9 новых параметров
- ✅ HierarchicalProcessor: _select_chunks_with_must_include, _extract_key_citations
- ✅ MetricsCollector: 4 новых метрики
- ✅ run.py: trigger_reason, user_aliases passing, avg_chunks calculation

### Tests ✅
- ✅ 6 test classes, 15+ test methods
- ✅ Auto-enable: threads>=60 OR emails>=300
- ✅ Must-include: mentions + last_update + exception (12)
- ✅ Skip LLM: no evidence optimization
- ✅ Merge policy: 3-5 citations
- ✅ Mail explosion: 100 threads, 500 emails
- ✅ F1: actions/mentions preserved

### Metrics ✅
- ✅ hierarchical_runs_total{trigger_reason}
- ✅ avg_subsummary_chunks
- ✅ saved_tokens_total{skip_reason}
- ✅ must_include_chunks_total{chunk_type}
- ✅ Recording methods: 4 new methods

### Config & Docs ✅
- ✅ config.example.yaml: hierarchical section updated
- ✅ HIERARCHICAL_ORCHESTRATION.md: comprehensive guide
- ✅ Примеры: standard, aggressive, high-quality
- ✅ Prometheus queries + Grafana dashboard
- ✅ Troubleshooting guide (4 issues)

### Deployment ✅
- ✅ Backward compatible (existing configs work)
- ✅ No breaking changes
- ✅ Линтер: 0 ошибок

---

## Pipeline Flow (Updated)

```
1. Ingest (EWS) → Messages
2. Normalize (HTML→text, cleaning)
3. Thread Building → Threads
4. Evidence Chunking → Chunks

5. 🔥 AUTO-ENABLE CHECK (NEW - Step 5)
   ├─ IF threads >= 60 → trigger_reason="auto_threads"
   ├─ IF emails >= 300 → trigger_reason="auto_emails"
   ├─ ELSE IF enable=true → trigger_reason="manual"
   └─ Record: hierarchical_runs_total{trigger_reason}

6. IF hierarchical_mode:
   ├─ Group chunks by thread
   │
   ├─ For each thread:
   │  ├─ 🔥 SELECT WITH MUST-INCLUDE (NEW)
   │  │  ├─ Find mention chunks (by user_aliases)
   │  │  ├─ Find last_update chunk (max timestamp)
   │  │  ├─ IF must_include > 8 → extend to 12 (exception)
   │  │  ├─ Select top regular chunks (fill remaining slots)
   │  │  └─ Record: must_include_chunks_total{chunk_type}
   │  │
   │  ├─ 🔥 SKIP LLM IF NO EVIDENCE (NEW)
   │  │  ├─ IF selected_chunks == [] → return empty ThreadSummary
   │  │  └─ Record: saved_tokens_total{skip_reason}
   │  │
   │  └─ LLM per-thread summarization
   │
   ├─ 🔥 MERGE POLICY (NEW)
   │  ├─ Extract 3-5 key citations per thread
   │  ├─ Format: [evidence_id] snippet...
   │  └─ Add to aggregator input:
   │     "=== Thread: X ===
   │      Summary: ...
   │      Key Citations (5):
   │        [ev1] ...
   │        [ev2] ..."
   │
   ├─ Final aggregation → EnhancedDigest v2
   │
   └─ 🔥 CALCULATE AVG SUBSUMMARY CHUNKS (NEW)
      └─ Record: avg_subsummary_chunks

7. Context Selection
8. Action Extraction
9. Ranking
10. JSON/Markdown Assembly
```

---

## Key Metrics

### Expected Results

| Metric | Value | Target |
|--------|-------|--------|
| `hierarchical_runs_total` | Varies | Track trends |
| `avg_subsummary_chunks` | 6-8 | 6-8 optimal |
| `saved_tokens_total` | 10K-50K/day | Maximize savings |
| `must_include_chunks_total` | 50-100/run | Ensure coverage |

### Prometheus Queries

**1. Hierarchical activation rate:**
```promql
rate(hierarchical_runs_total[1h])
```

**2. Trigger reason distribution:**
```promql
sum(hierarchical_runs_total) by (trigger_reason)
```

**3. Token savings:**
```promql
sum(rate(saved_tokens_total[5m])) by (skip_reason)
```

**4. Must-include usage:**
```promql
sum(rate(must_include_chunks_total[5m])) by (chunk_type)
```

**5. Avg subsummary chunks:**
```promql
avg_subsummary_chunks
```

---

## Сравнение: До vs После

### До (v0.9):
- Manual hierarchical activation
- Fixed chunk selection (top 8 by priority)
- No must-include guarantees
- No token optimization
- Minimal metrics

### После (v1.0):
- ✅ Auto-activation: threads>=60 OR emails>=300
- ✅ Smart chunk selection: must-include + regular
- ✅ Exception limit: 12 chunks для critical cases
- ✅ Merge policy: title + 3-5 citations
- ✅ Skip LLM optimization: saved_tokens
- ✅ 4 новых метрики: runs, avg_chunks, saved_tokens, must_include

**Преимущества:**
1. **Automatic scaling:** Не нужно вручную настраивать
2. **Guarantee critical info:** Mentions + last_update всегда включены
3. **Better traceability:** Merge policy с citations
4. **Cost optimization:** Skip LLM при отсутствии evidence
5. **Better observability:** 4 новых метрики

---

## Files Created/Modified

### Created:
1. `digest-core/tests/test_hierarchical_orchestration.py` (450+ lines)
2. `docs/development/HIERARCHICAL_ORCHESTRATION.md` (comprehensive guide)
3. `HIERARCHICAL_ORCHESTRATION_SUMMARY.md` (this file)

### Modified:
1. **digest-core/src/digest_core/config.py:**
   - Added 9 new HierarchicalConfig parameters
   - auto_enable, min_threads (60), min_emails (300)
   - per_thread_max_chunks_exception (12)
   - must_include_mentions, must_include_last_update
   - merge_max_citations, merge_include_title
   - skip_llm_if_no_evidence

2. **digest-core/src/digest_core/observability/metrics.py:**
   - Added 4 new metrics:
     * hierarchical_runs_total{trigger_reason}
     * avg_subsummary_chunks
     * saved_tokens_total{skip_reason}
     * must_include_chunks_total{chunk_type}
   - Added 4 recording methods

3. **digest-core/src/digest_core/hierarchical/processor.py:**
   - Added `_select_chunks_with_must_include()` method
   - Added `_extract_key_citations_from_chunks()` method
   - Updated `_summarize_single_thread()` signature (user_aliases)
   - Updated `_summarize_threads_parallel()` signature
   - Updated `process_hierarchical()` signature
   - Added skip LLM logic
   - Updated `_prepare_aggregator_input()` with merge policy

4. **digest-core/src/digest_core/run.py:**
   - Added trigger_reason detection
   - Added hierarchical_runs_total recording
   - Added user_aliases passing to process_hierarchical
   - Added avg_subsummary_chunks calculation

5. **digest-core/configs/config.example.yaml:**
   - Updated hierarchical section with all new params

---

## Commit Message

```
feat(hier): auto hierarchical mode with sub-summaries + must-include chunks + metrics + tests

Implementation:
- Auto-enable: threads>=60 OR emails>=300 (configurable thresholds)
- Trigger reasons tracked: auto_threads, auto_emails, manual
- Must-include chunks guaranteed:
  * User mentions (detected by user_aliases)
  * Last update chunk (most recent by timestamp)
  * Exception limit: 12 chunks (vs normal 8) when must_include overflows
- Merge policy: thread summary title + 3-5 key citations (extractive)
- Skip LLM optimization: if no evidence after selection → saved_tokens
- user_aliases passed through entire pipeline to hierarchical processor

Metrics (4 new):
- hierarchical_runs_total{trigger_reason}: tracks auto_threads, auto_emails, manual
- avg_subsummary_chunks: average chunks per thread subsummary
- saved_tokens_total{skip_reason}: tracks no_evidence, empty_selection savings
- must_include_chunks_total{chunk_type}: tracks mentions, last_update additions

Tests (comprehensive):
- TestAutoEnableThresholds: 60/300 thresholds, auto/manual modes
- TestMustIncludeChunks: mentions detection, last_update, exception limit (12)
- TestSkipLLM: empty evidence optimization
- TestMergePolicy: 3-5 citations extraction and formatting
- TestMailExplosion: 100 threads, 500 emails, latency validation
- TestF1Preservation: actions/mentions not lost with must-include logic

Configuration (backward compatible):
- hierarchical.auto_enable: true (NEW)
- hierarchical.min_threads: 60 (was 30)
- hierarchical.min_emails: 300 (was 150)
- hierarchical.per_thread_max_chunks_exception: 12 (NEW)
- hierarchical.must_include_mentions: true (NEW)
- hierarchical.must_include_last_update: true (NEW)
- hierarchical.merge_max_citations: 5 (NEW)
- hierarchical.merge_include_title: true (NEW)
- hierarchical.skip_llm_if_no_evidence: true (NEW)

Documentation:
- docs/HIERARCHICAL_ORCHESTRATION.md: architecture, config examples, 
  Prometheus queries, Grafana dashboard, troubleshooting guide
- config.example.yaml: updated with all new hierarchical params

Acceptance:
✅ Auto-enable triggered at 60 threads OR 300 emails
✅ Must-include chunks guaranteed (mentions + last_update)
✅ Exception limit (12) applied when must_include > 8
✅ Merge policy adds 3-5 citations to aggregator input
✅ Skip LLM saves tokens when no evidence
✅ F1 for actions/mentions preserved (not lost)
✅ Mail explosion test passes (100 threads, 500 emails, latency < 1s)
✅ 4 new metrics exported to Prometheus
✅ 0 linter errors
```

---

## Next Steps (Optional)

### v1.1 (Future Enhancements)
1. **Adaptive Thresholds:**
   - Auto-tune min_threads/min_emails based on system load
   - Machine learning для оптимизации порогов

2. **Enhanced Must-Include:**
   - Add "high_priority_senders" chunks
   - Deadline chunks с urgency > threshold

3. **Semantic Clustering:**
   - Улучшенный merge policy с semantic similarity
   - Citation diversity (избежать похожих citations)

4. **Cost Tracking:**
   - Detailed cost_saved_total metric
   - Cost per email comparison

---

## Summary

✅ **Все задачи выполнены:**
1. ✅ Auto-enable: threads>=60 OR emails>=300
2. ✅ Must-include: mentions + last_update (до 12 чанков)
3. ✅ Merge policy: title + 3-5 citations
4. ✅ Skip LLM: экономия токенов
5. ✅ 4 новых метрики
6. ✅ Comprehensive tests (6 test classes, 15+ methods)
7. ✅ Документация (HIERARCHICAL_ORCHESTRATION.md)
8. ✅ Config обновлён

**Результат:** Иерархический режим автоматически активируется при больших объёмах, гарантирует включение критических чанков, применяет merge-политику с citations и оптимизирует затраты на LLM. Система готова к production deployment.

