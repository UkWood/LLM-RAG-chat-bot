# Архитектура технического консультанта Сатурна v0.1

Дата: 2026-11-08  
Статус: целевая архитектура пилота; отдельные детали требуют проверки на реальном корпусе и целевой инфраструктуре.

## 1. Архитектурный принцип

Сайт и консультант — два независимых продукта.

Сайт остаётся статическим Astro-проектом. Консультант работает в отдельном репозитории, имеет собственный процесс подготовки знаний, собственные индексы, backend API и пользовательский интерфейс.

Репозиторий сайта читается только из зафиксированного snapshot. Интеграция не должна требовать изменений сайта для разработки или тестирования RAG.

## 2. Контуры системы

~~~mermaid
flowchart TB
  subgraph SRC["Read-only источники Saturn-Main-Site"]
    CONTENT["Markdown + frontmatter<br/>products / systems / articles / news / pages / groups"]
    DICT["YAML-словари<br/>interfaces / protocols / synonyms / applications / IO"]
    DOCMETA["documents / certificates<br/>из карточек products и systems"]
    FILES["Старый файловый сервер<br/>PDF / сканы / ПО / сертификаты"]
  end

  subgraph BUILD["Контур подготовки знаний"]
    SNAP["Read-only snapshot<br/>commit + path + hash"]
    REG["Registry / approval policy<br/>deny by default"]
    MAP["Site adapter<br/>entities + facts + relations"]
    CATALOG["Support catalog adapter<br/>document metadata"]
    FETCH["Allowlisted document fetcher"]
    PARSE["PDF/text parser<br/>pages + tables + headings"]
    CHUNK["Canonical chunks + provenance"]
    SNAPSHOT["Immutable Knowledge Snapshot"]
    LEX["BM25 index"]
    VEC["Local embeddings + Qdrant"]
  end

  CONTENT --> SNAP
  DICT --> SNAP
  DOCMETA --> SNAP
  FILES --> FETCH
  SNAP --> REG
  REG --> MAP
  REG --> CATALOG
  CATALOG --> FETCH
  FETCH --> PARSE
  MAP --> CHUNK
  PARSE --> CHUNK
  CHUNK --> SNAPSHOT
  SNAPSHOT --> LEX
  SNAPSHOT --> VEC

  subgraph RUN["Контур ответа"]
    UI["Отдельный статический UI<br/>вопрос → ответ → источники"]
    API["FastAPI"]
    POLICY["Query privacy + source policy"]
    ROUTER["Query planner / router"]
    RETR["Hybrid retrieval<br/>BM25 + vector + fusion"]
    RERANK["Local reranker"]
    GATE["Evidence / grounding gate"]
    PROVIDER["LLMProvider<br/>Qwen Cloud или local endpoint"]
    VERIFY["Citation & output validation"]
    RESULT["Answer / clarification / refusal"]
  end

  UI --> API --> POLICY --> ROUTER
  ROUTER --> RETR
  LEX --> RETR
  VEC --> RETR
  RETR --> RERANK --> GATE
  GATE --> PROVIDER --> VERIFY --> RESULT --> API --> UI
  GATE --> RESULT
~~~

## 3. Три канала знаний

### 3.1. Структурированный контент сайта

Адаптер читает выбранные Markdown-записи и словари из точного commit сайта. Astro runtime не требуется: адаптер должен работать с экспортированным/прочитанным содержимым и проверяемой схемой.

Основные типы:
- Product / Device — изделия и их технические поля;
- System — инженерные системы;
- Category — каталоговая категория, не система;
- Software — семантический тип для изделий группы программного обеспечения; в исходной схеме это всё ещё запись products;
- Group — группа каталога;
- Article — статья;
- Solution — страница pages.kind=solution;
- News — новость;
- Page — иная опубликованная информационная страница.

Характеристики импортируются не только как общий текст. Канонические поля и строки specs должны сохранять исходное имя, значение, единицы, условия и ссылку на исходный field path.

### 3.2. Каталог документов раздела «Поддержка»

