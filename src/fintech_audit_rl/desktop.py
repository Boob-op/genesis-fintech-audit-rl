"""Native Tkinter observer for GENESIS audit runs."""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from fintech_audit_rl.dashboard import build_dashboard_payload, metric_values, trajectory_label

SCENARIO_LABELS = {
    "duplicate": "Дубль счёта",
    "clean": "Чистая компания",
    "allocation": "Частичное распределение",
    "fx": "Ошибка FX",
    "period": "Ошибка периода",
    "allocation_fx": "Allocation + FX",
    "duplicate_allocation": "Duplicate + allocation",
    "distractors": "Чистые distractors",
}
POLICY_LABELS = {
    "reconciliation": "Reconciliation",
    "flag_all": "Flag all",
    "random_explorer": "Random explorer",
}


class AuditDesktop:
    BG = "#07110f"
    PANEL = "#10211c"
    PANEL_DARK = "#0b1714"
    LINE = "#29463c"
    TEXT = "#eef7f1"
    MUTED = "#8ca69c"
    ACCENT = "#7cff9b"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("GENESIS · FinTech Audit Console")
        self.root.geometry("1280x820")
        self.root.minsize(1060, 680)
        self.root.configure(bg=self.BG)
        self.payload: dict[str, Any] | None = None
        self.result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.scenario_by_label = {label: key for key, label in SCENARIO_LABELS.items()}
        self.policy_by_label = {label: key for key, label in POLICY_LABELS.items()}
        self._style()
        self._build()

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=self.MUTED)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 22), foreground=self.TEXT)
        style.configure("Eyebrow.TLabel", font=("Consolas", 9, "bold"), foreground=self.ACCENT)
        style.configure(
            "Metric.TLabel",
            background=self.PANEL,
            font=("Segoe UI Semibold", 24),
            foreground=self.ACCENT,
        )
        style.configure(
            "MetricName.TLabel",
            background=self.PANEL,
            font=("Consolas", 8, "bold"),
            foreground=self.MUTED,
        )
        style.configure(
            "Accent.TButton",
            background=self.ACCENT,
            foreground="#07110f",
            padding=(18, 11),
            font=("Segoe UI Semibold", 10),
            borderwidth=0,
        )
        style.map("Accent.TButton", background=[("active", "#a1ffb6"), ("disabled", "#31543d")])
        style.configure(
            "TCombobox",
            fieldbackground=self.PANEL_DARK,
            background=self.PANEL_DARK,
            foreground=self.TEXT,
            arrowcolor=self.ACCENT,
            padding=8,
        )
        style.configure(
            "TEntry",
            fieldbackground=self.PANEL_DARK,
            foreground=self.TEXT,
            insertcolor=self.TEXT,
            padding=8,
        )
        style.configure(
            "Treeview",
            background=self.PANEL_DARK,
            fieldbackground=self.PANEL_DARK,
            foreground=self.TEXT,
            rowheight=28,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=self.PANEL,
            foreground=self.MUTED,
            font=("Consolas", 8, "bold"),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#1d4434")])
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab", background=self.PANEL_DARK, foreground=self.MUTED, padding=(14, 8)
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.ACCENT)],
            foreground=[("selected", "#07110f")],
        )

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=self.BG, padx=26, pady=18)
        header.pack(fill="x")
        tk.Label(
            header,
            text="G",
            bg=self.ACCENT,
            fg=self.BG,
            font=("Segoe UI Black", 17),
            width=2,
            pady=4,
        ).pack(side="left")
        brand = tk.Frame(header, bg=self.BG)
        brand.pack(side="left", padx=12)
        tk.Label(
            brand, text="GENESIS", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 12)
        ).pack(anchor="w")
        tk.Label(
            brand, text="FINTECH AUDIT CONSOLE", bg=self.BG, fg=self.MUTED, font=("Consolas", 8)
        ).pack(anchor="w")
        tk.Label(
            header,
            text="●  LOCAL · TRUSTED VIEW",
            bg=self.BG,
            fg=self.ACCENT,
            font=("Consolas", 9, "bold"),
        ).pack(side="right")

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 22))
        controls = tk.Frame(
            body,
            bg=self.PANEL,
            width=270,
            padx=20,
            pady=22,
            highlightthickness=1,
            highlightbackground=self.LINE,
        )
        controls.pack(side="left", fill="y")
        controls.pack_propagate(False)
        tk.Label(
            controls,
            text="ПАРАМЕТРЫ ЗАПУСКА",
            bg=self.PANEL,
            fg=self.ACCENT,
            font=("Consolas", 9, "bold"),
        ).pack(anchor="w", pady=(0, 20))
        self.scenario = self._combo(
            controls, "Сценарий", list(SCENARIO_LABELS.values()), SCENARIO_LABELS["duplicate"]
        )
        self.policy = self._combo(
            controls, "Политика", list(POLICY_LABELS.values()), POLICY_LABELS["reconciliation"]
        )
        tk.Label(
            controls, text="Seed", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI Semibold", 9)
        ).pack(anchor="w", pady=(14, 6))
        self.seed = ttk.Entry(controls)
        self.seed.insert(0, "101")
        self.seed.pack(fill="x")
        self.run_button = ttk.Button(
            controls, text="Запустить расследование", style="Accent.TButton", command=self.run
        )
        self.run_button.pack(fill="x", pady=(22, 8))
        self.status = tk.Label(
            controls,
            text="Готово к запуску",
            bg=self.PANEL,
            fg=self.MUTED,
            wraplength=220,
            justify="left",
            font=("Segoe UI", 9),
        )
        self.status.pack(anchor="w", pady=8)
        tk.Frame(controls, bg=self.LINE, height=1).pack(fill="x", pady=20)
        tk.Label(
            controls,
            text="Что вы увидите",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w")
        tk.Label(
            controls,
            text="• публичные документы\n• действия worker\n• финальный submit\n• P/R/F1 и reward\n\nTruth и provenance агенту не передаются.",
            bg=self.PANEL,
            fg=self.MUTED,
            justify="left",
            font=("Segoe UI", 9),
            wraplength=220,
        ).pack(anchor="w", pady=10)

        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True, padx=(18, 0))
        metrics = ttk.Frame(content)
        metrics.pack(fill="x")
        self.metric_labels = []
        for name, note in (
            ("F1", "качество"),
            ("REWARD", "награда"),
            ("STEPS", "из 100"),
            ("TP / FP / FN", "matcher"),
        ):
            card = tk.Frame(
                metrics,
                bg=self.PANEL,
                padx=17,
                pady=13,
                highlightthickness=1,
                highlightbackground=self.LINE,
            )
            card.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(
                card, text=name, bg=self.PANEL, fg=self.MUTED, font=("Consolas", 8, "bold")
            ).pack(anchor="w")
            value = tk.Label(
                card, text="—", bg=self.PANEL, fg=self.ACCENT, font=("Segoe UI Semibold", 23)
            )
            value.pack(anchor="w")
            tk.Label(card, text=note, bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8)).pack(
                anchor="w"
            )
            self.metric_labels.append(value)

        split = tk.PanedWindow(
            content, orient="horizontal", bg=self.BG, sashwidth=5, sashrelief="flat"
        )
        split.pack(fill="both", expand=True, pady=(16, 0))
        trace_frame = tk.Frame(
            split,
            bg=self.PANEL,
            padx=12,
            pady=12,
            highlightthickness=1,
            highlightbackground=self.LINE,
        )
        detail_frame = tk.Frame(
            split,
            bg=self.PANEL,
            padx=12,
            pady=12,
            highlightthickness=1,
            highlightbackground=self.LINE,
        )
        split.add(trace_frame, minsize=330, width=390)
        split.add(detail_frame, minsize=500)
        tk.Label(
            trace_frame,
            text="ХОД РАССЛЕДОВАНИЯ",
            bg=self.PANEL,
            fg=self.ACCENT,
            font=("Consolas", 9, "bold"),
        ).pack(anchor="w", pady=(2, 10))
        self.trajectory = tk.Listbox(
            trace_frame,
            bg=self.PANEL_DARK,
            fg=self.TEXT,
            selectbackground="#1d4434",
            selectforeground=self.ACCENT,
            font=("Consolas", 10),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.trajectory.pack(fill="both", expand=True)
        self.trajectory.bind("<<ListboxSelect>>", self.show_step)

        self.notebook = ttk.Notebook(detail_frame)
        self.notebook.pack(fill="both", expand=True)
        self.step_text = self._text_tab("Шаг")
        self.ledger_tree = self._tree_tab("Проводки")
        self.invoice_tree = self._tree_tab("Счета")
        self.payment_tree = self._tree_tab("Платежи")
        self.manifest_text = self._text_tab("Manifest")

    def _combo(
        self, parent: tk.Widget, label: str, values: list[str], default: str
    ) -> ttk.Combobox:
        tk.Label(
            parent, text=label, bg=self.PANEL, fg=self.MUTED, font=("Segoe UI Semibold", 9)
        ).pack(anchor="w", pady=(0, 6))
        combo = ttk.Combobox(parent, values=values, state="readonly")
        combo.set(default)
        combo.pack(fill="x", pady=(0, 14))
        return combo

    def _text_tab(self, label: str) -> tk.Text:
        frame = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(frame, text=label)
        text = tk.Text(
            frame,
            bg=self.PANEL_DARK,
            fg="#b9d4c9",
            insertbackground=self.TEXT,
            font=("Consolas", 9),
            wrap="word",
            borderwidth=0,
            padx=14,
            pady=14,
        )
        text.pack(fill="both", expand=True)
        text.configure(state="disabled")
        return text

    def _tree_tab(self, label: str) -> ttk.Treeview:
        frame = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(frame, text=label)
        tree = ttk.Treeview(frame, show="headings")
        ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    def run(self) -> None:
        try:
            seed = int(self.seed.get())
        except ValueError:
            messagebox.showerror("Неверный seed", "Seed должен быть целым числом.")
            return
        scenario = self.scenario_by_label[self.scenario.get()]
        policy = self.policy_by_label[self.policy.get()]
        self.run_button.configure(state="disabled")
        self.status.configure(text="Worker исследует публичную историю…", fg=self.ACCENT)
        threading.Thread(target=self._worker, args=(scenario, policy, seed), daemon=True).start()
        self.root.after(80, self._poll)

    def _worker(self, scenario: str, policy: str, seed: int) -> None:
        try:
            self.result_queue.put(("ok", build_dashboard_payload(scenario, policy, seed)))
        except Exception as error:
            self.result_queue.put(("error", str(error)))

    def _poll(self) -> None:
        try:
            kind, result = self.result_queue.get_nowait()
        except queue.Empty:
            self.root.after(80, self._poll)
            return
        self.run_button.configure(state="normal")
        if kind == "error":
            self.status.configure(text="Запуск не выполнен", fg="#ff6b77")
            messagebox.showerror("Ошибка запуска", result)
            return
        self.payload = result
        self.status.configure(
            text=f"Завершено · episode {result['manifest']['episode_id'][:18]}…", fg=self.ACCENT
        )
        self._render()

    def _render(self) -> None:
        assert self.payload is not None
        for label, value in zip(self.metric_labels, metric_values(self.payload), strict=True):
            label.configure(text=value)
        self.trajectory.delete(0, "end")
        for event in self.payload["trajectory"]:
            self.trajectory.insert("end", trajectory_label(event))
        if self.payload["trajectory"]:
            self.trajectory.selection_set(len(self.payload["trajectory"]) - 1)
            self.trajectory.event_generate("<<ListboxSelect>>")
        self._fill_tree(
            self.ledger_tree,
            self.payload["ledger"],
            (
                "row_id",
                "timestamp",
                "account",
                "debit_minor",
                "credit_minor",
                "currency",
                "role",
                "invoice_id",
                "payment_id",
            ),
        )
        self._fill_tree(
            self.invoice_tree,
            self.payload["documents"]["invoices"],
            ("invoice_id", "entity_id", "issued_at", "due_at", "currency", "total_minor"),
        )
        self._fill_tree(
            self.payment_tree,
            self.payload["documents"]["payments"],
            ("payment_id", "timestamp", "currency", "amount_minor", "kind"),
        )
        self._set_text(self.manifest_text, self.payload["manifest"])

    def show_step(self, _event: object = None) -> None:
        if self.payload is None or not self.trajectory.curselection():
            return
        event = self.payload["trajectory"][self.trajectory.curselection()[0]]
        visible = {
            "action": event["action"],
            "observation": event["observation"],
            "visible_reward": event["reward"],
            "terminated": event["terminated"],
            "truncated": event["truncated"],
        }
        self._set_text(self.step_text, visible)
        self.notebook.select(0)

    def _set_text(self, widget: tk.Text, value: Any) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", json.dumps(value, ensure_ascii=False, indent=2))
        widget.configure(state="disabled")

    def _fill_tree(
        self, tree: ttk.Treeview, rows: list[dict[str, Any]], columns: tuple[str, ...]
    ) -> None:
        tree.delete(*tree.get_children())
        tree.configure(columns=columns)
        for column in columns:
            tree.heading(column, text=column.upper())
            tree.column(column, width=145, minwidth=80, anchor="w")
        for row in rows:
            tree.insert("", "end", values=[row.get(column, "—") for column in columns])


def run_desktop() -> None:
    root = tk.Tk()
    AuditDesktop(root)
    root.mainloop()
