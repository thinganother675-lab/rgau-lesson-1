# rgau-lesson-1

Учебный проект по наукометрии: **SciAgg RU**, агрегатор библиографии на Python 3.12+.

Реализованы Crossref/OpenAlex, публичное чтение ORCID, API «Белого списка», импорт официального PDF ВАК, сопоставление авторов и публикаций, SQLite и экспорт JSON/CSV/XLSX. Scopus требует собственных ключей и прав; eLIBRARY поддерживается через разрешённый импорт.

- [Инструкция запуска и описание проекта](README_RU.md)
- [Академический отчёт](REPORT_RU.md)
- [Шпаргалка для защиты](DEFENSE_CHEATSHEET_RU.md)
- [Источники](SOURCES.md)
- [Результаты проверки: 88 тестов](VALIDATION.md)
- [Исходные данные и восстановление SQLite](data/README.md)

## Быстрый запуск

После клонирования репозитория, в PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m sciagg demo
.venv\Scripts\python.exe -m pytest -q
```

Демонстрация читает сохранённые реальные ответы без сети. Исследовательский срез — **10.09.2026**; это не обещание актуальности всех списков и метрик в будущем.

SQLite-файлы и окружение Python не включены в Git. Для восстановления объединённой базы из включённых исходных снимков:

```powershell
.venv\Scripts\python.exe scripts/rebuild_database.py --db data/rebuilt.sqlite --use-validated-vak-json --audit examples/rebuild_audit.json
```

Исходные выгрузки сопровождаются URL, датами и SHA-256; Git сохраняет их байты без преобразования окончаний строк. Синтетические шаблоны в `examples/templates` не являются реальными метриками.

Для `[10, 8, 5, 4, 3, 1]` правильный индекс Хирша — **4**.

