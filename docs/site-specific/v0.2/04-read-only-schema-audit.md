# Read-only schema audit and canonical mapping — Saturn-Main-Site

Дата аудита: 2026-11-08  
Статус: **AUDIT COMPLETE — OWNER REVIEW REQUIRED**  
Область: только чтение UkWood/Saturn-Main-Site; никаких изменений исходного репозитория не выполнялось.

## 1. Зафиксированный snapshot

| Параметр | Значение |
|---|---|
| Repository | UkWood/Saturn-Main-Site |
| Branch | main |
| Exact commit | 084d759487bfab6e111549c9b5469711ac5fc13e |
| Commit date | 2026-11-03 08:05:16 UTC |
| Tree API | truncated=false |
| Default branch | main |
| Режим аудита | GitHub read-only GET |

Текущий HEAD main на момент аудита совпадает с commit, использованным в inventory v0.1. Snapshot можно использовать как воспроизводимую основу mapping. Перед будущим ingestion потребуется повторно зафиксировать exact commit: этот snapshot не считается автоматически актуальным навсегда.

В ходе аудита читались только файлы и Git metadata. Не выполнялись:
- создание или изменение branch, commit, PR, settings или workflow в Saturn-Main-Site;
- скачивание документов с файлового сервера;
- запуск build/deploy сайта;
- изменение /search/, /service/search/, search-index.json или doc-index.json;
- ingestion каких-либо source candidates.

## 2. Инвентаризация контента

В src/content/ обнаружено 438 Markdown-записей:

| Collection | Количество | Канонический тип |
|---|---:|---|
| products | 292 | Product / Device |
| systems | 25 | System или Category — различать по kind |
| groups | 23 | CatalogGroup |
| articles | 36 | Article |
| news | 22 | News |
| pages | 40 | Page / Section / Solution |
| **Всего** | **438** | |

В systems текущие записи содержат два разных семантических вида: 12 записей с kind: category и 13 инженерных систем. Коллекцию нельзя импортировать как однородный тип System.

Для pages:
- 13 записей имеют kind: solution;
- 5 записей имеют kind: section;
- остальные записи — обычные страницы, включая home и страницу-оглавление resheniya.

Software не является отдельной Astro collection: ПО хранится как Product в products, обычно с group: programmnoe-obespechenie. Это семантическая классификация, а не отдельный тип исходной записи.

## 3. Реальная схема Astro

Основной источник схемы: [src/content.config.ts](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/content.config.ts).

Общие поля:
- title — обязательная строка;
- subtitle — optional;
- oldUrl — прежний адрес старого сайта;
- legacyId — прежний числовой идентификатор;
- draft — boolean, default false.

### 3.1. Products

| Поле | Тип / смысл | Правило импорта |
|---|---|---|
| title | Обозначение изделия | Сохранять исходное значение |
| name | Полное наименование | Отдельное поле |
| article | Артикул | Не путать с legacyId |
| group | Reference на groups | Catalog membership |
| systems | Массив references на systems | Проверять kind каждого target |
| status | active, obsolete, discontinued; default active | Сохранять явность/default |
| notice | Оговорка к статусу | Отдельный текстовый факт |
| images | Массив путей | Метаданные; не скачивать автоматически |
| interfaces, protocols | Массивы значений из YAML dictionaries | Сохранять raw value и dictionary revision |
| ip | Строка | Не нормализовать до IP-класса без проверки |
| temperature_c | {min, max} | Typed projection; сохранить границы |
| mass_kg | Число | Typed projection |
| dimensions_mm | Tuple из трёх чисел | Порядок значений сохранять |
| lifetime_years | Число | Typed projection |
| power | Строка | Не преобразовывать без unit parsing |
| specs | {group?, name, value} | Сохранять каждую исходную строку, порядок, имя и текст значения |
| inputs, outputs | {kind, count, note?} | Хранить отдельно от исходных specs |
| features | Массив строк | Отдельные текстовые facts |
| connectors | {id, description, label} | Сохранять обозначение клеммы |
| documents | Массив doc objects | Support metadata channel |
| videos | {title, url, group?} | Ссылки; не считать просмотренным содержимым |
| certificates | Doc object или {kind: scan, image, title?} | Scan image — не PDF |
| related | References на products | Семантика связи требует provenance |
| variant_of | Reference на product | Не считать проверенным без происхождения |
| software | References на products | Поле подписано как совместимое ПО, но происхождение связи эвристическое |
| articles, solutions | References | Примеры применения; не техническое доказательство |

