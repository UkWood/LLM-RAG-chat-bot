# Checkpoint: переход к среде с LLM variables

## Последний checkpoint: numeric correction и30cases без infrastructure errors — 2026-11-07

Продолжение владельца «продолжай». Source6f7e728 исправляет numeric rejection контекстно подтверждённых names и вводит fixed phase error codes; final base/ONNX5project+224backendPASS (12/1skips),36targetedPASS. Один focused correction reviewer,2finding fixes RED→GREEN, без нового whole-branch reviewer loop.

Новые oracle/end-to-end выполнили каждый15/15cases без infrastructure errors, те же reviewed fixtures/provider/models/prompts. Первые исходные reports не менялись. [Новые responses и отдельные human review forms](../stages/2026-11-07-grounded-rag-corrected-responses.md), [source/tests/measured evidence](../stages/2026-11-07-grounded-rag-numeric-correction.md). Все measured report hashes привязаны к отдельным pending review JSON.

Следующее: human answer assessment и релевантность (d11/d12 приводят подтверждённые факты вне вопроса); d15 conflict presentation проверить отдельно. Runtime statuses/self-verifier не считаются score. Quality/prototype не приняты. Причина первоначального d03 pipeline_unavailable неизвестна: targeted trace и новые runs его не воспроизвели. Новые phase codes диагностируют будущее повторение, это не доказательство исправления старого error. Без новой причины smoke/прогоны не повторять. Source unchanged после6f7e728; последующий commit только docs/evidence. Существующий checkout/venvs/bundles сохраняются, старый dirty checkout не трогать; no merge/deploy/site operations. Ниже исторические checkpoints.

## Актуальная точка: первые ответы, диагностика остановлена — 2026-11-07

