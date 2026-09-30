# Десять предметных тем статьи: сельское хозяйство и AI/ML

30.09.2026. Темы — предложения для обсуждения, а не выполненные исследования. Основания выбора: PERSONAL_RESEARCH_MAP_RU.md. Полные ссылки L1–L16 и данные D1–D8: [литературный обзор](LITERATURE_REVIEW_RU.md). Оценка трудности — инженерная оценка 1–10, а сроки ниже предполагают неполную занятость и доступ к одному локальному компьютеру/VPS; это не «рейтинг крутости».

## 1. Калиброванная маршрутизация агрометеорологических запросов с отказом от ненадёжного выбора инструмента

**EN:** Calibrated Routing of Agrometeorological Queries with Abstention from Unreliable Tool Selection.

Идея: запрос специалиста направлять к проверенному расчёту ET0, суммы эффективных температур или контроля погодных данных; при недостаточных сведениях запрашивать уточнение. Модель выбирает маршрут, а численные операции исполняет обычный код. Это исследование ошибки выбора и границ автоматизации, а не новый алгоритм полива.

- **Аграрная проблема:** неоднозначный запрос, неверные единицы или пропущенный базовый параметр превращают корректную формулу в неправильный агроиндикатор. **AI/ML:** classifier/decision model + post-hoc calibration. **Личный fit:** Jev-router, shadow layer, frozen holdout, typed contracts.
- **Вопрос:** увеличивает ли калиброванный router долю правильно обработанных запросов при одинаковом риске ошибочного выполнения относительно lexical/ML baseline? **Гипотеза:** learned decision помогает на неявных намерениях, а abstention сокращает ошибочные действия; на простых запросах правила могут выиграть.
- **Данные:** D1 NASA POWER + D2 FAO-56; отдельный собственный корпус запросов с gold labels и аргументами. Погода не даёт готовую routing-разметку. **Baseline:** regex/schema rules, TF-IDF+logistic regression, nearest tool-description embedding, generative function calling.
- **Метод:** общий каталог инструментов, probability vector, dev-calibration, policy «execute / clarify / defer». **Метрики:** route macro-F1, selective risk/coverage, AURC, Brier/ECE, exact argument match, numeric success, p95 end-to-end, затраты на корректный завершённый запрос.
- **Результат:** воспроизводимый routing benchmark и таблица tradeoffs. **Трудность:** 6/10. **Объём:** 4–6 недель, 300–500 независимых сценариев, три расчётных инструмента, offline replay, один optional Jev-adapter.
- **Риск:** датасет сводится к ключевым словам; тогда отрицательный результат честнее сложного агента. **Prior art:** L1,L5,L6,L7,L11. **Нетривиальность:** групповой holdout, ошибки единиц, неоднозначность, недоступный инструмент, стоимость отказов, независимая разметка.

## 2. Селективный ML-триаж качества погодных данных перед вычислением агроклиматических индикаторов

**EN:** Selective ML Triage of Weather Data Quality Before Agroclimatic Indicator Computation.

Идея: определять, какие погодные окна можно пропустить в расчёт, а какие требуют проверки, оценивая не только anomaly label, но и изменение суммы температур или ET0. Детерминированные ограничения всегда проверяются до ML.

- **Проблема:** сбой единиц, застывший датчик или временной сдвиг искажает сельскохозяйственные расчёты. **AI/ML:** Isolation Forest/gradient boosting и calibrated review score. **Fit:** AgentWatch, missing≠zero, reconciliation API/БД, временные границы.
- **Вопрос:** при фиксированном бюджете проверки снижает ли ML-триаж искажение агроиндикатора больше robust rules? **Гипотеза:** contextual score выявит физически допустимые, но несогласованные окна; структурные ошибки лучше ловить правилами.
- **Данные:** D1, D3; clean windows и явно synthetic injections: bias, stuck, missing block, shift, unit conversion. QC flags отдельно от истинной причины. **Baseline:** диапазоны/consistency, Hampel, seasonal z-score, Isolation Forest без calibration.
- **Метод:** window features, regional/seasonal context, score + abstention, replay исходного/испорченного ряда. **Метрики:** PR-AUC, recall@review-budget, false alerts/1000 days, error downstream indicator, сохранённая доля валидных данных, p95.
- **Результат:** validator с доказуемыми границами влияния ошибок. **Трудность:** 5/10. **Объём:** 3–5 недель, 10–20 станций, небольшой табличный ML; без LLM в первом MVP.
- **Риск:** модель узнаёт рецепт искусственного сбоя; не доказывает реальное sensor-fault detection. **Prior art:** L13, D1/D3. **Нетривиальность:** отдельные fault-family/location holdouts, extreme-weather negative controls, downstream-cost оценка вместо одного F1.

