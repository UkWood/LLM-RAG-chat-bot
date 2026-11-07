# Передача контекста

## Рабочая точка: переход в новую среду — 2026-11-07

Владелец попросил сохранить работу для среды с добавленным API secret. Продолжать в ветке **docs/grounded-rag-redesign**, [PR13](https://github.com/UkWood/LLM-RAG-chat-bot/pull/13), не main и не старый V3. [Полный handoff и точные следующие шаги](handoffs/2026-11-07-grounded-rag-environment.md), [принятый дизайн](superpowers/specs/2026-11-07-grounded-rag-redesign-design.md), [план](superpowers/plans/2026-11-07-grounded-rag-implementation.md). Подход/реализация разрешены, inline метод сохраняется; повторное согласование не требуется.

Реализованы generic text/PDF snapshots и reuse existing retrieval, daily/manual atomic updater/live revocation, generic OpenAI-compatible client и core partial-answer orchestration. CLI пока умеет **только smoke**, full ask/runtime и15-case diagnostic ещё в работе.33targeted tests PASS; полные base+ONNX checkpoint verifiers5project+202backend PASS (12/1skips), отдельный actual OS PDF probe PASS. Реальный API/LLM quality NOT_RUN, final whole-branch review ещё впереди. Это WIP checkpoint, не завершение прототипа/deploy.

Новая среда: LLM_BASE_URL=https://api.aitunnel.ru/v1, LLM_MODEL=deepseek-v4.1-flash-1017, protected LLM_API_KEY. Сначала fresh environment-status/readiness и одна `PYTHONPATH=backend/src python3 -m saturn_ai.rag smoke` без раскрытия секрета. Work venv/model bundles ignored и могут не сохраниться; инструкции/identities в handoff. Saturn-Main-Site строго read-only; никаких live calls/сайтовых изменений до перехода не было. Прежние записи ниже исторические.


## Пересмотр: обычный RAG и частичные ответы — 2026-11-07

Владелец выбрал обычный RAG с проверкой подтверждений: отвечать на подтверждённую часть вопроса, пробелы формулировать вопросами с текстом «Для уточнения свяжитесь с поддержкой компании». [Подробный дизайн](superpowers/specs/2026-11-07-grounded-rag-redesign-design.md) и [ADR0011](decisions/0011-grounded-rag-redesign.md) пока PROPOSED; выбор подхода не равен согласию с ещё не рассмотренным документом. [Этап](stages/2026-11-07-grounded-rag-redesign.md).

Дополнение владельца: обновления автоматически; источник — опубликованный содержательный текст страниц и связанные PDF. Нестабильные категории/классификаторы не задают схему знаний. Рабочий дизайн дополнен lifecycle/policy версий; автоматический запуск раз в сутки и принудительный запуск авторизованным администратором согласованы. Используется готовая LLM по API (исходный предпочтительный вариант Qwen), без собственного обучения/дистилляции; обновляется KB, не веса LLM. Product code/registry не менялись.

Без обязательного enum planner перед поиском; исходный вопрос → existing hybrid/reranker → разрешённый context → сменная LLM → проверка утверждений/покрытия → ответ и вопросы к поддержке. Смысловая проверка LLM не является гарантией: первый шаг — малая открытая диагностика retrieval/oracle-context/end-to-end с настоящим разрешённым provider и оценкой человеком. Fake/mock только для code contracts; без runtime natural-generation quality NOT_RUN. Нового provider/model/sample/cloud допуска нет.

Отдельный fresh builder-check: важных вопросов, мешающих составить план, не осталось. Следующий шаг — принятие подробного документа, затем план небольшого диагностического этапа; product code/dataset/model runs ещё не начаты. Ветка docs/grounded-rag-redesign от main bb16530; [PR этой ветки](https://github.com/UkWood/LLM-RAG-chat-bot/pulls?q=is%3Apr+head%3Adocs%2Fgrounded-rag-redesign). V3 остаётся неслитым [draft PR12](https://github.com/UkWood/LLM-RAG-chat-bot/pull/12), его2/24+16/16и consumed dataset/START/report неизменны; не переносить его implementation в main. Saturn-Main-Site строго READ-ONLY. Исторические сведения ниже не отменяют новый выбор направления.


## Planner V2 corrective revision — 2026-11-06

Owner requested continuing after PR10 merge review found two Important blockers: discarded `нет` and protocol qualifiers. Corrections reject negation, unsupported Modbus/TCP/RTU qualification and modification requests outside supported lookup bindings before generation; unqualified protocol queries remain supported, V1 default unchanged. [Corrective report](stages/2026-11-06-planner-v2-corrections.md), [plan addendum](superpowers/plans/2026-11-06-typed-planner-v2.md). Final local verification5project+168backend PASS in both environments (base11optional skips/optional0), calibration14/14 positives20/20statuses without V1-positive regression; independent review fix pass complete. Current-head remote CI/merge outcome must be checked in PR10.

This is a post-blind corrective version. First experiment7bc6f11/dataset/START/report are immutable historical evidence; old8/24+14/16 numbers do NOT measure the corrected runtime. Its independent quality is NOT_RUN, prototype NOT accepted. No consumed-set replay/tuning or new safety/generalization claim. Fresh independent data/freeze needed before a future quality claim. Real sources/cloud unchanged; Saturn-Main-Site strictly READ-ONLY. Historical entries below describe earlier revisions.


## Typed planner V2: first blind assessment — 2026-11-06

Owner-approved PR9 design implemented in feat/typed-planner-v2; v1 remains default. Freeze7bc6f118e820fc5d4f648fb22997ad65d9e1c99c; independently authored/reviewed40case dataset consumed once after exclusive START. Actual V2 positives8/24, negative/ambiguity14/16, all22/40; V1 positives0/24, negative/ambiguity12/16. V2 emitted quote support/canonical validity1.0,unsafe0,errors0; quality target FALSE, full prototype NOT accepted. Calibration14/14 positives did not generalize. No code/config/grader changes after first result. [Stage report](stages/2026-11-06-typed-planner-v2.md), [first report](../evaluation/reports/2026-11-06-planner-v2-first-blind.json), [ADR0009](decisions/0009-typed-planner-v2.md).

Final local verification5project+161backend PASS in both environments (base11optional skips/optional0); independent review fixes RED→GREEN. Existing local bundles only, no new dependencies/approvals/cloud; Saturn-Main-Site strictly READ-ONLY. Next: separately designed/calibrated broader planner and fresh independent evaluation, not tuning on consumed cases or UI/cloud masking current coverage. Historical proposed/pending entries below superseded; publication/CI evidence appended after actual results.


## Актуально: после merge PR8, planner design — 2026-11-06

PR8 MERGED в maine0e44e54996b9f9e713899f7949746f27e33485b; main CI42209130861 SUCCESS проверен. Предыдущие open/unmerged сведения ниже исторические. Grounding quality остаётся8/20 positives, targetFalse; source-hit20/20 не означает answer20/20.

Подготовлен [proposed typed planner/projection design](superpowers/specs/2026-11-06-planner-expansion-design.md), [design report](stages/2026-11-06-planner-expansion-design.md). Код/новый dataset/benchmark НЕ создавались. Требуется принятие дизайна перед implementation. Рекомендация: compositional typed requirements, complete canonical fact groups, separate backend references, fresh independent blind set; semantic/generative router отдельно. Старые30cases сохранять как regression, tuning только calibration, не использовать exposed held_out как независимое доказательство. Новый proposed quality gate:24/24 positives +16/16 negative/ambiguity outcomes; меньший результат не является приёмкой. Saturn-Main-Site READ-ONLY, real sources/cloud по-прежнему закрыты.


## Текущий этап5: evidence gate — 2026-11-06

PR #7 MERGED в main861871b609f76ecad065e4b635e86ec3638b2cc8 после проверки clean head/all CI success; дальнейший merge нового PR не разрешён автоматически. Реализован bounded canonical evidence gate + Fake provider + exact claim/citation validation. [Design](superpowers/specs/2026-11-06-evidence-gate-design.md), [plan](superpowers/plans/2026-11-06-evidence-gate.md), [ADR0008](decisions/0008-evidence-gate.md), [stage report](stages/2026-11-06-evidence-gate.md).

Actual frozen dataset:8/20 positive answers, refusal8/8,clarification2/2,status accuracy.6,evidence recall.3; emitted claims/citations1.0,unsupported0. Held_out positives0/6. Grounding target NOT met, full prototype NOT accepted. Strict one-entity schema/manual grammar misses broader questions; keep failures, no held_out tuning. Source-hit20/20 prior retrieval remains valid but is not answer coverage. Next: separately designed/calibration-tested planner expansion before claiming full stage5/prototype acceptance; cloud/real sources still disabled. No new dependencies, Saturn-Main-Site READ-ONLY. Verification/review/PR evidence in stage report. Older sections below historical.


## Актуально: local reranking implementation — 2026-11-06

Owner approved design PR #6 and implementation. New bounded stage4 implemented after main92e7022: separate CPU pair scorer, canonical/policy-safe captured rerank and explicit atomic local preparation. Official mmarco-MiniLM revision1427fd652930e4ba29e8149678df786c240d8825 experiment: source-hit20/20, all-source/gold evidence1.0, MRR.916667,nDCG.867586; baseline hybrid17/20,nDCG.629721. Frozen data/settings; no held_out tuning. Retrieval target passes this small synthetic set only. Grounding/refusal/answer quality NOT_RUN, full prototype NOT accepted.

[Stage report](stages/2026-11-06-local-reranking.md), [accepted design](superpowers/specs/2026-11-06-local-reranking-design.md), [implementation plan](superpowers/plans/2026-11-06-local-reranking.md), [ADR-0007](decisions/0007-local-reranking.md). Prior proposed/open state below is historical. Weights/card/tokenizer only work/; explicit restoration required after environment replacement. License card Apache-2.0 declaration only, not production legal clearance. Next stage5 evidence gate/grounded pipeline; real sources pending, cloud disabled, Saturn-Main-Site READ-ONLY. Actual verification/review/publication follow in stage report; never infer merge from green CI.


## Актуальная точка продолжения — 2026-11-06

PR #5 уже MERGED в `92e70223c579d10dfc785263d24a23d92940c6c1`; main CI42166311910 success. Сведения об open PR #5 ниже исторические. Corpus/dataset frozen: BM25 17/20, E5 dense18/20, hybrid17/20; target100% unmet, reranking/grounding/refusal NOT_RUN.

Начат следующий этап: [proposed local reranking design](superpowers/specs/2026-11-06-local-reranking-design.md), [planning report](stages/2026-11-06-local-reranking-design.md). Implementation НЕ начата. После принятия дизайна составить detailed implementation plan и выполнять inline/TDD. Candidate cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 revision1427fd652930e4ba29e8149678df786c240d8825: прочитаны official card/config/tokenizer config; weights/hash/inference/license grant не проверены. card Apache-2.0 declaration не является legal clearance.

Saturn-Main-Site READ-ONLY, не допускать pending real sources, не изменять held_out под результат. Existing E5/operator artifacts только в work/, после смены среды могут отсутствовать.


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

## Публикация 2026-11-06

Commit b653014162b72b589eebd543a370a637f1dba92c опубликован в feat/embedding-model-preparation. [PR #5](https://github.com/UkWood/LLM-RAG-chat-bot/pull/5) открыт, не слит. [Push CI42165522960](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42165522960) на b653014 завершился success в обоих jobs, включая actual numeric preparation/swap tests. PR-event CI42165549055 на момент фиксации ещё in_progress; не считать его проверенным. Эта запись — отдельный docs commit, его CI следует проверять отдельно.

Публикация дизайна: [PR #6](https://github.com/UkWood/LLM-RAG-chat-bot/pull/6), branch feat/local-reranking-design, исходный commit55958ed. PR открыт, не принят/не слит; implementation не начата. CI проверять на текущем head PR, не выводить success из статуса предыдущих запусков.

## Публикация stage4

[PR #7](https://github.com/UkWood/LLM-RAG-chat-bot/pull/7), feat/local-reranking, implementation/fix commit2463ab0. PR открыт, НЕ слит. Design PR #6 закрыт как superseded: его accepted design и документация включены в #7; это не merge #6.

После review fix официальный pretrained benchmark повторён: metrics/baseline_metrics, все per-case ranks/raw scores и pinned identities точно совпали с committed report. Первоначальные timing measurements сохранены, повтор не используется для tuning. Full final base5+112PASS(skips11),optional5+112PASS(0 skips). Независимый review завершён, Important defect исправлен RED→GREEN, deferred product minors нет.

CI при публикации: push42168512725 и PR42168537774 на2463ab0 in_progress; это наблюдение, не заявление success. Проверять текущий head/actual checks в PR перед merge; новый docs commit проверяется отдельно. No automatic merge. Следующий отдельный stage5 — evidence gate/grounded pipeline, с собственным design/plan/quality gates.

Verified remote CI: [push42168613444](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42168613444) на d03a95d74535822f800b9cf02918eee7a7a863fe завершился SUCCESS, offline-checks и onnx-contracts (включая новые actual CPU pair contracts) оба success. Это CI реализации; данная запись — отдельный docs commit, его status проверять по текущему head PR #7. PR остаётся open/unmerged.

## Публикация

[PR #8](https://github.com/UkWood/LLM-RAG-chat-bot/pull/8), branch feat/evidence-gate, implementation commitf01ca77. PR открыт, НЕ слит; предыдущий PR7 merged861871b и main CI42169517262 SUCCESS. Текущие actual push/PR checks доступны в PR8; не выводить CI success из локальных тестов и не считать green CI quality acceptance.

Финальный actual replay после атомарного policy fix совпал с saved report по metrics/cases/model/snapshot/dataset identities. Единая optional команда завершилась strict_grounding_exit=1 именно из-за targetFalse, после133PASS backend tests; base verifier exit0. Ограниченная grammar/held_out0/6/false refusals не скрываются. Реальные source approvals/cloud/Saturn-Main-Site не менялись.

Публикация: [PR #9](https://github.com/UkWood/LLM-RAG-chat-bot/pull/9), feat/planner-expansion-design, initial commit1b14fb9. Design proposed, PR open/unmerged. До принятия владельцем код/new dataset не создавать. Актуальный CI смотреть на текущем head PR9; локальные doc checks не заменяют remote CI и не являются benchmark quality.

## Publication

[Implementation PR #10](https://github.com/UkWood/LLM-RAG-chat-bot/pull/10), branch feat/typed-planner-v2. PR open/unmerged; implementation freeze7bc6f11, first-result/report commitc0f0f3f. Docs-only PR9 superseded by this implementation including its owner-accepted design. Actual remote checks are available on the current head in PR10; local PASS is not a remote-CI claim or quality acceptance. The24/24+16/16 quality target remains FAILED. No runtime/config/grader change after freeze.
