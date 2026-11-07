# Ответы с лимитом4096 после диагностики d13

Source commit: `ac4d28983ee0a78f570d6310decad5a9b5cd479c`. Те же15 human-reviewed открытых synthetic сценариев, AITunnel/deepseek-v4.1-flash-1017, temperature0/max_tokens4096/JSON mode, прежние pinned E5/reranker. После воспроизведения finish_reason=length на2048 применён operator max_tokens4096 и безопасные provider reason codes. Промпты generation/verification, provider/model/dataset/numeric guard и исключение irrelevant не менялись. Generic default2048 в коде остаётся прежним; profile4096 указан явно. Один новый запуск каждого режима, без retries.

Human answer assessment **pending**. Runtime statuses и self-verifier не являются оценкой правильности. Эти повторные открытые измерения — проверка ответа при новом token budget, не blind/generalization/production acceptance. Первые исходные отчёты неизменны: [первая страница](2026-11-07-grounded-rag-first-responses.md).

## Состояния runtime, не human grades

| Режим | Выполнено | Infrastructure errors | Raw statuses |
| --- | --- | --- | --- |
| oracle | 15/15 | 0 | answered: 5, partial: 6, needs_support: 3, clarification: 1 |
| end-to-end | 15/15 | 0 | answered: 5, partial: 6, needs_support: 3, clarification: 1 |

- [Measured oracle report](../../evaluation/reports/2026-11-07-grounded-rag-oracle-budget4096.json), SHA256 `0f80c8ef5411401885ff50e8f4d7d170c3eadb695476d04fccebaae2e28fb524`. [Отдельная форма human review](../../evaluation/reviews/2026-11-07-grounded-rag-oracle-budget4096-pending.json).
- [Measured end-to-end report](../../evaluation/reports/2026-11-07-grounded-rag-end-to-end-budget4096.json), SHA256 `5d6d417908cf82fd3b3a115e2b7ee258af1fbd067f4da49c01d13d4da7130b3f`. [Отдельная форма human review](../../evaluation/reviews/2026-11-07-grounded-rag-end-to-end-budget4096-pending.json).

Заполнить reviewer и поля каждого case отдельно: correct_full_or_partial, false_refusal, unsupported_claims, citations_correct, missing_requested_parts, support_questions_correct, infrastructure_error, notes. Формы уже привязаны к точному SHA256 отчёта; null остаётся pending. Проверить принадлежность facts изделию/модификации, единицы, полноту и конфликт d15. Не заменять оценку человеком verdicts самой LLM.

## d01 — full

**Вопрос:** Какие питание и интерфейс у Лира-21?

**Evidence:**

- `lira21.html`: Напряжение питания 24 В.
- `lira21.html`: Интерфейс RS-485.

**Пробелы/условия:** Нет.

### oracle: `answered`

> Напряжение питания Лира-21 составляет 24 В. [1]
> Интерфейс Лира-21 — RS-485. [1]

- Claim `c1` quote: Напряжение питания 24 В.; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Claim `c2` quote: Интерфейс RS-485.; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.

### end-to-end: `answered`

> У Лира-21 напряжение питания 24 В. [1]
> У Лира-21 интерфейс RS-485. [1]

- Claim `c1` quote: Напряжение питания 24 В.; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Claim `c2` quote: Интерфейс RS-485.; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.

## d02 — full

**Вопрос:** Какой протокол поддерживает Лира-21?

**Evidence:**

- `lira21.html`: Поддерживаемый протокол Modbus RTU.

**Пробелы/условия:** Нет.

### oracle: `answered`

> Лира-21 поддерживает протокол Modbus RTU. [1]

- Claim `c1` quote: Поддерживаемый протокол Modbus RTU; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.

### end-to-end: `answered`

> Лира-21 поддерживает протокол Modbus RTU. [1]

- Claim `c1` quote: Поддерживаемый протокол Modbus RTU.; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.

## d03 — full

**Вопрос:** Сравните напряжение питания Лира-21 и Лира-22.