## 3. Отказ от неподтверждённого ответа в поиске агрономических норм с контролем версии источника

**EN:** Abstention from Unsupported Agronomic Answers with Source-Version Control.

Идея: выдавать краткое утверждение только при наличии подтверждающего фрагмента подходящего руководства; регион, культура и версия проверяются явно. Исследуется решение «доказательств достаточно / уточнить / отказ», а не универсальный фермерский чатбот.

- **Проблема:** правдоподобный совет может опираться на другую культуру, регион или устаревшее руководство. **AI/ML:** hybrid retrieval + reranker/entailment classifier + selective prediction. **Fit:** hybrid code-search, provenance SciAgg, Research Radar.
- **Вопрос:** уменьшает ли source-aware abstention unsupported claims при сопоставимой answer coverage? **Гипотеза:** version/region фильтры вместе с evidence score помогают на подменах источника, но снижают coverage.
- **Данные:** D7 как внешний QA probe, 20–40 официальных открытых агроруководств, собственные source-locator/date labels. D7 не содержит citations — они размечаются заново. **Baseline:** BM25, dense/hybrid RAG, long context, no-abstention RAG.
- **Метод:** metadata constraints + reranking + fragment sufficiency gate; ответы цитируют конкретный раздел. **Метрики:** supported precision, citation correctness, retrieval recall/nDCG, risk-coverage, answerable refusal rate, ошибочная региональная переносимость, цена.
- **Результат:** evidence evaluator и узкий corpus. **Трудность:** 6/10. **Объём:** 4–6 недель, 150–250 expert-reviewed QA, один тип агрономических норм.
- **Риск:** экспертная проверка трудоёмка; reference answer ≠ ground truth на сегодня. **Prior art:** L2,L3,L5,L8. **Нетривиальность:** paired evidence-removal/obsolete-version controls и оценка false support; само добавление RAG насыщено.

## 4. Бюджетный выбор оптической или радарной обработки при картировании сельхозкультур

**EN:** Budget-Aware Optical-versus-Radar Processing for Crop-Type Mapping.

Идея: дешёвую оптическую модель применять первой, а радарную обработку вызывать только когда ожидается выигрыш при облачности/неопределённости. Задача — уменьшить вычислительную цену при сохраняемой точности, а не просто определить культуру по спутнику.

- **Проблема:** облачность и неполные сезонные наблюдения затрудняют crop mapping. **AI/ML:** two-expert classifier и learned escalation gate. **Fit:** model routing/worker budget и pipeline telemetry; ДЗЗ пока новый навык.
- **Вопрос:** улучшает ли gate quality-cost frontier относительно all-optical/all-fusion? **Гипотеза:** дорогая ветка полезнее на определённых missingness/phenology группах.
- **Данные:** D4 для лёгкого старта, D5 PASTIS-R для независимой проверки. **Baseline:** optical-only, radar-only, always-fusion, entropy threshold, random escalation с тем же бюджетом.
- **Метод:** calibrated expected-error gate по optical embedding/coverage; только frozen experts. **Метрики:** macro-F1/IoU по задаче, GPU seconds, p95, radar-call fraction, worst-class F1, risk-coverage.
- **Результат:** routing-policy и воспроизводимый budget benchmark. **Трудность:** 8/10. **Объём:** 6–9 недель, одна crop-map задача, десятки ГБ D5, одна GPU.
- **Риск:** spatial leakage или недоступность части данных; выигрыш исчезнет после учёта I/O. **Prior art:** L12,L16. **Нетривиальность:** фиксированная цена, out-of-region и cloud-dropout тест; fusion уже известен.

## 5. Устойчивость расчётного аграрного tool pipeline к сбоям API и ошибкам размерности

**EN:** Robustness of Agricultural Calculation Tool Pipelines to API Failures and Unit Errors.

Идея: replay агрометеорологической цепочки при контролируемых timeout, malformed schema, stale data и неверных единицах. Сравнить обычный retry, LLM recovery и hybrid policy.

- **Проблема:** формально успешный ответ weather API может испортить итоговый расчёт или повторить операцию. **AI/ML:** классификатор причины/следующего шага или tool-using LLM. **Fit:** Hermes harness, очереди, recovery и end-to-end проверки.
- **Вопрос/гипотеза:** улучшает ли evidence-aware recovery успешность без роста неправильных повторов? Гипотеза — hard checks + learned selection полезнее свободного recovery на неоднозначных ошибках.
- **Данные:** D1 cached responses + D2 numerical oracle; faults маркируются synthetic. **Baseline:** retry/backoff, finite-state rules, unrestricted LLM retry. **Метод:** error taxonomy, bounded attempts, idempotency и обязательная валидация выхода.
- **Метрики:** correct completion, silent corruption, unnecessary retry, duplicate execution, p95/cost, recovery by fault type. **Результат:** небольшой replay fault-injection benchmark.
- **Трудность:** 6/10. **Объём:** 3–5 недель, одна цепочка, 6–8 типов ошибок. **Риск:** pure engineering без самостоятельного ML-вопроса; объединять с №1, если отдельный эффект не найден. **Prior art:** L6,L7. **Нетривиальность:** численно успешный, но семантически неверный результат и unit confusion.

