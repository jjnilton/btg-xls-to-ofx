"""Create anonymized (personal/identifiable data) copies of BTG Pactual statement spreadsheets (Extrato_*.xls),
suitable for use as test fixtures.

Usage:
    btg-anonymize [FILES...] [--out-dir DIR]

FILES can be one or more .xls/.xlsx paths, or glob patterns like *.xls.
If no files are given, prints usage and exits without processing.
"""

import argparse
import glob
import random
import re
import sys
from pathlib import Path

from openpyxl import Workbook

from .parser import (
    AMOUNT_COL,
    DATE_COL,
    DESCRIPTION_COL,
    CellValue,
    load_rows,
    norm_datetime,
    norm_number,
)

Rows = list[list[CellValue]]

FAKE_FIELDS = (
    ("Cliente:", "José Silva"),
    ("CPF:", "000.123.456-78"),
    ("Agência:", "0001"),
    ("Conta:", "123456-7"),
)

SALDO_DIARIO = "Saldo Diário"
PAYEE_PREFIX = "Recebedor"
SHEET_TITLE = "Extrato"
XLSX_EXT = ".xlsx"

MIN_AMOUNT = 1.0
MAX_AMOUNT = 500.0
INITIAL_BALANCE = 10_000.0
SEED = 42


def alias_description(desc: str, payee_aliases: dict[str, str]) -> str:
    if not desc.strip() or desc.strip() == SALDO_DIARIO:
        return desc
    if desc not in payee_aliases:
        payee_aliases[desc] = f"{PAYEE_PREFIX} {len(payee_aliases) + 1}"
    return payee_aliases[desc]


def anonymize(rows: Rows, payee_aliases: dict[str, str]) -> Rows:
    for row in rows:
        cells = ["" if c is None else str(c).strip() for c in row]

        for label, fake in FAKE_FIELDS:
            if label in cells:
                idx = cells.index(label)
                if idx + 1 < len(row):
                    row[idx + 1] = fake

        if len(row) > DESCRIPTION_COL and norm_datetime(row[DATE_COL]) is not None:
            desc = cells[DESCRIPTION_COL]
            row[DESCRIPTION_COL] = alias_description(desc, payee_aliases)
    return rows


def anonymize_values(rows: Rows, rng: random.Random) -> Rows:
    """Replace amounts with random values and recalculate the balances."""
    balance = INITIAL_BALANCE

    for row in rows:
        cells = ["" if c is None else str(c).strip() for c in row]

        if len(row) <= AMOUNT_COL or norm_datetime(row[DATE_COL]) is None:
            continue
        amount = norm_number(row[AMOUNT_COL])
        if amount is None:
            continue

        if cells[DESCRIPTION_COL] == SALDO_DIARIO:
            row[AMOUNT_COL] = round(balance, 2)
        else:
            sign = -1 if amount < 0 else 1
            row[AMOUNT_COL] = round(sign * rng.uniform(MIN_AMOUNT, MAX_AMOUNT), 2)
            balance += row[AMOUNT_COL]

    for row in rows:
        cells = ["" if c is None else str(c).strip() for c in row]
        if "Saldo atual:" in cells:
            idx = cells.index("Saldo atual:")
            for i, v in enumerate(row[idx + 1 :], start=idx + 1):
                if norm_number(v) is not None:
                    row[i] = round(balance, 2)
                    break
    return rows


def period_name(src: Path) -> str:
    """Use the same '2026-01' style name from the filename, with an
    _anonymized suffix before the extension."""
    m = re.search(r"(\d{4})-(\d{2})-\d{2}_a_", src.name)
    if m:
        return f"statement_{m.group(1)}-{m.group(2)}_anonymized{XLSX_EXT}"
    return f"{src.stem}_anonymized{XLSX_EXT}"


def expand_args(raw_args: list[str]) -> list[Path]:
    """Expand glob patterns and return a list of existing .xls/.xlsx paths."""
    workdir = Path.cwd()
    sources: list[Path] = []
    for arg in raw_args:
        if any(ch in arg for ch in "*?["):
            matches = glob.glob(arg, root_dir=workdir)
            for match in matches:
                p = workdir / match
                if p.suffix.lower() in (".xls", ".xlsx"):
                    sources.append(p)
        else:
            p = workdir / arg
            if p.suffix.lower() in (".xls", ".xlsx"):
                sources.append(p)
    return sorted(set(sources), key=lambda p: str(p))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="btg-anonymize",
        description="Create anonymized copies of BTG Pactual statement spreadsheets.",
    )
    _ = parser.add_argument(
        "files",
        nargs="*",
        help="one or more .xls/.xlsx files, or glob patterns like *.xls",
    )
    _ = parser.add_argument(
        "--out-dir",
        default=None,
        help="output directory for anonymized files (default: current directory)",
    )
    args = parser.parse_args(argv)

    sources = expand_args(args.files)
    if not sources:
        parser.print_help(sys.stderr)
        sys.exit(0)

    out_dir = Path(args.out_dir) if args.out_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    payee_aliases: dict[str, str] = {}  # shared across files -> deterministic aliases
    rng = random.Random(SEED)  # shared across files -> reproducible values

    for src in sources:
        rows = load_rows(str(src))
        rows = anonymize(rows, payee_aliases)
        rows = anonymize_values(rows, rng)
        dst = out_dir / period_name(src)

        wb = Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = SHEET_TITLE
        for r, row in enumerate(rows, start=1):
            for c, value in enumerate(row, start=1):
                if value is None:
                    continue
                if isinstance(value, str) and not value:
                    continue
                _ = ws.cell(row=r, column=c, value=value)
        wb.save(dst)
        print(f"OK: {src.name} -> {dst}")


if __name__ == "__main__":
    main()