**Evidence:**

- `lira21.html`: Напряжение питания 24 В.
- `lira22.html`: Напряжение питания 12 В.

**Пробелы/условия:** Нет.

### oracle: `answered`

> Напряжение питания Лира-21 составляет 24 В. [1]
> Напряжение питания Лира-22 составляет 12 В. [2]

- Claim `c1` quote: Напряжение питания 24 В; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Claim `c2` quote: Напряжение питания 12 В; chunk `d677c7c3bc26676585077ec4e9dffd9161db3cd360f7f128bf5c312521cfe727`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.
- Citation [2]: `lira22`, `https://example.invalid/rag-diagnostic/lira22.html`, SHA256 `000bac4472659b33ec9720c35fb471dd06b66a703ee9ee495ac95d7a2fcc28ed`.

### end-to-end: `answered`

> Напряжение питания Лира-21 составляет 24 В. [1]
> Напряжение питания Лира-22 составляет 12 В. [2]

- Claim `c1` quote: Напряжение питания 24 В; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Claim `c2` quote: Напряжение питания 12 В; chunk `d677c7c3bc26676585077ec4e9dffd9161db3cd360f7f128bf5c312521cfe727`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.
- Citation [2]: `lira22`, `https://example.invalid/rag-diagnostic/lira22.html`, SHA256 `000bac4472659b33ec9720c35fb471dd06b66a703ee9ee495ac95d7a2fcc28ed`.

## d04 — full

**Вопрос:** Как часто поверяют Орион-110?

**Evidence:**

- `orion.html`: Межповерочный интервал 12 месяцев.

**Пробелы/условия:** Нет.

### oracle: `answered`

> Межповерочный интервал Орион-110 составляет 12 месяцев. [1]

- Claim `c1` quote: Межповерочный интервал 12 месяцев.; chunk `0ccfad939dd29d4686b90884e1471858bd707fd80077b9bb31be2a1d513b8807`.
- Citation [1]: `orion`, `https://example.invalid/rag-diagnostic/orion.html`, SHA256 `195b34d7e4ecb2f8e178c10bfbb9fe345ed1912c7a6b3580aac41e105b762efe`.

### end-to-end: `answered`

> Межповерочный интервал Орион-110 составляет 12 месяцев. [1]

- Claim `c1` quote: Межповерочный интервал 12 месяцев.; chunk `0ccfad939dd29d4686b90884e1471858bd707fd80077b9bb31be2a1d513b8807`.
- Citation [1]: `orion`, `https://example.invalid/rag-diagnostic/orion.html`, SHA256 `195b34d7e4ecb2f8e178c10bfbb9fe345ed1912c7a6b3580aac41e105b762efe`.

## d05 — full

**Вопрос:** Какой диапазон давления у Вега модификации А?

**Evidence:**

- `vega-a.html`: Диапазон давления от 0 до 10 бар.

**Пробелы/условия:** Нет.

### oracle: `answered`

> Диапазон давления у Вега, модификации А: от 0 до 10 бар. [1]

- Claim `c1` quote: Диапазон давления от 0 до 10 бар.; chunk `208b1211fae937d34a3a63504c7c0d2ba85c3c2b9ef27951ee3d2916780313a8`.
- Citation [1]: `vega-a`, `https://example.invalid/rag-diagnostic/vega-a.html`, SHA256 `7e5bca4aa8bee11f906c12bb0a408a3d88392a54d3b40f532178ee7848c6b10b`.

### end-to-end: `answered`

> У Вега модификации А диапазон давления от 0 до 10 бар. [1]

- Claim `c1` quote: Диапазон давления от 0 до 10 бар.; chunk `208b1211fae937d34a3a63504c7c0d2ba85c3c2b9ef27951ee3d2916780313a8`.
- Citation [1]: `vega-a`, `https://example.invalid/rag-diagnostic/vega-a.html`, SHA256 `7e5bca4aa8bee11f906c12bb0a408a3d88392a54d3b40f532178ee7848c6b10b`.

