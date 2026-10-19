"""Guardrail tests for anonymize.py."""

import random
from datetime import datetime
from pathlib import Path
from typing import cast

import pytest

from btg_xls_to_ofx.anonymize import (
    Rows,
    alias_description,
    anonymize,
    anonymize_values,
    expand_args,
    main,
    period_name,
)
from btg_xls_to_ofx.parser import CellValue, load_rows, norm_number

SAMPLES = Path(__file__).parent.parent / "samples"


class TestAliasDescription:
    def test_deterministic_and_numbered(self):
        aliases: dict[str, str] = {}
        a = alias_description("João Silva", aliases)
        b = alias_description("Amazon Marketplace", aliases)
        assert (a, b) == ("Recebedor 1", "Recebedor 2")
        # Same input -> same alias
        assert alias_description("João Silva", aliases) == "Recebedor 1"

    def test_all_payees_use_the_same_sequence(self):
        aliases: dict[str, str] = {}
        _ = alias_description("João Silva", aliases)
        assert alias_description("Amazon Marketplace", aliases) == "Recebedor 2"

    def test_skips_blank_and_daily_balance(self):
        assert alias_description("", {}) == ""
        assert alias_description("Saldo Diário", {}) == "Saldo Diário"


class TestPeriodName:
    def test_extracts_period_from_filename(self):
        p = Path("Extrato_2026-01-01_a_2026-01-31_123(1).xls")
        assert period_name(p) == "statement_2026-01_anonymized.xlsx"

    def test_fallback_to_stem(self):
        assert period_name(Path("weird_name.xls")) == "weird_name_anonymized.xlsx"


class TestExpandArgs:
    def test_glob_pattern_expands(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.xls").write_bytes(b"")
        (tmp_path / "b.xlsx").write_bytes(b"")
        (tmp_path / "c.txt").write_bytes(b"")
        result = expand_args(["*.xls", "*.xlsx"])
        names = sorted(p.name for p in result)
        assert names == ["a.xls", "b.xlsx"]

    def test_literal_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "statement.xls").write_bytes(b"")
        result = expand_args(["statement.xls"])
        assert [p.name for p in result] == ["statement.xls"]

    def test_non_excel_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "notes.txt").write_bytes(b"")
        result = expand_args(["notes.txt"])
        assert result == []

    def test_duplicates_removed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dup.xls").write_bytes(b"")
        result = expand_args(["dup.xls", "dup.xls", "*.xls"])
        assert len(result) == 1
        assert result[0].name == "dup.xls"


