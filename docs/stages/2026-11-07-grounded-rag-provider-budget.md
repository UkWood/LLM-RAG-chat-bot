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
