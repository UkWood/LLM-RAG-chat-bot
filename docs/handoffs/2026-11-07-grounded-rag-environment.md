# Рабочая точка для новой среды — обычный RAG

## Сохранение для следующей среды с LLM — 2026-11-07

Владелец попросил сохранить рабочую точку и перейти в среду с LLM variables. Продолжать **docs/grounded-rag-redesign / PR13**, см. [новый handoff](2026-11-07-grounded-rag-llm-transition.md). Tasks1–4 и diagnostic tooling реализованы, один whole-branch review и3Important RED→GREEN fixes выполнены. API smoke здесь exit2 provider_configuration_required до HTTP: переменных/secret нет. Actual LLM oracle/end-to-end и human fixture/answer review **NOT_RUN/pending**. Первое действие в новой среде — fresh readiness/presence-only probe, затем одна smoke. Подход/inline метод не пересогласовывать; не повторять final review/дорогие модели для docs-only checkpoint. Saturn-Main-Site READ-ONLY, merge/deploy не выполнялись. Source fixes `7da1afa`; final base/ONNX5project+215backend PASS (12/1skips), отдельный outer PDF1/1PASS. Точный checkpoint/current CI — в PR13.


## Продолжение в свежей среде — 2026-11-07

Рабочая ветка `docs/grounded-rag-redesign`, [PR13](https://github.com/UkWood/LLM-RAG-chat-bot/pull/13), checkpoint `d8bf8de` восстановлен. Task4 runtime/`ask` добавлен в `bb94725`: проверка persisted hybrid index и model identities, live eligibility, captured as_of, явные operator public/cloud flags. Task5: новый открытый synthetic15case набор и retrieval/oracle/end-to-end runner, runbook и отдельный human review template. Это WIP без приёмки генерации/прототипа.

Fresh environment status: current/enforced, но `source_config_id=null`, secrets/runtime_variables пусты; процесс не содержит `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. Одна команда smoke завершилась exit2 `provider_configuration_required` **до HTTP**. Владелец получил инструкции по применению конфигурации через настройки; ключ в чат не запрашивался. Реальный API/LLM quality NOT_RUN. Human fixture/answer review pending, oracle/end-to-end LLM calls не выполнялись; не ставить `--reviewed-fixtures` до фактической проверки человеком.

Pinned local E5/reranker восстановлены, model/tokenizer/manifest hashes точно совпали с handoff. Actual CPU retrieval diagnostic на15новых вопросах: все gold quotes12/12 evidence-bearing cases в конечном context, mean quote recall1.0;3missing cases recall=null. Это только поиск на synthetic text, не generation/real-site quality. [Отчёт](../../evaluation/reports/2026-11-07-grounded-rag-retrieval.json), [operator runbook](../runbooks/grounded-rag-operator.md). Исторические datasets/reports не менялись. Saturn-Main-Site не читался и не изменялся; merge/deploy/service installation не выполнялись.

Один whole-branch review завершён:3Important issues исправлены regression RED→GREEN (повторяющиеся chunks, dotted HTML routes, oracle missing-context);30targeted PASS. Parser publication v2 требует явного refresh прежних stores. DNS/actual connection binding — deferred operational limitation: до real ingestion нужны enforced/tested egress controls. Real entity/unit/condition correctness и production readiness не заявляются. Base/ONNX до review5project+210backend PASS (12/1skips); окончательные source checks после fix pass записываются в stage report.

Checkpoint remote CI `d8bf8def78e5f6f4d00ac2afb231d852642712f0`: push42331534674 и PR42331539427 SUCCESS, offline-checks/onnx-contracts оба success. Результат текущего head публикуется по завершении проверок, не наследуется от checkpoint.


Дата:2026-11-07. **WIP, не приёмка прототипа и не готовый deploy.** Владелец добавил API secret/variables в конфигурацию будущей среды и прямо попросил сохранить работу и подготовить переход. В старой среде реальный API не вызывался.

## Где продолжать

Repository `UkWood/LLM-RAG-chat-bot`, ветка **`docs/grounded-rag-redesign`**, существующий [PR13](https://github.com/UkWood/LLM-RAG-chat-bot/pull/13). Название ветки историческое; PR теперь включает реализацию. База main `bb16530e5b9a4943abae5c1b0f526cb218f46b2d`; не переходить обратно к старому V3. Не создавать worktrees, не сбрасывать чужие изменения, не merge/deploy автоматически. Saturn-Main-Site строго read-only.

Сначала прочитать AGENTS.md, этот handoff, [принятый дизайн](../superpowers/specs/2026-11-07-grounded-rag-redesign-design.md) и [план](../superpowers/plans/2026-11-07-grounded-rag-implementation.md). Владелец сказал «примени рассуждения к проекту»: подход и реализация разрешены, inline/native метод уже выбран. Не запрашивать повторно согласование подхода/плана/метода. Остаётся один final whole-branch review после завершения задач; implementer subagents не использовались.

## Согласованные требования

- Обычный вопрос сразу идёт в hybrid search/reranker, без обязательного enum planner или стабильных классификаторов сайта.
- Источники — опубликованные содержательные тексты страниц и непосредственно связанные публичные PDF; сайт/его taxonomy в разработке, это не схема знаний бота.
- Готовая LLM через сменный OpenAI-compatible API, без собственного обучения/fine-tuning/дистилляции.
- Дать подтверждённую часть ответа; недостающие сведения обозначить вопросами и фразой «Для уточнения свяжитесь с поддержкой компании». Не выдумывать факты, контакты или отправленную заявку.
- Автообновление раз в сутки, плюс force-запуск администратором. Новые версии допускаются owner-authorized publication policy, без ручного подтверждения каждого hash; metadata/receipts всё равно сохраняются.
- Source/cloud/privacy boundaries и legacy contracts не ослабляются. Исторический неслитый draft PR12/V3 consumed dataset/START/reports не изменять и не использовать для tuning.

## Уже сохранённые компоненты

| Компонент | Фактическое состояние |
| --- | --- |
| `publication/policy.py`, `extract.py`, `snapshot.py` | Generic HTML main text/table content и PDF receipts; новая immutable snapshot независимо от taxonomy |
| `publication/pdf_worker.py` | pypdf text extraction в bwrap namespace без сети/доступа к рабочим файлам; при недоступной изоляции quarantine |
| Retrieval adapter | Явный type dispatch нового snapshot к существующим BM25/Qdrant/service; старый synthetic byte validator остаётся строгим |
| `publication/store.py`, `refresh.py`, `fetch.py` | Durable blobs/manifests, atomic pointer, current trusted-link eligibility отдельно от snapshot, edit/delete/replacement/revocation, controlled HTTPS crawler |
| `publication/__main__.py`, systemd examples | Operator refresh/status, daily dedupe в timezone и `--force`, serialization; service/timer не установлены и не запущены |
| `rag/provider.py` | Готовый generic HTTP JSON client; key из env, no redirects, timeout/HTTP/schema errors без secret leakage |
| `rag/application.py`, `contracts.py` | Original question search, one generation+verification, deterministic quotes/value checks, partial response/backend citations/current-policy checks; пока unit-tested с model double |
| `rag/__main__.py` | **Пока только `smoke`**: одна public synthetic API compatibility request, не quality benchmark |

Коммиты до checkpoint: `c76d049` accepted design/plan, `c252562` publication snapshots, `ec7f784` daily/manual updates, `0d32a5f` ready-model client. Application/smoke и этот handoff входят в следующий checkpoint commit. Точный опубликованный head и CI записаны в PR13.

Ничего не развёрнуто; реальный сайт/PDF через сеть ещё не индексировались. Readiness/quality генерации с настоящей LLM **NOT_RUN**. Зелёные mock/code tests этого не меняют.

## Первый шаг после смены среды — готовый API

Владелец предоставил конфигурацию для новой среды:

- runtime variable `LLM_BASE_URL=https://api.aitunnel.ru/v1`;
- runtime variable `LLM_MODEL=deepseek-v4.1-flash-1017`;
- protected secret exported as `LLM_API_KEY`, destination `api.aitunnel.ru`.

Значение ключа нигде в Git/чате/логах не хранится. Не просить его повторно в чат и не печатать env/header values. Вызвать `cloud_environment.environment_status({})` для выбранной **новой** среды: observations current, policy enforced, bindings ready. Старый environment_id не использовать. Проверить наличие переменных без раскрытия значений. Соблюдать inherited proxy/CA, без обходов.

После checkout нужной ветки достаточно Python3.12 и stdlib для первого smoke:

```bash
PYTHONPATH=backend/src python3 -m saturn_ai.rag smoke
```

Ожидаемо: exit0/status `compatible`, только safe provider metadata. Это одна маленькая synthetic request без контента сайта. Нет `.env` autoload: секрет/переменные должны быть в runtime process. При ошибке сохранять безопасный reason_code; не устраивать многократные retries или переключение model/provider без основания. Не называть compatibility качеством ответов.

## Что ещё требуется реализовать

1. Довести Task4: runtime/model/store loading, full `ask` CLI и проверку сохранённых index identities; smoke уже есть. Сейчас `Consultant` проверяется через прямой Python API, CLI ответа ещё отсутствует.
2. Task5:15новых **открытых diagnostic** вопросов/fixtures (5full/4partial/3missing/2ambiguous/1conflict), retrieval/oracle-context/end-to-end раздельно, actual configured ready LLM, human assessment. Никакого нового закрытого predicate router или surrogate Fake-quality report.
3. Operator README/runbook с реальными ограничениями и source/model configuration. Контакт поддержки не придумывать. Ссылки и metadata формирует backend.
4. Task6: один независимый whole-branch review, один Critical/Important RED→GREEN fix pass, итоговые base+ONNX checks и точный current-head CI, актуальные отчёты/PR. Прототип/production не принимать без actual evidence.

Особое внимание будущего reviewer: SSRF/redirect/DNS-rebinding и deployment egress boundary; PDF filesystem/network isolation; taxonomy-independent extraction; stale/version-policy race; неправильный entity/unit/condition при истинной цитате; malformed/partial model JSON; поддержка как вопрос без выдуманных предпосылок. Проверяющая LLM сама может ошибаться, unit double не является semantic proof.

## Локальные окружения и модели могут не сохраниться

Сначала проверить наличие/работоспособность `work/base-venv`, `work/venv`, `work/multilingual-e5-small`, `work/mmarco-reranker`. Они ignored, **не в Git**, не гарантируются новой средой. Процессы также не переносятся. Код/план/состояние задач сохранены в Git, не зависят от ignored ledger `work/grounded-rag/progress.md`.

При необходимости восстановить venv из существующих locked requirements (Python3.12):

```bash
python3 -m venv work/base-venv
work/base-venv/bin/python -m pip install --require-hashes -r backend/requirements.lock
python3 -m venv work/venv
work/venv/bin/python -m pip install --require-hashes -r backend/requirements-onnx.lock
```

Не заменять уже работающие окружения без причины. Restore source models только если они отсутствуют, по прежним pinned official inputs/[E5 report](../stages/2026-11-06-model-preparation.md)/[reranker report](../stages/2026-11-06-local-reranking.md), в work/, не в Git. Модели уже выбраны, нового выбора/обучения не требуется. Для первого API smoke local bundles не нужны.

| Bundle | Pinned revision | model.onnx SHA256 | tokenizer SHA256 |
| --- | --- | --- | --- |
| intfloat/multilingual-e5-small | 614241f622f53c4eeff9890bdc4f31cfecc418b3 | ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665 | 0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39 |
| cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | 1427fd652930e4ba29e8149678df786c240d8825 | 3e9a03ed1e966f7c5288dd4230e3d6a9bf5e3a170a06f1f4241c5bca12c6487c | 62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626 |

До перехода manifest hashes были8457aec437dc0c9a70d48a80e12f1b6911cddfbb84387ac24279785977e4ba77(E5) иa64e3c0397020fbb6820af70cdf5d82754db28adecb51246aa4d1189e72bc368(reranker). Restore требует прежнего provenance/card/license/profile; не подменять semantic bundle numeric graph.

## Проверки на рабочей точке

33targeted publication/refresh/provider/application tests PASS. App ambiguity regression RED→GREEN; CLI smoke missingmoduleRED→GREEN. Legacy retrieval+snapshot regression и publication27PASS на Task1. Actual OS-isolated two-page PDF integration PASS в outer runner; nested tool sandbox не разрешает user/net namespaces, production extractor там отказывает безопасно. Explicit probe:

```bash
SATURN_PDF_OS_TEST=1 PYTHONPATH=backend/src:backend/tests work/base-venv/bin/python -m unittest integration.test_publication_pdf -v
```

Этой команде нужен namespace-capable outer runner, не отключение изоляции worker. В ordinary suite OS-capability test явно skipped; это не PDF quality claim. Local HTTP contract tests требуют loopback socket permission в tool sandbox; они не обращаются к настоящему API.

Полные checkpoint checks завершены: `work/base-venv/bin/python scripts/verify_offline.py` —5project+202backend PASS,12skips; `work/venv/bin/python scripts/verify_offline.py` —5project+202backend PASS,1OS-capability skip. Отдельный actual OS PDF probe PASS. Docs checker и whitespace PASS. Существующий lexical17/20остаётся ожидаемым measured target failure, не показателем нового RAG. Final whole-branch review и live-provider/human-quality assessment ещё **не выполнены**.