## 6. Версионная память долговременного агента при обновлении агрономических руководств

**EN:** Version-Aware Memory in Long-Running Agents under Agronomic Guideline Updates.

Идея: проверить, сохраняет ли агент старую норму после смены подтверждённого источника и помогает ли явное invalidation знаний. Это offline timeline-эксперимент, без отправки полевых рекомендаций.

- **Проблема:** прошлый ответ из памяти может пережить обновление документа. **AI/ML:** retrieval/summary memory + conflict detection. **Fit:** Worklog, persistent agents и ежедневные обзоры.
- **Вопрос/гипотеза:** насколько version-aware memory уменьшает stale-answer rate при одинаковом контекстном бюджете? Ожидается меньше stale reuse ценой дополнительных retrieval calls.
- **Данные:** официальные руководства по одной культуре с проверенными версиями; curated timeline, D7 лишь источник формулировок. **Baseline:** full-history, summary memory, no memory, metadata-filtered RAG. **Метод:** document hash, validity interval, contradiction signal, invalidate старые утверждения.
- **Метрики:** stale-answer rate, valid citation rate, retained-correct knowledge, tokens/session, update latency. **Результат:** temporal memory benchmark.
- **Трудность:** 7/10. **Объём:** 5–7 недель, 10–20 последовательностей. **Риск:** мало реально меняющихся норм; не заменять их выдуманными изменениями. **Prior art:** L8,L3. **Нетривиальность:** устойчивые правильные знания тоже не должны теряться при обновлении.

## 7. Регионально сбалансированное активное обучение для разметки сельхозкультур

**EN:** Region-Balanced Active Learning for Crop-Type Annotation.

Идея: при фиксированном числе новых меток выбирать наблюдения с учётом неопределённости и недопредставленных регионов/культур. Simulated oracle использует закрытые от обучения существующие labels.

- **Проблема:** разметка новых полей дорогая, частые культуры вытесняют редкие. **AI/ML:** calibrated uncertainty + diversity/group sampling. **Fit:** budgets, holdout и routing; нужно освоить remote-sensing features.
- **Вопрос/гипотеза:** даёт ли group-aware query policy лучший worst-class F1 при том же label budget относительно entropy/random? Гипотеза положительна при региональном дисбалансе, но не универсальна.
- **Данные:** D4, затем D5. **Baseline:** random, entropy, margin, k-center. **Метод:** frozen embedding, uncertainty, region constraints; приобретение labels только из training pool.
- **Метрики:** learning-curve AUC, macro/worst-class F1, labels spent, coverage of groups, runtime. **Результат:** воспроизводимый annotation-budget experiment.
- **Трудность:** 7/10. **Объём:** 5–7 недель, 3 seed, несколько budgets. **Риск:** модель видела будущие pool labels; случайный pixel split даёт leakage. **Prior art:** L10,L12 и D4 benchmarks; отдельный обзор active-learning алгоритмов требуется до разработки. **Нетривиальность:** joint region/class budget вместо одной uncertainty.

## 8. Извлечение сравнимых результатов агрополевых опытов с проверкой единиц и контекста

**EN:** Extracting Comparable Agricultural Field-Trial Results with Unit and Context Verification.

Идея: извлекать из открытых статей строки «культура — treatment — control — показатель — единица — место/год — locator», отличая проценты прибавки от абсолютного урожая и не смешивая разные опыты.

- **Проблема:** автоматические обзоры путают сравниваемые условия. **AI/ML:** constrained extraction + verification model. **Fit:** SciAgg provenance/dedupe, парсеры, Research Radar.
- **Вопрос/гипотеза:** повышают ли unit/context checks точность извлечения сравнимых строк относительно schema-only LLM? Предположение — да, при меньшем количестве автоматически принятых строк.
- **Данные:** 30–50 OA статей о зерновых из Crossref/OpenAlex discovery; права полного текста и 150–250 gold rows проверить. **Baseline:** regex tables, single-pass LLM, two-pass extractor без unit rules.
- **Метод:** layout/table extraction, structured output, dimension checks, source locator, reject unsupported. **Метрики:** slot F1, exact tuple match, numeric/unit accuracy, false comparability, support precision, cost.
- **Результат:** небольшой verified trial-table dataset. **Трудность:** 7/10. **Объём:** 5–8 недель. **Риск:** дорогой gold и неоднородные таблицы; метаданные DOI не заменяют полные тексты. **Prior art:** L14, L1. **Нетривиальность:** comparable treatment/control единицы и lineage, не просто JSON extraction.

