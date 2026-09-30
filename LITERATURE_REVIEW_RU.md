# Литература, данные и осторожная проверка новизны

Срез: 30.09.2026. Это целевой обзор для выбора темы, не систематический review с доказанной полнотой. Поиск выполнен по текущему веб-индексу, arXiv, официальным страницам издателей, репозиториям авторов и карточкам датасетов. После неудачного обращения веб-инструмента метаданные AgXQA успешно сверены напрямую через Crossref и OpenAlex (HTTP 200); небольшие ответы сохранены в examples/research-2026-09-30 вместе с URL, датой и SHA-256. Это дополнительная проверка одной статьи, а не всего обзора. Подписные запросы Scopus/WoS не выполнены. У статьи в arXiv есть DOI репозитория, но это не означает рецензирование.

Практическая проверка данных: сохранён публичный ответ NASA POWER за 01–07.06.2025, демонстрационная точка 45°N, 38°E, UTC, параметры T2M/T2M_MAX/T2M_MIN/PRECTOTCORR. API вернул по 7 наблюдений, температуры в °C, осадки в mm/day и fill value −999. Это подтверждает получение малого погодного среза, но не проверяет полный набор входов FAO-56 или точность продукта для конкретного поля. См. [manifest.json](examples/research-2026-09-30/manifest.json).

## Как искали и отбирали

Запросы: agriculture tool routing LLM agent benchmark 2025 2026; AgriAgent tool orchestration; agricultural selective prediction calibration; agricultural weather data quality ML; active learning crop mapping; agricultural literature information extraction; agriculture time-aware RAG. Предпочтение: первичная статья, затем официальный dataset/repository. Страница с названием недостаточна: для ближайших конкурентов AgriAgent и AgroTools просмотрены полные HTML статьи, для данных — схемы/лицензии карточек. Для части остальных работ прочитаны abstract/описания издателя; это отражено ниже.

Не нашли готовую работу с тем же названием — **не доказательство новизны**. Отсутствие слова calibration в двух HTML также не доказывает отсутствия метода. Вывод ограничен просмотренным: ближайшие работы сосредоточены на общей оркестрации/мультимодальном tool use; точный агрометеорологический стенд с калибровкой, abstention и контролем единиц остаётся направлением для проверки, а не заявкой «впервые в мире».

## Основные работы

