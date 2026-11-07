# Grounded RAG: исправление потери claims из-за цифр в названиях

Продолжение PR13 после cab5f40, разрешено владельцем «продолжай». Принятый ordinary-RAG дизайн/inline метод сохраняются. First measured oracle/end-to-end reports, fixtures и datasets не меняются; human answer assessment pending.

## Причина и границы evidence

Одна адресная проверка d03 end-to-end на прежнем source cab5f40 с безопасным trace только authored synthetic request/JSON responses, без headers/key/env, дала два фактических claims: питание Лира-22 12В и Лира-21 24В. Точные короткие quotes присутствуют в context. Оба rejected до semantic verification: numbers(claim) содержит цифры имени изделия, numbers(short quote) их не содержит. Verification получила пустой claims list и вернула вопрос в поддержку. [Неизменный debug trace](../../evaluation/reports/2026-11-07-grounded-rag-d03-debug-trace.json). Это целевая диагностика unresolved failure, не повторный quality benchmark.

Первоначальный d03 pipeline_unavailable **не воспроизведён**. Trace этого запуска не содержит исходного exception первого измерения. Причина того error не установлена; нельзя называть её исправленной или приписывать провайдеру. GeneratorExit в trace — обычное закрытие generator expression, не ошибка результата.

## Минимальное исправление

Идентификаторы с буквами и цифрами (включая дефис) сверяются точными tokens только с текстом цитируемых chunks. Они исключаются из numeric-subset проверки как названия, а не технические величины. Нельзя использовать имя из другого нецитируемого source или его префикс. Оставшиеся числа и знаки, а также величины/единицы по-прежнему требуют exact quote support; semantic verification и live eligibility обязательны. Нет правил под конкретные вопросы/Лира/Орион, собственного planner или tuning expected labels.

Ошибки теперь имеют fixed codes этапа: invalid_generation_response, invalid_verification_response либо retrieval/generation/verification/render_unavailable. ProviderError сохраняет прежние безопасные provider_* codes. Exception messages, raw responses, credentials в публичный answer/error code не включаются; retries/self-rewrite не добавлены.

## Проверка

Сначала7регрессионных tests:6FAIL/1PASS на прежнем коде. После исправления34targeted application/provider/runtime/diagnostic tests PASS. Проверяются принятие корректного named claim с короткой quote, RS-485, знак температуры, отклонение invented values/units/другого изделия и fixed error codes без exception disclosure. Полные base/ONNX проверки и новые live measurements записываются после фактического завершения.

Следующий diagnostic разрешён изменением проверяемого компонента, с теми же human-reviewed fixtures/provider/models; при первой infrastructure error последующие API calls прекращаются. Новые runtime statuses не являются human quality grades. No merge/deploy/site operation/real ingestion.


Полные проверки первого варианта исправления до focused review: `work/base-venv/bin/python scripts/verify_offline.py` и `work/venv/bin/python scripts/verify_offline.py` → оба exit0,5project+222backend PASS (12/1skips); docs checker/whitespace PASS. Legacy lexical baseline17/20 остаётся ожидаемым measured target failure, не результатом новой LLM. Optional OS PDF isolation test не повторялся: extractor не менялся.


Один focused correction review выявил Important: digits в quote-only идентификаторе RS-485 могли подтвердить invented485каналов; Minor: БП-12В ошибочно распознавался как величина -12В. Последнее переклассифицировано как Important для текущего исправления: обычное название с суффиксом единицы всё ещё нарушало целевой contract. Оба findings независимо воспроизведены2новыми RED tests и исправлены одним проходом: identifier spans исключаются на обеих сторонах и из чисел, и из quantities, после проверки exact cited-context backing.36targeted tests PASS. Повторного reviewer loop нет. Полные проверки конечного варианта запущены заново из-за этих source changes; их actual outputs и новые measurements будут записаны отдельно.


