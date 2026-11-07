# Grounded RAG: operator CLI

Текущий scope — один доверенный оператор, CPU, локальные модели/индексы, сменная готовая API LLM. Нет web API, публичного chat endpoint, установленного timer, deployment или автоматического merge. Реальный корпус ещё не индексировался. Saturn-Main-Site строго read-only. Не отправлять исходники, INTERNAL, secrets или персональные данные в LLM; автоматического privacy-классификатора нет.

## Подготовка

Python3.12, locked dependencies: `backend/requirements.lock` для base-проверок; `backend/requirements-onnx.lock` для hybrid/runtime. Venv и bundles под ignored `work/` после смены среды надо восстановить. Использовать уже принятые official pinned profiles `config/embeddings/multilingual-e5-small.profile.json` и `config/rerankers/mmarco-minilm.profile.json`; [model preparation](../stages/2026-11-06-model-preparation.md), [reranker](../stages/2026-11-06-local-reranking.md). Runtime ничего не скачивает, numeric graph не заменяет semantic bundle.

Образец policy: `config/publication-policy.example.json`. Это пример конфигурации, не допуск реального сайта к cloud. Оператор задаёт owner-authorized `site_root`, permitted PDF origins, `cloud_allowed`, timezone и staleness. Новая версия bytes сохраняет точный hash/receipt и допускается только внутри этой publication policy. Unknown/out-of-scope URLs запрещены. Не передавать URL из вопроса индексатору.

Сеть индексатора должна ограничивать фактические назначения на уровне deployment egress: HTTPS configured origins, запрет private/link-local/metadata IP после DNS. Проверка DNS в приложении сама по себе не защищает от DNS rebinding и не заменяет сетевую границу. Публичный deployment этим этапом не допускается. Изоляция PDF требует Linux bubblewrap и разрешённых user/net namespaces; при её отсутствии extraction quarantine/failure, без небезопасного fallback.

## API configuration и smoke

Передать через настройки среды `LLM_BASE_URL`, `LLM_MODEL`, protected `LLM_API_KEY` с разрешённым доменом назначения. `.env` не загружается автоматически, ключ не писать в команды/репозиторий/чат. После применения проверить fresh environment status (current observations, ready bindings, enforced policy) и только наличие переменных в процессе, без их значений.