Отдельный адаптер строит реестр файлов из documents и certificates опубликованных изделий и систем. Он сохраняет:
- title;
- kind;
- version/date;
- исходный URL;
- раздел поддержки;
- список владельцев (product/system) и их canonical URL;
- provenance поля, откуда пришла ссылка.

Этот каталог — metadata index, а не полнотекстовый индекс PDF.

### 3.3. Полнотекстовые документы

Только после отдельного допуска документ скачивается по точному URL из каталога. Fetcher работает по allowlist хостов/путей, ограничивает redirects, размер, время и тип содержимого. Для каждой версии вычисляется hash исходных bytes.

Parser извлекает текст, заголовки, таблицы и физические страницы. Для PDF каждый chunk хранит page number. Если скан или таблица извлечены ненадёжно, источник помечается как требующий OCR/ручной проверки и не используется для технических утверждений до проверки.

## 4. Как учитываются два существующих поиска сайта

Существующие пользовательские функции не объединяются и не меняются:

1. /search/ — поиск по страницам и карточкам. Его индекс включает изделия, системы, статьи, новости, группы и часть страниц; у изделий/систем в индекс попадают в том числе названия документов. Полнотекстовое содержимое PDF в него не входит.
2. /service/search/ — поиск по каталогу документации. Он ищет по обозначению/наименованию изделия или системы и названию документа, учитывает тип, версию и владельцев. Сам PDF не разбирает и его текст не индексирует.

RAG не должен имитировать только один из этих поисков. Для вопроса он обращается к трём каналам знаний из раздела 3. Один вопрос может получить:
- факт из карточки изделия;
- relation из структурированного контента;
- ссылку из Support catalog;
- дополнительное доказательство из конкретной страницы PDF.

Каждый результат сохраняет тип и provenance. Это позволяет консультанту отвечать на вопрос о характеристике и одновременно показывать руководство, не смешивая «найти файл» с «найти ответ внутри файла».

## 5. Контракты данных

Все контракты должны быть versioned и иметь строгую валидацию.

### SourceRecord

~~~json
{
  "source_id": "saturn:products/bkd-pk-rf-2",
  "source_kind": "site_content",
  "source_revision": "git:084d759...:src/content/products/bkd-pk-rf-2.md",
  "content_sha256": "…",
  "title": "БКД-ПК-RF.2",
  "entity_type": "Product",
  "canonical_url": "/products/bkd-pk-rf-2/",
  "visibility": "UNKNOWN",
  "approval_state": "pending",
  "allowed_usage": [],
  "approval_id": null
}
~~~

### Entity и Relation

Entity содержит стабильный entity_id, тип, title, designation/name, status/notice, aliases и provenance. Relation содержит from_entity_id, to_entity_id, relation_type, source_id, source_field_path и признак явной/вычисленной обратной связи.

### DocumentRecord

DocumentRecord хранит отдельный document_id, URL, тип, title, version/date, hash bytes, доступность, количество страниц, owners, approval и parser revision. Стабильный URL не считается неизменяемой версией: если bytes изменились, появляется новая revision и требуется повторный допуск.

### Chunk

Chunk хранит chunk_id, document_id, source_id, snapshot_id, текст, heading path, page_start/page_end, entity IDs, visibility, content hash и chunker/parser revision.

### Evidence и Citation

Evidence хранит найденный chunk, retrieval channel, ranks/scores и policy revision. Citation строится backend из зарегистрированного источника: title, canonical URL, section, page, version. Модель не имеет права создавать эти поля.

## 6. Поиск и построение ответа

1. Проверить и нормализовать запрос: обозначения, кириллица/латиница, дефисы, точки, словари синонимов и точные алиасы.
2. Определить сущности и типы потребности без потери отрицания, квалификаторов, единиц и ограничений.
3. Выполнить lexical и dense retrieval по одному активному snapshot.
4. Объединить результаты (например, RRF), затем rerank локальной моделью.
5. Собрать evidence по каждому требованию вопроса. Проверить полноту списков/групп и отсутствие конфликтов.
6. Проверить policy на конкретные source revisions и назначение генерации.
7. Передать модели только ограниченный набор допущенных фрагментов и инструкции формата ответа.
8. Проверить, что каждое утверждение имеет evidence, все source IDs/page references существуют, а цитаты сформированы backend.
9. Вернуть один из статусов: answered, clarification, refused, service_error.

