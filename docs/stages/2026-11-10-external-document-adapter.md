# Этап 3B — External Document Adapter v0.1

Дата: 2026-11-10  
Репозиторий: UkWood/LLM-RAG-chat-bot  
Feature branch: feat/external-document-adapter-v0.1  
Baseline main: dee6011fa67de0bcc62b8304b7549b4ebde396b1 (PR #23 merged)  
PR: [#24 — External Document Adapter v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/24) (OPEN, NOT MERGED); передать сессии A на Acceptance Review.

## Назначение и реализованные интерфейсы

Вход строго SupportCatalogResult, полученный этапом 3A. Все поля кандидатов (document_id, canonical resolved URL, owner entities, source locators, source revisions и raw link occurrences) проверяются целиком до любого HTTP-запроса. Не готовый или противоречивый каталог отвергается целиком.

- external_document_transport.py: immutable DocumentFetchPolicy, validate_url, HTTPSPdfTransport, DocumentError.
- external_document_extractor.py: ExtractedPdf, validate_extraction, SubprocessPdfExtractor (только explicit development/test opt-in).
- external_pdf_worker.py: standalone pypdf worker, не связанный с legacy Registry.
- external_document_adapter.py: adapt_external_documents(catalog, policy, transport, extractor, previous_cache, parser_version) → ExternalDocumentResult.
- ExternalDocumentResult: immutable statuses/revisions/evidence/associations/diagnostics/cache и completeness flags.
- CachedPdfExtraction: явная immutable cache-record. Сам адаптер не реализует persistence/database.

## HTTPS policy и SSRF

Default-deny, без allowlist запросы запрещены. Exact lower-case DNS hostname, HTTPS и порт 443. Explicit path prefixes сопоставляются строго по сегментам, включая предварительный отказ от dot segments, nested percent escaping, encoded separators, userinfo, фрагментов, non-PDF URL. Пути /ftp, /public и /photos являются примерами параметров в тестах, не глобально включённым разрешением. Доверенность Git snapshot не означает доверенности произвольного URL.

На реальном transport проверяется весь DNS answer set с ipaddress.is_global; private, loopback, link-local, reserved, multicast, IPv4-mapped IPv6 адреса запрещены. HTTPS socket подключается только к проверенному numeric IP, peer IP повторно проверяется, TLS certificate/hostname verification и SNI используются по исходному доменному имени. Автоматические redirects запрещены; environment proxy не используется. Только один HTTP attempt на документ.

Проверяются HTTP status, Content-Type, Content-Encoding, Content-Length, actual streamed byte count, Transfer-Encoding, PDF header и ошибки truncated read. Превышения дают явную классификацию без evidence.

Начальные лимиты: PDF 16 MiB, pages 200, UTF-8 extracted text 2 MiB, per-page 128 KiB, decoded page content 4 MiB, worker RAM 512 MiB, CPU 20 s, worker wall 60 s, connect 10 s, read 20 s, download deadline 60 s, attempts 1. Действует ограничение числа документов.

## Worker isolation — существенное ограничение

Фактически worker запускается через отдельный процесс Python -I -B, получает bytes только через stdin, выдаёт JSON pages/stdout. POSIX RLIMIT_AS/CPU/FSIZE/CORE, лимит процесса по времени, input/output и отказ от encrypted/active/attached content. Сохраняется физическая нумерация PDF страниц начиная с 1, включая пустые страницы в отчёте. OCR не выполняется. Извлечение текстового слоя со страниц без него не имитируется.

НЕТ production-grade OS sandbox: RLIMIT и -I не устраняют все угрозы системных вызовов, сетевого доступа или filesystem. Поэтому SubprocessPdfExtractor() запрещает запуск по умолчанию (policy_denied). Для офлайн-тестов явно используется enable_development_worker=True; production запуск требует отдельного решения и внедрения OS-level confinement (seccomp/container namespace, FS/network deny и проверенной политики доступа). Для блокирующего DNS lookup введён bounded daemon resolver с общим download deadline; остаточные зависшие daemon DNS threads ограничиваются лимитом числа документов, но требуют эксплуатационной оценки.

PDF reader/worker не выполняет OCR, JavaScript или вложения. Данный модуль не объявляется production-safe.

## Revisions, cache и evidence

SHA-256 рассчитывается по реальным fetched bytes, включая изменения без смены URL. Revision identity: stable_id(namespace saturn-pdf-revision-v1, document_id, URL, bytes_sha256, parser_version). В PdfRevision хранятся bytes SHA-256, parser version, state (fetched, extracted, failed), page_count и hash канонического массива [physical_page, extracted_text] при extraction.

Изменение bytes или parser version приводит к re-extraction; reuse допускается только для идентичной revision с проверкой extracted_text_sha256 и page-number consistency. Owner/source associations формируются заново при каждом вызове, поэтому добавления и удаления владельцев не меняют identity версии. Удалённые URL исключаются из нового результата. Ошибка новой версии не подменяется прежними passages.

EvidenceUnit(evidence_type=pdf_passage) создаётся только для физической страницы с непустым фактическим текстом. Locator = canonical_pdf_url#page=N, source_revision_id указывает на точные bytes/parser revision, ID детерминирован через revision/номер страницы/hash текста. Document association связывает revision ID с исходными owners, locators и source revisions. Metadata из Support Catalog не выдаются за PDF text.

Для textless PDF: ocr_required, PdfRevision(fetched,page_count), без text evidence. Для смешанного PDF: evidence только текстовых страниц, статус partial_text, diagnostic ocr_required, complete=false. Для ошибок: диагностический status; после успешной загрузки — failed PdfRevision; после failed fetch нет вымышленного bytes SHA или revision.

## Тесты, ограничения и дальнейшие действия

Созданы offline unit/contract tests URL policy, pinned DNS/TLS transport, redirects, resource limits, processor failures, physical page numbering, revisions, owner associations, deterministic IDs, real-site source-derived fixture catalog с mock transport и synthetic PDF bytes. Никаких HTTP-загрузок реальных PDF сайта в CI.

Обязательно выполнить python scripts/verify_offline.py, offline-checks, onnx-contracts на финальном exact PR head и зафиксировать результаты в PR. До подтверждения CI не заявлять PASS или production-ready. Live smoke и scheduler не проводятся. UkWood/Saturn-Main-Site строго READ-ONLY и не изменяется. Этап 4 (Unified Snapshot) не начат.

## Фактическая проверка (reviewed code head, не documentation head)

- Проверенный implementation+security code head: 887108ea65feec91ddcd01631d742aaceb8c2b62 (commit DNS deadline hardening после первого code commit 6328da903dbd9ed98e67d0d803499581e2f27c32).
- Точная команда GitHub workflow: python scripts/verify_offline.py, итог: 5 project tests PASS, 320 backend tests OK (11 existing optional skips), synthetic lexical baseline source-hit@5 = 0.85 (исторический synthetic, не оценка PDF quality).
- [Push Actions #42847781478](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42847781478) — SUCCESS, offline-checks и onnx-contracts SUCCESS.
- [PR Actions #42847795850](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42847795850) — SUCCESS, offline-checks и onnx-contracts SUCCESS.
- Оба CI относятся к exact code head 887108ea65feec91ddcd01631d742aaceb8c2b62. Финальный docs head будет отличаться; его CI проверить отдельно, не обновляя SHA в документации циклически.
- Новые целевые тесты — 32 (31 в первом commit + 1 DNS deadline test), все PASS; real Saturn fixture проверен только offline с зафиксированными исходными source blobs и synthetic PDF bytes. Live HTTPS/PDF smoke: NOT_RUN; OS-level sandbox: NOT_IMPLEMENTED. Внешние реальные PDF не скачивались.

Документ сохраняет исторически проверенный code head; при проверке следующего documentation head ссылаться на CI в PR, не изменяя эту запись ради SHA.


## Consolidated Acceptance Review Corrections — CR-01 / CR-02 (2026-11-10)

**Reviewed initial head:** 69e30066f159f3612dc738dd8ad23477a515d927.  
**Corrective implementation/code head:** 86c352adc3bfed4cbc80265812b77f6f5a6e07b5.  
**PR:** [#24](https://github.com/UkWood/LLM-RAG-chat-bot/pull/24), OPEN, NOT MERGED.  
**Scope:** только bounded PDF subprocess stdout/stderr и точная диагностика termination. Existing URL/SSRF, revisions, canonical contracts и site repo не изменялись.

**CR-01 — PASS:** заменён неограниченный subprocess.run(capture_output=True). Родитель использует subprocess.Popen с nonblocking stdin/stdout через POSIX selector. Данные stdout читаются порциями, накопление строго ограничено верхним пределом max_text_bytes * 6 + max_pages * 128; превышение немедленно даёт resource_limit. stderr направлен в DEVNULL, не буферизуется и не попадает в diagnostics. Дочерний процесс принудительно убивается и reaped при ошибке и timeout, обычный ответ обрабатывается без регрессии. Лимиты worker RAM/CPU/wall и input bytes сохранены. Production-worker не включён.

**CR-02 — PASS:** отрицательный subprocess returncode проверяется **до** JSON decoding и всегда соответствует resource_limit, включая сигнал -9 с пустым или повреждённым stdout. Nonzero process exit с валидным структурированным error JSON сохраняет разрешённый код. Положительное завершение с malformed JSON/invalid worker reply даёт parser_error. Отсутствие evidence и PdfRevision(extraction_state=failed) после ошибки подтверждено.

**Новые regression tests:** девять CR-01/CR-02 test methods вместо одного прежнего общего smoke-теста. Проверяют ограничение stdout, бесконечную запись и reaping, большой stderr без deadlock, failed revision без fake evidence, SIGKILL -9 с пустым и invalid stdout, invalid JSON при rc=0, structured worker error, malformed nonzero reply, timeout с kill/reap, valid JSON и реальный успешный pypdf worker.

**Фактический code-head CI:** [push run #42852633667](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42852633667) на exact corrective code SHA 86c352adc3bfed4cbc80265812b77f6f5a6e07b5 — **SUCCESS**: offline-checks SUCCESS (5 project tests PASS; 328 backend tests OK, 11 existing optional skips; все 9 CR regression methods OK); onnx-contracts SUCCESS. Команда: python scripts/verify_offline.py. Предыдущий baseline — 320 backend tests (11 skips). Старые synthetic lexical metrics не являются PDF quality evaluation.

**Оставшееся ограничение:** RLIMIT/subprocess и stdout cap не заменяют OS-level network/filesystem/syscall sandbox. Production PDF-worker запрещён по умолчанию; live site PDF smoke и OS isolation NOT_RUN / NOT_IMPLEMENTED. Финальный documentation-head CI и URL зафиксированы в описании PR после его завершения; исторические code SHA не обновляются косметическими commits.
