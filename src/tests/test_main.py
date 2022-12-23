import pytest
from fastapi.testclient import TestClient

from ..main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "pkgs,expected_diff",
    [
        (
            ["pangeo-forge-runner==0.7.1"],
            # ./ci/env.yaml already has "pangeo-forge-runner==0.7.1",
            # therefore passing it here should result in no diff
            {"added": [], "changed": []},
        ),
        (
            ["pangeo-forge-runner==0.7.0"],
            # if we request a different version of pangeo-forge-runner from
            # the one which comes pre-installed in our env, then of course
            # we do expect to see a diff reported by the cloudrun service
            {
                "added": [],
                "changed": [
                    {
                        "name": "pangeo-forge-runner",
                        "version": "0.7.0",
                        "prior_version": "0.7.1",
                    }
                ],
            },
        ),
    ],
)
def test_main(pkgs, expected_diff):
    request = {
        "pangeo_forge_runner": {"cmd": ["--help"]},
        "install": {"pkgs": pkgs, "env": "cloudrun"},
    }
    response = client.post("/", json=request)
    assert response.status_code == 202
    assert response.json()["install_result"] == {
        "diff": expected_diff,
        "stderr": None,
    }
    assert response.json()["pangeo_forge_runner_result"].startswith(
        "This is an application.\n\n"
    )