### 3.2. Systems

- kind: system или category, default system;
- summary;
- applications;
- documents;
- videos;
- images, imageDark;
- articles, solutions;
- Markdown body.

category — раздел каталога/перечень изделий, а не инженерная система. Примеры: korpusa, newel, programmnoe-obespechenie, radiokontsentrator-brk.

Важное расхождение: текущий src/content/systems/radiokontsentrator-brk.md содержит kind: category, но старый scripts/model/enrich-systems.mjs не включает этот slug в hard-coded CATEGORIES, а migration/model/enrich-systems-report.md называет его system. Для импорта authoritative source — frontmatter конкретной записи на pinned commit; миграционные script/report не должны переопределять текущее значение.

Происхождение других полей тоже требует осторожности: enrich-systems.mjs формирует summary из первого подходящего абзаца, applications из hard-coded mapping, documents из отдельных Markdown-ссылок, kind документа — regex по title/URL, version — из заголовка с годом. В текущем frontmatter нет field-level review marker, поэтому нельзя определить, какие значения после миграции были вручную перепроверены.

### 3.3. Groups

- title;
- group;
- summary;
- icon;
- system — reference на запись systems.

groups.system означает соответствие содержимого группы странице системы/раздела каталога. Target может иметь kind: category; не превращать это автоматически в отношение инженерного состава.

### 3.4. Articles

- title, subtitle, section;
- products, systems;
- Markdown body.

### 3.5. News

- title;
- обязательный date;
- products;
- Markdown body.

### 3.6. Pages

- title, subtitle;
- kind: section или solution, optional;
- images;
- systems, products;
- groups: вложенные навигационные группы {title, icon, items[]};
- heading, lead, directions — поля главной страницы;
- Markdown body.

pages.groups — вложенная структура навигации страницы «Типовые решения». Это не collection groups и не техническая relation между изделиями.

groups.items ссылается на pages в целом; схема не требует, чтобы каждая такая страница имела kind: solution.

## 4. Важное правило обработки default values

Astro Zod schema применяет defaults. При чтении raw Markdown отсутствие поля не всегда означает подтверждённое отсутствие свойства.

Примеры:
- products.status отсутствует → effective default active; это не обязательно явное подтверждение статуса владельцем;
- systems.kind отсутствует → effective default system;
- draft отсутствует → effective default false;
- отсутствующие массивы interfaces, protocols, documents, features, systems и другие становятся пустыми массивами после schema parsing.

Для RAG adapter обязательно сохранять две формы:
1. raw frontmatter — какие поля реально присутствовали в файле;
2. schema-effective value — какое значение получает Astro после defaults.

Нельзя трактовать отсутствующее поле или schema-generated [] как утверждение «не поддерживает», «нет документов», «нет интерфейсов» или «не применяется».

Рекомендуемые атрибуты факта: field_present, raw_value, effective_value, default_applied.

## 5. Канонический mapping

