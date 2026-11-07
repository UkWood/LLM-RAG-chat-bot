# Исключение сведений вне вопроса

Владелец прямо потребовал: «Сведения вне вопроса нужно исключить». Это уточнение existing accepted ordinary-RAG behavior, не новая архитектура/пересогласование подхода. Parent74e5878 / PR13, существующий isolated checkout. Человек не принял качество всех прежних ответов; human answer assessment остаётся pending.

## Причина и исправление

Предыдущие live reports показывают d11/d12: неизвестная взрывозащита/цена сопровождались правдивыми характеристиками, которые не отвечали на вопрос. Generation prompt разрешал перечислять подтверждённые факты без явного ограничения requested scope; verification проверяла evidence support и полноту, но не давала отдельного исхода для true-but-unrequested.

Generation теперь требует только явно запрошенные сведения, atomic claims, без product overview/background. Если requested evidence отсутствует — claims=[] и конкретный вопрос о пробеле. Verification отдельно проверяет relevance каждой части утверждения; даже true claim или смешанный claim с лишней частью получает irrelevant. Вопросы также ограничены requested gaps/ambiguity, без вставок посторонних фактов. Статус supported означает одновременно evidence support и relevance.

Backend принимает bounded verdict irrelevant и не публикует такой claim/citation. Удаление лишь посторонней информации не создаёт искусственный gap в уже полном ответе. Unsupported/uncertain/deterministic rejection сохраняют прежнее fail-closed поведение. Если relevant claims не осталось — needs_support с вопросом, без factual answer. Нет enum planner, lexical keyword routing, правил под d11/d12, переписывания моделью или третьего LLM pass. Numeric/unit/quote/source revocation/citation checks не ослаблены. Смысловую relevance оценивает LLM, поэтому это проверяемое поведение, не абсолютная гарантия.

## Регрессии

4tests сначала FAIL на прежнем source: true-but-unrequested → только support question/no claims/no citations; удаление extras из полного ответа не делает partial; relevant partial сохраняется при удалении extras; mixed claim не публикуется целиком. После изменения40targeted application/provider/runtime/diagnostic tests PASS. Полные base/ONNX проверки запущены; actual outcomes и отдельные новые reports будут добавлены после завершения.

Предыдущие datasets/fixtures/measured reports неизменны. Новый live run допустим после изменения generation/verification contract: те же reviewed public synthetic15cases, provider/model/settings/local bundles; при первой infrastructure error последующие calls прекращаются. Human assessment отдельно, без заполнения полей от имени человека. No merge/deploy/real ingestion/site operation.
