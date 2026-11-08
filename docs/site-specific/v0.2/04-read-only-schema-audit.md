# Saturn-Main-Site: схема источника и правила адаптации

Дата аудита: 2026-11-09  
Статус: **ACCEPTED MAPPING BASELINE — schema evolution governed by ADR-0013**  
Источник: UkWood/Saturn-Main-Site, main, snapshot 084d759487bfab6e111549c9b5469711ac5fc13.

## 1. Что обнаружено в текущем snapshot

В src/content/ находится 438 Markdown-записей:

| Collection | Количество | Назначение |
|---|---:|---|
| products | 292 | Устройства, изделия и ПО |
| systems | 25 | 13 инженерных систем и 12 категорий каталога |
| groups | 23 | Группы каталога |
| articles | 36 | Статьи |
| news | 22 | Новости |
| pages | 40 | Страницы, 13 решений и 5 разделов |

ПО хранится в products, обычно с group: programmnoe-obespechenie; отдельной Astro collection для ПО нет.

Фактическая схема определяется src/content.config.ts. Основные product fields: title, name, article, group, systems, status, notice, images, interfaces, protocols, ip, temperature_c, mass_kg, dimensions_mm, lifetime_years, power, specs, inputs, outputs, features, connectors, documents, certificates, related, variant_of, software, articles, solutions.

Для systems важен kind:
- system — инженерная система;
- category — категория каталога.

pages.kind различает solution и section; остальные pages — обычные страницы. groups.system — соответствие каталожной группы странице системы/категории. pages.groups — навигационная структура, не состав инженерной системы.

Основные dictionaries в src/data/: interfaces.yaml, protocols.yaml, io-kinds.yaml, applications.yaml, industries.yaml, synonyms.yaml, spec-names.yaml, а также файлы порядка отображения. Значения этих файлов являются данными источника, а не неизменными enum в коде адаптера.

## 2. Принципы импорта

- Источник истины — Markdown/frontmatter/YAML в pinned Git snapshot, не собранные search-index.json и doc-index.json.
- Все non-draft записи и связи считаются доверенными.
- draft: true не включается в публичный corpus.
- Сохранять raw frontmatter и Markdown body наряду с typed projections.
- Сохранять порядок и исходные значения specs, единицы, диапазоны и qualifiers.
- status, notice и другие qualifiers не терять.
- Различать System, Category, Group, Product/Device, Software, Solution, Article, News и Page.
- Software — semantic subtype Product, не отдельная collection.
- Обратные relations строить только как projections с указанием исходного поля.
- Отсутствующее поле и schema default не являются утверждением об отсутствии функции/параметра.
- related остаётся related, software — source-declared software relation; не переименовывать произвольно в compatible_with.

## 3. Support Catalog и PDF

Документы обнаруживаются в documents и certificates у products/systems; прямые PDF-ссылки также извлекаются из Markdown body всех non-draft collections. Сохранять title, kind, url, version, date (если есть), source locator и все owner links.

Один файл может иметь нескольких owners. Дедупликация не должна терять их metadata.

Все прямые PDF-ссылки из доверенных non-draft записей автоматически обрабатываются по configured HTTPS host/path allowlist. Для каждого файла сохраняются URL, bytes hash, parser version, page count и физические номера страниц. Новый hash запускает автоматическое повторное извлечение. Отдельного approval нет.

Ошибки сетевого доступа и extraction — технические ошибки: metadata остаётся доступной, но несуществующий/неизвлечённый текст не представляется как evidence. Ограничения fetch/SSRF и sandbox parser — меры безопасности, не проверка достоверности.

## 4. Обнаружение и обработка изменений сайта

Каждый sync фиксирует точный commit main, Git tree и blob hashes.

Adapter автоматически обнаруживает:
- новые, изменённые и удалённые Markdown-файлы;
- новые или удалённые collections;
- изменения src/content.config.ts;
- новые/удалённые поля frontmatter;
- изменения типов и defaults;
- новые/удалённые значения dictionaries;
- изменение canonical routes и document URLs;
- новые/изменённые/удалённые PDF links и bytes.

Поведение:
- новые/изменённые записи автоматически импортируются;
- удалённые записи удаляются из активного snapshot;
- новые простые поля сохраняются как raw_fields и labelled evidence;
- неизвестная collection импортируется как generic SiteContent;
- неизвестные dictionary values сохраняются и не блокируют импорт;
- при несовместимом типе/семантике поля прежняя typed projection отключается, raw value сохраняется, а drift попадает в отчёт;
- новый snapshot публикуется атомарно, без частичной индексации.

Изменение схемы не требует ручного подтверждения контента. Оно может потребовать технического обновления mapping в AI-репозитории.

## 5. Контракт адаптера

В snapshot manifest фиксируются:
- source_repository, source_branch, source_commit;
- Git tree SHA и blob SHA каждого source file;
- schema_fingerprint для src/content.config.ts;
- отдельные fingerprints YAML dictionaries;
- adapter_version, mapping_version, parser versions;
- counts и added/changed/deleted IDs;
- schema drift events и parser warnings.

Адаптер должен поддерживать incremental sync и full rebuild из одного exact commit. Повторный импорт того же commit и тех же версий mapping/parser даёт идентичный canonical package.

## 6. Ограничения и границы

- UkWood/Saturn-Main-Site — строго READ-ONLY. Никакие изменения сайта, его URL, assets, workflows, /search/ или /service/search/ не допускаются.
- Не читать Old_Site/, migration reports/scripts и compiled search indexes как knowledge source.
- Не выполнять код сайта и не интерпретировать TypeScript schema как исполняемый код.
- Внешний inference/provider и разрешение передачи данных ему — отдельная настройка, не часть source trust.
- Текущий snapshot фиксирует состояние на дату аудита; production sync всегда берёт актуальный main, сохраняя точный commit в manifest.

## 7. Проверенные точки исходного snapshot

- [Astro content schema](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/content.config.ts)
- [Content model notes](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/docs/content-model.md)
- [Products](https://github.com/UkWood/Saturn-Main-Site/tree/084d759487bfab6e111549c9b5469711ac5fc13e/src/content/products)
- [Systems](https://github.com/UkWood/Saturn-Main-Site/tree/084d759487bfab6e111549c9b5469711ac5fc13e/src/content/systems)
- [Dictionaries](https://github.com/UkWood/Saturn-Main-Site/tree/084d759487bfab6e111549c9b5469711ac5fc13e/src/data)
- [Support catalog implementation](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/lib/service.ts)
- [Document metadata index](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/pages/doc-index.json.ts)
