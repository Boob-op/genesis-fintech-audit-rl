"""Deterministic train/dev/internal suite definitions and episode assembly."""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from fintech_audit_rl.benchmark.transforms import change_timezone, rename_ids, shuffle_ledger
from fintech_audit_rl.errors.allocation import short_allocate
from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.errors.fx import wrong_receipt_fx
from fintech_audit_rl.errors.period import wrong_invoice_period
from fintech_audit_rl.generator.company import (
    CleanCompany,
    clean_distractor_company,
    clean_usd_company,
    scaled_clean_kzt_company,
    seeded_clean_kzt,
)
from fintech_audit_rl.generator.truth import (
    allocation_truth,
    duplicate_truth,
    fx_truth,
    period_truth,
)
from fintech_audit_rl.schemas.private import PrivateBundle
from fintech_audit_rl.schemas.public import FxRow, LedgerRow
from fintech_audit_rl.storage.codec import csv_records, json_record, jsonl_records


@dataclass(frozen=True)
class EpisodeConfig:
    name: str
    split: str
    seed: int
    duplicate: bool = False
    allocation_actual_minor: int | None = None
    fx_case: bool = False
    fx_error: bool = False
    period_error: bool = False
    distractors: bool = False
    scale_pairs: int | None = None
    transform: str = "none"
    timezone: str = "Asia/Qyzylorda"


@dataclass(frozen=True)
class EpisodeBundle:
    public: CleanCompany
    private: PrivateBundle


def build_episode(config: EpisodeConfig) -> EpisodeBundle:
    if config.transform not in {"none", "rename", "shuffle"}:
        raise ValueError("unknown transform")
    if config.fx_case and config.duplicate:
        raise ValueError("FX case cannot contain duplicate invoice in v1")
    if config.fx_error and not config.fx_case:
        raise ValueError("FX mutation requires foreign case")
    if config.distractors and (
        config.fx_case
        or config.duplicate
        or config.allocation_actual_minor is not None
        or config.period_error
    ):
        raise ValueError("clean distractors cannot be combined with v1 mutations")
    if config.scale_pairs is not None and (
        config.distractors or config.fx_case or config.period_error
    ):
        raise ValueError("scaled KZT case cannot use distractors, FX, or period mutation")
    clean, metadata = (
        scaled_clean_kzt_company(config.seed, config.scale_pairs)
        if config.scale_pairs is not None
        else clean_distractor_company(config.seed)
        if config.distractors
        else clean_usd_company(config.seed)
        if config.fx_case
        else seeded_clean_kzt(config.seed)
    )
    if config.timezone != clean.policy.timezone:
        clean = change_timezone(clean, config.timezone)
    if config.transform == "rename":
        clean = rename_ids(clean)
    public = clean
    issues = []
    events = []
    if config.duplicate:
        public, event = duplicate_invoice_recognition(public, public.invoices[0].invoice_id)
        events.append(event)
        issues.append(duplicate_truth(public, event))
    if config.allocation_actual_minor is not None:
        public, event = short_allocate(
            public,
            public.payments[0].payment_id,
            public.invoices[0].invoice_id,
            config.allocation_actual_minor,
        )
        events.append(event)
        issues.append(allocation_truth(public, event))
    if config.fx_error:
        public, event = wrong_receipt_fx(public, public.payments[0].payment_id, "2026-11-09")
        events.append(event)
        issues.append(fx_truth(public, event))
    if config.period_error:
        if config.fx_case or config.duplicate:
            raise ValueError("period mutation is standalone in v1")
        public, event = wrong_invoice_period(public, public.invoices[0].invoice_id)
        events.append(event)
        issues.append(period_truth(public, event))
    if config.transform == "shuffle":
        public = shuffle_ledger(public, config.seed)
    generation = metadata.model_copy(update={"config_version": "suite-1"})
    return EpisodeBundle(
        public,
        PrivateBundle(truth=issues, provenance=events, generation=generation),
    )


CASE_TEMPLATES = (
    {"duplicate": False},
    {"duplicate": True},
    {"duplicate": False, "allocation_actual_minor": 40000},
    {"duplicate": False, "fx_case": True},
    {"duplicate": False, "fx_case": True, "fx_error": True},
    {"duplicate": False, "period_error": True},
    {
        "duplicate": False,
        "fx_case": True,
        "fx_error": True,
        "allocation_actual_minor": 6000,
    },
    {"duplicate": True, "allocation_actual_minor": 40000},
    {"duplicate": False, "distractors": True},
    {"duplicate": True, "scale_pairs": 34},
)


