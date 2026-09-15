import httpx

from sciagg.cli import main
from sciagg.http import Http
from sciagg.providers.crossref import Crossref
from sciagg.services import publication


def test_invalid_json_shape_isolated_from_successful_provider(tmp_path):
    from sciagg.models import Publication

    class Good:
        name = "good"

        def publication(self, doi):
            return Publication("good:1", "Real fixture title", doi=doi)

    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])))
    http = Http(tmp_path, client=client, min_interval=0)
    records, info = publication([Crossref(http), Good()], "10.1000/test")
    assert len(records) == 1 and records[0].id == "good:1"
    assert info["providers"][0]["status"] == "invalid_response"
    http.close()


def test_cli_invalid_journal_returns_nonzero_without_network(tmp_path, capsys):
    result = main(["--db", str(tmp_path / "test.sqlite"), "journal", "--issn", "1234-5678"])
    assert result == 2
    assert "Invalid ISSN" in capsys.readouterr().err


def test_cli_offline_missing_journal_is_failure(tmp_path, capsys):
    result = main(
        [
            "--db",
            str(tmp_path / "test.sqlite"),
            "--cache",
            str(tmp_path / "cache"),
            "--offline",
            "journal",
            "--issn",
            "2079-3537",
            "--json",
        ]
    )
    assert result == 2
    assert '"journal": null' in capsys.readouterr().out
