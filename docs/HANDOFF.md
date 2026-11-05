# Передача контекста

Обновлено: 2026-11-05, snapshot contracts и synthetic baseline.

## Восстановление

1. Прочитать AGENTS.md, README, PROJECT_STATUS, [согласованные критерии](acceptance/prototype-v1.md), [snapshot design](superpowers/specs/2026-11-05-snapshot-baseline-design.md) и [отчёт](stages/2026-11-05-snapshot-baseline.md).
2. PR #1 и #2 merged. Актуальная база main 909072fe928f004729e6db95482bb5342f0e6e63, CI 42062413579 success. Текущая ветка feat/snapshot-evaluation-baseline содержит новый этап 3a, [PR #3](https://github.com/UkWood/LLM-RAG-chat-bot/pull/3); push CI 42065607521 на 29422fe success. Последний head/checks смотреть в GitHub и отчёте, не предполагать merge.
3. Python 3.12 Linux x86_64 venv + pip install --require-hashes -r backend/requirements.lock, затем одна команда: work/venv/bin/python scripts/verify_offline.py. Включены document checks, 5 прежних +60 backend tests и baseline-preflight. --report сохраняет только малый отчёт labels/revisions/counts. Без сети после install, без ключей/GPU/моделей. work/venv может отсутствовать после snapshot.
4. Git/gh exec требуют sandbox network grant, proxy сохранять. GitHub merge API при PR #2 вернул 500; обычный local merge/non-force push был успешен, GitHub подтвердил merged=true. Не считать API failure доказательством нехватки прав и не менять credentials. При будущей интеграции проверять фактический PR/head/main/CI.

## Что реализовано и что это доказывает

M1 остаётся узким FakeLLMProvider fixture profile. Ingestion отделён от generation. Snapshot проверяет exact raw registry bytes и разрешённые SourceBlob receipts повторным canonical parsing: self-consistent forged/omitted chunks и stale policy revision не проходят. IndexedChunk содержит explicit visibility/scopes/hash/policy metadata.

Catalog только process-local atomic pointer; dense/lexical descriptors — metadata declarations, не настоящие index artifacts. Current policy и append-only revocations не откатываются вместе с corpus. Перед egress/result нужен новый policy check даже для старого capture. Raw receipts не экспортировать provider/report/index dumps. Отсутствие persistence/multi-worker и reparse cost — известные ограничения, не production-ready сервис.

Dataset: fixtures/evaluation/ + evaluation/datasets/synthetic-v1.json, 10 fictional docs/44 chunks/30 cases, 20 calibration и10 held_out. PDF fixtures воспроизводятся из manuals.json; English/ASCII PDF не проверяет Cyrillic extraction. Gold labels содержат ожидаемые facts/source/field/page, не ответы retriever. Preflight проверяет labels; retrieval/reranking/grounding=not_run, source_hit_at_5=null. Не объявлять Top-5/grounding пройденными по этому отчёту.

## Следующий шаг

Продолжить этап 3: настоящие local index adapters (Qdrant/embeddings/BM25) и retrieval evaluation на готовом dataset. Потом этапы 4/5 RRF/reranking/grounding, отдельный mock HTTP provider contract этапа 6. Held_out не использовать для калибровки. Полная prototype acceptance/M2 не завершена, ADR-0001 proposed; bounded решения в ADR-0002…0005.

## Полномочия и sources

Полные права на UkWood/LLM-RAG-chat-bot сохраняются; обычные изменения/commits/push/PR выполнять без повторного запроса. Merge PR #1/#2 явно поручен пользователем; новые PR не считать merged по green CI.

UkWood/Saturn-Main-Site строго READ-ONLY: без changes/commits/push/CI/URL/assets. Real registry содержит 8 pending/UNKNOWN, allowed0. Ни prototype acceptance, ни synthetic fixture approvals не разрешают реальные источники/cloud. До real ingestion нужны exact approvals, OS sandbox/egress и quality review; до cloud — privacy и endpoint/условия. Secrets не выводить, work/ и процессы не считать долговременной памятью.
