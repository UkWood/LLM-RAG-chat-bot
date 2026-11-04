# Передача контекста

Обновлено: 2026-11-04 после M1 merge и synthetic offline ingestion.

## Восстановление

1. Прочитать AGENTS.md, README.md, docs/PROJECT_STATUS.md и актуальные stage report/design/plan. Ветки и PR проверять по GitHub, не предполагать merge или сохранность work/venv и процессов.
2. M1 слит в main: PR #1, merge 0cfe174, CI 41798909615 success. Текущая ветка feat/offline-ingestion содержит этап 2; [PR #2](https://github.com/UkWood/LLM-RAG-chat-bot/pull/2), push CI 41801220416 на 88c2924 success; её публикация/CI описываются в [отчёте](stages/2026-11-04-offline-ingestion.md).
3. Проверки: python3 scripts/check_project.py; python3 -m unittest discover -s tests -v; затем backend suite в Python 3.12 venv с backend/requirements.lock. Установка с --require-hashes; команды в README. Lock пока Linux x86_64. После установки тесты offline, без моделей/ключей/GPU.
4. Проверить актуальный GitHub API, main SHA и CI. exec git/gh требуют sandbox network grant, proxy сохранять. Прежняя проблема CONNECT/Forbidden устранена; не менять токены и не просить заново разрешать api.github.com без фактической диагностики.

## Реализовано

M1: узкий synthetic-only RAG с FakeLLMProvider, источниками и отказами. Новый ingestion: строгий registry v1 runtime loader, immutable records, deny-before-read/hash/commit/scopes, Markdown site adapter и ограниченный PDF worker. Синтетические карточки и PDF tests не являются продукцией/документацией Сатурна. 41 backend + 5 прежних тестов PASS на текущем шаге; удалённый CI смотреть в актуальном PR.

Ingestion output отдельно от M1 evidence: произвольный parsed text нельзя направлять provider как проверенный факт. Реальный registry содержит 8 pending/UNKNOWN, allowed sources 0. Изменять permissions от имени владельца без основания нельзя.

## Следующий шаг и gates

Этап 3 — immutable snapshot/index contracts и local retrieval baseline на synthetic fixtures. Milestone M2 включает этапы 2–5 и не завершён. Полная production architecture ADR-0001 proposed; bounded offline implementation decisions — ADR-0002/0003.

До real ingestion нужны exact revision approvals, OS parser sandbox/egress и quality review. Процессные limits не заменяют sandbox. Поддержан ограниченный набор site fields; PDF tables/OCR, модели, Qdrant, реальная LLM, API/UI и deployment не реализованы. Ссылки карточки не разрешают PDF автоматически, downloader отсутствует.

## Полномочия

Полные права UkWood/LLM-RAG-chat-bot сохраняются: обычные изменения, commits/push/PR и проверки выполнять без повторного запроса. Merge M1 явно поручен владельцем. Новые интеграции фиксировать по факту, не выдавать green CI за merge.

UkWood/Saturn-Main-Site строго READ-ONLY. Не менять исходники, CI, URLs/assets, не делать commit/push. Pinned schema discovery: 084d759487bfab6e111549c9b5469711ac5fc13e. Не копировать служебные файлы/сайт в KB.

Историческая диагностика старой среды сохранена в Git-версии этого handoff до 0cfe174 и в предыдущих stage reports. Secrets — только защищённые настройки, не печатать environment/credential values. work/, /tmp и процессы не считаются долговременной памятью.
