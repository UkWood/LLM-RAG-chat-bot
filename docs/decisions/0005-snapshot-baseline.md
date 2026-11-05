# ADR-0005: snapshot-контракты и ранний synthetic baseline

Дата: 2026-11-05. Статус: implemented как инженерная детализация согласованного scope — snapshot-контракты и контрольный dataset до моделей/индексов.

## Решение

Завести immutable KnowledgeSnapshot с explicit IndexedChunk policy metadata: visibility, approval_state, scopes, source hash/commit/locator/title, policy revision и snapshot ID. Builder требует точного набора документов/chunks, совпадающего с разрешёнными версиями источников. Registry хранит immutable исходные JSON bytes, а ingestion — bounded SourceBlob receipts разрешённых файлов в памяти. Повторный canonical parsing approved bytes проверяет производный текст, metadata и полноту extraction. Caller-supplied text hashes не являются доказательством provenance.

SnapshotCatalog реализует только process-local atomic activation/capture полного bundle dense/lexical IndexDescriptor. Оба descriptors обязаны декларировать одинаковый snapshot и точный полный chunk coverage. Это контракт metadata, а не проверка содержимого реальных index artifacts. Runtime registry и append-only revocations независимы от corpus rollback, каждый выход через eligible_chunks проверяет текущий допуск. Старый capture не становится разрешением на egress/ответ без новой policy проверки.

Созданы отдельные 10 synthetic документов: 8 Markdown +2 трёхстраничных PDF. Gold dataset: 30 вопросов в согласованном распределении, 20 calibration/10 held_out. Ожидания authored и поддержаны source/field/page labels; negatives/clarifications без фиктивного evidence. PDFs воспроизводятся из page descriptions; реальные изделия не получают вымышленных характеристик.

Одна команда scripts/verify_offline.py проверяет прежние проверки, все тесты и baseline-preflight после отдельного locked install. Preflight не запускает retrieval/LLM: metrics отсутствуют, quality checks not_run, source_hit_at_5=null. Он не закрывает согласованную приёмку prototype v1.

## Альтернативы и последствия

Немедленное внедрение Qdrant/embeddings/BM25 выходит за scope этого PR; их adapters и измерение качества следуют далее. Самопроверки hashes без raw-byte binding оказалось недостаточно: независимый reviewer воспроизвёл forged chunks и stale registry revision. Выбраны receipts/reparse, а не новый caller-supplied extraction digest. Цена — память для bounded receipts и повторная CPU/PDF extraction при contract validation; latency/production readiness не заявляются.

Receipts не экспортируются в report/index dump/provider, только approved synthetic bytes в памяти. Persisted source storage, durable/многопроцессная атомарность, настоящая проверка index artifacts, model benchmark, scored retrieval и генерация по новому output не реализованы. Registry metadata не доказывает полномочия approved_by; реальные approvals остаются owner-managed и отсутствуют. Полный ADR-0001 остаётся proposed; Saturn-Main-Site read-only.
