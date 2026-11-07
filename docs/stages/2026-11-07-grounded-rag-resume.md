# Grounded RAG: продолжение после d8bf8de

Ветка docs/grounded-rag-redesign, существующий [PR13](https://github.com/UkWood/LLM-RAG-chat-bot/pull/13). Это продолжение принятого [дизайна](../superpowers/specs/2026-11-07-grounded-rag-redesign-design.md) и [плана](../superpowers/plans/2026-11-07-grounded-rag-implementation.md), без нового согласования подхода. Saturn-Main-Site не читался и не изменялся. Merge/deploy и установка systemd не выполнялись.

## Среда, smoke и checkpoint CI

Новый checkout восстановлен на точном d8bf8def78e5f6f4d00ac2afb231d852642712f0. Fresh environment current observations, network unrestricted/enforced. Но source_config_id=null, runtime variables/secrets/outbound identities пусты; presence-only probe показывает False для всех трёх LLM переменных. `PYTHONPATH=backend/src python3 -m saturn_ai.rag smoke` → exit2, `provider_configuration_required`, до HTTP. Не было live-call/retry/model switch, секретов в выводе нет. Владелец получил инструкцию применить API config через environment settings; инструмента изменения конфигурации здесь нет. Runtime и privacy/source authorizations не выдумывались.

[Push CI42331534674](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42331534674) и [PR CI42331539427](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42331539427) на d8bf8def SUCCESS; jobs offline-checks/onnx-contracts оба success. Commit combined statuses и connector workflow wrapper возвращали пустой список; фактические checks установлены через gh run list/view, а не истолкованы как отсутствие/успех CI.

## Реализация и диагностика

`bb94725`: Task4 runtime/ask. CLI сверяет model identity и saved descriptors, проверяет persisted Qdrant payloads/vectors, запрещает скрытое пересоздание удалённой коллекции. Publication store/current policy используется и после загрузки; source hashes и last_success привязаны к capture. Remote ask требует operator `--allow-cloud`, `--public-question` и cloud policy; backend формирует citations. Contract tests RED (missing runtime/ask) → GREEN19targeted; base verifier5project+205backend PASS,12optional skips. Это ещё до добавления Task5 tests.

Task5:15новых [open questions](../../evaluation/datasets/grounded-rag-open-v1.json), ordinary HTML [synthetic fixture](../../fixtures/rag-diagnostic/README.md) без прежних consumed sets. Режимы `retrieval`, `oracle`, `end-to-end` используют тот же Consultant; gold labels не передаются генератору, oracle выбирает только canonical IDs. Human review template — [отдельно](../../evaluation/human-review-template.json), null не считается успехом. Реальные запросы требуют human fixture review attestation/public/cloud flags. При первом infrastructure error дальнейшие API-вызовы прекращаются, remaining NOT_RUN; reason_codes фиксированные и не содержат exception/body/env secrets.5targeted diagnostic contracts PASS после двух RED→GREEN циклов.

Восстановлены pinned official models по прежним profiles, только ignored work/: E5 revision614241f622f53c4eeff9890bdc4f31cfecc418b3 и reranker1427fd652930e4ba29e8149678df786c240d8825. Model/tokenizer SHA256 совпали с handoff; manifest hashes8457aec437dc0c9a70d48a80e12f1b6911cddfbb84387ac24279785977e4ba77 иa64e3c0397020fbb6820af70cdf5d82754db28adecb51246aa4d1189e72bc368 тоже совпали. У reranker upstream path `onnx/model.onnx`; первое обращение к локальному прежнему имени `onnx_model.onnx` как upstream пути вернуло404, исправлено после official tree read. Checkpoint/model/provider не менялись. License declaration остаётся metadata-only, не production legal clearance.

[Actual retrieval report](../../evaluation/reports/2026-11-07-grounded-rag-retrieval.json):15cases,12сgold evidence имеют final quote recall1.0 каждый,3missing имеют null. Pool recall также сохранён, model/snapshot/dataset identities в отчёте. Это только маленький synthetic retrieval experiment. LLM генерация/oracle/end-to-end и human quality NOT_RUN/pending; readiness real API не установлена. Нет false claim prototype acceptance.

[Runbook](../runbooks/grounded-rag-operator.md) фиксирует команды, source/cloud boundaries, last_success/staleness, operator attestation, PDF limits/OCR quarantine, local exclusive storage и необходимость deployment egress boundary против DNS rebinding. Нет публичного privacy-classifier/service и production claim.

## Проверки и независимый review

Actual PDF capability test в nested sandbox завершился fail-closed quarantine; идентичный `SATURN_PDF_OS_TEST=1 PYTHONPATH=backend/src:backend/tests work/base-venv/bin/python -m unittest integration.test_publication_pdf -v` в разрешённом outer runner PASS1/1, две физические страницы. PDF worker isolation не отключалась. Обычные suites явно skip этот OS-capability test.

Один fresh whole-branch review выполняется отдельно от implementer; окончательные findings/fixes и base/ONNX/current-head CI будут записаны после получения фактических результатов. Полное завершение Task5/приёмка невозможны до ready API runtime и human fixture/answer assessment; следующий зависимый шаг — применить конфигурацию среды, fresh readiness, одна smoke, затем разрешённые diagnostics. Остальные изменения можно проверить/опубликовать без ожидания секрета.

## Итог одного независимого whole-branch review и fix pass

Reviewer прочитал всю ветку от bb16530 с текущими файлами, независимо выполнил41targeted tests PASS и воспроизвёл3Important defects. Critical нет; merge до исправления не рекомендован. Все3приняты по фактическому влиянию и исправлены одним pass, без повторного reviewer loop:

- Повторяющиеся1500char сегменты одной страницы получали один chunk ID: успешный refresh затем ломал lexical/hybrid. Теперь publication parser `published-text-v2` включает стабильный offset в field/ID; ID не теряются при повторяющемся тексте. Два regression tests сначала воспроизвели retrieval/runtime failures, затем PASS. Перед atomic promotion builder вызывает тот же `RetrievalService.publish(IndexSet(...))`, что и runtime, для полного bundle check. Отдельный malformed descriptor test RED completed→GREEN failed с сохранением прежнего active pointer. Начальная версия последнего теста проходила по неправильной причине (old snapshot mismatch), была исправлена до production fix и показала нужный RED.
- HTML route `pump-v2.1` раньше silently skipped по точке в пути. Теперь eligibility определяется policy и checked response media type, не URL punctuation; regression RED missing→GREEN indexed. Неподдержанный media type всё равно fail-closed, не разбирается как HTML/архив.
- Oracle missing-сценарии d10–d12 раньше имели empty context и обходили LLM. В dataset теперь отдельные `oracle_sources`, независимо от expected evidence: Лира21/22 distractors для unknown model, Лира21 для missing property, Орион110 для missing price. Regression RED0→GREEN6model calls (generation+verification для каждого). Expected evidence/gaps в provider не передаются; empty-context unit test остаётся только backend behavior, не generator quality. Human review новых oracle contexts pending.

30targeted publication/refresh/runtime/diagnostic tests PASS. Publication parser version и dataset identity изменились по исправлению механизма; existing stores v1 требуют явного refresh/reindex, скрытой миграции нет. Actual semantic retrieval повторён только из-за изменившихся snapshot/dataset identities: результат по всем cases прежний12/12quote coverage,3missing=null. Сохранённый текущий report относится к parser v2/обновлённому dataset; это не новый blind и не quality tuning.

Rulings: ledger вручную в ignored work/, потому что cloud helper scripts локально отсутствуют (цена — нет helper enforcement); Task5 остаётся pending, пока runtime/human inputs отсутствуют (цена — нет вывода о generation quality); declined actual semantic/entity/unit/injection correctness не превращается в acceptance, до real runtime/human assessment NOT_RUN (цена — нет engineering quality claim); production egress/PDF readiness проверяется в целевом окружении отдельно, local PDF PASS не доказывает production readiness (цена — deployment не принят).

Deferred minor: DNS preflight в PublicationFetcher не привязан к фактическому urllib/proxy connection. Runbook явно требует enforce/test deployment egress против private/link-local/metadata destinations до real ingestion; unrestricted CLI host самостоятельно этой гарантии не даёт. Реального ingestion/deployment не было. Redirect aliases reviewer проверил, воспроизводимого дефекта не нашёл; это не отдельное принятое изменение.


## Финальная рабочая точка перед переходом

Source fix commit `7da1afacde3260bab756c434fc90de1f24267187` после runtime `bb94725` и diagnostics `1ccbc3a`. Конечные проверки на source после единого fix pass:

- `work/base-venv/bin/python scripts/verify_offline.py` → exit0,5project+215backend PASS,12optional skips.
- `work/venv/bin/python scripts/verify_offline.py` → exit0,5project+215backend PASS,1OS-capability skip.
- Отдельный outer OS PDF probe1/1PASS; nested sandbox fail-closed, extractor isolation не отключалась.
- `work/base-venv/bin/python scripts/check_project.py`, `git diff --check` → PASS.
- Legacy lexical17/20остаётся ожидаемым measured target failure; historical reports/datasets не изменены.

Владелец попросил сохранить этот checkpoint и подготовить переход в среду с доступными API variables. [Новый handoff](../handoffs/2026-11-07-grounded-rag-llm-transition.md) — следующая точка входа, с точными prerequisites и командами. API compatibility/LLM natural generation/human assessment остаются NOT_RUN/pending. Итоговый checkpoint включает отдельный docs commit после source fix; exact-head push/PR CI проверяется и фиксируется в PR13 после публикации. Не наследовать checkpoint CI с d8bf8de и не считать pending результатом success. Merge/deploy/real-site operations не выполнялись.
