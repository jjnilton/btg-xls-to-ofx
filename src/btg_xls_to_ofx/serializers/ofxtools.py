"""OFX serializer backed by the ofxtools library.

Supports OFX v1 (SGML) and OFX v2 (XML). More spec-strict than the
plain backend. Requires the [ofxtools] optional dependency.

NOTE: LEDGERBAL is required by the OFX spec, so ofxtools raises
OFXSpecError if the ledger balance is None (unlike the plain backend,
which simply omits it).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from xml.etree import ElementTree as ET

from ofxtools import utils
from ofxtools.header import OFXHeaderV1, OFXHeaderV2
from ofxtools.models import (
    BANKACCTFROM,
    BANKMSGSRSV1,
    BANKTRANLIST,
    LEDGERBAL,
    SIGNONMSGSRSV1,
    SONRS,
    STATUS,
    STMTRS,
    STMTTRN,
    STMTTRNRS,
)
from ofxtools.models.ofx import OFX

from ..parser import BANK_ID, Transaction, make_fitid, trn_type

BRT = timezone(timedelta(hours=-3))


def aware(dt: datetime) -> datetime:
    """Make a naive datetime timezone-aware (ofxtools requires it)."""
    return dt.replace(tzinfo=BRT) if dt.tzinfo is None else dt


def money(value: float) -> Decimal:
    """Convert float to a 2-decimal Decimal (avoids float repr noise)."""
    return Decimal(str(value)).quantize(Decimal("0.01"))


def build_ofx_model(
    account_id: str, balance: float | None, transactions: list[Transaction]
) -> OFX:
    now = aware(datetime.now())
    start = aware(min(t[0] for t in transactions))
    end = aware(max(t[0] for t in transactions))

    stmttrns = [
        STMTTRN(
            trntype=trn_type(amount, memo),
            dtposted=aware(dt),
            trnamt=money(amount),
            fitid=make_fitid(dt, amount, memo),
            memo=memo if memo else "Transação",
        )
        for dt, amount, memo in transactions
    ]

    acct = BANKACCTFROM(bankid=BANK_ID, acctid=account_id, accttype="CHECKING")
    tranlist = BANKTRANLIST(*stmttrns, dtstart=start, dtend=end)
    if balance is not None:
        stmtrs = STMTRS(
            curdef="BRL",
            bankacctfrom=acct,
            banktranlist=tranlist,
            ledgerbal=LEDGERBAL(balamt=money(balance), dtasof=now),
        )
    else:  # ofxtools rejects explicit None for optional sub-aggregates
        stmtrs = STMTRS(curdef="BRL", bankacctfrom=acct, banktranlist=tranlist)

    return OFX(
        signonmsgsrsv1=SIGNONMSGSRSV1(
            sonrs=SONRS(
                status=STATUS(code=0, severity="INFO"),
                dtserver=now,
                language="POR",
            )
        ),
        bankmsgsrsv1=BANKMSGSRSV1(
            STMTTRNRS(
                trnuid="1",
                status=STATUS(code=0, severity="INFO"),
                stmtrs=stmtrs,
            )
        ),
    )


def serialize(ofx: OFX, v2: bool) -> bytes:
    et = ofx.to_etree()
    if v2:
        # OFXv2 (XML) is always UTF-8 per ofxtools' header codec
        header = str(
            OFXHeaderV2(
                version=203, security="NONE", oldfileuid="NONE", newfileuid="NONE"
            )
        )
        body = ET.tostring(et, encoding="unicode")
        codec = "utf-8"
    else:  # OFX v1 SGML: leaf elements without closing tags
        header = str(OFXHeaderV1(version=102, encoding="USASCII", charset="1252"))
        body = utils.tostring_unclosed_elements(et).decode("utf-8")
        codec = "latin-1"
    return (header + body + "\n").encode(codec)