Система не должна считать retrieval score вероятностью истинности. Точный source hit не доказывает, что найдено достаточно данных для полного ответа.

## 7. API и интерфейс

Предлагаемый минимальный API:

- POST /api/v1/chat — один вопрос, опциональный короткоживущий conversation/session ID;
- GET /health — liveness;
- GET /ready — readiness с проверкой активного snapshot/provider;
- отдельный закрытый diagnostic endpoint для разработчика.

Пример ответа:

~~~json
{
  "status": "answered",
  "answer": "…",
  "citations": [
    {
      "source_type": "pdf",
      "title": "Руководство по эксплуатации",
      "url": "https://…/manual.pdf",
      "page": 18,
      "entity_ids": ["product:bkd-pk-rf-2"]
    }
  ],
  "request_id": "…"
}
~~~

UI в пилоте: одно поле вопроса, кнопка отправки, ответ, список источников. Не требуется история диалогов между визитами, пользовательская авторизация или загрузка документов. Короткий session context допустим только для непосредственного уточнения в рамках текущего диалога.

## 8. Хранение и модели

- Registry/manifests — JSON/JSONL, versioned в AI-репозитории.
- Исходные документы и крупные corpus/index artifacts не коммитить.
- Snapshot и parser outputs — отдельное файловое хранилище.
- BM25 и dense index должны ссылаться на один snapshot и иметь одинаковое покрытие chunks.
- Qdrant — local mode или закрытый сервис в private network; никогда не открывать порт в Internet.
- Embeddings и reranker — локальные, CPU-first.
- LLM — сменный provider. Qwen Cloud используется только после подтверждения endpoint/API, региона, условий данных и отдельного cloud approval. Позже можно подключить local Qwen/llama.cpp через совместимый интерфейс.
- SQL-сервер для MVP не нужен.

## 9. Безопасность и эксплуатация

- Git-доступ к сайту — read-only (read-only deploy key/token/App permission).
- PDF fetch — allowlist точных хостов и источников; не принимать произвольные URL из запроса пользователя.
- Ограничения parser: максимальный размер файла, число страниц, время CPU/память, запрет сетевого доступа из parser worker.
- HTTPS, rate limits, CORS allowlist, request size limits, provider timeout и cancellation.
- Secrets только на backend, не в frontend/репозитории/logs.
- Безопасные логи: request ID, outcome, latency, source IDs и reason codes; не писать API keys и полный контекст документов.
- Revocation должна блокировать источник на runtime даже если старый snapshot ещё существует.
- Обновление snapshot выполняется атомарно; при ошибке остаётся предыдущий проверенный snapshot.

## 10. Границы повторного использования проектов

Основная база разработки — текущий репозиторий UkWood/LLM-RAG-chat-bot: его ingestion, source registry, snapshots, retrieval, reranking, evidence gate и evaluation contracts должны быть предметом аудита и дальнейшего развития.

Отдельный проект/кодовая база RAG_chat может использоваться только как справочный материал по возможным интеграциям Ollama, OpenAI-compatible API, FastAPI и widget UI. Не переносить оттуда целиком прежний RAG engine и не включать коммерческую административную панель, multi-tenant, CRM или аналитическую платформу. Эти функции не входят в продукт.

## 11. Ключевые архитектурные ограничения

1. Не использовать MiniSearch как RAG backend.
2. Не считать doc-index.json полнотекстовым содержимым документа.
3. Не полагаться на публичный crawler как единственный источник.
4. Не выводить совместимость/отношения из смысловой похожести.
5. Не передавать документы во внешний LLM без точного cloud approval.
6. Не объединять в одном индексе PUBLIC и будущие INTERNAL-источники.
7. Не объявлять качество на synthetic corpus доказательством качества на документации Сатурна.
