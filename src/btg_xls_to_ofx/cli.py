"""Convert BTG Pactual checking account statements (.xls/.xlsx) to OFX."""

import argparse
import re
import sys
from collections.abc import Callable

from . import __version__
from .parser import read_statement
from .serializers.plain import build_ofx

Backend = str  # "plain" | "ofxtools"

BACKEND_PLAIN = "plain"
BACKEND_OFXTOOLS = "ofxtools"


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="btg-xls-to-ofx",
        description="Convert a BTG Pactual checking account statement "
        + "(.xls/.xlsx) to OFX.",
        epilog="The ofxtools backend defaults to OFX v2; "
        + "pass --sgml/--ofx-version=1 to force OFX v1.",
    )
    _ = p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show program's version number and exit",
    )
    _ = p.add_argument("input", help="statement file (.xls/.xlsx)")
    _ = p.add_argument(
        "output",
        nargs="?",
        help="output .ofx file (default: input name with .ofx extension)",
    )
    _ = p.add_argument(
        "--backend",
        choices=[BACKEND_PLAIN, BACKEND_OFXTOOLS],
        default=None,
        help="serializer engine (default: plain)",
    )
    _ = p.add_argument(
        "--ofx-version",
        type=int,
        choices=[1, 2],
        default=None,
        help="OFX spec version: 1 (SGML) or 2 (XML)",
    )
    aliases = p.add_mutually_exclusive_group()
    _ = aliases.add_argument(
        "--sgml", action="store_true", help="alias for --ofx-version=1"
    )
    _ = aliases.add_argument(
        "--xml", action="store_true", help="alias for --ofx-version=2"
    )
    _ = p.add_argument(
        "--silent", action="store_true", help="suppress all non-error output"
    )
    return p


def resolve_backend_version(
    backend: Backend | None, version: int | None
) -> tuple[Backend, int]:
    """Resolve the (backend, version) pair from possibly-partial flags.

    Raises ValueError for the invalid combination (plain + v2).
    """
    if backend is None:
        if version is None or version == 1:
            return BACKEND_PLAIN, 1
        return BACKEND_OFXTOOLS, 2
    if backend == BACKEND_PLAIN:
        if version == 2:
            msg = (
                "OFX v2 is only available with --backend=ofxtools; "
                "the plain backend creates OFX v1 (SGML) only"
            )
            raise ValueError(msg)
        return BACKEND_PLAIN, 1
    # ofxtools: defaults to v2 (documented in --help); explicit 1 is fine
    return BACKEND_OFXTOOLS, version if version is not None else 2


def infer_notice(backend: Backend | None, version: int | None) -> str | None:
    """Message to show when a backend had to be inferred from a version flag."""
    if backend is None:
        if version == 1:
            return "note: assuming --backend=plain (only backend that creates OFX v1)"
        if version == 2:
            return (
                "note: OFX v2 requires the ofxtools backend; using --backend=ofxtools"
            )
    return None


def main(argv: list[str] | None = None) -> None:
    parser = make_parser()
    args = parser.parse_args(argv)

    backend_arg: Backend | None = args.backend
    version_arg: int | None = args.ofx_version
    # Alias flags set the version, but must agree with an explicit one
    if args.sgml:
        if version_arg not in (None, 1):
            parser.error("--sgml conflicts with --ofx-version=2")
        version_arg = 1
    elif args.xml:
        if version_arg not in (None, 2):
            parser.error("--xml conflicts with --ofx-version=1")
        version_arg = 2

    try:
        backend, version = resolve_backend_version(backend_arg, version_arg)
    except ValueError as e:
        parser.error(str(e))  # exits with code 2

    notice: Callable[[str], None] = (
        (lambda _msg: None)
        if args.silent
        else (lambda msg: print(msg, file=sys.stderr))
    )
    msg = infer_notice(backend_arg, version_arg)
    if msg is not None:
        notice(msg)

    # Lazily resolved so a base install (without the [ofxtools] extra)
    # works as long as the plain backend is selected.
    if backend == BACKEND_OFXTOOLS:
        try:
            from .serializers.ofxtools import build_ofx_model, serialize
        except ImportError:
            parser.error(
                "the ofxtools backend requires the optional dependency: "
                + "install with: pip install 'btg-xls-to-ofx[ofxtools]'"
            )

    src: str = args.input
    dst: str = args.output or re.sub(r"\.xlsx?$", "", src, flags=re.IGNORECASE) + ".ofx"

    account_id, balance, transactions = read_statement(src)
    if not transactions:
        print("Nenhuma transação encontrada no arquivo.")
        sys.exit(1)

    if backend == BACKEND_PLAIN:
        ofx = build_ofx(account_id, balance, transactions)
        with open(dst, "w", encoding="latin-1") as f:
            _ = f.write(ofx)
    else:
        model = build_ofx_model(account_id, balance, transactions)  # pyright: ignore[reportPossiblyUnboundVariable]
        with open(dst, "wb") as f:
            _ = f.write(serialize(model, v2=version == 2))  # pyright: ignore[reportPossiblyUnboundVariable]

    if not args.silent:
        print(f"OK: {len(transactions)} transações convertidas -> {dst}")


if __name__ == "__main__":
    main()
