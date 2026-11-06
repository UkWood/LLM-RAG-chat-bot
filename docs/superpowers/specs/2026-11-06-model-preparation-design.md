# Подготовка локального embedding checkpoint

Дата:2026-11-06. Следующий шаг после merged PR #4 a1093fb: реальные local dense/hybrid measurements. Владелец ранее подтвердил отсутствие checkpoint. Main CI42097546595 success. Hugging Face model-card HEAD сейчас возвращает CONNECT403 от envoy; runtime policy restricted/enforced не содержит huggingface.co. Это network blocker, не недостаток GitHub permissions. Запрос добавить host в опубликованную конфигурацию отправлен владельцу; elapsed time не является разрешением. Обход proxy/egress и зеркала не используются.

## Цель и решение

Подготовить независимую обратимую часть: reproducible local import из явно указанных trusted files, exact manifest/provenance и CPU smoke до atomic publication. Actual pretrained benchmark выполняется только при наличии настоящего checkpoint и проверенных model card/license; synthetic graph тестирует импорт, не семантику.

Альтернатива — скачивать неизвестный checkpoint автоматически из inference или выбирать model/конверсию без model-card — отвергнута. Приложение по-прежнему загружает только local files. Сеть используется отдельно оператором для получения публичных weights, после фактического разрешения нужных hosts. Model artifacts остаются в work/ или внешнем operator model storage, не в Git/KB.

Importer принимает model.onnx, tokenizer.json, model-card text, license text и profile JSON. Profile указывает model_id, exact source revision40hex, source URL, license ID и параметры существующего mean-pooling adapter. Hashes вычисляются по реально импортируемым bytes; model-card/license provenance записывается отдельно, не считается автоматической юридической экспертизой или production model selection. Разрешённые source URL только публичные https repo pages без auth/query/fragment; источник/card/license должны быть вручную проверены оператором. Никакие утверждения о реальном model ID/license не выдумываются при отсутствии доступа.

До publication временный каталог проходит LocalONNXEncoder validation (single-file/external-data/CPU), query+passage smoke и shape/finite/norm checks. Smoke текст синтетический и не берётся из evaluation gold labels. Неудаляемый существующий destination не перезаписывается; error оставляет предыдущую модель/соседние каталоги целыми, staging очищается. Prepared bundle содержит pinned model/tokenizer/manifest/provenance/card/license, без raw user data или secrets.

Smoke receipt включает exact hashes, identity, query/passages vectors hash и проверенные dimensions, но не сохраняет vectors/сырой input text. Повторный импорт тех же files/profile даёт одинаковые manifest/provenance/smoke receipt. Нельзя назвать smoke training/quality benchmark. Pooling/output/pad/prefix config проверяются по реальной model card до actual evaluation; нет fallback на чужие устройства/язык по предположению.

## Candidate discovery и gates

Official microsoft/unilm/e5 README подтверждает candidate multilingual-e5-small:12layers,384dimensions и ссылку на intfloat model repo. Это кандидат для CPU эксперимента, не production selection; SHA weights, exact revision, conversion и license модельной версии не проверены из-за HF block. При появлении доступа сначала проверяются model-card/config/license/ONNX availability, затем artifacts pin/import и unchanged calibration+held_out benchmark без подгонки.

## Проверки

TDD import success/determinism, corrupt hashes/malformed profile/URL/revision, invalid/external-data graph, output shape, file collision/symlink/partial failure и no model files in Git. Optional CI actual authored numeric graph для atomic import; base tests не требуют модели/ORT. Actual dense/hybrid report либо real measured с pinned identity, либо explicit blocked/not_run; BM25 report17/20 остаётся прежним.
