# Этап 3B — External Document Adapter v0.1

Дата: 2026-11-10  
Репозиторий: UkWood/LLM-RAG-chat-bot  
Feature branch: feat/external-document-adapter-v0.1  
Baseline main: dee6011fa67de0bcc62b8304b7549b4ebde396b1 (PR #23 merged)  
PR: создаётся после первой реализации, затем передаётся сессии A на Acceptance Review.

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

НЕТ production-grade OS sandbox: RLIMIT и -I не устраняют все угрозы системных вызовов, сетевого доступа или filesystem. Поэтому SubprocessPdfExtractor() запрещает запуск по умолчанию (policy_denied). Для офлайн-тестов явно используется enable_development_worker=True; production запуск требует отдельного решения и внедрения OS-level confinement (seccomp/container namespace, FS/network deny и проверенной политики доступа). Также требуется оценить гарантированный DNS resolution deadline для боевой эксплуатации.

PDF reader/worker не выполняет OCR, JavaScript или вложения. Данный модуль не объявляется production-safe.

## Revisions, cache и evidence

SHA-256 рассчитывается по реальным fetched bytes, включая изменения без смены URL. Revision identity: stable_id(namespace saturn-pdf-revision-v1, document_id, URL, bytes_sha256, parser_version). В PdfRevision хранятся bytes SHA-256, parser version, state (fetched, extracted, failed), page_count и hash канонического массива [physical_page, extracted_text] при extraction.

Изменение bytes или parser version приводит к re-extraction; reuse допускается только для идентичной revision с проверкой extracted_text_sha256 и page-number consistency. Owner/source associations формируются заново при каждом вызове, поэтому добавления и удаления владельцев не меняют identity версии. Удалённые URL исключаются из нового результата. Ошибка новой версии не подменяется прежними passages.

EvidenceUnit(evidence_type=pdf_passage) создаётся только для физической страницы с непустым фактическим текстом. Locator = canonical_pdf_url#page=N, source_revision_id указывает на точные bytes/parser revision, ID детерминирован через revision/номер страницы/hash текста. Document association связывает revision ID с исходными owners, locators и source revisions. Metadata из Support Catalog не выдаются за PDF text.

Для textless PDF: ocr_required, PdfRevision(fetched,page_count), без text evidence. Для смешанного PDF: evidence только текстовых страниц, статус partial_text, diagnostic ocr_required, complete=false. Для ошибок: диагностический status; после успешной загрузки — failed PdfRevision; после failed fetch нет вымышленного bytes SHA или revision.

## Тесты, ограничения и дальнейшие действия

Созданы offline unit/contract tests URL policy, pinned DNS/TLS transport, redirects, resource limits, processor failures, physical page numbering, revisions, owner associations, deterministic IDs, real-site source-derived fixture catalog с mock transport и synthetic PDF bytes. Никаких HTTP-загрузок реальных PDF сайта в CI.

Обязательно выполнить python scripts/verify_offline.py, offline-checks, onnx-contracts на финальном exact PR head и зафиксировать результаты в PR. До подтверждения CI не заявлять PASS или production-ready. Live smoke и scheduler не проводятся. UkWood/Saturn-Main-Site строго READ-ONLY и не изменяется. Этап 4 (Unified Snapshot) не начат.
