"""Unit tests for the pure helper functions in the parser module."""

from datetime import datetime

import pytest

from btg_xls_to_ofx.parser import (
    esc,
    make_fitid,
    norm_datetime,
    norm_number,
    ofx_date,
    trn_type,
)


class TestNormNumber:
    def test_float_and_int_passthrough(self):
        assert norm_number(42) == 42.0
        assert norm_number(3.14) == 3.14

    def test_none_and_bool(self):
        assert norm_number(None) is None
        assert norm_number(True) is None
        assert norm_number(False) is None

    def test_ptbr_format(self):
        assert norm_number("1.234,56") == 1234.56

    def test_us_format(self):
        assert norm_number("1234.56") == 1234.56

    def test_comma_only_decimal(self):
        assert norm_number("123,45") == 123.45

    def test_reais_prefix_and_spaces(self):
        assert norm_number("R$ 1.234,56") == 1234.56

    def test_negative(self):
        assert norm_number("-1.234,56") == -1234.56

    def test_empty_and_whitespace(self):
        assert norm_number("") is None
        assert norm_number("   ") is None
        assert norm_number("R$") is None

    def test_garbage(self):
        assert norm_number("abc") is None


class TestNormDatetime:
    def test_datetime_passthrough(self):
        dt = datetime(2026, 1, 15, 10, 30)
        assert norm_datetime(dt) is dt

    def test_string_with_seconds(self):
        assert norm_datetime("15/01/2026 10:30:45") == datetime(2026, 1, 15, 10, 30, 45)

    def test_string_without_seconds(self):
        assert norm_datetime("15/01/2026 10:30") == datetime(2026, 1, 15, 10, 30)

    def test_strips_whitespace(self):
        assert norm_datetime("  15/01/2026 10:30  ") == datetime(2026, 1, 15, 10, 30)

    def test_invalid(self):
        assert norm_datetime("2026-01-15") is None
        assert norm_datetime("not a date") is None
        assert norm_datetime(None) is None
        assert norm_datetime(12345) is None


class TestEsc:
    def test_escapes_special_chars(self):
        assert esc("A & B <C>") == "A &amp; B &lt;C&gt;"

    def test_no_special_chars(self):
        assert esc("plain text") == "plain text"

    def test_ampersand_first(self):
        # '&' must be escaped before '<' and '>' to avoid double-escaping
        assert esc("&lt;") == "&amp;lt;"


class TestOfxDate:
    def test_format(self):
        dt = datetime(2026, 1, 15, 10, 30, 45)
        assert ofx_date(dt) == "20260115103045[-3:BRT]"


class TestMakeFitid:
    def test_deterministic(self):
        dt = datetime(2026, 1, 15, 10, 30)
        assert make_fitid(dt, -100.0, "Pix") == make_fitid(dt, -100.0, "Pix")

    def test_length(self):
        fitid = make_fitid(datetime(2026, 1, 15), 10.0, "memo")
        assert len(fitid) == 22

    def test_unique_inputs(self):
        dt = datetime(2026, 1, 15, 10, 30)
        a = make_fitid(dt, -100.0, "Pix A")
        b = make_fitid(dt, -200.0, "Pix A")
        c = make_fitid(dt, -100.0, "Pix B")
        assert len({a, b, c}) == 3


class TestTrnType:
    @pytest.mark.parametrize("amount,expected", [(-50.0, "DEBIT"), (50.0, "CREDIT")])
    def test_pix(self, amount: float, expected: str) -> None:
        assert trn_type(amount, "Pix - Empresa 1") == expected

    @pytest.mark.parametrize("amount,expected", [(5000.0, "CREDIT"), (-100.0, "DEBIT")])
    def test_salario(self, amount: float, expected: str) -> None:
        assert trn_type(amount, "Salário") == expected

    def test_pagamento(self):
        assert trn_type(300.0, "Pagamento recebido") == "CREDIT"
        assert trn_type(-300.0, "Pagamento de fatura") == "DEBIT"

    def test_fallback_by_sign(self):
        assert trn_type(-10.0, "Compra qualquer") == "DEBIT"
        assert trn_type(10.0, "Estorno") == "CREDIT"

    def test_case_insensitive(self):
        assert trn_type(-50.0, "PIX ENVIADO") == "DEBIT"
