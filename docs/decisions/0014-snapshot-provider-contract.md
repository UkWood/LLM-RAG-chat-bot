# ADR-0014: provider-neutral Snapshot Provider на основе Git REST API

Дата: 2026-11-09  
Статус: **ACCEPTED — решение владельца**  
Область: получение read-only Git snapshot для Saturn Site Content Adapter в UkWood/LLM-RAG-chat-bot.

## Контекст

PR #20 добавил pure/offline Saturn Site Content Adapter. Он принимает неизменяемый PinnedSiteSnapshot и проверяет Git blob SHA по исходным bytes, но сам не обращается к Git-сервису и не получает исходный snapshot.

Требуется определить транспорт и границу между физическим GitHub/Gitea remote и стабильной логической идентичностью доверенного источника. В перспективе исходный сайт может быть перенесён с GitHub на собственный Gitea без изменения канонической модели знаний и адаптера.

Одновременно необходимо сохранить утверждённую в ADR-0012 и ADR-0013 архитектуру трёх каналов: Site Content Adapter, Support Catalog Adapter и External Document Adapter. PDF входят в обязательный корпус консультанта, хотя не обязаны входить в обычный Git snapshot сайта.

## Решение

### 1. REST API и последовательность провайдеров

- Основной транспорт Snapshot Provider — Git REST API.
- Первая реализация — GitHub REST API.
- Последующая реализация — Gitea REST API, реализующая тот же provider-neutral контракт и общий набор contract tests.
- REST API является согласованным основным способом получения snapshot; Git clone/CLI не является fallback текущего этапа.
- Provider-specific API, auth, response decoding, rate limits и особенности версий сервера изолируются внутри соответствующих реализаций.
- Site Content Adapter и канонические contracts не зависят от GitHub, Gitea, API URL, SDK, credentials, CI или deployment.

### 2. Логическая и физическая идентичность

Доверенный источник фиксирован:
- logical source ID: UkWood/Saturn-Main-Site;
- branch: main;
- Git ref: refs/heads/main.

Каждый физический remote связывается с этой логической идентичностью через доверенную конфигурацию. PinnedSiteSnapshot.repository всегда содержит logical source ID, а не физический URL или namespace Git-сервиса.

Переезд GitHub → Gitea меняет remote binding и реализацию транспорта, но не logical source ID, canonical entity IDs и семантику source provenance.

### 3. Pinning commit/tree и границы доверия

Git-провайдер является доверенным источником соответствия:

refs/heads/main → commit SHA → root tree SHA.

Branch ref разрешается один раз в начале синхронизации. После фиксации commit все дальнейшие операции выполняются только по неизменяемым commit/tree/blob SHA. Повторное обращение к подвижной ветке, включая финальную проверку HEAD, в рамках одной синхронизации запрещено.

Если main переместился во время получения файлов, текущая синхронизация остаётся привязанной к первоначальному commit. Следующая синхронизация самостоятельно разрешит актуальный main.

Проверка commit/tree означает согласованность идентификаторов в ответах доверенного провайдера и полное перечисление выбранного дерева. Она не объявляется независимой криптографической проверкой commit/tree: сырые сериализованные Git commit/tree objects самостоятельно не загружаются и не хешируются. Проверка подписи, автора или независимой аутентичности этих объектов в это решение не входит.

Семантика tree API различается по провайдерам и не должна трактоваться одинаково:

- GitHub: `truncated=true` у recursive tree response означает, что ответ ограничен; полный обход выполняется non-recursive запросами по закреплённым tree SHA.
- Gitea: endpoint `GET /repos/{owner}/{repo}/git/trees/{sha}` поддерживает `page`, `per_page`, `total_count` и `truncated`; в документированном API `truncated=true` означает наличие следующей страницы. Gitea provider обязан пройти последовательные страницы и проверить номера страниц, постоянство tree SHA и total_count, отсутствие дубликатов и точное совпадение числа собранных entries с total_count. Несогласованность `truncated` и total_count требует bounded terminal-page probe либо fail-closed, но не молчаливого принятия неполного дерева.
- Gitea API reference описывает path parameter `sha` как commit SHA, тогда как response `sha` является tree object SHA. Текущий upstream код Gitea допускает lookup как по commit ID, так и по tree ID, но это должно быть проверено на точной целевой версии сервера. Если child-tree lookup по tree SHA не поддерживается, разрешён безопасный fallback: recursive tree по закреплённому commit SHA с полной пагинацией. Если он не обеспечивает полноту, provider завершается явной ошибкой.

