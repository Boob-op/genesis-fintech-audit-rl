# Design note

## Назначение

Среда генерирует синтетическую финансовую историю компании, вносит четыре
формально заданных класса ошибок и оценивает ответ audit-agent. Все компании,
документы и суммы вымышлены. Версия финансовой спецификации — 1.0.0 в
`docs/error_spec.json`.

## Граница доверия

Generator создаёт public history и отдельно private truth/provenance. Worker
получает только публичный reset/step API с пятью действиями и лимитом 100 шагов.
Evaluator остаётся в доверенном процессе, независимо восстанавливает нарушения
по публичным данным и сопоставляет findings с truth максимальным one-to-one
matching. Seed, truth, provenance и диагностика оценщика worker не передаются.

Container worker запускается без сети, host mounts и capabilities, с read-only
root filesystem, непривилегированным UID и лимитами процессов/CPU/RAM. Это
проверяемая Linux-граница; developer subprocess сам по себе OS-изоляцией не
считается.

## Финансовая модель

- деньги хранятся целыми минимальными единицами;
- FX рассчитывается через `Decimal` с явно заданным округлением;
- период использует полуинтервал `[start, end)` и публичную business date;
- частичная оплата законна, ошибка allocation определяется инструкцией и
  фактическим распределением;
- duplicate invoice означает повторное признание одного обязательства, а не
  произвольную похожую сумму.

Поддержаны duplicate invoice, missing/partial allocation, wrong FX date/rate и
period cutoff, а также два фиксированных взаимодействия. UTC и
Asia/Qyzylorda проверяются с сохранением абсолютных моментов; историческое DST
не заявлено.

## Воспроизводимость и оценка

Локальный RNG и versioned config обеспечивают replay. Rename и shuffle не
меняют oracle score/reward. Метрики — P/R/F1, reward, steps и wall-clock;
`peak_traced_bytes` в отчёте является Python allocation peak, а не OS RSS.
Oracle помечен privileged и служит верхней границей, а не worker baseline.

Открытый набор содержит 10 train и 10 dev эпизодов; отдельные 20 internal
конфигураций остаются репетицией, а не заявлением об официальном hidden set.
Ограничения, измеренные сбои и результаты четырёх адаптеров находятся в
`reports/`.

## Проверка

`python -m fintech_audit_rl verify --full` проверяет синхронизацию документов,
комплект артефактов, Ruff и все тесты. Готовый Docker image выполняет ту же
команду offline с 2 CPU, 4 ГБ RAM и размером image менее 1 ГБ в CI.
