# Реестр первичных источников

Дата обращения: **10 сентября 2026 года**. Ниже перечислены документы организаций — владельцев данных и проверенные ими опубликованные интерфейсы. Это реестр оснований и ограничений; наличие документации не означает, что проект располагает подпиской или ключом. Подробности: [международные источники](docs/INTERNATIONAL_SOURCES_RESEARCH.md), [российские источники](docs/RUSSIAN_SOURCES_RESEARCH.md).

| Организация / первичный источник | Подтверждённый факт и границы |
|---|---|
| Crossref — [REST access/authentication](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) | Публичное чтение без регистрации, polite `mailto`, concurrency и response headers |
| Crossref — [изменения 21.07.2026](https://community.crossref.org/t/refining-rest-api-limits-for-improved-stability-and-reliability/16137) | Списки public/polite: 1/3 req/s; singleton: 5/10; лимит polite также по email |
| Crossref — [REST documentation](https://github.com/Crossref/rest-api-doc) | `works`, DOI lookup, filters, bibliographic/author queries; официальный репозиторий организации |
| Crossref — [Cited-by](https://www.crossref.org/documentation/cited-by/) | `is-referenced-by-count` описывает граф Crossref; условия получения списков цитирующих работ отличаются от публичного счётчика |
| OurResearch / OpenAlex — [authentication, 19.08.2026](https://help.openalex.org/api/authentication/) | Анонимные базовые запросы допускаются; бесплатный ключ, bearer header, текущие limits |
| OurResearch / OpenAlex — [стоимость, 09.08.2026](https://help.openalex.org/access/example-costs/) | $0.10/day без ключа, $1/day бесплатного бюджета с ключом; различная стоимость типов операций |
| OurResearch / OpenAlex — [пагинация](https://help.openalex.org/api/paging/) | Поддерживаемый `per_page<=100`; 200 — deprecated legacy; cursor для длинных выборок |
| OurResearch / OpenAlex — [endpoints](https://help.openalex.org/api/endpoints/) и [common attributes](https://help.openalex.org/data/common-attributes/) | Authors/works/sources, OpenAlex citation counts и h-index; это не Scopus/JCR показатели |
| OurResearch / OpenAlex — [counting](https://help.openalex.org/how-to/counting/) | Вложенные агрегаты профиля могут отставать от текущей выборки works |
| ORCID — [чтение записи](https://info.orcid.org/documentation/api-tutorials/api-tutorial-read-data-on-a-record/) и [API FAQ](https://info.orcid.org/documentation/integration-and-api-faq/) | v3.0, production hosts, `/read-public`, OAuth, видимость, группировка работ |
| ORCID — [квоты и условия](https://info.orcid.org/ufaqs/what-are-the-api-limits/) | Отдельные anonymous/Public/Member квоты; ограничения Public API на коммерческое использование |
| Elsevier — [authentication](https://dev.elsevier.com/tecdoc_api_authentication.html) | API key обязателен; доступ по IP/Insttoken и entitlement; ключ не равнозначен подписке |
| Elsevier — [Scopus Search](https://dev.elsevier.com/documentation/ScopusSearchAPI.wadl), [Author Retrieval](https://dev.elsevier.com/documentation/AuthorRetrievalAPI.wadl), [Abstract Retrieval](https://dev.elsevier.com/documentation/AbstractRetrievalAPI.wadl) | Документированные search/retrieval endpoints; views и ограничения доступа |
| Elsevier — [Serial Title](https://dev.elsevier.com/documentation/SerialTitleAPI.wadl), [пример JSON](https://dev.elsevier.com/payloads/metadata/serialTitleSearchResp.json) | DOI не используется как ключ журнала; lookup по ISSN, SJR/SNIP/CiteScore и годы. Пример данных исторический |
| Elsevier — [API quotas](https://dev.elsevier.com/api_key_settings.html) | Недельные квоты по API; Citation Overview требует отдельного допуска |
| Elsevier — [journal metrics policy](https://dev.elsevier.com/journal_metrics.html), [Scopus metrics](https://www.elsevier.com/en-au/products/scopus/metrics) | Различие CiteScore/SJR/SNIP и правила использования метрик |
| SCImago — [официальная карточка журнала и квартилей](https://www.scimagojr.com/journalsearch.php?q=14762&tip=sid) | SJR quartile зависит от категории и года; поддерживаемый публичный REST API не подтверждён; help page отвечала 403 |
| Clarivate — [JCR ranks/ties/quartiles](https://clarivate.com/academia-government/blog/a-primer-on-ties-in-the-jcr/) | JIF quartile по категории, обработка равных рангов. Подписные JCR данные проектом не получены |
| eLIBRARY — [руководство](https://elibrary.ru/projects/subscription/manual_elibrary_for_user.pdf), [регистрация автора](https://elibrary.ru/help_author_info.asp) | Платформа, РИНЦ, SCIENCE INDEX и авторские идентификаторы; разные сущности не сливаются по названию |
| eLIBRARY — [API information](https://elibrary.ru/projects/api/api_info.asp) | API существует, но проверка адреса перенаправлена на IP block; актуальные credentials/договор/лимиты не подтверждены. Обход не выполнялся |
| eLIBRARY — [регламент Ядра РИНЦ 18.02.2026](https://elibrary.ru/projects/corerisc/corerisc_reglament.pdf) | Ядро включает экспертный отбор и не сводится к механическому объединению Scopus/WoS/RSCI |
| ВАК / Минобрнауки — [положение](https://vak.gisnauka.ru/about/vak-regulations), [рецензируемые издания](https://vak.gisnauka.ru/documents/editions) | Назначение перечня, отдельные документы категорий; К1–К3 не являются квартилями |
| ВАК / Минобрнауки — [JSON публичного сайта](https://vak.gisnauka.ru/api/news/news-list?type=19) | Сохранён ответ с текущей ссылкой на перечень по состоянию на 14.08.2026; это внутренний интерфейс сайта без обещания стабильного API |
| РЦНИ — [ЕГПНИ / Белый список](https://www.rcsi.science/activity/belyy-spisok/), [FAQ и методики](https://journalrank.rcsi.science/ru/info/) | Уровни 1–4, различные методики по годам; уровни не являются CiteScore/SJR/JCR квартилями |
| РЦНИ — [обновление 21–22.05.2026](https://www.rcsi.science/press-center/news/perechen-nauchnykh-zhurnalov/obnovleniya-v-edinom-gosudarstvennom-perechne-nauchnykh-izdaniy-belom-spiske/) | Изменения состава и уровней по протоколу 25.03.2026; нельзя считать уровни 2025 неизменными |
| РЦНИ — [документация открытого API](https://journalrank.rcsi.science/ru/api-docs/docs/) | `GET /api/record-sources/{issn}/level`, сведения по ISSN и уровням разных лет |
| РЦНИ — [JSON export](https://journalrank.rcsi.science/ru/record-sources/download/?dataType=Json), [описание JSON](https://journalrank.rcsi.science/ru/record-sources/download-description/?dataType=Json) | Реальная полная выгрузка сохранена; export `issns` отличается от API `issn`; метки внешних баз имеют собственную дату |

## Фактически проверенные международные данные

Дополнительно: ISSN International Centre, [What is an ISSN?](https://www.issn.org/understanding-the-issn/what-is-an-issn/), официальный источник, обращение 10.09.2026: формат, контрольный символ, связь с названием и носителем; ISSN не гарантирует качество содержания.

[Сводка живой проверки](examples/live/international_summary.json) содержит реальные timestamps, три OpenAlex профиля и небольшой sample публикаций; [полные сохранённые ответы](examples/live/international_validation.json) содержат raw provenance. Кандидаты выбраны после поиска имён Jorge Hirsch, Konstantin Novoselov, Andre Geim. Они обозначают профили источника; полнота и безошибочность авторского корпуса не сертифицированы.

DOI `10.1073/pnas.0507655102` получен из Crossref и OpenAlex. Разные citation counts хранятся отдельными наблюдениями, без сложения. [Дополнительная проверка Crossref](examples/live/crossref_search_validation.json) фиксирует author candidate search и точный ORCID filter. [Скрипт повторения](examples/live/validate_international.py) использует сетевые запросы и кэш.

Российские исходные JSON/PDF и `.meta.json` находятся в `data/raw`; контрольные суммы и точные URL загрузки указаны в сопроводительных файлах. Текущие значения метрик не выводятся из текстов документации или исторических examples.

ORCID: [публичная запись 0000-0001-7175-3497](https://pub.orcid.org/v3.0/0000-0001-7175-3497/record), живой запрос 10.09.2026; сохранён в `examples/live/orcid_record.json`. PNAS landing page оригинальной статьи Hirsch встретила HTTP 403; библиографическая запись и DOI проверены через Crossref/OpenAlex, чтение полного текста на PNAS не заявляется.
