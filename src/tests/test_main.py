import subprocess

import pytest
from fastapi.testclient import TestClient

from ..main import app

client = TestClient(app)

# note, if bumping this, you must do so in ./ci/env.yaml as well
# NOTE: because tests alter environment in a pre-determined sequence,
# they cannot be run individually or out-of-sequence.
STARTING_VERSION = "pangeo-forge-runner==0.7.1"


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    # the tests change the underlying conda environment, so let's reset that
    # before exiting the test session, so that the developer doesn't have to
    # manually do so before running the next test session. this doesn't matter
    # for ci, but for local development it's very helpful
    proc = subprocess.run(
        f"mamba run -n cloudrun pip install -U {STARTING_VERSION}".split()
    )
    assert proc.returncode == 0


@pytest.mark.parametrize(
    "pkgs,expected_diff,expected_error",
    [
        (
            [STARTING_VERSION],
            # ./ci/env.yaml already has this version,
            # therefore passing it here should result in no diff
            {"added": [], "changed": []},
            None,
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
                        "prior_version": STARTING_VERSION.split("==")[-1],
                    }
                ],
            },
            None,
        ),
        (
            ["pangeo-forge-runner==0.7.05"],
            # this version doesn't exist, so pip will throw an error
            None,
            "ERROR: No matching distribution found for pangeo-forge-runner==0.7.05",
        ),
    ],
)
def test_main(pkgs, expected_diff, expected_error):
    request = {
        "pangeo_forge_runner": {"cmd": ["--help"]},
        "install": {"pkgs": pkgs, "env": "cloudrun"},
    }
    response = client.post("/", json=request)

    if expected_error:
        assert response.status_code == 422
        assert expected_error in response.json()["detail"]
    else:
        assert response.status_code == 202
        assert response.json()["install_result"]["diff"] == expected_diff
        assert response.json()["pangeo_forge_runner_result"].startswith(
            "This is an application.\n\n"
        )
