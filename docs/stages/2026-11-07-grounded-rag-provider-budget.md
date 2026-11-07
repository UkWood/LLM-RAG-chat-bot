# Task5: классификация provider failure и лимит ответа

Продолжение по прямому «Продолжай по плану», parenta83888e / PR13, тот же isolated checkout. Task5 tooling/source implementation уже есть; следующий независимый технический blocker — d13 verification provider_invalid_or_unavailable_response. Human fixture review подтверждён ранее, human answer review пока pending.

## Фактическое расследование

Fresh environment observations current, network enforced, destination api.aitunnel.ru разрешён,3bindings ready/protected key scoped к этому домену. Одно адресное обращение передало только сохранённый public synthetic d13 verification payload, без generation/retrieval replay и без automatic retry. Observer записал whitelist metadata: response bytes/hash, choices count/type, whitelisted finish_reason, content type, exception types/line; не body/header/key/env values.

[Безопасный probe report](../../evaluation/reports/2026-11-07-grounded-rag-d13-provider-probe.json):13.122s, HTTP response received,1choice, finish_reason=length, content_type=NoneType, request max_tokens2048. Это воспроизводимый truncation исхода для того же payload; старый общий код скрывал отличие от network/JSON error. Исходное тело первого исторического d13 не сохранено, поэтому нельзя утверждать, что именно оно имело тот же envelope. Первый диагностический error остановил calls; дальнейших live обращений до изменения проверяемого компонента/бюджета не было.

## Исправление диагностируемости

Строгие границы не ослаблены: finish_reason=length → output_truncated; invalid envelope/choices → invalid_response_envelope; invalid model JSON/content → invalid_response_content; tools/other finish shape → unsupported_response_shape; timeout → timeout, transport errors → transport_unavailable, HTTP statuses по-прежнему http_*. Никаких exception/body/header/secret values в reason_code, redirects/retries/fallback/model switch не добавлены. Malformed choice/message закрываются ProviderError вместо случайного AttributeError.

2новых tests сначала дали7FAIL на старом provider (table subcases+timeout); после изменения42targeted application/provider/runtime/diagnostic PASS. Полные base/ONNX source checks запускаются заново из-за изменения клиента.

Следующий единственный oracle/end-to-end diagnostic profile использует max_tokens4096 вместо2048 по наблюдаемому finish_reason=length. Это bounded operator override внутри существующего16…8192, не новый provider/model или ослабление complete/JSON requirements. Default generic budget в коде остаётся2048; прикладной tested profile явно фиксируется в report identity/командах. Prompts/fixtures/retrieval/models unchanged. Если снова будет infrastructure error — остановить следующие calls, без увеличивающего цикла/retry. Отдельные новые reports с SHA-bound pending reviews; старые reports неизменны.

Task5 acceptance требует human answer assessment. Общее «продолжай» не заполнение quality grades; no merge/deploy/site/real ingestion.


Полные source checksac4d289: `work/base-venv/bin/python scripts/verify_offline.py` и `work/venv/bin/python scripts/verify_offline.py` оба exit0,5project+230backendPASS (12/1skips),42targetedPASS. Старые report/dataset files не менялись. [Public synthetic сохранённый d13 request](../../evaluation/reports/2026-11-07-grounded-rag-d13-verification-request.json) содержит точный request/prompt hashes, question/evidence/claims без credentials/header; предназначен только для адресного воспроизведения с явным основанием, не automatic retry.


## Единый profile4096: фактические результаты

Sourceac4d289, явный max_tokens4096, неизменные API/model/prompts/fixtures/pinned bundles. Один oracle и один end-to-end: оба exit0,15/15cases,0infrastructure errors,30completion calls на режим. Raw states одинаковы: answered5/partial6/needs_support3/clarification1; это не human correctness scores. D13 завершён, d14/d15 не пропущены; d10–d12 без factual claims/citations, d06–d09 только requested confirmed parts.

- [Oracle report](../../evaluation/reports/2026-11-07-grounded-rag-oracle-budget4096.json), SHA256 `0f80c8ef5411401885ff50e8f4d7d170c3eadb695476d04fccebaae2e28fb524`.
- [End-to-end report](../../evaluation/reports/2026-11-07-grounded-rag-end-to-end-budget4096.json), SHA256 `5d6d417908cf82fd3b3a115e2b7ee258af1fbd067f4da49c01d13d4da7130b3f`.
- [Все responses/evidence и новые SHA-bound pending human review forms](2026-11-07-grounded-rag-budget4096-responses.md).

Observer d15 в обоих режимах зафиксировал deterministic rejection двух drafts: они содержали номер редакции1 при коротких quotes только о24/48В. Guard не ослаблялся; final response — вопрос о противоречии24/48В, без выбора напряжения/совета подключения. Остальных exception/rejection events не наблюдалось. Это раскрытая technical detail для human assessment, не quality verdict.

Task5 technical tooling/fixtures/smoke/operator docs отмечены по факту; отдельная human answer assessment остаётся pending. Task6 review/fix/source verification/publish work выполнены, current-head CI фиксируется в PR13. Нет нового reviewer loop/consumed evaluation replay. Source послеac4d289 не менялся, следующий checkpoint docs/evidence; прежние reports/dataset/fixtures неизменны.

Следующий обязательный вход — оценка человеком всех15responses в обоих режимах: факты, полнота/релевантность, false refusals/unsupported claims, citations и support questions. Ранее получено fixture approval, но не answer acceptance. Prototype/production не приняты, no merge/deploy/site operation.