| Source | Canonical object | Допустимое использование |
|---|---|---|
| products | Entity(Product) | Карточка изделия, raw facts, описание, ссылки на документы |
| systems с kind=system | Entity(System) | Описание инженерной системы; applications — с provenance |
| systems с kind=category | Entity(Category) | Каталоговая навигация и принадлежность к разделу |
| groups | Entity(CatalogGroup) | Группировка каталога |
| articles | Entity(Article) + text passages | Информационный контекст |
| news | Entity(News) + dated passage | Исторический контекст; дата обязательна |
| pages с kind=solution | Entity(Solution) + passages | Описание типового решения |
| pages с kind=section | Entity(SectionPage) | Навигация/оглавление, не самостоятельное техническое утверждение |
| обычные pages | Entity(Page) + passages | Информационные страницы |
| src/data/*.yaml | Dictionaries / taxonomy / ordering | Контролируемые значения и aliases; не самостоятельные технические факты |

Стабильный logical ID можно строить как saturn:{collection}:{slug}. Для каждого source revision фиксировать:
- exact site commit;
- repository path;
- Git blob SHA;
- SHA-256 bytes, вычисленный при ingestion;
- source collection и slug;
- field path или Markdown heading;
- canonical route.

Canonical routes, подтверждённые текущей структурой:
- products: /products/{slug}/;
- systems: /systems/{slug}/;
- groups: /catalog/{slug}/;
- articles: /articles/{slug}/;
- news: /news/{slug}/;
- pages: /{slug}/.

legacyId и oldUrl — миграционные атрибуты, не primary key.

## 6. Dictionaries и вспомогательные данные

Основные словари:
- interfaces.yaml — 13 интерфейсов;
- protocols.yaml — 11 протоколов;
- io-kinds.yaml — 4 вида входов/выходов;
- applications.yaml — 10 областей применения;
- synonyms.yaml — 3 явно заданных сокращения/расшифровки;
- spec-names.yaml — regex mapping названий характеристик в общие display names.

spec-names.yaml предназначен прежде всего для нормализации сравнительной таблицы. Он не заменяет исходное имя характеристики и не доказывает эквивалентность единиц или условий.

systems-order.yaml и software-order.yaml — порядок отображения, не факты о применении/совместимости.

industries.yaml содержит 6 отраслевых классификаций. В комментарии файла прямо указано, что описание и распределение систем, решений, материалов и оборудования предварительные и требуют уточнения с владельцем. Не использовать эти списки как подтверждённые инженерные связи.

## 7. Три канала знаний на реальной схеме

### 7.1. Site Content

Читать только:
- src/content/{products,systems,groups,articles,news,pages}/**
- выбранные src/data/*.yaml;
- src/content.config.ts как schema contract.

Не включать в knowledge corpus:
- Old_Site/**
- migration/**
- inventory/**
- scripts/**
- public/admin/**
- compiled search-index.json и doc-index.json как source of truth;
- служебные workflow, design docs и code comments как технические знания об изделиях.

### 7.2. Support Catalog

Doc schema:
- title;
- kind: manual, software, presentation, certificate, declaration, registry, datasheet, other;
- url;
- optional version;
- optional date.

certificates может содержать обычный doc object либо scan image (kind: scan). Скан не должен ошибочно поступать в PDF parser.

Каталог формируется только из documents/certificates products и documents systems. У документа могут быть несколько owners.

### 7.3. External Document

Точный URL сохраняется из source field. Текущая функция fileUrl() и workflow preview используют PUBLIC_ASSET_ORIGIN=https://www.mnppsaturn.ru для allowlisted старых файловых каталогов (/ftp, /public, /photos и др.). Это подтверждает конфигурацию preview, но не доказывает доступность конкретного файла и актуальность его редакции.

Внешний fetch разрешать только после отдельного approval exact URL + revision/hash. Не выводить доступность PDF из наличия ссылки.

## 8. Существующие поиски сайта — границы

- /search/ использует /search-index.json, который собирается из коллекций сайта. Для products в нём есть обозначение, имя, группа, systems, terms, specs, features, названия документов и ограниченный фрагмент body; PDF text отсутствует.
- Для products/systems body в поисковом индексе ограничен 4000 символами; articles/pages — 8000; news — 3000.
- Search index обозначает все записи systems одним k: system, не различая kind: category. Для RAG нельзя использовать это поле вместо исходного kind.
- /service/search/ использует /doc-index.json, который содержит metadata: title, kind, section, version, URL, owners. Внутренний текст PDF не извлекается.
- Текущие поиски и их код не изменять. Адаптер должен читать первичные Markdown/frontmatter/YAML.

### 8.1. Дедупликация Support Catalog

src/lib/service.ts объединяет записи по точному raw URL. При совпадении URL к первой записи добавляются owners, но title/kind/version второй записи не сравниваются и не сохраняются как отдельные варианты.

В RAG adapter нельзя повторять это поведение с потерей metadata:
- сохранять все owner-field occurrences;
- нормализовать URL только отдельной проверяемой функцией;
- выявлять конфликт title/kind/version/date;
- объединять документ только при совместимой identity;
- не удалять owner provenance.

## 9. Проверки целостности и их ограничения

scripts/model/check-content.mjs проверяет:
- существование references на products/systems/groups/articles/pages;
- значения интерфейсов, протоколов, applications и IO kinds по словарям;
- URL prefix (/ или http(s));
- часть route/nav consistency;
- некоторые ограничения YAML dictionaries и CMS options.

Он не проверяет:
- истинность или инженерную корректность relations;
- подтверждение совместимости ПО;
- доступность внешнего URL/PDF;
- содержимое PDF;
- актуальность редакции документа;
- качество извлечения таблиц;
- ручное подтверждение автоматически сгенерированных связей.

Зелёный check-content означает структурную согласованность в его пределах, но не source approval и не factual validation.

## 10. Что требуется до первой coding task

1. Утвердить правила provenance и review для relation/fact projections из ADR-0013.
2. Утвердить distinction System vs Category и отдельную роль CatalogGroup.
3. Утвердить правило: missing/default field не является отрицательным техническим утверждением.
4. Утвердить список полей, которые могут стать answer evidence без ручной проверки, и список только навигационных/heuristic associations.
5. Зафиксировать exact allowlist source paths и mapping dictionary revisions.
6. Сформировать synthetic fixtures из representative records и негативных случаев.
7. Только после этого создать bounded coding task на canonical contracts.

## 11. Открытые ограничения

- Это статический read-only audit. Astro build и check:content не запускались.
- Ни один PDF не скачивался и не анализировался.
- Ни один source candidate не получил approval.
- Ни один external provider/cloud request не выполнялся.
- Ни одна relation не прошла инженерную ручную проверку в рамках этого аудита.
- Source commit 084d759... фиксирует только snapshot на 2026-11-03; перед реальным ingestion потребуется новая проверка HEAD и source changes.

## 12. Source references

Все ссылки ниже указывают на один pinned commit 084d759487bfab6e111549c9b5469711ac5fc13e:

- [Content schema](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/content.config.ts)
- [Content model notes](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/docs/content-model.md)
- [Product coverage report](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/migration/model/coverage.md)
- [Relation enrichment script](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/scripts/model/enrich-relations.mjs)
- [Relation enrichment report](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/migration/model/enrich-relations-report.md)
- [Product enrichment script](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/scripts/model/enrich-products.mjs)
- [Product enrichment report](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/migration/model/enrich-report.md)
- [Systems enrichment script](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/scripts/model/enrich-systems.mjs)
- [Systems enrichment report](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/migration/model/enrich-systems-report.md)
- [Content integrity checker](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/scripts/model/check-content.mjs)
- [Support catalog adapter in site](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/lib/service.ts)
- [Document index builder](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/pages/doc-index.json.ts)
- [URL and asset origin rules](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/lib/url.ts)
- [Industries taxonomy — preliminary](https://github.com/UkWood/Saturn-Main-Site/blob/084d759487bfab6e111549c9b5469711ac5fc13e/src/data/industries.yaml)
