# Model preparation: промежуточная точка

2026-11-06. Ветка feat/embedding-model-preparation от a1093fb.

Подготовлены дизайн/план, explicit local import/provenance/CPU smoke и semantic evaluation gate. Целевые 8 тестов прошли, включая actual numeric ONNX; semantic quality не измерена. Работа WIP: full verification, независимый review, документация CLI/profile, optional CI и PR ещё не завершены.

Официальная model card на huggingface.co в текущей среде получает CONNECT403/envoy даже после сообщения владельца об обновлении настройки. Проверка среды показала старый allowed_hosts и spec_revision1. Владелец переводит продолжение в новую среду; проверить доступ перед скачиванием. Модели, hashes, license и model revision не выдумывать. Ни реальные источники, ни Saturn-Main-Site не изменялись.

Точка восстановления и следующие действия: [HANDOFF](../HANDOFF.md), [план](../superpowers/plans/2026-11-06-model-preparation.md). Эта запись фиксирует промежуточное состояние, а не завершение этапа.
