"""Verified aggregate metrics and failure analysis for adapter runs."""

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from fintech_audit_rl.benchmark.runner import AdapterResult
from fintech_audit_rl.evaluation.metrics import metrics


def summarize(results: tuple[AdapterResult, ...]) -> list[dict]:
    grouped: dict[str, list[AdapterResult]] = defaultdict(list)
    for result in results:
        grouped[result.adapter].append(result)
    rows = []
    for adapter in sorted(grouped):
        items = grouped[adapter]
        tp = sum(item.tp for item in items)
        fp = sum(item.fp for item in items)
        fn = sum(item.fn for item in items)
        aggregate = metrics(tp, tp + fp, tp + fn)
        count = Decimal(len(items))
        rows.append(
            {
                "adapter": adapter,
                "privileged": items[0].privileged,
                "runs": len(items),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "micro_precision": str(aggregate.precision),
                "micro_recall": str(aggregate.recall),
                "micro_f1": str(aggregate.f1),
                "mean_episode_f1": str(sum(Decimal(item.f1) for item in items) / count),
                "mean_reward": str(sum(Decimal(item.reward) for item in items) / count),
                "mean_steps": str(sum(Decimal(item.steps) for item in items) / count),
                "total_elapsed_seconds": sum(item.elapsed_seconds for item in items),
                "mean_elapsed_seconds": sum(item.elapsed_seconds for item in items) / len(items),
                "max_peak_traced_bytes": max(item.peak_traced_bytes for item in items),
            }
        )
    return rows


def write_summary(results: tuple[AdapterResult, ...], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summarize(results), indent=2, sort_keys=True) + "\n", "utf-8")


def write_failure_analysis(results: tuple[AdapterResult, ...], path: Path) -> None:
    by_adapter = {row["adapter"]: row for row in summarize(results)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Анализ результатов адаптеров\n\n"
        "Это измерение синтетического открытого набора, а не оценка скрытого набора жюри "
        "и не доказательство обучения модели.\n\n"
        "- `reconciliation`: F1=1 на текущих шаблонах. Это ожидаемо для скриптовой политики, "
        "написанной под опубликованную семантику; результат не доказывает обобщение.\n"
        f"- `flag_all`: {by_adapter['flag_all']['fp']} FP и "
        f"{by_adapter['flag_all']['fn']} FN. Массовые обвинения не проходят exact matcher.\n"
        f"- `random_explorer`: {by_adapter['random_explorer']['fn']} FN; F1=1 только на clean "
        "эпизодах благодаря пустому ответу, ошибки он не обнаруживает.\n"
        "- `oracle`: F1=1, но он привилегирован, читает truth у evaluator и не является обычной "
        "агентной политикой. Его steps/reward нельзя трактовать как честное сравнение стоимости.\n\n"
        "`peak_traced_bytes` измеряет только Python allocations доверенного benchmark-процесса "
        "через tracemalloc и не является RSS worker/container. Wall-clock включает запуск subprocess. "
        "OS RSS и лимиты контейнера проверяются отдельно в Б09.\n",
        "utf-8",
    )