def _open_split(split: str, seed_start: int) -> tuple[EpisodeConfig, ...]:
    transforms = ("none", "rename", "shuffle")
    return tuple(
        EpisodeConfig(
            name=f"{split}-{index:02d}",
            split=split,
            seed=seed_start + index,
            transform=transforms[index % len(transforms)] if split == "dev" else "none",
            **template,
        )
        for index, template in enumerate(CASE_TEMPLATES, 1)
    )


TRAIN = _open_split("train", 1000)
DEV = _open_split("dev", 2000)
HOLDOUT_TEMPLATES = (
    {"duplicate": False},
    {"duplicate": False, "fx_case": True},
    {"duplicate": False, "distractors": True},
    {"duplicate": False, "scale_pairs": 34},
    {"duplicate": False},
    *([CASE_TEMPLATES[6]] * 3),
    *([CASE_TEMPLATES[7]] * 2),
    CASE_TEMPLATES[1],
    CASE_TEMPLATES[2],
    CASE_TEMPLATES[4],
    CASE_TEMPLATES[5],
    CASE_TEMPLATES[1],
    CASE_TEMPLATES[2],
    CASE_TEMPLATES[4],
    CASE_TEMPLATES[5],
    CASE_TEMPLATES[1],
    CASE_TEMPLATES[2],
)
HOLDOUT = tuple(
    EpisodeConfig(
        name=f"internal-holdout-{index:02d}",
        split="internal_holdout",
        seed=3000 + index,
        transform=("none", "rename", "shuffle")[index % 3],
        timezone="UTC" if index % 4 == 0 else "Asia/Qyzylorda",
        **template,
    )
    for index, template in enumerate(HOLDOUT_TEMPLATES, 1)
)


def paired_configs() -> tuple[tuple[EpisodeConfig, EpisodeConfig], ...]:
    return tuple(
        (
            config,
            replace(
                config,
                name=f"{config.name}-paired",
                transform="rename" if config.transform == "none" else "none",
            ),
        )
        for config in (*TRAIN, *DEV)
    )


def export_episode(bundle: EpisodeBundle, root: Path) -> None:
    public_dir = root / "public"
    private_dir = root / "private"
    public_dir.mkdir(parents=True, exist_ok=False)
    private_dir.mkdir(parents=True, exist_ok=False)
    public = bundle.public
    (public_dir / "manifest.json").write_text(json_record(public.manifest) + "\n", "utf-8")
    (public_dir / "policy.json").write_text(json_record(public.policy) + "\n", "utf-8")
    (public_dir / "invoices.jsonl").write_text(jsonl_records(public.invoices), "utf-8")
    (public_dir / "payments.jsonl").write_text(jsonl_records(public.payments), "utf-8")
    (public_dir / "ledger.csv").write_text(csv_records(public.ledger, LedgerRow), "utf-8")
    (public_dir / "fx.csv").write_text(
        csv_records(public.fx, FxRow)
        if public.fx
        else "date,source_currency,target_currency,rate\n",
        "utf-8",
    )
    (private_dir / "truth.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.private.truth], sort_keys=True)
        + "\n",
        "utf-8",
    )
    (private_dir / "provenance.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in bundle.private.provenance], sort_keys=True
        )
        + "\n",
        "utf-8",
    )
    (private_dir / "generation.json").write_text(
        json_record(bundle.private.generation) + "\n", "utf-8"
    )


def export_suite(configs: tuple[EpisodeConfig, ...], root: Path) -> list[dict]:
    root.mkdir(parents=True, exist_ok=False)
    index = []
    for config in configs:
        bundle = build_episode(config)
        export_episode(bundle, root / config.split / bundle.public.manifest.episode_id)
        item = asdict(config)
        if item["timezone"] == "Asia/Qyzylorda":
            item.pop("timezone")
        item.update(
            {
                "episode_id": bundle.public.manifest.episode_id,
                "ledger_count": bundle.public.manifest.ledger_count,
                "document_count": (
                    bundle.public.manifest.invoice_count + bundle.public.manifest.payment_count
                ),
                "issue_types": [issue.type for issue in bundle.private.truth],
            }
        )
        index.append(item)
    (root / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    return index
