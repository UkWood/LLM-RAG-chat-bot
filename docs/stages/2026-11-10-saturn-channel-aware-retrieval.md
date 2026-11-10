# Этап 4B — Saturn Channel-Aware Retrieval v0.1

Дата: 2026-11-10  
Проект: AI Technical Consultant — МНПП «Сатурн»  
Репозиторий: `UkWood/LLM-RAG-chat-bot`  
Baseline `main`: `2da357db4543c9ca173db7663bbd18396d221cc3` (PR #25 merged)  
Ветка: `feat/saturn-channel-aware-retrieval-v0.1`  
PR: [#26](https://github.com/UkWood/LLM-RAG-chat-bot/pull/26)  
Статус: Consolidated Acceptance Review Corrections — implementation updated, exact-head CI required; **NO MERGE**.

## Final Acceptance Correction — CR-03: adjacent decimal engineering units

**Starting review head:** `d182b369fd1e1e6c5735491b772459ff09ffd225`.  
**Scope:** только Saturn tokenizer, targeted regression tests и этот отчёт; принятые CR-01 immutable publication и CR-02 prepared BM25, `saturn_qdrant.py`, ADR, canonical contracts, ingestion adapters и legacy retrieval не изменялись. Тот же [PR #26](https://github.com/UkWood/LLM-RAG-chat-bot/pull/26), без merge и без этапа 5.

- **Tokenizer identity:** `saturn-technical-tokenizer/0.2.1` (вместо `0.2.0`). Значение включено в `SaturnIndexManifest.tokenizer_version`, `lexical_config_hash` и deterministic `bundle_id`; corpus indexes должны быть пересобраны для нового tokenizer. Поисковый source text, `REPRESENTATION_VERSION` и encoder/Qdrant vector representation не менялись.
- **Правило:** только явно перечисленные, непосредственно примыкающие буквенные единицы измерения разбиваются лексически на два searchable tokens — *literal signed numeric value* и *unit token*. Например, `0,5МПа` → (`0,5`, `мпа`), `12.5V` → (`12.5`, `v`), `-0,5бар` → (`-0,5`, `бар`), `10.5кВт` → (`10.5`, `квт`), `-20.5°C` → (`-20.5`, `°c`). Разделённое `0,5 МПа` получает те же tokens. Оригинальный `SearchRecord.text`, evidence ID и provenance остаются без изменений; единица не отбрасывается.
- **Ограниченный literal unit vocabulary:** `мпа`, `кпа`, `па`, `бар`, `квт`, `вт`, `гц`, `кгц`, `мгц`, `в`, `а`, `mpa`, `kpa`, `bar`, `kw`, `w`, `hz`, `kv`, `mv`, `ma`, `v`, `a`, `°c`, `°f` (с Unicode `casefold`). Неизвестный suffix не интерпретируется как физическая единица. **Нет** пересчёта единиц, semantic equivalence, распознавания физических величин либо новых инженерных facts.
- **Безопасность идентификаторов:** `RS-485`, `БКД-ПК-РФ.2`, `БКД-ПК-RF.2` остаются цельными, разными searchable identifiers. `12.5V-CONTROL`, `12.5V2`, `0,5unknown` и `АБ-12.5V` не разбиваются на предполагаемые numeric facts. Значения `-20`, `+20`, `20` сохраняют различие; `−20` (U+2212) нормализуется в `-20` только лексически, без изменения source. Decimal comma/dot и literal ranges не преобразуются.
- **Tests:** четыре targeted CR-03 метода добавлены в `backend/tests/unit/test_saturn_channel_retrieval.py`: separated/attached units и signed Unicode forms; отрицательные opaque-device cases; `SaturnBM25Index.search` по literal numeric query, включая `0,5`, `12.5`, `-0,5`, `10.5`, `-20.5`, source IDs, deterministic ranking и parity с reference `_bm25`; versioned manifest и повторная сборка. Все прежние 398 backend тестов остаются в полном suite; итоговые counts и оба CI jobs на **final exact PR head** фиксируются в PR после GitHub Actions, без новых SHA-only commits.
- **Ограничение:** bounded allowlist позволяет распознавать перечисленные единицы, не любые возможные сокращения или Unicode-символы; это сознательно консервативный lexical baseline.

## Consolidated Acceptance Review Corrections — PR #26 (CR-01–CR-03)

**Source review head:** `2ef92e3e69acbd9999ad3bb15b43e610e95e7106`.  
**Статус:** три замечания исправлены в исходной ветке `feat/saturn-channel-aware-retrieval-v0.1`, без нового PR и без изменения архитектуры или source trust. Финальный точный SHA и оба Actions jobs подтверждать в самом [PR #26](https://github.com/UkWood/LLM-RAG-chat-bot/pull/26); не обновлять этот документ ради очередного документационного SHA.

### CR-01 — BLOCKER: immutable published retrieval bundle

- `SaturnRetrievalBundle` — frozen dataclass: snapshot, records, document metadata, lexical/metadata/dense bindings, manifest и mapping словарных aliases не подменяются обычным присваиванием. Изменяемый alias-dict изолирован через `MappingProxyType`. `SaturnBM25Index` и `SaturnMetadataIndex` содержат исключительно immutable tuples и заблокированные field assignments. `SaturnQdrantIndex` после конструктора запрещает обычное изменение индекса, канонических payloads, vectors, point IDs и backend binding; payload tuples являются неизменяемыми.
- `SaturnRetrievalService` запрещает переназначение `_active`, публикационного `_lock` и `policy_provider` через обычное присваивание. Изменение authoritative active bundle происходит только внутри `publish()` под единым `RLock`, после прежних строгих проверок 4A и полной сверки индексов/manifest.
- Жизненный цикл local Qdrant учитывает отдельный active retain и каждый in-flight search retain, получаемый **до** возможного swap. После публикации новой ревизии старый Qdrant получает deferred `close()`, но закрывается только после последнего reader release. Даже внешний вызов `dense.close()` для ещё активного index не обрывает текущий запрос. Ошибки cleanup после успешного pointer swap являются post-publication cleanup diagnostics, а не ошибкой публикации.
- Корректный старый active сохраняется при failed candidate validation/publish. Ни snapshot, ни index bindings не заменяются частями: один capture — одна согласованная ревизия. Не создаётся второй authoritative pointer.
- **Граница гарантии:** in-process immutability против обычного Python assignment; не sandbox для произвольного вредоносного кода в том же процессе с `object.__setattr__` или прямым доступом к private QdrantClient. Такие подмены до публикации по-прежнему обнаруживает структурный `validate()`.

### CR-02 — IMPORTANT: prepared BM25 reuse

- `SaturnBM25Index` и отдельный `SaturnMetadataIndex` индексируют `tokens`, `_prepared` term-frequency maps и длины документов **один раз**, до публикации. `search()` использует эти prepared artifacts, а не повторно вызывает `tokenize(record.text)` для каждого запроса.
- При каждом policy-filtered запросе DF/N/average length пересчитываются **только по eligible records**. Таким образом математическая формула `BM25(k1=1.2,b=0.75)`, динамические блокировки, сортировка `(-score, canonical_id)`, отдельность answer evidence / metadata и bounded `top_k` сохранены.
- Source-derived canonical evidence IDs, dictionary aliases и RRF `k=60` не изменены. Без новой зависимости; legacy synthetic `retrieval/lexical.py` не менялся. Формула сравнена с независимой reference implementation исходного BM25.
- Валидация prepared tokens/coverage выполняется до publication; immutable index не нуждается в затратной полной повторной tokenization при каждом search.

### CR-03 — IMPORTANT: sign-preserving engineering tokenization

- `TOKENIZER_VERSION = saturn-technical-tokenizer/0.2.0`, `REPRESENTATION_VERSION = saturn-evidence-representation/0.1.1`. Обе версии входят в index identity; изменение tokenizer влияет на `lexical_config_hash` и `bundle_id`, representation — на dense content identity.
- Знаки `-20` и `+20` сохраняются и не совпадают с `20`. Математический Unicode minus `−20` (U+2212) **только внутри распознанного числового токена** нормализуется в ASCII `-20`. Не происходит числового преобразования знаков/значений.
- `0,5` и `0.5` — цельные, но **лексически разные** числовые токены. Диапазоны `-20..+20`, `10-20`, `5–7` сохраняются как цельные literal tokens, без интерпретации границ или units. Инженерные identifiers `RS-485`, `БКД-ПК-РФ.2`, `БКД-ПК-RF.2` остаются цельными, с различением кириллицы и латиницы.
- Правило одинаково для индексируемых evidence, metadata, словарных aliases и пользовательских запросов.

### Targeted regression and acceptance evidence

`backend/tests/unit/test_saturn_channel_retrieval.py` дополнен adversarial методами на frozen field/index/service rebinding, согласованную внешнюю подмену компонентов, закрытие active Qdrant, старый in-flight reader после swap, конкурентные корректные publications, сохранение previous active при failed publish, отсутствие повторной tokenization/файлового I/O, независимую BM25 parity с policy-filtered DF, равные scores/tie-break, empty/no matches, изменение корпуса, forged prepared tokens, sign/decimal/range tokens, numeric ranking и versioned manifest.

- Baseline до исправлений: **387 backend tests OK (11 optional skips), 5 project checks PASS**.
- После добавления CR regression suite — **398 backend tests** в полном GitHub offline job (11 existing optional skips). Все final outcomes, а также `offline-checks` и `onnx-contracts` на окончательном head см. [PR #26 / Checks](https://github.com/UkWood/LLM-RAG-chat-bot/pull/26/checks); до их завершения статус PASS не объявляется.
- Команда CI: `python scripts/verify_offline.py`. Legacy synthetic retrieval/evaluation и source-derived Saturn fixture продолжили запускаться в том же полном suite, без изменения frozen datasets. Semantic relevance реального Saturn corpus и производственная embedding-модель не подтверждены.

### Остаточные границы

Процессная (не межпроцессная и не персистентная) атомарность, trusted in-process encoder, отсутствие production dense model/evaluation, Qdrant server, generation/citations/UI, прежний config provenance limitation 4A и PDF OS sandbox остаются без изменений. `UkWood/Saturn-Main-Site` — строго READ-ONLY. PR остаётся **OPEN / NOT MERGED** до повторного независимого Acceptance Review. Этап 5 не начат.

## 1. Что реализовано

Saturn-specific retrieval API:
- `build_saturn_retrieval_bundle(snapshot, *, encoder=None, qdrant_path=None)`;
- `SaturnRetrievalService.publish(bundle) / capture() / search_saturn(query, mode="lexical", top_k=5)`;
- `search_saturn(service, query, *, mode="lexical", top_k=5)`;
- `SaturnPolicyProvider.activate(policy) / capture()`.

Модули: `backend/src/saturn_ai/retrieval/saturn_channel.py`, `saturn_qdrant.py`. Оригинальные `lexical.py`, `dense.py`, `service.py`, legacy `Registry`, synthetic evaluation data и все адаптеры/ADR не изменялись.

Каждый bundle включает **один validated `SaturnKnowledgeSnapshot`** и все соответствующие индексы. До build и publish вызывается `SaturnSnapshotManager.activate` на *временном* manager: это структурная повторная сборка из исходных immutable validation sources, а не проверка одного seal/hash. Runtime-сервис хранит **одну authoritative active-ссылку** на полный bundle. Отсутствуют независимые active snapshot/lexical/Qdrant pointers.

### Answer Evidence

- SearchRecord содержит canonical `EvidenceUnit.evidence_id`, type, exact snapshot ID, source revision ID, entity ID, source locator, canonical URL, hash поисковой representation.
- Для PDF сохраняются оригинальный URL, revision ID, bytes SHA-256, parser version и физическая страница. Metadata-only PDF не создаёт evidence.
- Index representation составляется только из оригинального `EvidenceUnit.text` и source-backed titles связанных `SiteEntity` (relation добавляет только title подтверждённого object). Новых технических facts/relations не выводится.
- Покрытие `answer_evidence` и `evidence_pointers` проверяется точно. Draft records отсутствуют в строго принятом snapshot. Unknown fields продолжают индексироваться как `site_field`.

### Technical lexical baseline

- BM25: `k1=1.2`, `b=0.75`, `candidate_limit=40`, deterministic `(-score, evidence_id)`.
- Tokenizer casefold + сохранение дефисов, точек, слэшей в технических термах; `БКД-ПК-РФ.2` и `БКД-ПК-RF.2` не смешиваются.
- Только **явные** пары `code` / `aliases` в проверенных YAML dictionaries используются для bounded query expansion: максимум 256 пар, 8 aliases на entry и максимум 32 расширения запроса. Произвольные `label`, `value`, dictionary metadata не объявляются инженерными синонимами. Ни один словарь сам не становится доказательством технического свойства.
- Полностью локальный BM25, без encoder, GPU, cloud и сети.

### Optional Qdrant Dense

- Qdrant local memory; опционально local path + проверяемое открытие существующей collection (без server/remote endpoint).
- Явно переданный Encoder с canonical identity; проверяются dimensions, batch cardinality, конечность/ненулевой norm, identity/hash, snapshot/evidence IDs и содержимое всех фактически stored points через scroll (включая payload и vector).
- Batches ≤16, dimensions ≤8192, ограничено суммарное число vector scalars. Query filter ограничен eligible IDs, exact snapshot ID, encoder ID. Qdrant выполняет локальный filtered lookup по подтверждённым IDs; возвращаемый cosine score детерминированно вычисляется из validated normalized vectors; tie-break по score и canonical evidence ID.
- В CI используются deterministic controlled vectors, не языковая модель. Production embedding model **не выбран**.
- `dense` и `hybrid` без готового dense index → явная ошибка, никакого hidden lexical fallback.

### RRF / Document Metadata Search

- RRF `k=60`, fusion исключительно по canonical evidence ID. Raw lexical/dense ranks, scores и provenance валидируются перед слиянием. Результаты сохраняют независимые traces.
- Document Metadata Search — самостоятельный BM25 по title, kind, version/date, canonical URL, owner title/slug (всё из verified snapshot). Один результат на canonical SupportDocument ID с оригинальным DocumentMatch: owners, source locators, extraction status и PDF revision. Document scores не участвуют в evidence RRF.
- Query coordinator проверяет тип/length/top_k/mode, сохраняет исходный запрос и возвращает `SaturnRetrievalResult` со snapshot ID, bundle ID, двумя каналами, traces и manifest. Нет LLM planner, generation, citations, URL fetch.

## 2. Manifest, readiness и атомарность

`SaturnIndexManifest`: exact snapshot ID, corpus hash, representation/tokenizer versions, BM25 configuration hash, source dictionary fingerprints, optional encoder identity hash/Qdrant config, evidence/document counts, coverage hashes, content hashes и deterministic bundle ID.

Каждый publish выполняет source-structural validation и повторно сверяет actual BM25/metadata/Qdrant artifacts с манифестом. Любое несоответствие fail-closed, прежний active bundle сохраняется. После readiness gate выполняется один process-local pointer swap под `RLock`. Search захватывает bundle однократно и не смешивает ревизии. Отдельные durable/multi-worker/disk-persistence гарантии не заявляются.

## 3. Operational policy

Отдельный `SaturnOperationalPolicy` содержит blocked evidence, document, source revision, PDF revision и entity IDs. Это **эксплуатационная блокировка**, а не approval и не ослабление trusted Saturn source root. Provider выдаёт текущий immutable policy state.

Поиск проверяет policy перед выборкой и повторно после неё; newly blocked candidates отсеиваются из обоих каналов, ranks восстанавливаются до fusion. Отказ policy provider → fail closed. Клиент не делает fetch, не добавляет пользовательские документы и не обращается к cloud. `cloud_generate` остаётся решением следующего этапа.

## 4. Ограничения ресурсов

Baseline (не production SLA): query ≤4000 chars; `top_k` ≤40; candidates/channel ≤40; records (evidence + metadata) ≤10000; representation ≤20000 chars/record и ≤2 млн chars/bundle; embedding batches ≤16; dimensions ≤8192; общий vector budget ≤2 млн scalars. Индекс — только по валидированному серверному snapshot.

## 5. Проверки и различие уровней качества

Файл: `backend/tests/unit/test_saturn_channel_retrieval.py`.

Покрытие тестов: canonical evidence IDs/provenance/physical PDF pages, structured fields/unknown fields/relation, metadata-only isolation, multi-owner documents, tokenization Cyrillic/Latin, explicit dictionary alias, BM25 math/determinism/empty search, Qdrant local real stored points, controlled vectors, RRF, invalid vectors/config, missing/corrupted Qdrant points, corrupted BM25/metadata/manifest, snapshot mismatch, fail-closed policy and recheck, concurrent publication/search, query bounds/no network, pinned source-derived Saturn fixture pipeline with synthetic PDF extraction.

Команда для реальной проверки: `python scripts/verify_offline.py`. Проверки GitHub Actions: `offline-checks` и `onnx-contracts`. Exact-head results должны быть подтверждены в PR перед Review; не выдавать начальный synthetic baseline за новые результаты.

Отдельно различаются:
1. Functional correctness: контракты/индексы/policy/atomicity, проверяемые тестами.
2. Synthetic retrieval quality: исторические synthetic datasets не модифицированы.
3. Real Saturn semantic quality: без pinned production encoder и согласованного relevance benchmark **не измерялась**. Controlled Qdrant vectors не подтверждают инженерную релевантность/semantic search.

## 6. Зафиксированные ограничения и следующий этап

- Retrieval возвращает только ранжированные ссылки на проверенные данные. Backend-generated citations и grounded generation — **этап 5**.
- В 4A `SiteContentPackage` пока не содержит bytes `astro.config.mjs`, поэтому production `SITE_URL` origin не может независимо подтверждаться. Обхода в 4B нет.
- Нет durable restart recovery, multi-worker publication, production Qdrant server/encoder, reranker calibration, OCR, PDF worker OS isolation, FastAPI/UI и cloud egress.
- `UkWood/Saturn-Main-Site` строго read-only.
- После успешного exact-head CI передать **весь PR** архитектурной сессии A для одного независимого Acceptance Review. Не выполнять merge, не начинать этап 5.
