# ADR-0002: ограниченный synthetic-only M1

Дата: 2026-11-04. Статус: implemented для M1 по поручению владельца продолжить offline этап. Не заменяет proposed ADR-0001.

## Контекст и решение

Реальные источники не допущены; нужно проверить вертикальный pipeline без GPU, сетевых моделей и ключей. Выделен отдельный fixtures/synthetic manifest с authored вымышленными изделиями, test_only=true и cloud_allowed=false. Ingestion принимает exact byte hashes, explicit PUBLIC/approved и local scopes; запрещённые источники не индексируются.

Для M1 используются Python 3.12 standard library, immutable dataclasses, unittest, индекс в памяти, точное designation/aspect matching и два полных шаблона вопросов. Parser принимает только полную грамматику синтетического факта. Provider — offline test-only, возвращает claims; приложение требует буквальное совпадение с evidence и само строит citations. Denylist проверяется до и после provider. Результаты всегда test_only=true.

## Альтернативы и последствия

Сразу устанавливать production FastAPI/Pydantic/Qdrant/модели не требуется для M1 acceptance и добавило бы неиспользуемые зависимости. Свободное extractive копирование произвольного Markdown отклонено после regression с injection внутри раздела. Full-match грамматика сдерживает возможности и создаёт ложные отказы, зато явно проверяет bounded fixture flow без недоказанных эвристик confidence.

Это не benchmark поиска, не защита произвольных документов и не production schema. M2 заменит fixture adapter нормальным ingestion/policy; API-этап введёт Pydantic и locked dependencies. Возможности cloud, streaming, свободных консультаций и реальный sample не разрешаются этим решением. Никаких вымышленных owner approvals в production registry не добавлено.