class TestMain:
    def test_no_args_prints_help_and_exits(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.err
        assert "btg-anonymize" in captured.err

    def test_processes_explicit_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "Extrato_2026-01-01_a_2026-01-31_123(1).xls"
        _ = src.write_bytes(
            (
                Path(__file__).parent.parent / "samples" / "statement_2026-01.xlsx"
            ).read_bytes()
        )

        out_dir = tmp_path / "out"
        main([str(src), "--out-dir", str(out_dir)])

        assert (out_dir / "statement_2026-01_anonymized.xlsx").exists()
        captured = capsys.readouterr()
        assert "OK:" in captured.out

    def test_processes_glob_pattern(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        sample = Path(__file__).parent.parent / "samples" / "statement_2026-01.xlsx"
        (tmp_path / "file1.xlsx").write_bytes(sample.read_bytes())
        (tmp_path / "file2.xlsx").write_bytes(sample.read_bytes())

        out_dir = tmp_path / "out"
        main(["*.xlsx", "--out-dir", str(out_dir)])

        assert (out_dir / "file1_anonymized.xlsx").exists()
        assert (out_dir / "file2_anonymized.xlsx").exists()


class TestAnonymize:
    def make_rows(self) -> Rows:
        return [
            ["Cliente:", "Real Name", None, "CPF:", "111.222.333-44"],
            ["Agência:", "9999", None, "Conta:", "987654-3"],
            [None, datetime(2026, 1, 5, 10, 0), None, None, None, None, "João Silva"],
            [None, datetime(2026, 1, 6, 10, 0), None, None, None, None, "Amazon"],
            [None, datetime(2026, 1, 6, 12, 0), None, None, None, None, "Saldo Diário"],
        ]

    def test_replaces_identity_fields(self):
        rows = anonymize(self.make_rows(), {})
        assert rows[0][1] == "José Silva"  # Cliente
        assert rows[0][4] == "000.123.456-78"  # CPF
        assert rows[1][1] == "0001"  # Agência
        assert rows[1][4] == "123456-7"  # Conta

    def test_aliases_all_payees_only_in_dated_rows(self):
        rows = anonymize(self.make_rows(), {})
        assert rows[2][6] == "Recebedor 1"
        assert rows[3][6] == "Recebedor 2"
        # Saldo Diário and dates/amounts columns are untouched
        assert rows[4][6] == "Saldo Diário"
        assert isinstance(rows[2][1], datetime)

    def test_aliases_shared_across_calls(self):
        aliases: dict[str, str] = {}
        _ = anonymize(self.make_rows(), aliases)
        rows2 = anonymize([self.make_rows()[2]], aliases)
        assert rows2[0][6] == "Recebedor 1"

    def test_real_samples_are_anonymized(self):
        # The shipped samples must not leak real identity values and must
        # still parse correctly through the converter.
        # Skip Office lock files (~lock.filename#) and other non-Excel files.
        for sample in SAMPLES.iterdir():
            if sample.name.startswith(".") or sample.name.startswith("~"):
                continue
            if sample.suffix.lower() not in (".xls", ".xlsx"):
                continue
            rows = load_rows(str(sample))
            flat = {str(c) for row in rows for c in row if c is not None}
            assert "José Silva" in flat
            assert "000.123.456-78" in flat
            assert "123456-7" in flat


class TestAnonymizeValues:
    def make_rows(self) -> Rows:
        def dt(d: int) -> datetime:
            return datetime(2026, 1, d, 10, 0)

        header = cast(list[CellValue], [None] * 7 + ["Saldo atual:", None, 800.0])
        return [
            header,
            [
                None,
                dt(1),
                "Outra Categoria",
                "Pix enviado",
                None,
                None,
                "Amazon",
                None,
                None,
                None,
                -50.0,
            ],
            [
                None,
                dt(1),
                None,
                None,
                None,
                None,
                "Saldo Diário",
                None,
                None,
                None,
                750.0,
            ],
            [
                None,
                dt(2),
                "Transferência",
                "Pix recebido",
                None,
                None,
                "João Silva",
                None,
                None,
                None,
                100.0,
            ],
            [
                None,
                dt(2),
                None,
                None,
                None,
                None,
                "Saldo Diário",
                None,
                None,
                None,
                850.0,
            ],
        ]

    def test_amounts_change_but_keep_sign_and_range(self):
        rows = anonymize_values(self.make_rows(), random.Random(1))
        sent = norm_number(rows[1][10])
        received = norm_number(rows[3][10])
        assert sent is not None and received is not None
        assert sent != -50.0
        assert -500.0 <= sent <= -1.0
        assert received != 100.0
        assert 1.0 <= received <= 500.0

    def test_balances_are_recalculated_and_consistent(self):
        rows = anonymize_values(self.make_rows(), random.Random(1))
        first_day = norm_number(rows[2][10])
        second_day = norm_number(rows[4][10])
        sent = norm_number(rows[1][10])
        received = norm_number(rows[3][10])
        assert (
            first_day is not None
            and second_day is not None
            and sent is not None
            and received is not None
        )
        assert first_day == round(10_000.0 + sent, 2)
        assert second_day == round(first_day + received, 2)
        # 'Saldo atual:' reflects the final balance
        assert rows[0][9] == second_day

    def test_deterministic_given_same_seed(self):
        a = anonymize_values(self.make_rows(), random.Random(7))
        b = anonymize_values(self.make_rows(), random.Random(7))
        assert a == b