Human fixture/context review подтверждён владельцем («Проверил: сценарии и контекст пригодны»); API smoke compatible. Oracle один раз: exit0,15/15cases,0infrastructure errors, видны пропуски подтверждённых сведений. End-to-end один раз: exit2, d03 pipeline_unavailable, d04–d15 NOT_RUN; d01/d02 needs_support. Никаких retries/model switches. [Measured evidence и команды](../stages/2026-11-07-grounded-rag-resume.md#первые-llm-diagnostics-после-human-fixture-review--2026-11-07), [ответы и human review forms](../stages/2026-11-07-grounded-rag-first-responses.md). Оба отчёта измерены на505a266 и сохранены неизменными с SHA256.

Human answer assessment pending; quality/prototype не приняты. Следующий шаг — оценить фактические ответы и локализовать pipeline error/потерю claims, а не снова запускать smoke/весь набор. Исходные drafts в report не сохраняются, точная причина pipeline_unavailable неизвестна. Offline probe выявил отклонение claim с цифрами в имени изделия при короткой quote без этих цифр; это не доказательство причины каждого measured отказа. Source/prompts/filters/fixtures не менялись. work/venv и pinned E5/reranker восстановлены, все прежние model/tokenizer/manifest hashes совпали. Старый dirty checkout сохранён. Ниже исторические checkpoints; их pending fixture/runtime blockers не актуальны.

## Текущее продолжение: smoke compatible — 2026-11-07

Destination mismatch исправлен в текущем executor: api.aitunnel.ru разрешён и совпадает с protected key scope, все bindings ready, observations current, restricted network enforced. На remote checkpoint505a266 выполнена одна public synthetic smoke: **exit0, compatible, HTTP/JSON contract only**, без retries/provider/model switches. [Фактическое evidence](../stages/2026-11-07-grounded-rag-resume.md#aitunnel-smoke-после-исправления-destination-scope--2026-11-07). Smoke не повторять без новой причины.

Следующий блокирующий вход — фактический human fixture/context review15сценариев, evidence/gaps/oracle_sources; владельцу задан конкретный вопрос со ссылкой на набор. Пока подтверждения нет, oracle/end-to-end NOT_RUN, `--reviewed-fixtures` не ставить. Natural generation quality/human answer assessment/prototype acceptance остаются pending. Checkout восстановлен в /workspace/work/grounded-rag-resume, прежний dirty checkout сохранён. Runtime bundles/venvs не восстановлены в этом продолжении; проверить наличие перед следующей диагностикой. Ниже исторические checkpoints и исходные инструкции перехода; старые network/variables blockers больше не описывают текущую среду.

## Обновление после фактического resume — 2026-11-07

Переменные теперь присутствуют, все bindings ready; observations current, restricted network enforced. Однако api.aitunnel.ru не разрешён сетью, secret binding LLM_API_KEY разрешён только для api.deepseek.com. **Smoke NOT_RUN до HTTP**, ключ не отправлялся. В настройках среды нужны разрешение api.aitunnel.ru и действительный AITunnel credential с этим domain scope; затем fresh status/presence и одна smoke. Provider/model не переключались. Human fixture/context review всё ещё pending. [Stage evidence](../stages/2026-11-07-grounded-rag-resume.md#проверка-новой-среды-destination-mismatch--2026-11-07).

Новая рабочая копия /workspace/work/grounded-rag-resume на docs/grounded-rag-redesign; старый dirty checkout feat/embedding-model-preparation сохранён. Следующие разделы описывают исходную передачу, отсутствие переменных в них историческое.

Владелец2026-11-07попросил сохранить рабочую точку и перейти в новую среду, где будут доступны переменные доступа к LLM. **WIP: generation quality/prototype/production не приняты.**

## Где продолжать

Репозиторий `UkWood/LLM-RAG-chat-bot`, ветка **docs/grounded-rag-redesign**, существующий [PR13](https://github.com/UkWood/LLM-RAG-chat-bot/pull/13). Точный checkpoint SHA и exact-head CI см. в PR13 и `git rev-parse HEAD`; эта документация входит в checkpoint, не может содержать собственный SHA. Не main, не прежний draft V3/PR12. Base bb16530, resumed d8bf8de; новые runtime/ask bb94725, diagnostics/runbook1ccbc3a, review-fix `7da1afa`, последующий docs checkpoint виден в истории.

Прочитать AGENTS.md, README, PROJECT_STATUS, [принятый дизайн](../superpowers/specs/2026-11-07-grounded-rag-redesign-design.md), [план](../superpowers/plans/2026-11-07-grounded-rag-implementation.md), [resume stage report](../stages/2026-11-07-grounded-rag-resume.md), [operator runbook](../runbooks/grounded-rag-operator.md). Предыдущий [environment handoff](2026-11-07-grounded-rag-environment.md) сохраняет pinned model hashes/restore inputs; его упоминания «smoke only», незавершённого Task4 и ещё не проведённого review исторические.

Approach/implementation/inline метод уже разрешены; не запрашивать их повторно. Existing isolated checkout, без worktree/force/reset. Обычные commits/push/update PR13 разрешены; **не merge/deploy автоматически**. Saturn-Main-Site строго READ-ONLY, в этом продолжении не читался и не менялся. Старые consumed datasets/START/reports неизменны.

## Сохранённое состояние

- Tasks1–4: generic HTML/PDF snapshots, atomic daily/manual updater и live revocation; generic ready OpenAI-compatible provider; ordinary question→hybrid/reranker→одна генерация/одна verification→подтверждённый полный/частичный ответ и backend citations/support questions; persisted runtime и `ask` CLI. No own LLM training, no enum planner.
- Task5 tooling:15новых открытых synthetic вопросов (5full/4partial/3missing/2ambiguous/1conflict), ordinary HTML fixtures, separate retrieval/oracle/end-to-end command, human assessment template. **Human fixture/context review pending, actual oracle/end-to-end LLM NOT_RUN.** Отдельные oracle_sources содержат topical/distractor context для missing cases; expected evidence/gaps модели не передаются.
- Actual CPU E5+reranker retrieval: все gold quotes12/12evidence-bearing cases в final context;3missing cases recall=null. [Report](../../evaluation/reports/2026-11-07-grounded-rag-retrieval.json). Это open synthetic retrieval, не generation/real-site quality.
- Один независимый whole-branch reviewer завершён (41targeted PASS);3Important findings исправлены одним regression RED→GREEN pass: unique offset IDs для повторяющихся chunks и bundle pre-promotion validation, dotted HTML routes, oracle missing-context bypass.30targeted post-fix PASS. Повторного reviewer loop не делать без нового существенного основания. Final base/ONNX verifier exit0:5project+215backend PASS (12/1skips). Exact-head CI см. PR13.
- Publication parser **v2** меняет snapshot/chunk identities. Старые storesv1 fail-closed; оператор должен сделать `refresh --force` с правильной policy/model. Production store/real corpus здесь не создавались.
- Deferred operational limitation: DNS preflight не гарантирует фактическое public-only соединение urllib/proxy; до real ingestion требуются enforced/tested egress controls против private/link-local/metadata. Local PDF worker actual outer-runner test PASS; production isolation/deployment не проверены и не разрешены.

## Почему API не запускался

В этой среде fresh status: observations_current=true, network unrestricted/enforced, source_config_id=null, runtime_variables=[],secrets=[]. Presence-only probe: все три LLM vars отсутствуют. Одна команда smoke дала **exit2 provider_configuration_required до HTTP**. Не было real API calls/retries/provider switches; ключ не печатался и в чат не запрашивался. Владелец попросил переход вместо попытки подменить окружение.

## Первые действия в новой среде

1. Fresh environment-status текущего executor: current observations, policy enforced, нужные bindings ready. Не брать environment_id из старого чата. Проверить только наличие переменных без раскрытия values/header/key.
2. Ожидаемые owner-provided настройки: `LLM_BASE_URL=https://api.aitunnel.ru/v1`, `LLM_MODEL=deepseek-v4.1-flash-1017`, protected `LLM_API_KEY` export в process, destination api.aitunnel.ru. `.env` автоматически не читается. Не просить ключ в чат, не печатать env и credential values. Использовать inherited proxy/CA, без обхода.
3. Из корня checkout одна небольшая public synthetic compatibility request:

```bash
PYTHONPATH=backend/src python3 -m saturn_ai.rag smoke
```

`compatible` означает только HTTP/JSON compatibility. При ошибке записать безопасный reason_code; не делать повторных циклов/model switches. Для первого smoke local models/venv не нужны (Python3.12+stdlib).

4. Перед actual diagnostic человек проверяет [15вопросов/evidence/gaps/oracle_sources](../../evaluation/datasets/grounded-rag-open-v1.json) и [fixture README](../../fixtures/rag-diagnostic/README.md). Не ставить `--reviewed-fixtures` от имени человека без основания. Это разрешение на пригодность открытых сценариев, не приёмка будущих ответов.
5. После ready runtime и фактической fixture review выполнить oracle и end-to-end с готовой LLM на этих synthetic public inputs по runbook. Первый infrastructure error останавливает последующие calls; remaining cases NOT_RUN. Не заменять провайдер новым Fake/planner/самодельной моделью. Установленные expected labels не становятся ответами.
6. Человек оценивает реальные responses по [template](../../evaluation/human-review-template.json) отдельно от self-verifier, с SHA256 исходного measured report. Correct full/partial, false refusals, unsupported claims, citations, missed parts и support questions раздельно. Пока этого нет quality остаётся NOT_RUN/pending; не выдавать retrieval100% или unit doubles за acceptance.
7. Сохранить stage/status/ADR/handoff/PR13 с фактическими results и проверенным current-head CI. Site/API/UI/deployment/real-source operation — не автоматическое продолжение этого checkpoint.

## Restore ignored work

Venvs/models/processes могут не пережить смену среды; проверить перед восстановлением. Рабочие окружения не заменять без причины.

```bash
python3 -m venv work/base-venv
work/base-venv/bin/python -m pip install --require-hashes -r backend/requirements.lock
python3 -m venv work/venv
work/venv/bin/python -m pip install --require-hashes -r backend/requirements-onnx.lock
```

Bundles `work/multilingual-e5-small` и `work/mmarco-reranker` восстановлены в этой среде по official pinned profiles. Model/tokenizer hashes и manifest hashes8457aec437dc0c9a70d48a80e12f1b6911cddfbb84387ac24279785977e4ba77(E5),a64e3c0397020fbb6820af70cdf5d82754db28adecb51246aa4d1189e72bc368(reranker) точно совпали с прежним handoff. При потере восстановить по profiles/stage reports; upstream reranker model path `onnx/model.onnx`, локальное имя source файла `onnx_model.onnx`. Ни модели, ни index/corpus dumps, ни secrets не коммитить. License declarations metadata-only, не production clearance.

Один full base и ONNX verifier после конечного source fix и отдельный outer PDF probe записаны в stage report. Docs-only переход не требует replay дорогих моделей/старых consumed evaluations. Проверить exact-head remote CI, не наследовать success с d8bf8de. Никаких сервисов/таймеров в среде не запущено.