## d06 — partial

**Вопрос:** Назовите интерфейс Лира-21 и скажите, поддерживает ли он BACnet.

**Evidence:**

- `lira21.html`: Интерфейс RS-485.

**Пробелы/условия:** Поддержка BACnet неизвестна, отсутствие сведений не доказывает отсутствие поддержки.

### oracle: `partial`

> Интерфейс Лира-21 — RS-485. [1]
> Поддерживает ли Лира-21 BACnet?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Интерфейс RS-485.; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.

### end-to-end: `partial`

> Интерфейс Лира-21 — RS-485. [1]
> Поддерживает ли Лира-21 протокол BACnet?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Интерфейс RS-485.; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.

## d07 — partial

**Вопрос:** Как питается Лира-22 и при какой температуре работает?

**Evidence:**

- `lira22.html`: Напряжение питания 12 В.

**Пробелы/условия:** Рабочая температура Лира-22 неизвестна.

### oracle: `partial`

> Лира-22 имеет напряжение питания 12 В. [1]
> При какой температуре работает Лира-22?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Напряжение питания 12 В.; chunk `d677c7c3bc26676585077ec4e9dffd9161db3cd360f7f128bf5c312521cfe727`.
- Citation [1]: `lira22`, `https://example.invalid/rag-diagnostic/lira22.html`, SHA256 `000bac4472659b33ec9720c35fb471dd06b66a703ee9ee495ac95d7a2fcc28ed`.

### end-to-end: `partial`

> Лира-22 имеет напряжение питания 12 В. [1]
> При какой температуре работает Лира-22?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Напряжение питания 12 В.; chunk `d677c7c3bc26676585077ec4e9dffd9161db3cd360f7f128bf5c312521cfe727`.
- Citation [1]: `lira22`, `https://example.invalid/rag-diagnostic/lira22.html`, SHA256 `000bac4472659b33ec9720c35fb471dd06b66a703ee9ee495ac95d7a2fcc28ed`.

## d08 — partial

**Вопрос:** Что измеряет Орион-110 и какой у него гарантийный срок?

**Evidence:**

- `orion.html`: Предназначен для измерения температуры.

**Пробелы/условия:** Гарантийный срок неизвестен.

### oracle: `partial`

> Орион-110 предназначен для измерения температуры. [1]
> Какой гарантийный срок у Орион-110?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Предназначен для измерения температуры.; chunk `0ccfad939dd29d4686b90884e1471858bd707fd80077b9bb31be2a1d513b8807`.
- Citation [1]: `orion`, `https://example.invalid/rag-diagnostic/orion.html`, SHA256 `195b34d7e4ecb2f8e178c10bfbb9fe345ed1912c7a6b3580aac41e105b762efe`.

### end-to-end: `partial`

> Орион-110 предназначен для измерения температуры. [1]
> Какой гарантийный срок у Орион-110?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Предназначен для измерения температуры.; chunk `0ccfad939dd29d4686b90884e1471858bd707fd80077b9bb31be2a1d513b8807`.
- Citation [1]: `orion`, `https://example.invalid/rag-diagnostic/orion.html`, SHA256 `195b34d7e4ecb2f8e178c10bfbb9fe345ed1912c7a6b3580aac41e105b762efe`.

## d09 — partial

**Вопрос:** Диапазон и точность Вега модификации Б?

**Evidence:**

- `vega-b.html`: Диапазон давления от 0 до 16 бар.

**Пробелы/условия:** Точность неизвестна.

### oracle: `partial`

> Диапазон давления Вега, модификация Б: от 0 до 16 бар. [1]
> Какая точность у Вега модификации Б?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Диапазон давления от 0 до 16 бар.; chunk `5b009f975dddf2cffdaf5e9153de06ed67b2dda83db003eaf64c4336b3ddc314`.
- Citation [1]: `vega-b`, `https://example.invalid/rag-diagnostic/vega-b.html`, SHA256 `9ff776ca267a1fa8989ebd32a5b5a3edcc6a4ee00768c267d211cd0af1e7c464`.