| ID | Первичный источник / год | Что уже сделано и почему это важно | Глубина / ограничение |
|---|---|---|---|
| L1 | [ShizishanGPT](https://arxiv.org/abs/2409.13537), 2024 | Агро-LLM уже объединяет поиск, знания и специализированные инструменты | Abstract; недостаточно назвать агентную интеграцию новым методом |
| L2 | [AgXQA](https://doi.org/10.1016/j.compag.2024.109349), 2024 | Предметный QA и encoder-baseline, включая ирригационные вопросы | Страница издателя; полный корпус/условия скачивания в этой сессии не проверены |
| L3 | [Agri-Query](https://arxiv.org/abs/2508.18093), 2025 | RAG и long-context уже сравнивались на многоязычных руководствах сельхозмашины | Abstract; метрики/поднабор воспроизвести только после проверки оригинальных файлов |
| L4 | [AgriGPT](https://arxiv.org/abs/2508.08632), 2025 | Предметная экосистема моделей/данных, Agri-342K | Abstract; полезен как фон, не обещание свободного доступа к любой части |
| L5 | [CottonBot](https://doi.org/10.1016/j.atech.2025.101640), 2025 | RAG с локальными LLM, погодой и датчиками уже реализован для хлопка | Издатель/abstract; общий «чатбот с погодой» насыщен |
| L6 | [AgriAgent](https://arxiv.org/html/2601.08308v1), 2026 | Иерархия сложности, contract planning и capability-aware orchestration | Полный HTML; abstract обещает release после acceptance, поэтому данные не считаются гарантированно доступными |
| L7 | [AgroTools](https://arxiv.org/html/2605.22366v1), 2026 | Исполняемый аграрный benchmark с оценкой процесса и результата | Полный HTML + карточка данных; главный близкий конкурент |
| L8 | [TARAG](https://www.sciencedirect.com/science/article/pii/S0168169926003819), 2026 | Время уже включают в retrieval для защиты растений | Страница издателя; свой timestamp-filter сам по себе не новизна |
| L9 | [Uncertainty Guarantees on Automated Precision Weeding](https://arxiv.org/abs/2501.07185), 2025 | Conformal uncertainty уже применён в аграрной автоматизации | Abstract; нельзя заявлять первый «безопасный агро-ИИ» |
| L10 | [Group-Conditional Conformal Prediction for Crop and Weed Classification](https://arxiv.org/abs/2308.15094), 2023 | Групповые гарантии могут отличаться от общей marginal coverage | Abstract; важен контроль регионов и классов |
| L11 | [Selective Conformal Risk Control](https://arxiv.org/abs/2512.12844), 2025 | Существуют методы совместного отбора и контроля риска | Abstract; применять только с проверкой предпосылок, не объявлять гарантию под distribution shift |
| L12 | [AgriFM](https://arxiv.org/abs/2505.21357), 2025 | Multisource temporal foundation models для crop mapping | Abstract; сильный baseline для дорогих геоданных, но тяжёлый старт |
| L13 | [Multimodal Fusion Anomaly Detection for Agricultural Wireless Sensors](https://onlinelibrary.wiley.com/doi/full/10.1002/eng2.13021), 2024 | Агросенсорная anomaly detection уже исследуется | Страница/abstract; авторы отмечают проблему публичных данных, доступ своего массива не установлен |
| L14 | [Automatic Structuring of Agricultural Documents into Tables](https://doi.org/10.3173/air.34.51), 2025 | LLM-извлечение таблиц из агродокументов уже исследовано | Библиографическая запись издателя через CiNii; нужен выход к первичному полному тексту перед реализацией |
| L15 | [AgMMU](https://arxiv.org/abs/2504.10568), 2025 | Существует сельскохозяйственный multimodal QA benchmark | Abstract; годится для fallback-анализа после проверки image/data rights |
| L16 | [Multi-modal Temporal Attention Models](https://arxiv.org/abs/2112.07558), публикация 2022 | Optical/radar fusion и устойчивость к облачности уже исследованы | Abstract + PASTIS-R README; простое добавление Sentinel-1 недостаточно |

## Данные: доступность и чего в них нет

| ID | Точный источник | Проверенное содержимое | Практическая граница |
|---|---|---|---|
| D1 | [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), [units/quality FAQ](https://power.larc.nasa.gov/docs/faqs/data/) | Дневные метеорологические/радиационные ряды, JSON/CSV, AG community | Реанализ/модельные продукты; не ground truth каждого поля. Единицы и UTC/LST брать из метаданных |
| D2 | [FAO-56, главы 2/4](https://www.fao.org/4/x0490e/x0490e00.htm) | Определение ET0, формулы и требования к данным | Эталонный алгоритм, не датасет пользовательских запросов и не новая ML-модель |
| D3 | [NOAA GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/), [README](https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt) | Станционные данные и QC flags | Станции выбирать по фактическому покрытию. QC-флаг не полная ручная разметка причин ошибок |
| D4 | [CropHarvest](https://github.com/nasaharvest/cropharvest), [schema](https://github.com/nasaharvest/cropharvest/blob/main/data/README.md) | Геометки, crop/non-crop, часть multiclass, Sentinel/климатические признаки | Проверить лицензию каждого входящего источника; нет готовых меток «вред от неверной рекомендации» |
| D5 | [PASTIS / PASTIS-R](https://github.com/khlaifiabilel/PASTIS) | Французские agricultural parcels, временные оптические/радарные данные, официальные folds | Десятки ГБ; лицензию датасета проверять в Zenodo отдельно от MIT-кода |
| D6 | [AgroTools data](https://huggingface.co/datasets/AgroTools/AgroTools) | Публично отображаемые 539 test rows, изображения и контекст задач | License: other, карточка просит уточнить redistribution terms; raw не включать в учебный репозиторий без проверки |
| D7 | [AgriLLM eval 800](https://huggingface.co/datasets/AI71ai/agrillm-qa-eval-800/blob/main/README.md) | Англоязычные system/user/reference, заявленная Apache-2.0, смесь экспертных и synthetic QA | Нет source/date/region columns. Для citation/temporal benchmark нужна дополнительная разметка |
| D8 | [AgXQA / AWM-Bench](https://dsiweb.cse.msu.edu/awm-bench/) | Публичная первичная страница benchmark | Скачать и проверить лицензию/разделы до планирования эксперимента; не утверждать загрузку полного корпуса |

## Сопоставление с десятью кандидатами

| Кандидат | Близкое prior art | Насыщенность | Проверяемая добавка / риск |
|---|---|---|---|
| 1. Маршрутизация расчётных инструментов | L1,L5,L6,L7,L11 | Высокая для «агента вообще» | Калиброванный abstention, bilingual/group holdout, ошибки единиц, cost-risk-coverage; собственная разметка обязательна |
| 2. Триаж качества погоды | L13, D1,D3 | Высокая для anomaly detection | Проверять влияние ошибок на агроиндикатор и цену human-review; synthetic ≠ реальные неисправности |
| 3. Доказательность агро-QA | L2,L3,L5,L8 | Очень высокая для RAG | Не генерировать советы, измерять отказ при неподтверждённом фрагменте/устаревшей версии; нужны источники к ответам |
| 4. Адаптивный optical/radar compute | L12,L16 | Высокая | Селективное применение дорогой модальности при фиксированном бюджете, missingness и out-of-region test |
| 5. Восстановление tool pipeline | L6,L7 | Высокая для retry | Типы отказов, unit/schema checks и idempotency; выделить одну вычислительную цепочку |
| 6. Версионная память сезонных норм | L8,L3 | Высокая | Invalidation/retrieval подмена старой нормы новой, контролируемый timeline; нужны подтверждённые версии |
| 7. Активная разметка crop maps | L12,L10 | Высокая для active learning | Class/region-balanced budget, сравнение с entropy/random; лицензии и spatial leakage |
| 8. Извлечение результатов полевых опытов | L14, L1 | Высокая для extraction | Единицы, знаменатели, treatment/control, точный locator; дорогое экспертное gold |
| 9. Неисправность vs стресс растения | L13 | Реальная аграрная задача | Причинная разметка редко открыта; без неё это только simulator study |
| 10. Локальный/cloud cascade | L5,L15,L7 | Высокая для routing | Quality-budget Pareto на фиксированных agro-tasks; модели/устройства надо реально измерить |

## Главный вывод по новизне

Рекомендуется кандидат 1. Возможный вклад — небольшой воспроизводимый benchmark маршрутизации **агрометеорологических расчётных запросов** с исполняемыми проверками и раздельной оценкой ошибок выбора, аргументов, калибровки и воздержания. Сравнить с сильными простыми методами и показать, где learned router полезен, а где детерминированное правило лучше. Не утверждать, что Jev уже калиброван на агрономии, что типизированный JSON исключает неправильный смысл, либо что tool router улучшает урожайность.

До статьи остаётся расширить backward/forward snowballing от L6/L7, проверить предметный benchmark с агрономом и зафиксировать новые доступные статьи. Дата обращения ко всем ссылкам в этом файле: **30.09.2026**; год работы указан отдельно.
