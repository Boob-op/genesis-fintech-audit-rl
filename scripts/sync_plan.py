"""Build the full plan from its four authoritative source documents."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = [
    ("1. План разработки и задачи", "PLAN.md"),
    ("2. Модули и архитектура", "docs/MODULES.md"),
    ("3. Матрица требований", "REQUIREMENTS.md"),
    ("4. Решения и открытые вопросы", "DECISIONS.md"),
]
HEADER = """# GENESIS FinTech — полный план проекта

Единый документ: утверждённая редакция 4 плана и актуальный прогресс разработки.
Статус реализации указан в разделе 1; наличие плана не означает готовности программы.

## Оглавление

1. [План разработки и задачи](#part-1)
2. [Модули и архитектура](#part-2)
3. [Матрица требований](#part-3)
4. [Решения и открытые вопросы](#part-4)

Все четыре документа включены полностью. Автоматическая сборка: `python scripts/sync_plan.py`.
Редактировать исходные разделы, затем пересобирать этот файл.

"""


def render() -> str:
    chunks = [HEADER]
    for index, (title, name) in enumerate(PARTS, 1):
        body = (ROOT / name).read_text(encoding="utf-8").rstrip()
        chunks.append(f'---\n\n<a id="part-{index}"></a>\n\n# {title}\n\n{body}\n\n')
    return "".join(chunks).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "GENESIS_FULL_PLAN.md"
    content = render()
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            print("Full plan is stale. Run: python scripts/sync_plan.py")
            return 1
        print("Full plan is synchronized.")
        return 0
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    print("Full plan rebuilt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
