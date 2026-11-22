# GENESIS FinTech — Audit RL Environment

Воспроизводимая среда для расследования ошибок в синтетических финансовых документах. Генератор создаёт компанию, агент исследует публичные записи через `reset/step`, независимый оценщик сопоставляет найденные ошибки с эталоном и рассчитывает награду.

**Статус: техническая реализация и автономная приёмка Б00–Б09.2 завершены; проект готов к передаче.**
Репозиторий: [Boob-op/genesis-fintech-audit-rl](https://github.com/Boob-op/genesis-fintech-audit-rl).

Для сдачи через личный кабинет GENESIS нужна ссылка на папку Google Диска с видео, кодом и описанием. Порядок и короткий сценарий записи — в [SUBMISSION.md](SUBMISSION.md). Внешняя отправка ещё не подтверждена.

## Быстрый старт

Требуются Python 3.11 и [uv](https://docs.astral.sh/uv/getting-started/installation/). Из корня репозитория выполните:

```sh
uv sync --locked --dev --python 3.11
uv run --no-sync python -m fintech_audit_rl verify --full
```

После установки зависимостей проверку можно запускать непосредственно:

```sh
python -m fintech_audit_rl verify --full
```

Для этого активируйте `.venv` или используйте `.venv/Scripts/python.exe` на Windows
(`.venv/bin/python` на Linux). `verify --full` проверяет синхронизацию плана,
комплект сдачи, статический анализ, форматирование и все тесты. Ненулевой exit
code означает провал проверки.

## Контейнер

```sh
docker build -t genesis-audit-dev .
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 \
  --cpus 2 --memory 4g --user 65534:65534 \
  --env PYTHONDONTWRITEBYTECODE=1 genesis-audit-dev \
  python -m fintech_audit_rl verify --full
```

Сборка загружает зависимости; готовый образ проверяется без сети. CI также
проверяет размер image <1 ГБ. Ограничение 60 секунд применяется supervisor к
каждому worker episode, а лимит действий среды равен 100.
[Последний CI-прогон основной ветки](https://github.com/Boob-op/genesis-fintech-audit-rl/actions/runs/45036001543)
проверил Windows, Linux и контейнер без сети с 2 CPU / 4 ГБ RAM.
В Windows PowerShell используйте команду `docker run` одной строкой либо замените символы продолжения `\` на обратные кавычки PowerShell.

## План и правила

- [Полный план одним файлом](GENESIS_FULL_PLAN.md)
- [Текущий этап и задачи](PLAN.md)
- [Архитектура модулей](docs/MODULES.md)
- [Требования](REQUIREMENTS.md)
- [Решения и вопросы](DECISIONS.md)
- [Инструкции для работы над проектом](AGENTS.md)
- [Исходное задание](genesis.pdf)

Финансовая [спецификация ошибок 1.0.0](docs/error_spec.json), архитектура и
ограничения реализации описаны в [DESIGN.md](DESIGN.md). Реализованы четыре
класса ошибок, два взаимодействия, public worker API, независимый evaluator,
изолированный контейнерный режим и benchmark четырёх адаптеров.

Зависимости зафиксированы в `uv.lock`. Локальные инструменты, `.venv`, секреты и результаты запусков исключены из Git.

## Комплект и ограничения

В репозитории находятся 10 train + 10 dev эпизодов, 80 adapter runs, 114
публичных шагов траекторий, тесты, отчёт и MIT-лицензия к авторскому коду.
`genesis.pdf` остаётся материалом организаторов и этой лицензией не
перелицензируется. Internal holdout является нашей репетицией, не официальным
hidden set. Исторические DST-зоны, LLM/API, обучение весов, GPU, БД и облако
не входят в заявленный объём. Observer UI добавлен отдельно после обязательной
приёмки и не меняет финансовое ядро. Актуальный CI-статус смотрите в GitHub Actions.

## Нативный интерфейс наблюдения

На Windows можно открыть desktop-приложение без браузера и локального сервера:

```powershell
.\.venv\Scripts\python.exe -m fintech_audit_rl desktop
```

Выберите сценарий, политику и seed, затем нажмите «Запустить расследование».
Интерфейс показывает публичные документы, шаги worker, финальный submit и
P/R/F1/reward. Truth и provenance агенту и presentation payload не передаются.
Tkinter observer является необязательной демонстрационной оболочкой; официальный
автономный запуск и приёмка по-прежнему выполняются через `verify --full`.

Короткое итоговое демо:

```sh
python scripts/run_demo_suite.py
```

Оно показывает clean case, реальную ошибку, ложный flag-all ответ,
allocation+FX interaction и повторяемость одинакового seed.

## Первое сквозное демо

```sh
python -m fintech_audit_rl demo --seed 101 --output runs/demo/trajectories.jsonl
```

Это developer subprocess первого KZT-сценария; он сам по себе не подтверждает OS-изоляцию. Полный набор ошибок проверяется отдельными тестами и benchmark. Вывод содержит метрики и путь к JSONL; closed-режим в траектории показывает агенту нулевой placeholder, фактическая оценка выводится владельцу запуска.

Для подготовленного образа можно запустить worker в изолированном контейнере:

```sh
docker build -t genesis-audit-dev .
python -m fintech_audit_rl demo --seed 101 --isolated --output runs/isolated/trajectories.jsonl
```

Этот режим требует доступного Docker. Образ собирается заранее с сетью; worker запускается без сети, host mounts и с read-only файловой системой. Результат фактической проверки прав фиксируется в GitHub Actions после её прохождения.
