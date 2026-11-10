# Этап 4B — Saturn Channel-Aware Retrieval v0.1

Дата: 2026-11-10  
Проект: AI Technical Consultant — МНПП «Сатурн»  
Репозиторий: `UkWood/LLM-RAG-chat-bot`  
Baseline `main`: `2da357db4543c9ca173db7663bbd18396d221cc3` (PR #25 merged)  
Ветка: `feat/saturn-channel-aware-retrieval-v0.1`  
PR: #26 или фактический номер после создания  
Статус: реализация для независимого Acceptance Review; **NO MERGE**.

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
- Batches ≤16, dimensions ≤8192, ограничено суммарное число vector scalars. Query filter ограничен eligible IDs, exact snapshot ID, encoder ID. Tie-break по rounded cosine score и canonical evidence ID.
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