### end-to-end: `partial`

> Диапазон давления Вега модификации Б: от 0 до 16 бар. [1]
> Какова точность Вега модификации Б?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Диапазон давления от 0 до 16 бар.; chunk `5b009f975dddf2cffdaf5e9153de06ed67b2dda83db003eaf64c4336b3ddc314`.
- Citation [1]: `vega-b`, `https://example.invalid/rag-diagnostic/vega-b.html`, SHA256 `9ff776ca267a1fa8989ebd32a5b5a3edcc6a4ee00768c267d211cd0af1e7c464`.

## d10 — missing

**Вопрос:** Какие характеристики у Лира-999?

**Evidence:**

- Подтверждённых фактов для ответа нет.

**Пробелы/условия:** Лира-999 отсутствует в материалах. Не переносить сведения Лира-21/22.

### oracle: `needs_support`

> Какие характеристики у Лира-999?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.


### end-to-end: `needs_support`

> Какие характеристики у Лира-999?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.


## d11 — missing

**Вопрос:** Есть ли у Лира-21 взрывозащита?

**Evidence:**

- Подтверждённых фактов для ответа нет.

**Пробелы/условия:** Взрывозащита неизвестна. Не утверждать её наличие или отсутствие.

### oracle: `needs_support`

> Есть ли у Лира-21 взрывозащита?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.


### end-to-end: `needs_support`

> Есть ли у Лира-21 взрывозащита?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.


## d12 — missing

**Вопрос:** Сколько стоит Орион-110?

**Evidence:**

- Подтверждённых фактов для ответа нет.

**Пробелы/условия:** Цена неизвестна.

### oracle: `needs_support`

> Сколько стоит Орион-110?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.


### end-to-end: `needs_support`

> Сколько стоит Орион-110?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.


## d13 — ambiguous

**Вопрос:** Какой диапазон давления у Вега?

**Evidence:**

- `vega-a.html`: Диапазон давления от 0 до 10 бар.
- `vega-b.html`: Диапазон давления от 0 до 16 бар.

**Пробелы/условия:** Нужно уточнить модификацию А/Б; нельзя выдать один диапазон как общий.

### oracle: `partial`

> У модификации А Вега диапазон давления от 0 до 10 бар. [1]
> У модификации Б Вега диапазон давления от 0 до 16 бар. [2]
> Уточните, пожалуйста, какую модификацию Вега вы имеете в виду — А или Б?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Диапазон давления от 0 до 10 бар.; chunk `208b1211fae937d34a3a63504c7c0d2ba85c3c2b9ef27951ee3d2916780313a8`.
- Claim `c2` quote: Диапазон давления от 0 до 16 бар.; chunk `5b009f975dddf2cffdaf5e9153de06ed67b2dda83db003eaf64c4336b3ddc314`.
- Citation [1]: `vega-a`, `https://example.invalid/rag-diagnostic/vega-a.html`, SHA256 `7e5bca4aa8bee11f906c12bb0a408a3d88392a54d3b40f532178ee7848c6b10b`.
- Citation [2]: `vega-b`, `https://example.invalid/rag-diagnostic/vega-b.html`, SHA256 `9ff776ca267a1fa8989ebd32a5b5a3edcc6a4ee00768c267d211cd0af1e7c464`.

### end-to-end: `partial`

