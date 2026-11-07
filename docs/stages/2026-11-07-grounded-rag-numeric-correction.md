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
