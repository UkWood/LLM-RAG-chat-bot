# Передача контекста

## Продолжение 2026-11-06: actual checkpoint и измерение

Предыдущий сетевой blocker снят: runtime policy unrestricted/enforced, huggingface.co и us.aws.cdn.hf.co вернули HTTP200 через штатный proxy. Получен официальный intfloat/multilingual-e5-small revision614241f622f53c4eeff9890bdc4f31cfecc418b3; CPU smoke прошёл, artifacts только в ignored work/. Model card декларирует MIT; отдельного LICENSE нет, сохранена точная строка декларации, это не production legal clearance.

На неизменных 10docs/44chunks/30cases: dense source-hit@5=18/20 (calibration12/14, held_out6/6), hybrid17/20 (13/14,4/6), BM25 baseline17/20 (14/14,3/6). Цель100% не пройдена. Reranking/grounding/refusal NOT_RUN; M1 generator не менялся. Не подгонять held_out. Следующий шаг — отдельный план reranking/evidence gate и calibration-only улучшений; реальные источники по-прежнему pending/UNKNOWN, Saturn-Main-Site только чтение.

Проверки: base verifier 5 project +93 backend tests, 6 optional skips; optional verifier 5+93 без skips. Десять targeted preparation tests PASS; canonical URL regression RED→GREEN. Обновлён optional CI. Отчёт: [model preparation](stages/2026-11-06-model-preparation.md). Публикация/CI фиксируются ниже по фактическому результату. Прежние блокеры и сведения о PR #4 ниже исторические (PR #4 merged a1093fb).


## Точка перехода в новую среду — 2026-11-06

PR #4 слит: main `a1093fb826c27d68db215c0d2c0211d3d6e2ef2f`, CI42097546595 success (проверено до начала подготовки модели). Текущая ветка `feat/embedding-model-preparation` — промежуточная работа, ещё без PR/полной проверки и review. Прежние сведения ниже о незавершённом merge #4 исторические.

Владелец сообщил, что добавил huggingface.co в опубликованную конфигурацию. Текущая среда продолжает использовать spec_revision1, allowed_hosts только api.github.com/github.com (+package_managers); повторный HEAD официальной model card после сообщения владельца всё ещё CONNECT403/envoy (2026-11-06 04:29 UTC). Новую сессию запускать с обновлённой средой, сначала проверить effective policy и фактический HTTPS. Это сетевые правила среды, а не переменная приложения. Обход прокси/зеркала не использовать. Возможные дополнительные хосты для весов определять по фактическому redirect/отказу.

Сохранена WIP-подготовка: local explicit files/profile → pinned model/tokenizer/card/license provenance → CPU smoke → atomic new directory. Никаких моделей/секретов в Git. Numeric runtime_contract не допускается к semantic evaluation. Команда `PYTHONPATH=backend/src work/retrieval-venv/bin/python -m unittest discover -s backend/tests -p test_model_preparation.py -v`: 8 PASS, включая actual numeric ONNX, cleanup и конкурентное создание destination. Это только целевые проверки; общий CI/полный suite этой ветки ещё не проверены. Не заявлять готовность к merge.

Продолжить по [плану подготовки](superpowers/plans/2026-11-06-model-preparation.md): review импорта/provenance (включая canonical source URL и трактовку license_id как заявления оператора, не доказательства лицензии), CLI docs/profile example, optional CI для новых actual tests, full verification; затем actual checkpoint с проверенной model card/license/revision и dense/hybrid benchmark, если доступ появился. Candidate intfloat/multilingual-e5-small пока не выбран окончательно; license/weights/hash не проверены. Source-hit BM25 остаётся17/20, neural quality NOT_RUN. После этого stage report/ADR/status, PR и фактический CI. Виртуальные окружения под work/ могут не пережить смену среды: восстановить из requirements-onnx.lock.

Обновлено:2026-11-05, local retrieval baseline.

## Восстановление

Прочитать AGENTS.md, README, PROJECT_STATUS, [retrieval design](superpowers/specs/2026-11-05-local-retrieval-design.md), [report](stages/2026-11-05-local-retrieval.md), [prototype acceptance](acceptance/prototype-v1.md). PR #1/#2/#3 merged; база be71efde2b7a3f572d790d416bf642f3a9798017, main CI42089988455 success. Текущая ветка feat/local-retrieval-baseline, [PR #4](https://github.com/UkWood/LLM-RAG-chat-bot/pull/4); push CI42094770037 на95eb0b0 success в обоих jobs. Последние head/checks смотреть в GitHub и отчёте, не предполагать merge.

Python3.12: установить hash-locked backend/requirements.lock в work/venv, затем work/venv/bin/python scripts/verify_offline.py. Для optional runtime отдельный requirements-onnx.lock. После install всё CPU/offline, без ключей/GPU/языковой модели. work/venv и процессы не гарантируются после snapshot. Git/gh exec требуют sandbox network grant, proxy/credentials сохранять; не выводить секреты.

## Actual measurement

Corpus10docs/44chunks и dataset30cases неизменны. BM25 k1=1.2/b=.75 и schema aliases frozen до evaluation. Source-hit@5=17/20=.85, calibration14/14, held_out3/6. All-source80%, gold-evidence72.5%, MRR≈.701667. Failed q005/q013/q016 сохранены; target1.0 не достигнут. Preflight остаётся label validation, а measured lexical report отдельный.

Dense/hybrid/reranking/grounding/refusal NOT_RUN в quality report: владелец подтвердил, что local embedding checkpoint нет. Не представлять known CI vectors или authored numeric ONNX graph как neural benchmark. Actual Qdrant local/query/persistence/corruption/policy contracts проверены. No auto model downloads или cloud embeddings.

Local ONNX profile требует trusted owner-provisioned model.onnx/tokenizer.json/manifest.json, hashes, mean pooling, dimensions/prefixes/pad/output. External-data tensors запрещены recursively; runtime использует exact verified bytes (иначе unpinned sidecar/hash-load swap обходили identity). Optional CI выполняет numeric graph inference, sidecar и file-swap regression. Конкретная embedding-модель не выбрана; model-card/license и настоящий model benchmark впереди.

## Runtime boundaries

RetrievalService atomic pointer хранит actual IndexSet, проверяет полные artifacts до публикации. Explicit lexical-only не выдаёт себя за dual index. Current policy/revocations фильтруются до и после search, survivor ranks renumber передRRF; corpus rollback policy не откатывает. Returned text/citations брать из canonical snapshot, не model metadata. New retrieval ещё не подключён к M1 generator.

Process-local/local SDK до10000chunks, не server-Qdrant/multi-worker/durable publication. Qdrant float32 reopen tie rule: round6 только для ordering, raw scores сохраняются. Latency включает canonical reparse, не SLA. Raw corpus/index/model dumps и user logs в repo не сохранять.

## Следующие действия

Обеспечить локальный embedding artifact и провести dense/hybrid quality benchmark; далее reranking и evidence/grounding. Tune только calibration, не чинить held_out частными правилами. --require-source-hit-target даёт exit1 при85%; обычный code verification сохраняет измеренный failure, не объявляет prototype acceptance.

Полные права LLM-RAG-chat-bot сохраняются; обычные commits/push/PR без повторного запроса. Новые PR не считаются merged по green CI. Saturn-Main-Site строго READ-ONLY. Real registry8pending/UNKNOWN,allowed0; ничего не разрешать от имени владельца. До real ingestion нужны exact source approvals и OS parser sandbox/quality review; до cloud privacy/endpoint gates. ADR-0001 proposed, bounded decisions ADR-0002…0006.
