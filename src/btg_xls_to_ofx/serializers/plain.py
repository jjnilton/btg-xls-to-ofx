"""Hand-rolled OFX v1 (SGML) serializer (default backend).

Builds the OFX document by string assembly; no extra dependencies.
Creates OFX v1 only (OFX v2 requires the ofxtools backend).
"""

from datetime import datetime

from ..parser import (
    BANK_ID,
    ORG,
    Transaction,
    esc,
    make_fitid,
    ofx_date,
    trn_type,
)


def build_ofx(
    account_id: str, balance: float | None, transactions: list[Transaction]
) -> str:
    now = datetime.now()
    start = min(t[0] for t in transactions)
    end = max(t[0] for t in transactions)

    lines = [
        "OFXHEADER:100",
        "DATA:OFXSGML",
        "VERSION:102",
        "SECURITY:NONE",
        "ENCODING:USASCII",
        "CHARSET:1252",
        "COMPRESSION:NONE",
        "OLDFILEUID:NONE",
        "NEWFILEUID:NONE",
        "",
        "<OFX>",
        "<SIGNONMSGSRSV1>",
        "<SONRS>",
        "<STATUS>",
        "<CODE>0",
        "<SEVERITY>INFO",
        "</STATUS>",
        f"<DTSERVER>{ofx_date(now)}",
        "<LANGUAGE>POR",
        f"<FI><ORG>{esc(ORG)}</FI>",
        "</SONRS>",
        "</SIGNONMSGSRSV1>",
        "<BANKMSGSRSV1>",
        "<STMTTRNRS>",
        "<TRNUID>1",
        "<STATUS><CODE>0<SEVERITY>INFO</STATUS>",
        "<STMTRS>",
        "<CURDEF>BRL",
        "<BANKACCTFROM>",
        f"<BANKID>{BANK_ID}",
        f"<ACCTID>{esc(account_id)}",
        "<ACCTTYPE>CHECKING",
        "</BANKACCTFROM>",
        "<BANKTRANLIST>",
        f"<DTSTART>{ofx_date(start)}",
        f"<DTEND>{ofx_date(end)}",
    ]

    for dt, amount, memo in transactions:
        lines += [
            "<STMTTRN>",
            f"<TRNTYPE>{trn_type(amount, memo)}",
            f"<DTPOSTED>{ofx_date(dt)}",
            f"<TRNAMT>{amount:.2f}",
            f"<FITID>{make_fitid(dt, amount, memo)}",
            f"<MEMO>{esc(memo) if memo else 'Transação'}",
            "</STMTTRN>",
        ]

    lines += ["</BANKTRANLIST>"]
    if balance is not None:
        lines += [
            "<LEDGERBAL>",
            f"<BALAMT>{balance:.2f}",
            f"<DTASOF>{ofx_date(now)}",
            "</LEDGERBAL>",
        ]
    lines += [
        "</STMTRS>",
        "</STMTTRNRS>",
        "</BANKMSGSRSV1>",
        "</OFX>",
        "",
    ]
    return "\n".join(lines)
