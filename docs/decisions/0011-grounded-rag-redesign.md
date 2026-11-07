# ADR-0011: обычный RAG и подтверждённые частичные ответы

Статус: **accepted bounded implementation**. Владелец выбрал направление обычного RAG с проверкой подтверждений; подробный [дизайн](../superpowers/specs/2026-11-07-grounded-rag-redesign-design.md) принят после уточнений и прямой просьбы владельца применить подход к проекту.

Причина: mandatory schema planner блокирует естественные вопросы до поиска; независимый V3 результат2/24положительных против4/24V2не подтвердил calibration35/36. История сохранена в [PR12](https://github.com/UkWood/LLM-RAG-chat-bot/pull/12), не слита и не переписывается.

Предлагается исходный вопрос → existing hybrid/reranker → bounded context → сменная LLM → детерминированная проверка evidence/citations плюс проверяемый смысловой pass → подтверждённый ответ и вопросы к поддержке. Не требовать enum intent/полноты canonical fact schema перед поиском. Частичное подтверждение полезно: отсутствие материала обозначать вопросом и текстом «Для уточнения свяжитесь с поддержкой компании». Backend не выдумывает контакт и не отправляет сообщение.

Изменение all-needs/quote-only относится к отдельному новому пути после принятия дизайна; старые contracts/benchmarks неизменны. Это предложение уточнить ADR0008/0009/0010 и acceptance, а не считать их автоматически изменёнными. Детерминированная проверка цитат не доказывает смысл; проверяющая LLM тоже ошибается. Quality проверять настоящим разрешённым provider и человеком, отдельно retrieval/oracle-context/end-to-end. Fake/mock подтверждают только code/HTTP contracts. Неподтверждённые утверждения в измерении блокируют принятие checker; небольшая диагностика не является production acceptance.

Saturn-Main-Site read-only, source/privacy/cloud boundaries сохраняются. Дизайн не разрешает реальный sample, model download, cloud call или merge. Следующий шаг после одобрения документа — подробный план малого диагностического этапа, без повторного строительства большого planner.


Дополнение владельца к направлению: автоматическое обновление опубликованных страниц и непосредственно связанных публичных PDF без ручного подтверждения каждой версии. Категории и классификаторы сайта нестабильны и не являются обязательной схемой KB/понимания вопроса; ориентируемся на актуальные тексты и PDF. Exact hashes сохраняются для provenance, допуск версий выводится из согласованной автоматической policy. Discovery не охватывает development branches/весь repository и не разрешает произвольные внешние ресурсы. Удалённые/устаревшие версии исключаются, новая база включается атомарно, кеш и история не подменяют актуальные evidence. Расписание владельца: автоматический запуск раз в сутки плюс принудительный запуск авторизованным администратором; предельный возраст при длительных сбоях — отдельная operational policy; код/registry не изменены, подробный документ остаётся предложенным.


Уточнение модели: использовать готовую обученную LLM через сменный API (предпочтительный исходный вариант Qwen), без собственного обучения/fine-tuning/дистилляции. Готовая дистиллированная модель или локальное размещение за совместимым API возможны после отдельной проверки provider. Обновление базы не меняет веса LLM.


## Implementation checkpoint2026-11-07

Task4 publication-backed ask/runtime и Task5 synthetic diagnostic tooling реализованы, один whole-branch review/fix pass выполнен. См. [resume report](../stages/2026-11-07-grounded-rag-resume.md) и [operator runbook](../runbooks/grounded-rag-operator.md). Fresh environment не содержит API bindings; smoke provider_configuration_required до HTTP. Actual generation/semantic support quality NOT_RUN, human fixture/answer review pending; synthetic retrieval12/12gold-containing cases не является acceptance консультанта. Publication parser v2 имеет offset IDs, старые stores требуют отдельного refresh. Deployment egress against DNS rebinding остаётся обязательной внешней границей до real ingestion. Решение о готовности к prototype/production не принято.


Обновление2026-11-07: в текущей среде network destination/protected key scope исправлены, fresh ready/current/enforced подтверждены. Одна AITunnel public synthetic smoke на505a266 → exit0 compatible (HTTP/JSON only), см. [stage evidence](../stages/2026-11-07-grounded-rag-resume.md#aitunnel-smoke-после-исправления-destination-scope--2026-11-07). Это закрывает API compatibility prerequisite, но human fixture/context review pending; oracle/end-to-end generation и human answer assessment NOT_RUN/pending. Acceptance и архитектурные границы не меняются.


После подтверждённого владельцем fixture/context review выполнены первые реальные diagnostics на505a266: oracle15/15 без infrastructure errors; end-to-end остановлен на d03 pipeline_unavailable, остальные12NOT_RUN. Измерения сохранены неизменными; наблюдаются пропуски подтверждённых фактов, human answer review pending. [Ответы/оценка](../stages/2026-11-07-grounded-rag-first-responses.md). Compatibility не стала quality acceptance; перед расширением нужно локализовать ошибку и потерю claims. Новых архитектурных решений/допуска production нет.


Correction6f7e728: context-backed exact identifiers отделены от измеренных чисел/единиц в numeric guard, при этом источник имени ограничен цитируемыми chunks. Ни общий pool, ни цифры названия/интерфейса не доказывают technical values. Сохраняются semantic verification, live eligibility, backend citations; добавлены fixed phase errors без exception disclosure. [Доказанный дефект/регрессии/measurements](../stages/2026-11-07-grounded-rag-numeric-correction.md): оба новых diagnostic15/15 без infrastructure errors, но нерелевантные дополнительные сведения d11/d12 и human quality assessment остаются открытыми. Это реализационное исправление accepted bounded design, не смена архитектуры/приёмка качества.


Прямое требование владельца «Сведения вне вопроса нужно исключить» реализовано вf41c25f: evidence support необходим, но недостаточен; каждый clause должен отвечать requested part, иначе verifier выдает irrelevant. Backend не публикует такой claim/citation; удаление только extras не создаёт искусственного missing part. Нет planner/keyword rules/третьего LLM pass. [Регрессии и реальные outputs](../stages/2026-11-07-grounded-rag-relevance.md): d10–d12 без factual claims/sources в oracle и full path; общий human assessment pending, full path остановлен отдельным provider response error наd13. Семантическую relevance оценивает модель, абсолютная гарантия не заявляется.
