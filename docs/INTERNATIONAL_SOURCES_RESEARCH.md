# Международные источники: проверка API и метрик

Дата обращения ко всем источникам: **2026-09-10**. Проверены официальные документы; доступность описанного endpoint не равна успешной проверке с пользовательскими credentials. Закрытые Scopus/JCR данные в ходе исследования не получены. Ниже — основания для реализации, а не заявление о полноте покрытия конкретного сотрудника.

## Матрица возможностей

| Источник | Доступ | Практическая роль | Ограничение интерпретации |
|---|---|---|---|
| Crossref REST | Без регистрации; polite pool с реальным `mailto` | DOI, библиография, ISSN, авторские поля, связи версий | Не реестр авторских профилей; цитирования ограничены графом Crossref |
| OpenAlex | Небольшой анонимный бюджет; бесплатный ключ увеличивает его | Профили, публикации, affiliations, citations, воспроизводимый расчёт метрик | Собственное покрытие и разрешение идентичностей; показатели нельзя подписывать «Scopus» |
| ORCID Public API | Публичное чтение; OAuth client credentials для `/read-public` | ORCID iD, связи с работами, публичные employment/education | Видимость и полнота зависят от записи; не источник citation count/h-index |
| Elsevier Scopus API | API key обязателен; полнота зависит от подписки и entitlement | Scopus author ID, документы, собственные citation/author metrics | API key сам по себе не гарантирует подписной доступ |
| Serial Title API | Elsevier key и применимые права | CiteScore, SJR, SNIP по журналам и годам | Значение SJR не содержит автоматически SJR quartile |
| SCImago | Публичные страницы/разрешённые выгрузки | SJR и квартили по category/year | Документированный публичный REST API в этой проверке не найден |
| JCR / Clarivate | Доступ по правам организации или проверяемый экспорт | JIF и JIF quartile по category/year | Не заменяется CiteScore или SJR; закрытый API здесь не подтверждён |

