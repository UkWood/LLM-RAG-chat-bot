# Открытая synthetic диагностика

Все приборы, тексты и URL вымышлены и написаны для этой проверки. Нет копирования Saturn-Main-Site или старых consumed blind sets. Это открытый набор, не blind acceptance и не показатель работы на настоящем сайте.

`evaluation/datasets/grounded-rag-open-v1.json` содержит15вопросов:5full/4partial/3missing/2ambiguous/1conflict. Expected evidence — точные подстроки HTML main text; gaps — инструкции человеку, не генератору. Oracle передаёт только IDs соответствующих canonical chunks. End-to-end не получает gold context или ожидаемые ответы.

Перед первым LLM-прогоном человек проверяет вопросы, evidence/gaps и пригодность сценариев. Только после этой проверки оператор использует `--reviewed-fixtures`. Author/code-review не заменяет domain/human acceptance; сейчас review pending. Retrieval-only разрешён как техническая диагностика до этой проверки.

Для оценки скопировать `evaluation/human-review-template.json`, заполнить имя reviewer, SHA256 измеренного отчёта и отдельную запись для каждого из15case IDs. Сопоставить original question, expected evidence/gaps, фактические claims/quotes/backend citations. Указывать false refusals, неподтверждённые утверждения, пропуски, неверные вопросы поддержки и infrastructure errors отдельно. `null` означает pending, а не успех. Не подставлять verdicts проверяющей LLM вместо оценки человека. Сохранить review отдельно в evaluation/reviews/; не переписывать исходный измеренный отчёт.
