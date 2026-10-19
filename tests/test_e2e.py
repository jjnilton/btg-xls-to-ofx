"""End-to-end tests: run the CLI on sample statements and validate the
generated OFX file by parsing it back with ofxtools."""

# ofxtools ships untyped models: all values parsed from the OFX file are
# Any. Silence the Any-related rules for this boundary file only.
# pyright: reportAny=false, reportExplicitAny=false

from pathlib import Path
from typing import Any

import pytest
from ofxtools.Parser import OFXTree

from btg_xls_to_ofx.cli import main
from btg_xls_to_ofx.parser import read_statement

SAMPLES = Path(__file__).parent.parent / "samples"
STATEMENTS = [
    SAMPLES / "statement_2026-01.xlsx",
    SAMPLES / "statement_2026-03.xls",
]

# Backend/version combos covered end-to-end: "flags, expected header"
BACKENDS: list[tuple[list[str], str | bytes]] = [
    ([], b"OFXHEADER:100"),  # default: plain backend, OFX v1
    (["--backend=plain", "--sgml"], b"OFXHEADER:100"),
    (["--backend=ofxtools"], b"<?xml"),  # defaults to v2
    (["--backend=ofxtools", "--sgml"], b"OFXHEADER:100"),
    (["--backend=ofxtools", "--ofx-version=1"], b"OFXHEADER:100"),
]


def parse_and_check(dst: Path, src: Path) -> None:
    """ofxtools raises OFXSpecError on any invalid OFX, so a successful
    parse+convert already means the file is structurally valid."""
    tree = OFXTree()
    _ = tree.parse(str(dst))
    stmt: Any = tree.convert().statements[0]

    acct, balance, txns = read_statement(str(src))
    assert stmt.account.acctid == acct
    stmt_txns: list[Any] = stmt.banktranlist
    assert len(stmt_txns) == len(txns)
    if balance is not None:
        balamt = stmt.ledgerbal.balamt
        assert float(balamt) == pytest.approx(balance)

    # Values survive the round-trip: sign, amount, and FITID uniqueness
    amounts = [float(t.trnamt) for t in stmt_txns]
    assert sorted(amounts) == sorted(t[1] for t in txns)
    fitids = [t.fitid for t in stmt_txns]
    assert len(fitids) == len(set(fitids))


@pytest.mark.parametrize(
    "flags,header",
    BACKENDS,
    ids=[
        "default",
        "plain-sgml",
        "ofxtools-default-v2",
        "ofxtools-sgml",
        "ofxtools-v1",
    ],
)
@pytest.mark.parametrize("src", STATEMENTS, ids=[p.suffix[1:] for p in STATEMENTS])
def test_generates_valid_ofx(
    tmp_path: Path, src: Path, flags: list[str], header: bytes
) -> None:
    dst = tmp_path / (src.stem + ".ofx")
    main([str(src), str(dst), *flags])
    assert dst.exists()
    assert dst.read_bytes().lstrip()[: len(header)] == header
    parse_and_check(dst, src)


def test_default_output_name(tmp_path: Path) -> None:
    src = tmp_path / "statement.xls"
    _ = src.write_bytes((SAMPLES / "statement_2026-03.xls").read_bytes())
    main([str(src)])
    assert (tmp_path / "statement.ofx").exists()


def test_no_transactions_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    xlsx = tmp_path / "empty.xlsx"
    from openpyxl import Workbook

    Workbook().save(xlsx)
    with pytest.raises(SystemExit) as exc:
        main([str(xlsx), str(tmp_path / "empty.ofx")])
    assert exc.value.code == 1
    assert "Nenhuma transação" in capsys.readouterr().out


def test_plain_backend_rejects_v2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = SAMPLES / "statement_2026-01.xlsx"
    with pytest.raises(SystemExit) as exc:
        main([str(src), str(tmp_path / "out.ofx"), "--backend=plain", "--xml"])
    assert exc.value.code == 2
    assert "--backend=ofxtools" in capsys.readouterr().err