Основания: [Crossref access](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/), [OpenAlex API](https://help.openalex.org/api/endpoints/), [ORCID read tutorial](https://info.orcid.org/documentation/api-tutorials/api-tutorial-read-data-on-a-record/), [Elsevier authentication](https://dev.elsevier.com/tecdoc_api_authentication.html), [Elsevier journal metrics](https://dev.elsevier.com/journal_metrics.html).

## Crossref

Базовый адрес `https://api.crossref.org`. Подтверждены `GET /works/{doi}`, `GET /works?query.bibliographic=...`, `GET /journals/{issn}/works`. Параметры `filter`, `rows`, `select`, `cursor=*`; последующие страницы используют `message.next-cursor`. Нулевой результат поиска — отсутствие найденной записи по данному запросу, а не доказательство отсутствия публикации. [Официальное описание REST API](https://github.com/Crossref/rest-api-doc), [пагинация](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/).

Ключ публичному режиму не нужен; контакт передаётся параметром `mailto`. Обновление **21 июля 2026** уточняет лимиты: одиночные записи public/polite — 5/10 запросов в секунду, списки — 1/3. Polite pool ограничивается также по email, поэтому менять IP для обхода нельзя. Проверять `x-rate-limit-limit`, `x-rate-limit-interval`, `x-rate-limit-type`, учитывать 429. Таблица access дополнительно указывает concurrency 1/3. Надёжнее читать фактические headers и сохранять консервативные локальные лимиты. [Обновление Crossref 2026](https://community.crossref.org/t/refining-rest-api-limits-for-improved-stability-and-reliability/16137), [access/concurrency](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/).

`is-referenced-by-count` — число входящих цитирований в Crossref; `references-count` относится к библиографии самой работы. REST не предоставляет универсальный список всех цитирующих DOI любому пользователю. Полное Cited-by обслуживание имеет отдельные условия членства. Счётчики не сопоставимы напрямую со Scopus. [Crossref Cited-by](https://www.crossref.org/documentation/cited-by/).

## OpenAlex: существенное изменение относительно старых примеров

Документация authentication обновлена **19 августа 2026**: анонимные базовые запросы разрешены, ключ бесплатный. Поддерживаются `api_key=...` и `Authorization: Bearer ...`; для приложения предпочтителен header, чтобы ключ не попадал в URL журналов. Ограничение скорости — 100 запросов/с; `per_page` максимум **100**, обычная пагинация до 10 000 результатов, далее cursor. Нельзя копировать старое предположение «ключ всегда обязателен» или `per_page=200` без проверки. Использовать `GET https://api.openalex.org/rate-limit` с credentials и headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Credits-Used`, `X-RateLimit-Reset`. [Актуальная authentication](https://help.openalex.org/api/authentication/).

На дату проверки бесплатный дневной бюджет: $0.10 без ключа, $1 с бесплатным ключом. Это единицы учёта API, не обещание списания денег. Singleton lookup бесплатен; list/filter стоит $0.10 за 1000 вызовов, keyword search — $1 за 1000. Не включать платный план автоматически. [Стоимость операций, обновлено 9 августа 2026](https://help.openalex.org/access/example-costs/).

Подтверждённые формы запросов:

```text
GET https://api.openalex.org/authors/{openalex_author_id}
GET https://api.openalex.org/authors?search={name}
GET https://api.openalex.org/works/{openalex_work_id}
GET https://api.openalex.org/works?filter=authorships.author.id:{id},publication_year:2020-2025&per_page=100&cursor=*
GET https://api.openalex.org/sources/{openalex_source_id}
```

Это шаблоны, placeholders URL-кодируются библиотекой HTTP. В ответе страницы `results`, следующий cursor в `meta.next_cursor`. [Endpoints](https://help.openalex.org/api/endpoints/), [официальный quick reference с фильтрами](https://help.openalex.org/api/llm-quick-reference/).

`cited_by_count`, `summary_stats.h_index`, `counts_by_year` принадлежат OpenAlex. `summary_stats.2yr_mean_citedness` нельзя маркировать JCR JIF. Вложенные агрегаты пересчитываются отдельно и могут расходиться с текущей выдачей; для анализа за период получать works и рассчитывать показатели на явном наборе документов. [Common attributes](https://help.openalex.org/data/common-attributes/), [предупреждение о задержке агрегатов](https://help.openalex.org/how-to/counting/).

## ORCID

Production: `https://pub.orcid.org/v3.0` (Public), `https://api.orcid.org/v3.0` (Member). `POST https://orcid.org/oauth/token` с form fields `client_id`, `client_secret`, `grant_type=client_credentials`, `scope=/read-public` выдаёт bearer token для публичного чтения. Не путать это с пользовательским OAuth `/authenticate`, подтверждающим владение iD. `/read-limited` доступен через Member API с согласием пользователя. [Официальный FAQ, hosts/scopes/token](https://info.orcid.org/documentation/integration-and-api-faq/).

```text
GET https://pub.orcid.org/v3.0/{orcid}/record
GET https://pub.orcid.org/v3.0/{orcid}/works
GET https://pub.orcid.org/v3.0/{orcid}/work/{put_code}
GET https://pub.orcid.org/v3.0/search/?q={query}
Accept: application/vnd.orcid+json
Authorization: Bearer {token}
```

Работы сгруппированы по идентификаторам: несколько assertions не считать несколькими публикациями. Сохранять visibility, источник assertion и отношения external ID (`self`, `part-of`, `version-of`). [Чтение и группировка записей](https://info.orcid.org/documentation/api-tutorials/api-tutorial-read-data-on-a-record/).

Опубликованные квоты: anonymous 12 req/s и 25k reads/day на IP; registered Public 12 req/s и 100k/day на Client ID; Member 24 req/s без дневной usage quota. Burst 40; превышение очереди может дать **503**. Public API имеет условия некоммерческого использования; применимость к организационной интеграции проверяется до production. [Квоты и условия ORCID](https://info.orcid.org/ufaqs/what-are-the-api-limits/).

## Elsevier / Scopus

Каждый запрос содержит `X-ELS-APIKey`; institution access определяется IP подписчика или `X-ELS-Insttoken`, выданным Elsevier. Insttoken не выводится из ключа. Секреты в env, не в SQLite/raw response metadata/логи. `401` означает проблему credentials; `403` может означать отсутствие entitlement, что не эквивалентно пустому результату. [Authentication](https://dev.elsevier.com/tecdoc_api_authentication.html), [описание headers/status Serial Title](https://dev.elsevier.com/documentation/SerialTitleAPI.wadl).

| Назначение | Подтверждённый GET endpoint | Основание |
|---|---|---|
| Документы | `https://api.elsevier.com/content/search/scopus?query=...` | [Scopus Search WADL](https://dev.elsevier.com/documentation/ScopusSearchAPI.wadl) |
| Профиль автора | `https://api.elsevier.com/content/author/author_id/{id}` | [Author Retrieval WADL](https://dev.elsevier.com/documentation/AuthorRetrievalAPI.wadl) |
| Автор по ORCID | `https://api.elsevier.com/content/author/orcid/{orcid}` | [Author Retrieval WADL](https://dev.elsevier.com/documentation/AuthorRetrievalAPI.wadl) |
| Запись по Scopus ID | `https://api.elsevier.com/content/abstract/scopus_id/{id}` | [Abstract Retrieval WADL](https://dev.elsevier.com/documentation/AbstractRetrievalAPI.wadl) |
| Журнал по ISSN | `https://api.elsevier.com/content/serial/title/issn/{issn}` | [Serial Title WADL](https://dev.elsevier.com/documentation/SerialTitleAPI.wadl) |

Author Retrieval поддерживает `view=METRICS`; сохранять только возвращённые поля, не обещать одинаковую полноту всем ключам. Author ID может быть superseded: WADL описывает 300/301 и `alias` behavior. Нужна история crosswalk, а не бесследная перезапись ID.

Опубликованные квоты сбрасываются раз в 7 дней, отдельно для каждого API: Search 20k/9 req/s; Author Retrieval 5k/3; Abstract Retrieval 10k/9; Serial Title 20k/6. Search STANDARD до 200 результатов, COMPLETE до 25. На 429 читать `X-RateLimit-Reset`, `X-ELS-Status`; `QUOTA_EXCEEDED` не лечится быстрыми повторами. Citation Overview — **access-controlled API**, по умолчанию не включён, требуется рассмотрение Elsevier. [Официальные квоты](https://dev.elsevier.com/api_key_settings.html).

В официальном JSON example Serial Title присутствуют `SJRList.SJR`, `SNIPList.SNIP`, годы `@year`, `citeScoreYearInfoList` с отдельными current/tracker years. Это пример старых данных, не свежие значения. Он не доказывает наличие category-level quartile в любом response. [Официальный JSON sample](https://dev.elsevier.com/payloads/metadata/serialTitleSearchResp.json). Условиями показа метрик ограничена репликация продукта и коммерческое использование; наличие API не даёт произвольных прав перепубликации. [Journal metrics policy](https://dev.elsevier.com/journal_metrics.html).

## Квартили: три самостоятельных системы

| Система | Что ранжируется | Как хранить |
|---|---|---|
| CiteScore | Scopus sources, собственный показатель/percentile | `system=CiteScore`, год метрики, ASJC category, значение/percentile, подтверждённый quartile |
| SJR | Журналы по SCImago Journal Rank | `system=SJR`, год, category, SJR и quartile отдельно |
| JCR JIF | Журналы по Journal Impact Factor в Web of Science category | `system=JCR_JIF`, JCR metric year, category, rank и quartile |

CiteScore использует четырёхлетнее окно; старое описание launch 2016 с тремя годами не использовать. SJR взвешивает цитирования по престижу источника. SNIP нормирует различия дисциплин и не является квартилированием. [Elsevier journal metrics](https://www.elsevier.com/researcher/author/tools-and-resources/measuring-a-journals-impact), [Elsevier Scopus metrics](https://www.elsevier.com/en-au/products/scopus/metrics), [Elsevier современное описание четырёхлетнего окна](https://researcheracademy.elsevier.com/uploads/2024-09/4768%20Get%20published%20and%20noticed%20A5_WEB.pdf).

SCImago явно показывает таблицу `Category / Year / Quartile`; один журнал может иметь разные категории. Прямое чтение страницы help при проверке вернуло 403; обход защиты не выполнялся. Публичный поддерживаемый API не подтверждён, поэтому baseline — импорт разрешённого экспорта/введённого значения со ссылкой и годом. [Пример официальной карточки SCImago с определением квартилей](https://www.scimagojr.com/journalsearch.php?q=14762&tip=sid).

JCR назначает rank/quartile для каждой категории. Для JIF одинаковые значения имеют одинаковый rank, с пропусками следующих рангов; поэтому распределение журналов может не быть ровно по 25%. JIF quartile нельзя получать простым округлением чужого percentile. [Clarivate: ranks, ties, quartiles](https://clarivate.com/academia-government/blog/a-primer-on-ties-in-the-jcr/).

**Проектное решение:** нельзя иметь одно необъяснимое поле `quartile`. Все значения получают `provider`, `metric_system`, `metric_year`, `category_id/name`, `retrieved_at`, `source_url`, `raw_evidence`, `status`. Для best quartile сохранять исходные категории и явно именовать правило выбора. Если года публикации нет в доступной выгрузке, возвращать `missing_year`, а не молча подставлять последний год. Год релиза отчёта и год метрики различать. Нулевые цитирования — наблюдавшийся ноль; credentials missing/forbidden/not found/parse error — разные статусы с `value=null`.

## Минимальная проверка перед production

1. Crossref/OpenAlex: один singleton и одна ограниченная страница с сохранением даты, статуса и обезличенных headers; не заявлять полную выборку при незавершённом cursor.
2. ORCID: проверить публичный record и раскрытие works groups; не просить у пользователя пароль ORCID.
3. Scopus: health check с настроенным key, отдельный entitlement status каждого используемого endpoint/view. При недоступности предложить официальный экспорт, не scrape.
4. Journal metrics: тест с двумя категориями и двумя годами должен сохранять все наблюдения; пустое значение запрещено автоматически превращать в Q4.
5. При сравнении авторов показывать источник, период публикаций, момент citation snapshot и покрытие. Вычисленный h-index по выбранному периоду обозначать как локальный расчёт по указанному корпусу.
