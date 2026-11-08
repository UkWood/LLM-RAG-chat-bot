# ADR-0013: доверие к данным Saturn и эволюция схемы адаптера

Дата: 2026-11-09  
Статус: **ACCEPTED — owner confirmed**  
Область: Site Content Adapter, Support Catalog Adapter, External Document Adapter.

## Контекст

Содержимое UkWood/Saturn-Main-Site, взаимосвязи сущностей и PDF по ссылкам сайта просмотрены и проверены специалистами МНПП «Сатурн». Источник считается доверенным. Сайт находится в разработке: collections, поля, параметры, классификаторы, страницы и документы могут добавляться, изменяться и удаляться.

Следовательно, системе нужна не ручная верификация контента, а устойчивый механизм обнаружения и обработки изменений структуры.

## Решение

### 1. Единая политика доверия

- Trust root: UkWood/Saturn-Main-Site, branch main.
- Все записи сайта, frontmatter relations, YAML dictionaries и документы из documents/certificates считаются доверенными.
- draft: true исключается из публичного knowledge corpus; остальные записи автоматически индексируются.
- Никаких ручных approval, semantic review или отдельного подтверждения PDF.
- Смысл связи определяется полем источника. Импортированная связь считается достоверной именно в значении этого поля, но не должна переименовываться в более сильное отношение без прямого основания.

### 2. Provenance — только техническая прослеживаемость

Для каждого объекта сохраняются:
- repository, branch, commit SHA;
- source path и Git blob SHA;
- content SHA-256;
- collection/slug, field path или Markdown heading;
- canonical URL, если она определена;
- для PDF — исходный URL, bytes SHA-256, parser version и физические страницы.

Эти данные обеспечивают повторяемость snapshot, корректные citations, diff и диагностику. Они не являются approval status и не блокируют использование новой revision.

### 3. Эволюция источника и schema drift

Каждый sync:
1. Получает точный HEAD main и фиксирует commit.
2. Обнаруживает все файлы и collections под src/content/, не полагаясь на статический перечень файлов.
3. Читает актуальный src/content.config.ts и YAML dictionaries src/data/.
4. Сравнивает source tree, schema fingerprint, field inventory и dictionary values с предыдущим успешным snapshot.
5. Обрабатывает добавления, изменения и удаления, формирует drift report.
6. Строит новый immutable snapshot и публикует его атомарно после проверки целостности.

Правила изменений:
- **Content change:** автоматически переиндексировать изменённую запись и зависимые projections.
- **New/deleted record:** добавить или убрать её из активного snapshot.
- **New field / parameter / dictionary value:** сохранить исходное значение в универсальный raw extension, включить его в labelled text evidence; specialized typed mapping добавляется при необходимости.
- **New collection:** импортировать как generic SiteContent (title, frontmatter, body, path, commit, hash), не терять данные; позже расширить domain mapping.
- **Removed field / renamed field / changed type:** не применять прежнюю typed interpretation к новому значению. Сохранить raw representation, отметить несовместимость в drift report и обновить adapter mapping.
- **Route or URL change:** обновить canonical URL/citations по текущей структуре сайта.
- **Dictionary changes:** синхронизировать значения автоматически; не зашивать отрасли, protocols, interfaces или spec names в код как неизменные списки.

Unknown additive data не должно пропадать молча. Несовместимые значения не должны интерпретироваться старым mapping. Ошибка одного нового поля не должна незаметно обнулять весь документ или snapshot.

### 4. Versioned adapter mapping

- Версия Site Adapter и версия mapping фиксируются в snapshot manifest.
- Fingerprint схемы сайта и fingerprints dictionaries фиксируются отдельно.
- Fixtures отражают реальные текущие collections и ключевые поля, а также synthetic drift cases: добавление/удаление поля, collection, enum value, изменение типа, удаление страницы и смена PDF bytes.
- Изменение mapping — штатная задача разработки в UkWood/LLM-RAG-chat-bot, не изменение сайта и не повторное подтверждение содержимого.
- До полного mapping unknown fields/collections сохраняются как generic evidence, а не отбрасываются.

### 5. PDF и Support Catalog

- Любая PDF-ссылка из доверенного documents/certificates автоматически попадает в Support Catalog.
- Файл скачивается с configured trusted origin/path allowlist; отдельного approval нет.
- Новая ссылка или новый bytes hash запускает fetch и extraction автоматически.
- Несколько owners сохраняются для одного документа.
- Если fetch/extraction не удался, metadata остаётся в каталоге, но PDF text не выдаётся за доступное evidence. Это техническое состояние обработки, не сомнение в достоверности документа.

### 6. Безопасность и provider boundary

- Read-only доступ к сайту, HTTPS, host/path allowlist, SSRF/redirect protection, resource limits и изоляция PDF parser обязательны. Это защита инфраструктуры, не контентная верификация.
- cloud_generate остаётся отдельным разрешением на передачу публичных материалов внешнему provider; оно не связано с подтверждением достоверности источника.
- Ни URL из вопроса пользователя, ни произвольный внешний URL не могут инициировать fetch.

## Последствия

- Содержимое и связи сайта доступны без ручного approval workflow.
- Изменения сайта автоматически попадают в следующий snapshot.
- Добавления схемы не приводят к потере данных; сложные изменения требуют обновления mapping.
- Provenance сохраняет точность citations и позволяет воспроизводить ответы по прежним revisions.
- Небольшие изменения сайта обычно не требуют coding; изменения семантики или типов полей требуют адаптации parser/mapping и contract tests.

## Acceptance

Решение считается реализованным, когда тесты подтверждают:
- автоматический импорт текущих non-draft records и trusted linked PDFs;
- обработку add/update/delete;
- обнаружение schema/dictionary drift;
- сохранение unknown fields и unknown collections;
- отсутствие stale typed interpretation при изменении типа поля;
- автоматическое обновление PDF по изменению bytes hash;
- сохранение provenance, owners и canonical citations;
- неизменность Saturn-Main-Site (read-only).