Владелец выбрал `https://api.aitunnel.ru/v1` и `deepseek-v4.1-flash-1017`. После исправления network destination/key scope 2026-11-07 выполнена одна public synthetic smoke на checkpoint505a266: exit0 `compatible`, только HTTP/JSON contract. [Evidence](../stages/2026-11-07-grounded-rag-resume.md#aitunnel-smoke-после-исправления-destination-scope--2026-11-07). Прежние ошибки отсутствия bindings/destination mismatch исторические. Human fixture/context review pending; oracle/end-to-end quality NOT_RUN. Без новой причины smoke не повторять. Client поддерживает chat/completions JSON object, temperature0, finish_reason=stop, один ответ; провайдер обязан поддерживать этот контракт. No redirects/retries/model fallback. `LLM_TIMEOUT_SECONDS` по умолчанию60, `LLM_MAX_TOKENS`2048 (16…8192), `LLM_JSON_MODE=1`. Для явно локального loopback API допустим `LLM_ALLOW_LOCAL_HTTP=1`; удалённый API требует HTTPS/key.

```bash
PYTHONPATH=backend/src python3 -m saturn_ai.rag smoke
```

Одна маленькая public synthetic request, без материалов сайта. `compatible` означает только HTTP/JSON contract, не качество ответов. Не повторять автоматически при ошибке; сохранить безопасный reason_code и исправить конкретную причину.

## Refresh/status/ask

Сначала создать/проверить правильную operator policy вне Git. Команды выполняются из корня checkout; `work/publication-policy.json` и `work/publication-store` — примеры операторских путей.

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.publication --policy work/publication-policy.json --store work/publication-store refresh --model-dir work/multilingual-e5-small
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.publication --policy work/publication-policy.json --store work/publication-store status
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.publication --policy work/publication-policy.json --store work/publication-store refresh --model-dir work/multilingual-e5-small --force
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.rag ask --policy work/publication-policy.json --store work/publication-store --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --allow-cloud --public-question --query 'Публичный технический вопрос'
```

`--allow-cloud` разрешает конкретный настроенный provider для этого запуска, `--public-question` подтверждает проверку публичности вопроса оператором. Оба флага и `cloud_allowed=true` в policy обязательны для удалённой LLM. Они не являются автоматическим допуском неизвестных материалов. Без доверенной операторской проверки этот CLI нельзя выставлять публичным сервисом. Контакт поддержки не задан: backend использует только согласованную фразу без выдуманного email/телефона.

`ask` требует hybrid publication. Lexical-only refresh доступен для contract/debug, но не становится hybrid fallback. Publication parser v2 включает стабильный offset в ID каждого сегмента, поэтому повторяющийся текст не создаёт duplicate IDs. Stores от прежнего parser v1 надо заново обновить операторским `refresh --force` (daily dedupe иначе может пропустить этот день): несовместимый capture отвергается, скрытой миграции нет. Runtime сверяет snapshot, embedding identity, lexical/dense descriptors и реальные persisted vectors/payloads. Изменившийся, отсутствующий или несовместимый индекс даёт error; его восстанавливает отдельный updater. Qdrant local — один процесс с exclusive storage lock, не multi-worker server. На новом snapshot следующий CLI-запуск получает новую версию; долго живущий процесс обязан быть перезапущен/перезагружен отдельно.

`status` показывает last_success/last_attempt/health; `as_of` ответа — last_success захваченной версии (Unix seconds). Updater сериализован file lock, dedupe по календарному дню `refresh_timezone`; `--force` — ручной admin запуск. `deploy/` содержит пример systemd daily timer/service, здесь они не установлены. Для эксплуатации надо проверить service paths/user/env, shared store permissions и network boundary отдельно.

Наблюдённые замены/удаления/убранные ссылки отзываются live, даже если новый index build не прошёл. Network error не приравнивается к удалению; последняя успешная версия доступна только пока policy разрешает и не истёк `max_age_seconds` (default172800). Это окно обнаружения изменений, а не real-time sync. Ошибки API/индексации не выдаются за доказанное отсутствие свойства. Подтверждённые независимые части сохраняются при пробелах/отзывах.

HTML — только main/article, без nav/footer/scripts; ≤2MB/page. PDF — текстовый, ≤20MB,≤200pages,≤500000extracted chars; без OCR, ZIP, изображений и общего разбора нестандартных архивов. OS worker лишён сети и workspace/secrets; сканы/ошибки/unsupported content отклоняются. Crawl bounded: по policy и общий100MB, до4redirect hops, configured HTTPS destinations. Произвольные источники и изменившаяся taxonomy не превращаются в фиксированную схему фактов.

## Три независимых диагностических режима

[Набор](../../fixtures/rag-diagnostic/README.md) и `evaluation/datasets/grounded-rag-open-v1.json` открыты и полностью synthetic. Исторические consumed datasets не используются. Сначала человек проверяет15вопросов и gold evidence/gaps. Чтение/правка fixture review не является приёмкой ответов.

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation.rag_diagnostic --mode retrieval --fixture-root fixtures/rag-diagnostic --dataset evaluation/datasets/grounded-rag-open-v1.json --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --report work/rag-retrieval.json
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation.rag_diagnostic --mode oracle --fixture-root fixtures/rag-diagnostic --dataset evaluation/datasets/grounded-rag-open-v1.json --reviewed-fixtures --allow-cloud --public-questions --report work/rag-oracle.json
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation.rag_diagnostic --mode end-to-end --fixture-root fixtures/rag-diagnostic --dataset evaluation/datasets/grounded-rag-open-v1.json --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --reviewed-fixtures --allow-cloud --public-questions --report work/rag-end-to-end.json
```

Флаги review/public/cloud ставит только оператор после фактической проверки. Oracle может работать без retrieval models: это тот же Consultant с заранее выбранным canonical context из отдельного `oracle_sources`, включая topical/distractor context для missing cases; expected evidence/gaps ему не передаются. Genuinely empty-context shortcut проверяется отдельно unit tests как backend behavior. Retrieval передаёт исходный вопрос без planner, сравнивает quotes после поиска; missing cases имеют recall=null. Report содержит hashes snapshot/dataset/models и raw statuses; self-verifier не является quality grader. Первый infrastructure error прекращает дальнейшие API-вызовы, remaining cases NOT_RUN.

После измерения человек сохраняет отдельную оценку по [template](../../evaluation/human-review-template.json) с SHA256 исходного отчёта. Неподтверждённые факты, ложные отказы, пропуски/вопросы поддержки и citations оцениваются отдельно. Без реального runtime/human assessment quality остаётся NOT_RUN/pending; synthetic retrieval score не означает готовность консультанта.


## Первые фактические diagnostics — 2026-11-07

Fixture/context review подтверждён владельцем. Oracle15/15 выполнен без infrastructure errors; end-to-end остановлен на d03 pipeline_unavailable, d04–d15 NOT_RUN. [Исходные ответы и SHA-bound human review forms](../stages/2026-11-07-grounded-rag-first-responses.md). Human answer review pending, quality не принята; предыдущая запись pending fixture review выше историческая. Не повторять smoke/набор без новой причины: сначала оценить результаты и локализовать failure. Сохранённый report содержит fixed reason_code, не исходный draft/exception; не выдавать pipeline_unavailable за доказанный provider/network сбой.


## После numeric correction6f7e728

Новые oracle/end-to-end оба15/15,0infrastructure errors, [ответы и pending human review](../stages/2026-11-07-grounded-rag-corrected-responses.md). Предыдущая остановка d03 историческая; её причина не установлена. Numeric identifiers требуют exact cited-chunk backing и не становятся numeric/quantity evidence. Backend теперь различает invalid_generation_response/invalid_verification_response и retrieval/generation/verification/render_unavailable; provider_* codes сохраняются. Fixed code не содержит exception/body/credentials; при error остановить последующие calls, не retry автоматически. Human answer review и вопросы релевантности d11/d12 всё ещё pending; повторный smoke не нужен.


## Requested scope и последние measurements

Sourcef41c25f: публикуются только relevant+supported claims; verdict irrelevant исключает и claim, и его citation. Если requested evidence отсутствует — конкретный support question без постороннего product overview. Последние [reports/responses/review forms](../stages/2026-11-07-grounded-rag-relevance-responses.md): oracle15/15/0errors; end-to-end остановлен наd13 provider_invalid_or_unavailable_response при verification, d14–d15NOT_RUN. Никакого retry; не объявлять report awaiting_human_review полным успехом. D11/d12 без лишних характеристик в обоих режимах. Предыдущие numeric-correction результаты исторические; human answer acceptance pending.


## Tested profile4096 и safe provider reasons

Actual d13 verification probe при2048 вернул finish_reason=length/content=null. Для выбранного API/model испытан process profile `LLM_MAX_TOKENS=4096`; задайте эту runtime variable через настройки или перед командой, например `LLM_MAX_TOKENS=4096 PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.rag ask ...`. Это не secret; `.env` автоматически не загружается. Generic default2048 в коде прежний: команды без override используют inherited значение/default. Диапазон16…8192/response limit/strict finish_reason=stop/JSON guards сохранены.

Sourceac4d289: output_truncated — finish length; invalid_response_envelope — envelope/choices JSON/shape; invalid_response_content — model JSON/content; unsupported_response_shape — tools/other finish; timeout/transport_unavailable отдельно; HTTP http_* прежние. Никаких exception/body/header/key в reason, automatic retry/budget escalation нет. При error остановить следующие calls.

Новые oracle/end-to-end4096 оба15/15/0errors: [responses/reports/SHA-bound human forms](../stages/2026-11-07-grounded-rag-budget4096-responses.md). Старый stopped profile2048 immutable. Дальше human answer review, не автоматическое расширение на UI/site/deploy.
