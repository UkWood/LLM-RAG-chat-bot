# Этап M1: синтетический offline RAG

Дата: 2026-11-04. Ветка feat/m1-offline-rag. Продуктовый commit: fd0598b.

Решения зафиксированы в [ADR-0002](../decisions/0002-synthetic-offline-m1.md).

## Результат и решения

Поручение владельца продолжить M1 применено только к synthetic/offline вертикальному срезу. Это не приёмка всей production архитектуры, ADR-0001 остаётся proposed; реальные источники pending/UNKNOWN и не индексировались. Saturn-Main-Site не изменялся и не использовался для fixture data.

Реализованы immutable dataclass contracts, строгий отдельный test-only manifest с byte SHA-256, parser синтетических Markdown sections, in-memory index, entity/aspect retrieval, evidence gate, сменный LLMProvider protocol и FakeLLMProvider, extractive claim validation, backend-only citations и CLI. Политика проверяется до индексации, перед генерацией и перед выдачей; runtime denylist блокирует отзыв в ходе генерации. INTERNAL не достигает provider. Ошибка provider возвращает error без исключения/секретов; отсутствие evidence — refusal без вызова provider.

Решение для M1: Python standard library без зависимостей, сетевых запросов и моделей. Dataclasses вместо production Pydantic и unittest вместо целевой pytest-команды позволяют запускать срез в существующей offline CI среде. При API-этапе нужны production схемы и dependency lock. Provider не возвращает URL; каждое утверждение должно буквально совпадать с текущим evidence. Одного валидного chunk ID недостаточно.

При проверке найден пробел heading-only parser: инструкция внутри поддерживаемого раздела проходила как evidence. Новый тест сначала воспроизвёл сбой, затем parser ограничен полной грамматикой учебного факта. Неподдерживаемое содержимое не индексируется. Это узкий adapter для authored fixtures, не универсальное решение prompt injection или grounding произвольных документов.

## Фактическая проверка

- Baseline: python3 scripts/check_project.py PASS; 5 прежних unittest PASS.
- RED: backend discovery вернул ModuleNotFoundError saturn_ai.application до реализации.
- GREEN: PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v — 15 тестов PASS (до финального review).
- Проверены характеристика/источник, поиск руководства, no_evidence, неизвестное изделие, неоднозначность, user/document injection, INTERNAL/UNKNOWN/pending/revoked/scopes, byte drift, manifest tampering/path traversal, fabricated claims, отзыв до/во время генерации, ошибка provider и запрет cloud.
- CLI: DEMO-100 → answered, учебный RS-485, source demo-100, heading Интерфейсы, SHA-256 и chunk ID. DEMO-999 → refused/unknown_entity, sources=[], grounding=[]. Обе команды завершились с exit 0. Отказ является нормальным результатом CLI.
- git diff --check PASS. CI расширен backend unittest suite, предыдущие проверки сохранены.

## Независимое review и исправления

Review fd0598b выявило три Important: частичный ответ на смешанный/отрицательный вопрос; совпадение известного префикса неизвестной модели DEMO-100.5 или DEMO-100/999; принятие дубликатов JSON policy keys. Minor: невалидные типы manifest приводили к traceback вместо контролируемой ошибки.

Регрессионные тесты воспроизвели все замечания (RED). Исправления: full-match грамматика двух поддержанных вопросов, захват суффикса обозначения целиком, JSON object_pairs_hook с запретом повторов и проверки типов до set/membership. Теперь 20 backend tests PASS. Повторная независимая проверка исходных probes и всех 20 тестов подтвердила исправление четырёх замечаний; residual Important в этой области не найдено. User injection безопасно отказывается; документная injection не попадает в context/ответ. Стоимость строгой грамматики — ложные отказы для иных естественных формулировок, что допустимо и явно ограничено M1 fixtures.

## GitHub и сеть

GitHub connector API доступен, права admin/push подтверждены. git/gh через обычный sandbox получили socket/proxy failure; с предоставленным инструментом network grant и прежним proxy fetch и gh API успешны. Токены не менялись и не выводились.

Получен main 7aa59e4 (handoff). Прежние Actions действительно success:

- [41707910933](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/41707910933), 0b199b3.
- [41708009193](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/41708009193), b6be294.
- [41792968340](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/41792968340), 7aa59e4.

PR и результаты CI новой ветки будут записаны после фактической публикации. Branch protection/CD не настраивались и не заявляются активными.

## Ограничения и следующий шаг

Это M1 fixture profile с точным entity matching и двумя intents, без dense/BM25/reranker, PDF, сервера/API/UI, privacy classifier и реальной LLM. Fictional fixtures не показывают качество русского поиска или инженерных консультаций. Ссылки example.invalid намеренно не ведут к реальным документам. Stream, sessions и request IDs относятся к будущему API-контракту.

Следующий продуктовый этап: ingestion adapter сайта/PDF и runtime PUBLIC registry enforcement; реальный sample — только после явного допуска exact revisions. До него можно расширять parser/policy на синтетических fixtures. Cloud/production по-прежнему закрыты.