До включения Gitea provider обязательны version-specific conformance tests: root lookup по commit SHA, child lookup по tree SHA, pagination и полная сверка total_count. Основание: [Gitea Get Tree API](https://docs.gitea.com/enterprise/api/operations/get-tree/), [upstream implementation](https://github.com/go-gitea/gitea/blob/main/services/repository/files/tree.go), [issue #35117](https://github.com/go-gitea/gitea/issues/35117), [fix PR #35177](https://github.com/go-gitea/gitea/pull/35177).

### 4. Blob integrity и Git object format

Каждый выбранный blob загружается по SHA, найденному в закреплённом tree. Его bytes независимо проверяются пересчётом канонического Git blob object hash по точному заголовку Git blob и исходным bytes с использованием алгоритма object format данного репозитория.

Raw content SHA-256 вычисляется дополнительно и хранится как content provenance. Он не заменяет Git blob object ID.

Object format должен быть установлен по авторитетной информации провайдера/репозитория либо по явно заданной и проверенной trusted configuration. Нельзя выбирать алгоритм только по бренду Git-сервиса или только по длине строки SHA.

Текущие PinnedSiteSnapshot, SiteFileRevision, SiteSourceRevision и Site Content Adapter поддерживают 40-символьные SHA-1 object IDs. Поэтому contract v0.1 допускает успешную выдачу snapshot только для SHA-1 object format. Неизвестный или неподдерживаемый формат приводит к fail-closed. Поддержка SHA-256 Git object format потребует отдельного versioned изменения provider-neutral canonical contracts и adapter verification; это не часть данного этапа.

### 5. Выбор файлов

Snapshot Provider получает только файлы, необходимые существующему Site Content Adapter:
- все Markdown-файлы под src/content/ с расширением .md;
- все YAML-файлы под src/data/ с расширением .yaml или .yml;
- src/content.config.ts;
- tracked regular files под src/pages/ с поддерживаемыми расширениями `.astro` и `.ts` (исключая `.d.ts`); любой другой тип файла диагностируется как route-source drift и приводит к fail-closed, пока политика не будет явно обновлена;
- astro.config.mjs;
- src/lib/url.ts, src/lib/nav.ts и src/lib/service.ts, если они присутствуют.

src/content.config.ts и astro.config.mjs обязательны. Каждый выбранный файл, присутствующий в закреплённом tree, должен быть получен полностью и пройти проверку. Отсутствие blob, ошибка получения, неполный ответ, несовпадение hash или неподдерживаемый тип объекта не могут быть проигнорированы.

Новые Markdown collections/records, YAML dictionaries и файлы маршрутов `.astro`/`.ts` обнаруживаются по дереву автоматически. На проверенном read-only commit Saturn-Main-Site `084d759487bfab6e111549c9b5469711ac5fc13e` baseline составляет 23 route files: 19 `.astro` и 4 `.ts`. Другие расширения под src/pages/ не скачиваются и не игнорируются молча: они создают route-source drift и блокируют sync до явного обновления политики и тестов. Выборочная политика путей версионируется отдельно от Git provider. Изображения, PDF, шрифты, видео, generated assets, compiled search indexes и прочие ненужные бинарные материалы массово не скачиваются.

### 6. PDF — обязательная часть корпуса, но отдельный канал получения

PDF остаются полноценной и обязательной частью информационного корпуса AI Technical Consultant согласно ADR-0012 и ADR-0013.

Обычный Git snapshot не загружает PDF. Их обнаружение и каталогизация относятся к Support Catalog Adapter; получение PDF по доверенным ссылкам, извлечение текста и формирование page-level evidence относятся к External Document Adapter. Это разделение ответственности не является исключением PDF из корпуса и не вводит дополнительный ручной approval.

Архитектура также должна допускать будущий случай, когда PDF физически хранится в Git/Gitea. Если Support Catalog record будет содержать точные logical source ID, commit SHA, path и blob SHA, будущий External Document Adapter или отдельный Git-backed document source сможет выборочно получить этот blob через тот же read-only provider-neutral Git object transport, проверить принадлежность path/blob закреплённому commit и повторно проверить object hash и raw content SHA-256.

Такой механизм не входит в обычный PinnedSiteSnapshot file set, не запускает массовую загрузку assets и не переносит PDF parsing в Snapshot Provider. Git-backed PDF retrieval не реализуется в рамках этого решения.

### 7. Безопасность и полнота

Обязательны HTTPS, проверка TLS, allowlist API origin/repository, read-only credentials с минимальными правами, защита secrets, запрет user-controlled URL/ref/path, контроль redirects, валидация путей и типов объектов, конечные resource limits и bounded retries.

Неполный snapshot, усечённое дерево, отсутствие обязательного файла, ошибка получения blob, несовпадение Git object hash, неизвестный object format или превышение hard limit означают ошибку синхронизации. Частичный snapshot не возвращается и не может заменить предыдущий активный Knowledge Snapshot.

## Последствия

- GitHub можно использовать первым без привязки Site Content Adapter к GitHub API.
- Gitea можно подключить позднее как вторую реализацию того же контракта.
- Изменение main во время sync не создаёт смешанный snapshot: текущая операция остаётся закреплена на исходном commit.
- Полнота дерева и целостность каждого blob становятся проверяемыми условиями успешной синхронизации.
- PDF ingestion сохраняет отдельный канал и остаётся обязательной частью целевой базы знаний.
- Текущая canonical model остаётся SHA-1-only; иная Git object format требует отдельного изменения contracts/adapter.

## Не входит в решение

Не реализуются GitHub/Gitea Provider, PDF ingestion, Git-backed PDF retrieval, изменения canonical contracts или Site Content Adapter, retrieval/embedding/reranking, LLM/provider, API/UI, deployment и production scheduling.

Saturn-Main-Site остаётся строго READ-ONLY. Любое изменение существующих canonical contracts сначала выносится на отдельное архитектурное согласование.
