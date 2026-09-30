# Три мини-проекта исследования

30.09.2026. Здесь предложены эксперименты; ни одна гипотеза ещё не проверена на аграрных данных. Связь с опытом — PERSONAL_RESEARCH_MAP_RU.md, литература/доступ — LITERATURE_REVIEW_RU.md.

## A. Маршрутизация инструментов агрометеорологических расчётов

### Проблема

Специалист формулирует запрос свободным языком: «достаточно ли исходных данных для расчёта испаряемости», «какова сумма эффективных температур за неделю», «почему рассчитанное значение аномально». Система должна выбрать проверенный расчёт или проверку данных, извлечь обязательные параметры и отказаться от выполнения, если смысл или вход неполны. Выбор ET0 вместо суммы температур, использование ветра другой высоты и подмена missing нулём опаснее некрасивой формулировки ответа.

### Research gap

AgriAgent и AgroTools уже исследуют оркестрацию/исполнение; CottonBot уже соединяет LLM с погодой. Возможная добавка — отдельный **контролируемый эксперимент** о risk-coverage/cost в узком расчётном domain с explicit abstention, bilingual/group holdout и численными reference checks. Это ещё не доказанная лакуна всей литературы. Нельзя назвать новый sidecar или API-call научной новизной.

### Вопрос и гипотеза

При одном и том же каталоге, контексте и лимите допустимой ошибки увеличивает ли post-hoc calibrated learned router количество корректно завершённых запросов по сравнению с rule/TF-IDF baseline? Гипотеза: улучшение возможно на неявных и смешанных намерениях; на явных запросах правила конкурентны. Проверка отрицательного результата предусмотрена.

### Данные

[NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) — публичные historical weather snapshots. Выбрать 3–5 неперсональных точек в сельскохозяйственных регионах, 2020–2025, избегать live прогноза. Из metadata получить единицы/временную систему; не считать сеточный реанализ точным наблюдением поля. [FAO-56](https://www.fao.org/4/x0490e/x0490e00.htm) — определения и эталон ET0.

Создать 300–500 **независимых семантических сценариев**, не 500 paraphrases десяти шаблонов: request, required facts, allowed route set, clarification requirement, gold arguments, expected output. Один сценарий может иметь несколько допустимых маршрутов. Включить нетематику и запросы, которые невозможно решить имеющимися инструментами. Не генерировать все labels тем же LLM, который оценивается. Агроном/преподаватель проверяет предметные labels; два проверяющих независимо оценивают сложный поднабор и фиксируют расхождения.

### Метод

Три инструмента: ET0 по FAO-56; degree-days с явно заданной базовой температурой/правилом отсечения; weather-quality validation. Семантический router возвращает probabilities для маршрутов и clarify/defer. Hard schema/unit/range checks отдельно, до исполнения. ET0 и degree-days вычисляются кодом, не языковой моделью. Post-hoc calibration только на calibration subset; пороги/варианты описаний только на development. Jev — необязательная black-box ветка; основной baseline воспроизводим локально.

### Baselines и метрики

Regex + schema rules; TF-IDF + logistic regression; embedding nearest-description; generative function calling; oracle route для отделения routing errors от argument/executor errors. Macro-F1, accepted-set accuracy, clarification precision/recall; risk=incorrect executed / all executed; coverage=executed / all requests, дополнительно coverage только answerable. ECE/Brier для вероятности правильного **маршрута**, не для всего pipeline. Энд-ту-энд correctness требует правильных route, arguments, units и численного результата. p50/p95 включает timeout/retries, стоимость считается на корректно завершённый запрос, а не только успешный API-call.

### Дизайн

Group split ориентировочно 50/20/30% train-development/calibration/final test; парафразы, RU/EN пары и один underlying weather-window остаются в одной группе. Для непривычных формулировок отдельный untouched holdout с новыми авторами запросов. Фиксировать hashes corpus/catalog/model/prompt до финального прогона. Learned baselines обучаются только на train; calibration не становится train. Отдельные ablations: без abstention, без calibration, без hard checks, bare keyword catalog vs trigger catalog. Сравнения парные на одних сценариях, bootstrap по группам и CI для риск/coverage. Повторные stochastic runs не считаются независимыми наблюдениями. При 0 ошибках на n принятых примерах верхний риск не равен нулю; например, n=100 даёт около 3% односторонней верхней границы 95% по правилу трёх.

### MVP и вклад

Первый MVP: 60 сценариев для **разработки**, три functions и сильный rule baseline, JSONL replay и таблица ошибок. Это smoke, не финальная статистика. Затем экспертная разметка/заморозка корпуса и сравнительные прогоны. Возможный вклад статьи: domain benchmark, reproducible selective-routing protocol и реальные пределы применения learned routing. Никаких обещаний роста урожайности или снижения водопотребления без field trial.

### Риски / fit

Corpus слишком лёгкий, неопределённые gold labels, API model drift, calibration разваливается на RU/OOD; недостаточен final n. Если правило выигрывает, публикационная ценность — честный failure/robustness analysis, а не искусственный усложнённый агент. Повторно используются sidecar contracts, frozen scoring, bootstrap, timeouts, provenance. Старые Jev thresholds и 95% developer accuracy не переносятся.

## B. Триаж качества погоды для агроклиматического расчёта

### Проблема и пробел

Временно сдвинутый ряд или некорректная единица может оставаться «в допустимом диапазоне», но менять сумму температур и reference ET0. Anomaly detection в агросенсорах уже существует (L13). Возможная лакуна конкретного эксперимента — review-budget и **downstream agronomic indicator error**, а не новый универсальный детектор.

### Вопрос / гипотеза

При бюджете ручной проверки 5/10/20% окон снижает ли context-aware ML-триаж ошибку итогового агроиндикатора по сравнению с Hampel + физическими правилами? Гипотеза: multi-feature context даст пользу для мягкого bias/shift, тогда как явные units/schema лучше выявляет обычный код. Предельная сильная жара — допустимый negative control, не автоматически ошибка.

### Данные

[GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt): actual station series TMIN/TMAX/PRCP и QC flags; выбрать 10–20 станций после проверки inventory и достаточного сезонного покрытия. [POWER](https://power.larc.nasa.gov/docs/faqs/data/) — независимый grid context, не абсолютная истина. Для первого индикатора использовать degree-days с заданной base temperature, потому что GHCN обычно не даёт полный набор FAO-56 humidity/radiation/wind. ET0 добавлять только при полной отдельно проверенной метеосхеме.

Clean reference windows отбирать по QC/consistency и ручной проверке небольшого набора. Вводить synthetic faults 1/3/7 дней: missing, stuck, scale, additive bias, date shift, duplicate/out-of-order. Сохранять неизменный original и injection recipe. Называть задачу detection of controlled corruption, а не доказанное распознавание всех реальных sensor faults.

### Метод и baselines

Hard rules: sentinel missing, units, TMIN≤TMAX, precipitation≥0, date/order. Дальше robust seasonal deviations, temporal/sibling features, Isolation Forest и supervised gradient boosting; signal «accept / review / unusable». Baselines: rule-only, Hampel, seasonal z-score, random review budget, uncalibrated classifier. Индикатор считать на original/corrupted/accepted/repaired вариантах, не скрывая dropped coverage. Repair — отдельная ветка; первый MVP данные не исправляет автоматически.

### Метрики / эксперимент

PR-AUC, recall at review budget, false alerts per station-month, preserved-valid coverage; weighted absolute error degree-days и detection delay. Основная метрика: снижение downstream error при одинаковом числе review flags. Missing outcome не трактовать как нулевую ошибку.

Train на ранних годах/выбранных станциях; calibration на иных блоках; final — новые станции и годы. В каждом split разные исходные station-window groups; corruption versions не пересекают splits. Держать отдельный never-seen fault-family test, чтобы модель не выучила генератор. Ablations: без независимого weather context, без seasonality, без calibration. Extreme-but-consistent погодные эпизоды отрицательными controls. Повторить 3 seeds; CI кластеризовать по station/season. Ошибки причин классифицировать отдельно от факта «окно требует review».

### MVP / вклад / риски

2–3 станции, degree-days, rules+Hampel, три injections и offline replay — первый MVP за неделю. Табличный ML и полный grouped evaluation — ещё 2–4 недели. Вклад: domain evaluation protocol, review-budget tradeoff и ограниченная демонстрация переносимости. Риски: QC flags неполны, contextual bias между station/grid, инъекции нереалистичны; field accuracy не доказана. Fit: data-quality, temporal metadata, snapshot replay и бюджет верификации; LLM необязателен.

## C. Evidence-gated поиск агрономических норм

### Проблема / пробел

Один корректно звучащий ответ может цитировать документ, который не подтверждает заявленную норму или относится к другой культуре/региону. RAG уже насыщен; TARAG показывает, что время тоже исследуется. Возможный вклад — **paired control dataset** с поддерживаемыми/неподдерживаемыми утверждениями, отказом и точным source locator для узкого набора агронорм.

### Вопрос / гипотеза

Снижает ли metadata+evidence gate долю неподтверждённых принятых ответов при той же coverage по сравнению с hybrid RAG? Гипотеза: source-aware gate особенно полезен при удалении нужного фрагмента или смене региона/версии; на полном корпусе дополнительный gate может не улучшить baseline.

### Данные

Выбрать **одну культуру и один тип нормы**, например определения/исходные требования расчёта водопотребности, без химических дозировок. 20–40 официальных OA guides, source URL, edition/date, locale, sections, content hash. Для MVP хватит FAO-56 и 3–5 открытых crop-specific manuals после проверки прав. [AgriLLM eval 800](https://huggingface.co/datasets/AI71ai/agrillm-qa-eval-800/blob/main/README.md) использовать лишь как внешний challenge: source/date fields отсутствуют, ответы не подтверждают сегодняшнюю норму. На 150–250 своих QA разметить answerable, exact supporting passage, scope, required clarification. Материалы с неизвестным сроком действия не выдать за «актуальные».

### Метод / baselines

BM25+dense RRF, metadata filtering, reranker. Evidence classifier определяет, достаточно ли retrieved passage; policy abstains при неполных region/crop/version. Ответ содержит короткое утверждение и section locator. Baselines: BM25 extractive, dense/hybrid RAG без gate, long-context с тем же corpus, no-generation passage return. Простое возвращение правильного фрагмента может быть лучшим решением; сравнение обязательно.

### Метрики и дизайн

Retrieval recall@k/nDCG; supported accepted precision; coverage только answerable и отдельно all; false refusal, citation correctness, region/version leakage, latency/cost. BLEU/ROUGE не главная метрика; LLM-judge проверяется слепой экспертной выборкой и не является единственным oracle.

Split по документу/семейству нормы, а не random QA. Paraphrases и paired conditions одного вопроса вместе. Для final corpus independent edition/domain-source holdout. Controls: убрать supporting passage; добавить похожий несоответствующий регион; оставить только устаревшую версию; подменить citation; добавить конфликтующие источники. По группе сравнить vanilla retrieval, metadata-only, evidence-only и combined. Калибровка на отдельном subset; reference answer не включать в retrieval index. Bootstrap по source groups; все документы и gold-hashes заморозить.

### MVP / вклад / fit / риски

40 development questions, 5 guides, BM25 и extractive answers — первый этап. Затем source annotations, controls, calibration и final test. Вклад — протокол evidence/abstention, размеченный корпус с проверенной лицензией и конкретные failure modes. Не называть интерфейс «новым агрономическим консультантом». Fit: code-search locators, SciAgg provenance, Research Radar. Риски: metadata ambiguity, высокая стоимость эксперта, непереносимость зарубежных норм на РФ, synthetic QA contamination. Оценка scope — 4–6 недель.
