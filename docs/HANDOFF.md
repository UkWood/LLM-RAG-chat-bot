# Передача контекста

Обновлено:2026-11-05, local retrieval baseline.

## Восстановление

Прочитать AGENTS.md, README, PROJECT_STATUS, [retrieval design](superpowers/specs/2026-11-05-local-retrieval-design.md), [report](stages/2026-11-05-local-retrieval.md), [prototype acceptance](acceptance/prototype-v1.md). PR #1/#2/#3 merged; база be71efde2b7a3f572d790d416bf642f3a9798017, main CI42089988455 success. Текущая ветка feat/local-retrieval-baseline, [PR #4](https://github.com/UkWood/LLM-RAG-chat-bot/pull/4); push CI42094770037 на95eb0b0 success в обоих jobs. Последние head/checks смотреть в GitHub и отчёте, не предполагать merge.

Python3.12: установить hash-locked backend/requirements.lock в work/venv, затем work/venv/bin/python scripts/verify_offline.py. Для optional runtime отдельный requirements-onnx.lock. После install всё CPU/offline, без ключей/GPU/языковой модели. work/venv и процессы не гарантируются после snapshot. Git/gh exec требуют sandbox network grant, proxy/credentials сохранять; не выводить секреты.

## Actual measurement

Corpus10docs/44chunks и dataset30cases неизменны. BM25 k1=1.2/b=.75 и schema aliases frozen до evaluation. Source-hit@5=17/20=.85, calibration14/14, held_out3/6. All-source80%, gold-evidence72.5%, MRR≈.701667. Failed q005/q013/q016 сохранены; target1.0 не достигнут. Preflight остаётся label validation, а measured lexical report отдельный.

Dense/hybrid/reranking/grounding/refusal NOT_RUN в quality report: владелец подтвердил, что local embedding checkpoint нет. Не представлять known CI vectors или authored numeric ONNX graph как neural benchmark. Actual Qdrant local/query/persistence/corruption/policy contracts проверены. No auto model downloads или cloud embeddings.

Local ONNX profile требует trusted owner-provisioned model.onnx/tokenizer.json/manifest.json, hashes, mean pooling, dimensions/prefixes/pad/output. External-data tensors запрещены recursively; runtime использует exact verified bytes (иначе unpinned sidecar/hash-load swap обходили identity). Optional CI выполняет numeric graph inference, sidecar и file-swap regression. Конкретная embedding-модель не выбрана; model-card/license и настоящий model benchmark впереди.

## Runtime boundaries

RetrievalService atomic pointer хранит actual IndexSet, проверяет полные artifacts до публикации. Explicit lexical-only не выдаёт себя за dual index. Current policy/revocations фильтруются до и после search, survivor ranks renumber передRRF; corpus rollback policy не откатывает. Returned text/citations брать из canonical snapshot, не model metadata. New retrieval ещё не подключён к M1 generator.

Process-local/local SDK до10000chunks, не server-Qdrant/multi-worker/durable publication. Qdrant float32 reopen tie rule: round6 только для ordering, raw scores сохраняются. Latency включает canonical reparse, не SLA. Raw corpus/index/model dumps и user logs в repo не сохранять.

## Следующие действия

Обеспечить локальный embedding artifact и провести dense/hybrid quality benchmark; далее reranking и evidence/grounding. Tune только calibration, не чинить held_out частными правилами. --require-source-hit-target даёт exit1 при85%; обычный code verification сохраняет измеренный failure, не объявляет prototype acceptance.

Полные права LLM-RAG-chat-bot сохраняются; обычные commits/push/PR без повторного запроса. Новые PR не считаются merged по green CI. Saturn-Main-Site строго READ-ONLY. Real registry8pending/UNKNOWN,allowed0; ничего не разрешать от имени владельца. До real ingestion нужны exact source approvals и OS parser sandbox/quality review; до cloud privacy/endpoint gates. ADR-0001 proposed, bounded decisions ADR-0002…0006.
