# Saturn source data quality register

Дата: 2026-11-08  
Статус: **PROPOSED CONTROL REGISTER — owner review required**  
Snapshot: UkWood/Saturn-Main-Site@084d759487bfab6e111549c9b5469711ac5fc13e.

Этот реестр дополняет [read-only schema audit](04-read-only-schema-audit.md). Он описывает риски интерпретации данных, а не дефекты сайта, которые нужно исправлять в исходном репозитории.

## 1. Field coverage

Последний доступный отчёт в snapshot: migration/model/coverage.md.

| Поле | Записей из 292 | Доля |
|---|---:|---:|
| Изображения | 203 | 70% |
| Документы (ссылки) | 151 | 52% |
| Сертификаты / декларации (coverage report metric) | 1 | 0% (rounded) |
| Характеристики specs | 154 | 53% |
| Строк характеристик | 2574 | — |
| Строк с разделёнными name/value | 2417 | 94% |
| Features | 84 | 29% |
| Connectors | 3 | 1% |
| Interfaces | 56 | 19% |
| Protocols | 11 | 4% |
| IP | 122 | 42% |
| Temperature | 106 | 36% |
| Mass | 137 | 47% |
| Dimensions | 140 | 48% |
| Lifetime | 124 | 42% |
| Explicit obsolete status | 31 | 11% |
| Product → systems references | 290 | 99% |

Дополнительные результаты миграционных отчётов:
- inputs/outputs извлечены у 22 изделий;
- variant_of сформирован для 18 изделий;
- related присутствует у 108 изделий;
- software links найдены у 21 изделия;
- примеры применения изделий найдены у 62 изделий.

Эти числа — данные доступных migration reports, а не заново вычисленная статистика текущего corpus. Перед production ingestion coverage нужно пересчитать на exact pinned snapshot и сохранить новый manifest.

### Интерпретация

- Пустой interfaces не доказывает отсутствие интерфейсов.
- Пустой protocols не доказывает отсутствие протоколов.
- Отсутствие documents не доказывает отсутствие документации на файловом сервере.
- Отсутствие features не означает, что изделие не выполняет функций.
- Незаполненное inputs/outputs не означает ноль входов/выходов.
- specs содержит больше исходных сведений, чем набор canonical fields.
- status может быть defaulted в active; нужно различать explicit и defaulted.
- specs.value может включать единицу, условие, диапазон, точность, «не более», «не менее» и пояснение. Нельзя извлекать число, потеряв qualifiers.

## 2. Извлечение характеристик и conflicts

scripts/model/enrich-products.mjs строит inputs/outputs из нескольких источников:
1. specs;
2. обозначения модулей (например AI/AO/DI/DO/DOR);
3. описаний connectors.

Приоритет выбора в скрипте: specs, затем title, затем connectors. Отчёт migration/model/enrich-report.md фиксирует два расхождения:
- MP-AI10-AO4-DI6: analog outputs 2 (характеристики) против 4 (обозначение);
- МР AI4-AO2-DI2-DO2-D: discrete outputs 6 (характеристики) против 2 (обозначение).

Текущий frontmatter не содержит отдельного provenance/conflict field для этих projection values. Поэтому:
- raw specs остаётся первичным textual evidence;
- inputs/outputs маркируются derived_projection;
- conflict report не должен теряться;
- при unresolved conflict structured claim не должен проходить как однозначный.

## 3. Relation provenance risks

scripts/model/enrich-relations.mjs создавал relations по точным упоминаниям обозначений в body text. В частности:
- software links — если обозначение ПО встречается в тексте изделия или обозначение изделия встречается в тексте ПО;
- article/solution examples — по точным упоминаниям;
- system examples — по совпадению изделий системы и упоминаниям в тексте;
- page products/systems — по упоминаниям изделий и их system mappings;
- news/products и article/products/systems — по упоминаниям.

Алгоритм учитывает регистр, нормализует тире/пробелы, ограничивает количество links и исключает страницы-перечни. Он не является инженерной экспертизой.

scripts/model/enrich-products.mjs дополнительно формирует:
- related из legacy good_id links и текстовых упоминаний;
- variant_of по шаблонам обозначений;
- inputs/outputs по эвристикам характеристик, обозначений и клемм.

Следствие: поле в frontmatter не всегда равно manually reviewed relation. Источник не хранит field-level reviewed marker. Наличие relation и успешный check-content подтверждают лишь существование target, не истинность связи.

### Другие миграционно-генерируемые поля

- systems.summary формируется из первого подходящего абзаца body.
- systems.applications заполняется hard-coded mapping в enrich-systems.mjs.
- systems.documents извлекаются из отдельных Markdown-ссылок; kind выводится regex по названию/URL, version — из заголовка года.
- pages.kind=solution выставляется для hard-coded списка из 13 страниц; images переносится из первой картинки body.
- pages.groups на странице resheniya строится из заголовков и ссылок.
- groups.system назначается через hard-coded GROUP_SYSTEM mapping или совпадение slug.

