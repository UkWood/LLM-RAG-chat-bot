# Этап 3a: snapshot contracts и synthetic evaluation baseline

Дата: 2026-11-05. Ветка feat/snapshot-evaluation-baseline. Scope согласован владельцем после обсуждения следующего шага: snapshot-контракты и набор ~10 документов/~30 вопросов до подключения моделей.

## Основание и результат

PR #2 проверен и слит по поручению владельца: main 909072fe928f004729e6db95482bb5342f0e6e63, [CI 42062413579](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42062413579) success. GitHub merge API вернул HTTP 500; обычный git merge + non-force push успешен, API подтвердил merged=true. Старые отчёты описывают состояние PR до этого merge.

Добавлены [дизайн](../superpowers/specs/2026-11-05-snapshot-baseline-design.md), [план](../superpowers/plans/2026-11-05-snapshot-baseline.md) и [ADR-0005](../decisions/0005-snapshot-baseline.md).

Snapshot-контракт содержит immutable документы и явные policy/provenance metadata на каждом IndexedChunk. Подтверждаются точный registry и source bytes, canonical parser output и coverage. В памяти реализованы activation/capture bundle, смена версии/удаление документа, откат corpus и независимые current policy/revocations. Descriptors dense/lexical проверяют только metadata декларации: ни реальных индексов, ни embeddings в этом PR нет.

Создано 10 authored вымышленных документов, 44 chunks: 8 Markdown +2 PDF (по 3 физические страницы). EDU-410/420/430, EDU-CONFIG, EDU-HEAT, категория, статья диагностики и таблица units. PDF source fixtures воспроизводятся из committed page descriptions; это исходные учебные документы, не dump реального корпуса или индексов. PDF text ASCII/English, вопросы на русском; качество извлечения русских PDF/OCR этим не доказано.

[Dataset](../../evaluation/datasets/synthetic-v1.json): 30 размеченных вопросов, 20 expected answered /8 refused /2 clarification; 20 calibration/10 held_out, по одному held_out каждой категории. Позитивные labels покрывают все 10 source documents, связывают literal fact с source/field/physical page. Есть multi-doc, переформулировки, опечатки, unsupported facts, invented variant, injection и out-of-domain. Это ожидания для следующего evaluation, а не фактические ответы реализованного retriever.

## Проверки и evidence

- Snapshot RED: отсутствующий saturn_ai.snapshots, затем GREEN на 8 initial тестах.
- Dataset RED: отсутствующий evaluation.dataset, затем GREEN на 8 тестах, включая unsupported facts/pages, contradictory labels, distributions, revision drift, malformed keys и reproducible PDF bytes.
- Независимое review 1788198 нашло P1: self-consistent forged/omitted chunks проходят без привязки к raw bytes; P2: registry entries меняются под старой revision. Оба воспроизведены RED. Исправлены immutable original registry bytes/reload и SourceBlob receipts + full canonical reparse. Три regression tests (включая missing/duplicate/drift receipts) GREEN. Fix f4d22ea.
- Финальная проверка: scripts/verify_offline.py — document/registry checks PASS, 5 прежних +60 backend tests PASS, затем synthetic preflight PASS. Итого 65 code tests; это отдельные проверки от 30 dataset cases.
- Unified CI command сохраняет все предыдущие проверки и добавляет preflight. Locked dependencies неизменны: PyYAML 6.0.3 /pypdf 6.10.0, Python 3.12 Linux x86_64. Тесты/preflight без сети после install, без ключей/GPU/моделей.
- [Preflight report](../../evaluation/reports/2026-11-05-baseline-preflight.json): 10 docs /44 chunks /30 labels; snapshot 820b9c032a001af50276178bfa765e414667b1e8046ad2070f0a68122af1c680, dataset a50e5efaf8784607816ebef75d41987b6ffb342ebcee2e5669cb42ac8b0929ce. Retrieval/reranking/grounding=not_run, source_hit_at_5=null. Report не содержит raw questions/corpus или index dumps.
- Registry реальных источников и M1 application/provider не менялись. Все 8 реальных кандидатов остаются pending/UNKNOWN. Saturn-Main-Site не читался и не изменялся на этом шаге.

Команда после установки backend/requirements.lock:

```bash
work/venv/bin/python scripts/verify_offline.py --report evaluation/reports/2026-11-05-baseline-preflight.json
```

Во время работы использован work/ingestion-venv; после snapshot venv может потребовать пересоздания. Команда без --report выполняет те же проверки, не записывая артефакт. Report детерминирован для тех же input bytes и locked parsers.

## Публикация

Base 909072f; commits 7dead21 (snapshot contracts), 80d5dc4 (corpus/dataset/validator), 1788198 (unified command/CI/report), f4d22ea (review fixes). [PR #3](https://github.com/UkWood/LLM-RAG-chat-bot/pull/3) открыт в main. Git push exit 0; API подтвердил head 29422fe60543095847daa6b8d07a6d37c66f6ec4 (публикация документации). Push [CI 42065607521](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42065607521) на этом head success; jobs API подтвердил success locked install и unified tests/preflight. PR [CI 42065691981](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42065691981) запускается независимо. Эти наблюдения сохраняются последующим documentation-only commit; актуальные checks последнего head читать в PR. Автоматический merge не предусмотрен, состояние при публикации OPEN.

## Ограничения и следующий шаг

Это bounded этап 3a, не весь этап 3 и не приёмка полноценного прототипа/M2. SnapshotCatalog process-local, без persistent/multi-worker recovery; index descriptors не проверяют настоящие vectors/BM25 artifacts. Canonical reparse увеличивает CPU cost; performance не измерялась. Receipts с approved bytes только в памяти, не передаются provider и не экспортируются.

Следующий PR: настоящие local index adapters (Qdrant/embeddings/BM25) и измеряемый retrieval baseline, используя подготовленные snapshot/dataset. Дальше RRF/reranking и grounding. Для Top-5 должны быть реальные результаты по всем must_answer; label preflight нельзя выдавать за source-hit@5=100%. Held_out не использовать для подбора порогов. Real sample/cloud требуют отдельного допуска, нынешний PR их не разрешает.

## Проверка перед merge PR #3

По поручению владельца проверен PR head b3f32c2: comments/reviews отсутствуют, mergeable CLEAN, оба CI success. Единая локальная проверка повторена. Git diff --check первоначально интерпретировал ASCII PDF fixtures как текст и отметил пробелы в обязательных PDF xref entries. Добавлена .gitattributes с *.pdf binary; PDF bytes/hashes не менялись. Повторный diff check проходит. Это исправление классификации Git, не изменение corpus/labels или parser behavior. Финальный head и CI проверяются после публикации; факт merge подтверждается отдельно по GitHub/main.

## Последующее событие: merge PR #3

По поручению владельца PR #3 проверен и слит: be71efde2b7a3f572d790d416bf642f3a9798017, main CI42089988455 success, 65 code tests и preflight PASS. Сведения об открытом PR выше относятся к моменту публикации.