> У Веги, модификации А, диапазон давления от 0 до 10 бар. [1]
> У Веги, модификации Б, диапазон давления от 0 до 16 бар. [2]
> Уточните, пожалуйста, какую модификацию Веги вы имеете в виду: А или Б?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Диапазон давления от 0 до 10 бар.; chunk `208b1211fae937d34a3a63504c7c0d2ba85c3c2b9ef27951ee3d2916780313a8`.
- Claim `c2` quote: Диапазон давления от 0 до 16 бар.; chunk `5b009f975dddf2cffdaf5e9153de06ed67b2dda83db003eaf64c4336b3ddc314`.
- Citation [1]: `vega-a`, `https://example.invalid/rag-diagnostic/vega-a.html`, SHA256 `7e5bca4aa8bee11f906c12bb0a408a3d88392a54d3b40f532178ee7848c6b10b`.
- Citation [2]: `vega-b`, `https://example.invalid/rag-diagnostic/vega-b.html`, SHA256 `9ff776ca267a1fa8989ebd32a5b5a3edcc6a4ee00768c267d211cd0af1e7c464`.

## d14 — ambiguous

**Вопрос:** Какое питание нужно прибору Лира?

**Evidence:**

- `lira21.html`: Напряжение питания 24 В.
- `lira22.html`: Напряжение питания 12 В.

**Пробелы/условия:** Нужно уточнить Лира-21/Лира-22; допустимо показать различия с обозначениями.

### oracle: `partial`

> Для Лира-21 напряжение питания составляет 24 В. [1]
> Для Лира-22 напряжение питания составляет 12 В. [2]
> Уточните, пожалуйста, о какой модели прибора Лира идёт речь: Лира-21 или Лира-22?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Напряжение питания 24 В.; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Claim `c2` quote: Напряжение питания 12 В.; chunk `d677c7c3bc26676585077ec4e9dffd9161db3cd360f7f128bf5c312521cfe727`.
- Citation [1]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.
- Citation [2]: `lira22`, `https://example.invalid/rag-diagnostic/lira22.html`, SHA256 `000bac4472659b33ec9720c35fb471dd06b66a703ee9ee495ac95d7a2fcc28ed`.

### end-to-end: `partial`

> Для Лира-22 указано напряжение питания 12 В. [1]
> Для Лира-21 указано напряжение питания 24 В. [2]
> Уточните, пожалуйста, какая именно модель Лира имеется в виду: Лира-21 или Лира-22?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.

- Claim `c1` quote: Напряжение питания 12 В; chunk `d677c7c3bc26676585077ec4e9dffd9161db3cd360f7f128bf5c312521cfe727`.
- Claim `c2` quote: Напряжение питания 24 В; chunk `03ea9837a2e72757971d155ef742c1cf763d56373e4f4ba710e45b35bd091ae4`.
- Citation [1]: `lira22`, `https://example.invalid/rag-diagnostic/lira22.html`, SHA256 `000bac4472659b33ec9720c35fb471dd06b66a703ee9ee495ac95d7a2fcc28ed`.
- Citation [2]: `lira21`, `https://example.invalid/rag-diagnostic/lira21.html`, SHA256 `cee802e861a62922777115cd623f60df84877d128ff38336328deab5a8155ece`.

## d15 — conflict

**Вопрос:** Какое напряжение питания нужно Ультра-8 редакции 1?

**Evidence:**

- `ultra-card.html`: Напряжение питания 24 В.
- `ultra-manual.html`: Напряжение питания 48 В.

**Пробелы/условия:** Источники одной редакции противоречат друг другу; не выбирать одно напряжение и не советовать подключение.

### oracle: `clarification`

> Какое напряжение питания у Ультра-8 редакции 1: 24 В или 48 В?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.


### end-to-end: `clarification`

> Какое напряжение питания у Ультра-8 редакции 1: 24 В или 48 В?
> В доступных материалах подтверждения недостаточно. Для уточнения свяжитесь с поддержкой компании.


## Наблюдения для human review

Оба режима15/15/0infrastructure errors; прежний d13 обработан. D10–d12 без factual claims/citations, d06–d09 без посторонних характеристик. D15 даёт только вопрос о конфликтующих24/48В: два drafts с номером редакции1 без полного numeric quote support отклонены до verifier. Human verdicts не выставлены автоматически. Старый [profile2048](2026-11-07-grounded-rag-relevance-responses.md) сохранён неизменным;4096 — отдельное измерение.
