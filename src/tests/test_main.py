import subprocess

import pytest
from fastapi.testclient import TestClient
from pytest_lazyfixture import lazy_fixture

from ..main import app

client = TestClient(app)

DEFAULT_RUNNER_VERSION = "pangeo-forge-runner==0.7.1"


def call_pip(cmd, pkgs):
    proc = subprocess.run(f"mamba run -n cloudrun pip {cmd} {' '.join(pkgs)}".split())
    assert proc.returncode == 0


@pytest.fixture
def no_install_no_error():
    cmd = ["--help"]
    pkgs = [DEFAULT_RUNNER_VERSION]
    expected_diff = {"added": [], "changed": []}
    expected_error = None

    call_pip("install -U", pkgs)

    yield cmd, pkgs, expected_diff, expected_error


@pytest.fixture
def add_pkg():
    added_pkg = "black==22.12.0"

    cmd = ["--help"]
    pkgs = [DEFAULT_RUNNER_VERSION, added_pkg]
    expected_diff = {"added": [{"name": "black", "version": "22.12.0"}], "changed": []}
    expected_error = None

    # make sure that black will be the only pkg added under test
    call_pip("uninstall -y", [added_pkg])
    call_pip("install -U", [DEFAULT_RUNNER_VERSION])

    yield cmd, pkgs, expected_diff, expected_error


@pytest.fixture
def runner_called_proc_error():
    cmd = ["bake", "--unsupported-arg"]
    pkgs = [DEFAULT_RUNNER_VERSION]
    expected_diff = {"added": [], "changed": []}
    expected_error = "error: unrecognized arguments: --unsupported-arg\n"

    call_pip("install -U", pkgs)

    yield cmd, pkgs, expected_diff, expected_error


@pytest.fixture
def change_runner_version():
    cmd = ["--help"]
    pkgs = ["pangeo-forge-runner==0.7.0"]
    # if we request a different version of pangeo-forge-runner from
    # the one which comes pre-installed in our env, then we expect
    # to see a diff reported by the service
    expected_diff = {
        "added": [],
        "changed": [
            {
                "name": "pangeo-forge-runner",
                "version": "0.7.0",
                "prior_version": DEFAULT_RUNNER_VERSION.split("==")[-1],
            }
        ],
    }
    expected_error = None

    # make sure default version is installed here, so that we can be sure the
    # changed version will be installed by the service under test
    call_pip("install -U", [DEFAULT_RUNNER_VERSION])

    yield cmd, pkgs, expected_diff, expected_error


@pytest.fixture
def installation_error():
    cmd = ["--help"]
    # this version doesn't exist on pypi, which is what we want for this test!
    pkgs = ["pangeo-forge-runner==0.7.05"]
    expected_diff = {"added": [], "changed": []}
    expected_error = (
        "ERROR: No matching distribution found for pangeo-forge-runner==0.7.05"
    )
    yield cmd, pkgs, expected_diff, expected_error


@pytest.fixture(
    params=[
        lazy_fixture("no_install_no_error"),
        lazy_fixture("add_pkg"),
        lazy_fixture("runner_called_proc_error"),
        lazy_fixture("change_runner_version"),
        lazy_fixture("installation_error"),
    ]
)
def fixture(request):
    return request.param


def test_main(fixture):
    cmd, pkgs, expected_diff, expected_error = fixture
    request = {
        "pangeo_forge_runner": {"cmd": cmd},
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