Текущий source frontmatter не позволяет установить, какие из этих значений были вручную скорректированы после миграции. До отдельного review сохранять их origin как legacy_frontmatter_origin_unknown либо известный derivation type, а не считать автоматически проверенными.

### Правила допуска relation types

| Relation | Source origin | Без дополнительной проверки |
|---|---|---|
| products.group | Legacy/catalog mapping | Допустимо как catalog membership, не engineering compatibility |
| products.systems | В основном old catalog/group tables; target может быть Category | Допустимо как source association после разделения System/Category; не как proof of compatibility |
| groups.system | Enrichment mapping | Навигационное соответствие группы и страницы |
| products.related | Legacy link и/или textual mention | Только generic related/navigation |
| products.variant_of | Pattern-based enrichment | Candidate variant relation, пока не reviewed |
| products.software | Textual mention matching | Candidate association, не доказательство совместимости |
| products.articles/solutions | Textual mention matching | Example/reference navigation, не proof of use |
| systems.articles/solutions | Co-occurrence of products from system | Example/reference navigation |
| pages.products/systems | Textual mention matching | Candidate mapping; не подтверждённый composition list |
| news.products | Textual mention matching | Mention association |
| articles.products/systems | Textual mention matching | Mention association |
| pages.groups.items | Navigation links | Только page grouping/navigation |
| industries.yaml mappings | Предварительная классификация | Не использовать как подтверждённую engineering relation |

products.systems target обязательно проверяется на systems.kind. Category membership нельзя интерпретировать как участие изделия в инженерной системе.

## 4. Taxonomy and migration drift

Обнаружены расхождения между актуальными данными и вспомогательными migration docs/scripts:

1. docs/content-model.md указывает 42 pages, но фактическое число Markdown records в src/content/pages/ на pinned commit — 40.
2. docs/content-model.md указывает 109 изделий с related, а migration/model/enrich-report.md — 108.
3. В docs/content-model.md и migration/model/coverage.md различаются некоторые проценты заполнения canonical fields. Например mass, dimensions, temperature и lifetime.
4. src/content/systems/radiokontsentrator-brk.md явно содержит kind: category, но scripts/model/enrich-systems.mjs не включает slug в hard-coded category set, а migration/model/enrich-systems-report.md описывает его как system.
5. industries.yaml прямо помечен как предварительный список; распределение систем, решений, материалов и изделий требует уточнения владельцем.
6. src/pages/search-index.json.ts обозначает все systems одним поисковым типом system, не сохраняя category distinction.

Решение: для adapter использовать pinned source records + текущую schema; migration reports/scripts — только provenance clues. Не использовать их как замену текущему frontmatter.

## 5. Support Catalog risks

- documents schema содержит title/kind/url и optional version/date.
- certificates может быть PDF/URL document либо scan image.
- loadDocuments() объединяет entries по exact URL и сохраняет metadata первой записи; последующие occurrences только добавляют owners.
- При одинаковом URL с разными title/kind/version/date текущая логика сайта не формирует conflict report.
- ServiceDoc не сохраняет date; doc-index.json передаёт title/kind/section/version/url/owners.
- check-content.mjs проверяет только URL prefix, не HTTP availability, content type, redirects, PDF validity или revision.

RAG adapter должен хранить все owner-field occurrences и metadata variants. Автоматическое объединение возможно только после явной проверки identity. Документы с kind software/other/scan не отправлять в PDF parser автоматически.

## 6. CMS/schema alignment note

public/admin/config.yml содержит комментарий, что Sveltia CMS пока не используется. Его product document fields не полностью повторяют Zod schema: product documents не expose version/date; certificates hidden; system documents expose version but not date.

Это не мешает read-only ingestion из Markdown, но означает, что будущие редакторские изменения могут не иметь всех schema fields в UI. В рамках RAG проекта нельзя менять CMS сайта; это отдельный вопрос владельца.

## 7. Required ingestion safeguards

1. Read raw frontmatter and Markdown before applying schema defaults.
2. Store raw field presence and effective default separately.
3. Preserve every specs row and raw unit/qualifier.
4. Tag derived projections and their extraction method.
5. Keep source approval and field/relation semantic review as separate states.
6. Do not treat heuristic mention relations as technical proof.
7. Keep navigation and taxonomy links outside engineering relation graph.
8. Preserve all Support Catalog owners and detect metadata conflicts.
9. Require exact PDF approval and byte hash; never infer from page approval.
10. Fail closed on unresolved conflict, missing provenance or stale source snapshot.

## 8. Owner decisions requested

- Confirm the proposed provenance classes in ADR-0013.
- Confirm which relations can be used for navigation only.
- Confirm whether any existing relations have already been manually reviewed outside the Git source and can be supplied as a separate reviewed manifest.
- Confirm whether applications.yaml can be used as a controlled site taxonomy, while industries.yaml remains provisional.
- Confirm whether the first pilot should initially answer only from direct product/system facts and approved PDF passages, leaving heuristic relations out of answer generation.