## 9. Селективная классификация «сбой наблюдения или стресс растения» в агромониторинге

**EN:** Selective Classification of Observation Faults versus Crop Stress in Agricultural Monitoring.

Идея: сигнал по датчику сначала относить к проверке измерения, наблюдению растения или insufficient evidence. Причина не определяется по одному числу влажности.

- **Проблема:** ошибочный датчик провоцирует агрономическое действие, а настоящее событие списывают на сбой. **AI/ML:** multisignal classifier + abstention. **Fit:** telemetry, data-quality и typed decision.
- **Вопрос/гипотеза:** улучшает ли объединение соседних/погодных сигналов различение причин относительно single-sensor model? Ожидается эффект при независимых сигналах.
- **Данные:** реалистичный путь — simulator с известными причинами и затем малая договорённая запись датчика; D1 только контекст. Публичный корпус с подтверждёнными одновременно fault/stress labels **не установлен**. **Baseline:** thresholds, single-source classifier, rules-only triage.
- **Метод:** bounded state features, cross-signal consistency, group calibration, abstention. **Метрики:** confusion по причинам, harmful false-action rate, delay, coverage, PR-AUC.
- **Результат:** сначала simulator study, не полевая эффективность. **Трудность:** 8/10. **Объём:** 6–10 недель плюс сбор. **Риск:** нет causal labels; поэтому тема не выбрана основной. **Prior art:** L13. **Нетривиальность:** разделение ошибок измерения и агрономического события с явно неполным знанием.

## 10. Локальная модель с селективной облачной эскалацией для аграрных multimodal задач

**EN:** Local Models with Selective Cloud Escalation for Agricultural Multimodal Tasks.

Идея: локальный worker обрабатывает ограниченный набор agro-tasks, escalation происходит по откалиброванному сигналу сложности/неуверенности. Сравнить реальное end-to-end качество и затраты, включая сеть.

- **Проблема:** нестабильная связь и вычислительный бюджет при обработке агроизображений/запросов. **AI/ML:** local VLM + routing classifier. **Fit:** LM Link/LM Studio интерес, VPS harness, model routing; наличие конкретной GPU не предполагается без проверки.
- **Вопрос/гипотеза:** может ли cascade сохранить качество always-cloud при меньшем числе cloud calls? Предположение — да на смеси лёгких/трудных задач, не при общем distribution shift.
- **Данные:** D6 после уточнения лицензии; L15/AgMMU после проверки release. **Baseline:** always-local, always-cloud, entropy gate, random gate budget-matched.
- **Метод:** независимый routing signal, fixed model versions, offline cached evaluation, network-outage replay. **Метрики:** exact/slot correctness, cloud fraction, p95 with timeout, tokens/energy proxy, risk-coverage, failure recovery.
- **Результат:** quality-cost-latency Pareto curve. **Трудность:** 8/10. **Объём:** 6–8 недель. **Риск:** hardware/data rights и нестабильный cloud version. **Prior art:** L5,L7,L15. **Нетривиальность:** реальные ограничения исполнения, а не demo «локальная модель ответила».

## Три предпочтительных направления

**№1 — основной выбор.** Наиболее прямое использование опыта Jev, falsifiable вопрос, маленькая инфраструктура и numerical oracle. Главный труд — качественная независимая разметка запросов, а не GPU. ML должен честно конкурировать с правилами; возможность отрицательного результата делает дизайн исследуемым.

**№2 — сильная альтернатива при акценте преподавателя на данных/ML.** Более предметные погодные ряды и простой табличный MVP. Однако инъекции сбоев не дают доказательства реальных неисправностей, а необычная погода не должна считаться ошибкой. Связь с опытом качества данных особенно сильна.

**№3 — альтернатива при предпочтении текстов/источников.** Хорошо использует retrieval и библиографию, но RAG уже насыщен, а source/date labels требуют эксперта. Вклад должен быть в measurable abstention/evidence evaluation, а не в интерфейсе чатбота.

№4/7/10 технически привлекательны, но требуют больше данных/GPU и новых навыков ДЗЗ. №9 нельзя рекомендовать без реальных причинных меток. №5 удобно включить как robustness-part №1; №6 и №8 перспективны после появления verified corpus. Подробные планы трёх выбранных направлений: [ARTICLE_TOP3_PROPOSALS_RU.md](ARTICLE_TOP3_PROPOSALS_RU.md).
