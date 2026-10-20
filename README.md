# btg-xls-to-ofx

Convert BTG Pactual checking account statements (.xls/.xlsx) to OFX,
suitable for importing into ledger-cli, GnuCash, HomeBank, KMyMoney, etc.

## For users

### Requirements

- **Python ≥ 3.10**
- [pip](https://pypi.org/project/pip/), [pipx](https://pipx.pypa.io/), or [uv](https://docs.astral.sh/uv/)

### Install

using `pip`:

```sh
python -m venv .venv && source .venv/bin/activate
pip install --user git+https://github.com/jjnilton/btg-xls-to-ofx
# optional support for OFX v2: pip install --user git+https://github.com/jjnilton/btg-xls-to-ofx#egg=btg-xls-to-ofx[ofxtools]
```

using `pipx`:

```sh
pipx install git+https://github.com/jjnilton/btg-xls-to-ofx
# optional support for OFX v2: pipx install 'git+https://github.com/jjnilton/btg-xls-to-ofx#egg=btg-xls-to-ofx[ofxtools]'
```

using `uv`:

```sh
uv tool install git+https://github.com/jjnilton/btg-xls-to-ofx
# optional support for OFX v2: uv tool install 'btg-xls-to-ofx[ofxtools] @ git+https://github.com/jjnilton/btg-xls-to-ofx'
```

### Usage

Use the `--help` argument to see the available options:

```sh
usage: btg-xls-to-ofx [-h] [--version] [--backend {plain,ofxtools}]
                      [--ofx-version {1,2}] [--sgml | --xml] [--silent]
                      input [output]

Convert a BTG Pactual checking account statement (.xls/.xlsx) to OFX.

positional arguments:
  input                 statement file (.xls/.xlsx)
  output                output .ofx file (default: input name with .ofx
                        extension)

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --backend {plain,ofxtools}
                        serializer engine (default: plain)
  --ofx-version {1,2}   OFX spec version: 1 (SGML) or 2 (XML)
  --sgml                alias for --ofx-version=1
  --xml                 alias for --ofx-version=2
  --silent              suppress all non-error output


The ofxtools backend defaults to OFX v2; pass --sgml/--ofx-version=1 to force OFX v1.
```

Example usage:

```sh
# btg-xls-to-ofx file.xls [output-filename.ofx] [flags]
btg-xls-to-ofx "Extrato_2026-01-01_a_2026-01-31_12345678901(1).xls" [output.ofx]
```

> [!NOTE]
> It also can be used from an ephemeral environment with `pipx` or `uvx`:

pipx:

```sh
pipx run --spec git+https://github.com/jjnilton/btg-xls-to-ofx btg-xls-to-ofx "Extrato_....xls" [output.ofx]
```

uv:

```sh
uvx --from git+https://github.com/jjnilton/btg-xls-to-ofx btg-xls-to-ofx "Extrato_....xls" [output.ofx]
```

## For developers

This project is split into four parts:

| Part | Files | Description |
|-------|-------|----------------|
| CLI | `src/btg_xls_to_ofx/cli.py` | argparse entry point (`btg-xls-to-ofx` script); resolves `--backend` / `--ofx-version` / `--sgml` / `--xml` / `--silent` |
| Parsing | `src/btg_xls_to_ofx/parser.py` | Reads `.xls`/`.xlsx` (format sniffing by header), normalizes pt-BR numbers and dates, extracts account ID / balance / transactions |
| Serializers | `src/btg_xls_to_ofx/serializers/plain.py` | Hand-rolled OFX v1 (SGML) output without extra dependencies |
| | `src/btg_xls_to_ofx/serializers/ofxtools.py` | ofxtools-backed serializer; supports OFX v1 and v2; requires the `[ofxtools]` extra |
| Anonymizer | `src/btg_xls_to_ofx/anonymize.py` | `btg-anonymize` CLI that strips real identity data, aliases payees, randomizes amounts with seeded RNG, recalculates balances |

Console scripts are declared in `pyproject.toml` under `[project.scripts]`: `btg-xls-to-ofx` and `btg-anonymize`.

#### Data flow

```text
statement.xls
      │
      ▼
   cli.py ──► parser.py ──┬──► serializers/plain.py   ──► statement.ofx   (v1)
   (argparse)             └──► serializers/ofxtools.py ──► statement.ofx   (v1/v2)

btg-anonymize ──► anonymize.py ──► samples/*_anonymized.xlsx
```

The parser is shared by both serializers and by the anonymizer, so statement-parsing rules live in one place.


### Setup

Clone this repository and activate the virtual environment:

```sh
git clone https://github.com/jjnilton/btg-xls-to-ofx btg-xls-to-ofx && cd btg-xls-to-ofx
python -m venv .venv && source .venv/bin/activate
btg-xls-to-ofx # run the program
```

Alternatively, using `pip`:

> [!NOTE] `[dev,ofxtools]`, are optional dependency sets
declared in `pyproject.toml`; `-e` installs the project in editable
mode so source edits take effect without reinstalling.

```sh
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,ofxtools]'

```

Or `uv`:

```sh
uv sync --all-extras          # create .venv and install everything from uv.lock
uv run btg-xls-to-ofx         # run the program
```

### Pre-commit checks

The repo ships a git pre-commit hook (via the
[pre-commit](https://pre-commit.com/) framework) that blocks commits
failing any of: `ruff check` (lint), `ruff format --check`
(formatting), and `pytest`.

All hooks are `local` and run through
`uv run --frozen`, so tool versions come from `uv.lock`.

Setting it up:

In the virtual environment:

```
pre-commit install
```

Or with uv:

```sh
uv run pre-commit install
```

Useful commands:

```sh
uv run pre-commit run --all-files   # check everything on demand
uv run pre-commit run ruff-check    # run a single hook
```

### Lint and format

Lint and format with [ruff](https://github.com/astral-sh/ruff):

```sh
ruff check src tests          # report problems
ruff check --fix src tests    # auto-fix what's safe
ruff format src tests         # format code (ruff format --check to verify only)
```

### Running tests

Run the test suite with [pytest](https://docs.pytest.org/en/stable/).

From a virtual environment:

```sh
pytest
```

Or with `uv`:

```sh
uv run pytest
```

To run a single test file:

```sh
uv run pytest tests/test_cli.py
```

The suite includes unit tests (`test_parser.py`), integration tests
against the anonymized samples (`test_integration.py`), end-to-end CLI
tests (`test_e2e.py`), and anonymizer tests (`test_anonymize.py`).

### Version checks

The Minimum Python version is checked with [vermin](https://github.com/netromdk/vermin):

```sh
vermin --eval-annotations -t=3.10- src  # fails if code needs > 3.10
```

While vermin helps with static heuristic; the authoritative check is running the
test suite on a real 3.10 interpreter, e.g.:

```sh
uv venv --python 3.10 /tmp/venv310
uv pip install -p /tmp/venv310 '.' 'pytest' 'xlwt' 'ofxtools'
/tmp/venv310/bin/python -m pytest tests
```

### Generating anonymized statements

To share a sheet/statement file without real data, a tool `btg-anonymize`
is included. It replaces personal/identifiable data with placeholders.

#### Usage

```
usage: btg-anonymize [-h] [--out-dir OUT_DIR] [files ...]

Create anonymized copies of BTG Pactual statement spreadsheets.

positional arguments:
  files              one or more .xls/.xlsx files, or glob patterns like *.xls

options:
  -h, --help         show this help message and exit
  --out-dir OUT_DIR  output directory for anonymized files (default: current directory)
```

#### Examples

```sh
# one or more files
btg-anonymize Extrato_2026-01-01_a_2026-01-31_123(1).xls Extrato_2026-03.xls

# glob patterns
btg-anonymize "*.xls" "*.xlsx"

# default output is the current directory; use --out-dir to change it
btg-anonymize "*.xls" --out-dir /tmp/anonymized
```

## License

GPL-3.0-only, see [LICENSE](LICENSE).
