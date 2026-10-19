"""Unit tests for CLI argument resolution: the backend/version matrix,
--sgml/--xml aliases, and --silent."""

from pathlib import Path

import pytest

from btg_xls_to_ofx.cli import (
    infer_notice,
    main,
    resolve_backend_version,
)

SAMPLES = Path(__file__).parent.parent / "samples"
STATEMENT = SAMPLES / "statement_2026-01.xlsx"


class TestResolveBackendVersion:
    @pytest.mark.parametrize(
        "backend,version,expected",
        [
            (None, None, ("plain", 1)),  # bare invocation
            ("plain", None, ("plain", 1)),
            ("plain", 1, ("plain", 1)),
            (None, 1, ("plain", 1)),  # v1 with no backend -> plain
            ("ofxtools", None, ("ofxtools", 2)),  # ofxtools defaults to v2
            ("ofxtools", 1, ("ofxtools", 1)),
            ("ofxtools", 2, ("ofxtools", 2)),
            (None, 2, ("ofxtools", 2)),  # v2 with no backend -> ofxtools
        ],
    )
    def test_matrix(
        self,
        backend: str | None,
        version: int | None,
        expected: tuple[str, int],
    ) -> None:
        assert resolve_backend_version(backend, version) == expected

    def test_plain_with_v2_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="--backend=ofxtools"):
            _ = resolve_backend_version("plain", 2)


class TestInferNotice:
    def test_no_notice_for_explicit_combos(self) -> None:
        assert infer_notice(None, None) is None
        assert infer_notice("plain", 1) is None
        assert infer_notice("ofxtools", None) is None
        assert infer_notice("ofxtools", 2) is None

    def test_notice_when_backend_inferred(self) -> None:
        assert "plain" in (infer_notice(None, 1) or "")
        assert "ofxtools" in (infer_notice(None, 2) or "")


class TestVersionFlag:
    def test_version_flag_exits_0_and_prints(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from importlib.metadata import version as pkg_version

        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert f"btg-xls-to-ofx {pkg_version('btg-xls-to-ofx')}" in out


class TestCliMatrix:
    def test_invalid_combo_exits_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            main(
                [
                    str(STATEMENT),
                    str(tmp_path / "out.ofx"),
                    "--backend=plain",
                    "--ofx-version=2",
                ]
            )
        assert exc.value.code == 2
        assert "--backend=ofxtools" in capsys.readouterr().err

    def test_conflicting_alias_exits_2(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            main(
                [
                    str(STATEMENT),
                    str(tmp_path / "out.ofx"),
                    "--sgml",
                    "--xml",
                ]
            )
        assert exc.value.code == 2

    def test_alias_conflicts_with_version_flag(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            main(
                [
                    str(STATEMENT),
                    str(tmp_path / "out.ofx"),
                    "--ofx-version=2",
                    "--sgml",
                ]
            )
        assert exc.value.code == 2

    def test_version_inference_prints_note(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main([str(STATEMENT), str(tmp_path / "out.ofx"), "--sgml"])
        assert "assuming --backend=plain" in capsys.readouterr().err

    def test_ofxtools_backend_alone_is_silent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main([str(STATEMENT), str(tmp_path / "out.ofx"), "--backend=ofxtools"])
        assert capsys.readouterr().err == ""

    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        assert capsys.readouterr().out.startswith("btg-xls-to-ofx ")

    def test_silent_suppresses_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        dst = tmp_path / "out.ofx"
        main([str(STATEMENT), str(dst), "--sgml", "--silent"])
        captured = capsys.readouterr()
        assert captured.out == "" and captured.err == ""
        assert dst.exists()
