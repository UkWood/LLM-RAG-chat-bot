# Исключение сведений вне вопроса

Владелец прямо потребовал: «Сведения вне вопроса нужно исключить». Это уточнение existing accepted ordinary-RAG behavior, не новая архитектура/пересогласование подхода. Parent74e5878 / PR13, существующий isolated checkout. Человек не принял качество всех прежних ответов; human answer assessment остаётся pending.

## Причина и исправление

Предыдущие live reports показывают d11/d12: неизвестная взрывозащита/цена сопровождались правдивыми характеристиками, которые не отвечали на вопрос. Generation prompt разрешал перечислять подтверждённые факты без явного ограничения requested scope; verification проверяла evidence support и полноту, но не давала отдельного исхода для true-but-unrequested.

Generation теперь требует только явно запрошенные сведения, atomic claims, без product overview/background. Если requested evidence отсутствует — claims=[] и конкретный вопрос о пробеле. Verification отдельно проверяет relevance каждой части утверждения; даже true claim или смешанный claim с лишней частью получает irrelevant. Вопросы также ограничены requested gaps/ambiguity, без вставок посторонних фактов. Статус supported означает одновременно evidence support и relevance.

Backend принимает bounded verdict irrelevant и не публикует такой claim/citation. Удаление лишь посторонней информации не создаёт искусственный gap в уже полном ответе. Unsupported/uncertain/deterministic rejection сохраняют прежнее fail-closed поведение. Если relevant claims не осталось — needs_support с вопросом, без factual answer. Нет enum planner, lexical keyword routing, правил под d11/d12, переписывания моделью или третьего LLM pass. Numeric/unit/quote/source revocation/citation checks не ослаблены. Смысловую relevance оценивает LLM, поэтому это проверяемое поведение, не абсолютная гарантия.

## Регрессии

4tests сначала FAIL на прежнем source: true-but-unrequested → только support question/no claims/no citations; удаление extras из полного ответа не делает partial; relevant partial сохраняется при удалении extras; mixed claim не публикуется целиком. После изменения40targeted application/provider/runtime/diagnostic tests PASS. Полные base/ONNX проверки запущены; actual outcomes и отдельные новые reports будут добавлены после завершения.

Предыдущие datasets/fixtures/measured reports неизменны. Новый live run допустим после изменения generation/verification contract: те же reviewed public synthetic15cases, provider/model/settings/local bundles; при первой infrastructure error последующие calls прекращаются. Human assessment отдельно, без заполнения полей от имени человека. No merge/deploy/real ingestion/site operation.


Конечный source `f41c25fb986c8e59b5db369dabda2843cfc02490`: base/ONNX `scripts/verify_offline.py` оба exit0,5project+228backend PASS (12/1skips),40targetedPASS.4новых tests RED→GREEN; numeric/source/policy boundaries сохранены. Прежний lexical baseline17/20 остаётся историческим измерением и не выдаётся за новый RAG quality score.

Fresh environment status перед live runs: current observations, restricted policy enforced, AITunnel destination разрешён, все3bindings ready и protected key scoped к api.aitunnel.ru. Секреты/headers/values не печатались; inherited proxy/CA сохранены. Один oracle затем один end-to-end выполняются на том же human-reviewed public synthetic наборе; observer сохраняет только synthetic decoded payload/result и fixed exception type/line в ignored work/, без изменения prompt/response или дополнительных calls. Итоги записываются после фактического завершения.


## Фактическая live проверка f41c25f

- Один oracle: exit0,15/15cases,0infrastructure errors, raw states answered5/partial6/needs_support3/clarification1. [Исходный report](../../evaluation/reports/2026-11-07-grounded-rag-oracle-relevance.json), SHA256 `9291b3eb8a8343cc60cc51e4bd16c7f294fa165ae24de91ade8bd4b754fd1862`.
- Один end-to-end: exit2; d01–d12 обработаны без error, d13 provider_invalid_or_unavailable_response во время verification, d14–d15 NOT_RUN. Raw states answered5/partial4/needs_support3/error1/not_run2. [Исходный report](../../evaluation/reports/2026-11-07-grounded-rag-end-to-end-relevance.json), SHA256 `43fa38b5875df3a354547c13bbc5253764a516ac7302b5625c376070bf2c58e1`.

Observer: oracle30completion calls; end-to-end26attempts (25decoded responses, последняя verification без decoded response). Ошибка остановила следующие calls, retries/model switches не было. Safe ProviderError не различает timeout/network/невалидный envelope/content; точная причина не установлена, не выдавать её за доказанный дефект relevance. Provider client/proxy/key/model/settings не менялись.

[Все ответы и новые SHA-bound pending human review forms](2026-11-07-grounded-rag-relevance-responses.md). В обоих режимах d10–d12 теперь needs_support без factual claims и sources: на взрывозащиту/цену не выдаются сторонние характеристики. В d06–d08 сохранены запрошенные части, убраны лишние protocol/interface/поверка. Oracle d01–d05 сохраняет requested facts; ambiguous/conflict handling записан без автоматического human verdict. Это наблюдения scope по actual outputs, не полный human quality score.

Требование владельца реализовано через generation+verification contract и backend suppression.4регрессии RED→GREEN подтверждают deletion/partial/complete/mixed cases; live cases демонстрируют отсутствие прежних вне-вопросных facts. Глобальная безошибочность семантического self-check не заявляется. End-to-end15/15 **не завершён успешно** из-за provider response error, human assessment/prototype/production acceptance pending.

Предыдущие initial/numeric-correction reports/dataset/fixtures неизменны. Source послеf41c25f не менялся; следующий checkpoint только docs/evidence. Повторной whole-branch reviewer петли нет. Docs/whitespace/report identity/hash-bound pending review checks выполняются перед push; exact-head CI фиксируется в PR13. Saturn-Main-Site не читался/не изменялся, merge/deploy/real ingestion не было.