Конечный source commit `6f7e728a642ac7010c9d6e93fa5a66a7cbb0b41f`: повторные base/ONNX verify_offline оба exit0,5project+224backend PASS (12/1skips); targeted36PASS. Дополнительные2tests воспроизвели findings ревью RED→GREEN; теперь numeric evidence не берётся из цифр quote-only identifiers, а суффикс единицы в backed identifier не становится величиной. Это9новых tests относительно215backend на прежнем source.

Новые diagnostics запускаются один раз на6f7e728 через observer `work/run_traced_diagnostic.py` вокруг штатного `rag_diagnostic.main`, с теми же runbook arguments: mode oracle/end-to-end, reviewed-fixtures/allow-cloud/public-questions, прежние model dirs. Observer сохраняет только authored synthetic decoded payload/result и function/line/exception type локально в ignored work/, не headers/client/env/exception text; он не меняет prompt/response и не добавляет calls. End-to-end начинается только если oracle exit0.


## Фактические measurements после исправления

На source6f7e728 выполнены один oracle и один end-to-end, оба exit0,15/15cases каждый,0infrastructure errors. Observer зафиксировал30HTTP completion calls в каждом режиме (generation+verification), events empty: exception/rejected-candidate events не наблюдались. Нет retries/provider/model/prompt/fixture switches. Первые measurements и dataset SHA256 проверены неизменными.

- [Oracle report](../../evaluation/reports/2026-11-07-grounded-rag-oracle-numeric-correction.json): SHA256 `813a9d6335ee3e2fdb9d006b94ee64dbd7ee4bc65c762cc81c09242484301131`, raw statuses answered5/partial8/needs_support2.
- [End-to-end report](../../evaluation/reports/2026-11-07-grounded-rag-end-to-end-numeric-correction.json): SHA256 `bd5c9db7bde8d91bb2b5869b8d23bb5f4bdb3e9588c38c29762108e5ff56c9d2`, raw statuses answered5/partial9/needs_support1.

[Все новые ответы/evidence и отдельные SHA-bound pending human reviews](2026-11-07-grounded-rag-corrected-responses.md). Runtime statuses **не оценки правильности**. d01–d04 теперь содержат питание/интерфейс/протокол/поверку, которые прежде терялись, а d03 сравнивает12В и24В. Это наблюдение по outputs, не human score.

Открытые вопросы качества: в d11/d12 end-to-end приводит подтверждённые, но не отвечающие на вопрос факты; oracle d12 тоже добавляет назначение/поверку вместо одной поддержки по отсутствующей цене. d15 сохраняет оба конфликтующих значения с указанием source и вопросом о приоритете; его пригодность должен отдельно оценить человек, не self-verifier. Human answer assessment pending, prototype/production **не приняты**. Дальше — оценка этих реальных responses и работа над релевантностью, без подгонки под конкретные question strings.

Причина первого d03 pipeline_unavailable остаётся неизвестной: targeted trace и исправленные runs её не воспроизвели. Объявлять этот исходный error исправленным нельзя; новые phase codes позволят локализовать повторение без раскрытия тела/ключа. Code/source tests подтверждают устранение numeric-name rejection, а новые runtime runs — отсутствие infrastructure errors в данных конкретных запусках.

Решения implementer: exact token-backed identifier handling вместо отключения numeric guard; проверка cited chunks вместо всего context pool; unit-suffix finding переклассифицирован как Important и исправлен в одном pass. Риск: синтаксические tokens не доказывают семантическую принадлежность значения изделию; semantic verifier и human assessment остаются обязательными. Нет deferred reviewer findings после2RED→GREEN fixes; остающиеся вопросы model relevance/human quality не скрыты. Один focused review, без повторного reviewer loop.

Local docs/whitespace/report identity/SHA-bound review checks выполняются перед публикацией; current-head CI проверяется и фиксируется в PR13. Source unchanged после6f7e728, последующий checkpoint только docs/evidence. Saturn-Main-Site не читался/не изменялся; real ingestion/merge/deploy/service activation не выполнялись.
