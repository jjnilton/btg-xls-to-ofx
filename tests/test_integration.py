"""Integration tests: real anonymized statement files -> parsed data -> OFX."""

import re
from datetime import datetime
from pathlib import Path
from typing import cast

import pytest

from btg_xls_to_ofx.parser import (
    Transaction,
    load_rows,
    read_statement,
)
from btg_xls_to_ofx.serializers.plain import build_ofx

SAMPLES = Path(__file__).parent.parent / "samples"
JAN_STATEMENT = SAMPLES / "statement_2026-01.xlsx"
MAR_STATEMENT = SAMPLES / "statement_2026-03.xls"  # real legacy BIFF file

Statement = tuple[str, float | None, list[Transaction]]


@pytest.fixture(scope="module")
def jan() -> Statement:
    return read_statement(str(JAN_STATEMENT))


@pytest.fixture(scope="module")
def mar() -> Statement:
    return read_statement(str(MAR_STATEMENT))


class TestLoadRows:
    def test_loads_xlsx_sample(self) -> None:
        rows = load_rows(str(JAN_STATEMENT))
        assert isinstance(rows, list)
        assert all(isinstance(r, list) for r in rows)
        assert len(rows) > 0

    def test_sniffs_format_by_content_not_extension(self, tmp_path: Path) -> None:
        # Copy real xlsx sample under an .xls extension: must still parse
        fake = tmp_path / "fake.xls"
        _ = fake.write_bytes(JAN_STATEMENT.read_bytes())
        assert load_rows(str(fake)) == load_rows(str(JAN_STATEMENT))


class TestReadStatement:
    def test_account_id(self, jan: Statement, mar: Statement) -> None:
        assert jan[0] == "123456-7"
        assert mar[0] == "123456-7"

    def test_balance_consistent_with_transactions(self, jan: Statement) -> None:
        # Samples are generated with anonymized amounts: the final balance
        # must equal INITIAL_BALANCE plus the sum of all transactions.
        from btg_xls_to_ofx.anonymize import INITIAL_BALANCE

        _, balance, txns = jan
        assert balance == pytest.approx(INITIAL_BALANCE + sum(a for _, a, _ in txns))

    def test_balance_present(self, jan: Statement, mar: Statement) -> None:
        assert isinstance(jan[1], float) and jan[1] > 0
        assert isinstance(mar[1], float) and mar[1] > 0

    def test_transaction_counts(self, jan: Statement, mar: Statement) -> None:
        assert len(jan[2]) == 27
        assert len(mar[2]) == 39

    def test_no_daily_balance_rows(self, jan: Statement, mar: Statement) -> None:
        for _, txns in (("jan", jan), ("mar", mar)):
            assert all("Saldo Diário" not in memo for _, _, memo in txns[2])

    def test_amounts_consistent_with_descriptions(
        self, jan: Statement, mar: Statement
    ) -> None:
        for _, txns in (("jan", jan), ("mar", mar)):
            for _, amount, memo in txns[2]:
                if "enviado" in memo or "boleto" in memo:
                    assert amount < 0, memo
                elif "recebido" in memo or "salário" in memo:
                    assert amount > 0, memo

    def test_dates_within_statement_period(
        self, jan: Statement, mar: Statement
    ) -> None:
        for dt, _, _ in jan[2]:
            assert datetime(2026, 1, 1) <= dt <= datetime(2026, 1, 31, 23, 59, 59)
        for dt, _, _ in mar[2]:
            assert datetime(2026, 3, 1) <= dt <= datetime(2026, 3, 31, 23, 59, 59)

    def test_transactions_have_memo(self, jan: Statement, mar: Statement) -> None:
        for _, txns in (("jan", jan), ("mar", mar)):
            assert all(memo.strip() for _, _, memo in txns[2])


class TestBuildOfx:
    def test_ofx_structure(self, jan: Statement) -> None:
        account_id, balance, txns = jan
        ofx = build_ofx(account_id, balance, txns)

        # Header
        assert ofx.startswith("OFXHEADER:100\nDATA:OFXSGML\nVERSION:102")
        assert "<CURDEF>BRL" in ofx
        assert "<BANKID>208" in ofx
        assert f"<ACCTID>{account_id}" in ofx

        # Period covers all transactions
        start = min(t[0] for t in txns)
        end = max(t[0] for t in txns)
        assert f"<DTSTART>{start.strftime('%Y%m%d')}" in ofx
        assert f"<DTEND>{end.strftime('%Y%m%d')}" in ofx

        # One STMTTRN per transaction, all sections properly closed
        assert ofx.count("<STMTTRN>") == len(txns)
        assert ofx.count("</STMTTRN>") == len(txns)
        assert "<LEDGERBAL>" in ofx
        assert balance is not None
        assert f"<BALAMT>{balance:.2f}" in ofx
        assert ofx.rstrip().endswith("</OFX>")

    def test_fitids_unique(self, jan: Statement) -> None:
        ofx = build_ofx(*jan)
        fitids = cast("list[str]", re.findall(r"<FITID>(\w+)", ofx))
        assert len(fitids) == len(set(fitids)), "duplicate FITIDs in OFX"

    def test_trntype_matches_amount_sign(self, jan: Statement) -> None:
        ofx = build_ofx(*jan)
        blocks = cast("list[str]", re.findall(r"<STMTTRN>\n(.*?)\n</STMTTRN>", ofx))
        for block in blocks:
            m_type = re.search(r"<TRNTYPE>(\w+)", block)
            m_amount = re.search(r"<TRNAMT>(-?[\d.]+)", block)
            assert m_type is not None
            assert m_amount is not None
            trntype = m_type.group(1)
            amount = float(m_amount.group(1))
            assert (trntype == "DEBIT") == (amount < 0)

    def test_escapes_memo_special_chars(self) -> None:
        txns: list[Transaction] = [
            (datetime(2026, 1, 1, 12, 0), -50.0, "Foo & Bar <baz>")
        ]
        ofx = build_ofx("1234", None, txns)
        assert "Foo &amp; Bar &lt;baz&gt;" in ofx
        assert "& Bar <baz>" not in ofx

    def test_empty_memo_falls_back(self) -> None:
        txns: list[Transaction] = [(datetime(2026, 1, 1, 12, 0), -50.0, "")]
        ofx = build_ofx("1234", None, txns)
        assert "<MEMO>Transação" in ofx

    def test_no_balance_omits_ledgerbal(self, jan: Statement) -> None:
        account_id, _, txns = jan
        ofx = build_ofx(account_id, None, txns)
        assert "<LEDGERBAL>" not in ofx

    def test_amounts_formatted_two_decimals(self, jan: Statement) -> None:
        ofx = build_ofx(*jan)
        amounts = cast("list[str]", re.findall(r"<TRNAMT>(\S+)", ofx))
        assert all(re.fullmatch(r"-?\d+\.\d{2}", a) for a in amounts)
