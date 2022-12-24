import subprocess

import pytest
from fastapi.testclient import TestClient
from pytest_lazyfixture import lazy_fixture

from ..main import app

client = TestClient(app)


def call_pip(cmd, pkgs):
    proc = subprocess.run(f"mamba run -n cloudrun pip {cmd} {' '.join(pkgs)}".split())
    assert proc.returncode == 0


@pytest.fixture
def default_runner_version():
    return "pangeo-forge-runner==0.7.1"


@pytest.fixture
def default_pkgs(default_runner_version):
    return [default_runner_version]


@pytest.fixture
def default_cmd():
    return ["--help"]


@pytest.fixture
def default_env():
    return "cloudrun"


@pytest.fixture
def no_install_diff():
    return {"added": [], "changed": []}


@pytest.fixture
def no_install_no_error(default_cmd, default_pkgs, default_env, no_install_diff):
    call_pip("install -U", default_pkgs)
    yield default_cmd, default_pkgs, default_env, no_install_diff, None


@pytest.fixture
def add_pkg(default_cmd, default_pkgs, default_env):
    added_pkg = ["black==22.12.0"]
    expected_diff = {"added": [{"name": "black", "version": "22.12.0"}], "changed": []}
    # make sure that black will be the only pkg added under test
    # so install it first (to capture its dependencies)
    call_pip("install -U", default_pkgs + added_pkg)
    # and then uninstall it (if we don't do this as two steps, the diff is non-deterministic.)
    call_pip("uninstall -y", added_pkg)
    yield default_cmd, default_pkgs + added_pkg, default_env, expected_diff, None


@pytest.fixture
def runner_called_proc_error(default_pkgs, default_env, no_install_diff):
    cmd = ["bake", "--unsupported-arg"]
    expected_error = "error: unrecognized arguments: --unsupported-arg\n"
    call_pip("install -U", default_pkgs)

    yield cmd, default_pkgs, default_env, no_install_diff, expected_error


@pytest.fixture
def change_runner_version(default_cmd, default_runner_version, default_env):
    pkgs = ["pangeo-forge-runner==0.7.0"]
    assert pkgs[0] != default_runner_version
    # if we request a different version of pangeo-forge-runner from
    # the one which comes pre-installed in our env, then we expect
    # to see a diff reported by the service
    expected_diff = {
        "added": [],
        "changed": [
            {
                "name": "pangeo-forge-runner",
                "version": "0.7.0",
                "prior_version": default_runner_version.split("==")[-1],
            }
        ],
    }
    # make sure default version is installed here, so that we can be sure the
    # changed version will be installed by the service under test
    call_pip("install -U", [default_runner_version])
    yield default_cmd, pkgs, default_env, expected_diff, None


@pytest.fixture
def installation_error(default_cmd, default_env, no_install_diff):
    # this version doesn't exist on pypi, which is what we want for this test!
    pkgs = ["pangeo-forge-runner==0.7.05"]
    expected_error = (
        "ERROR: No matching distribution found for pangeo-forge-runner==0.7.05"
    )
    yield default_cmd, pkgs, default_env, no_install_diff, expected_error


@pytest.fixture
def nonexistent_env_error(default_cmd, default_pkgs, no_install_diff):
    expected_error = "'nonexistent_env' is not a conda env name on this system"
    yield default_cmd, default_pkgs, "nonexistent_env", no_install_diff, expected_error


@pytest.fixture(
    params=[
        lazy_fixture("no_install_no_error"),
        lazy_fixture("add_pkg"),
        lazy_fixture("runner_called_proc_error"),
        lazy_fixture("change_runner_version"),
        lazy_fixture("installation_error"),
        lazy_fixture("nonexistent_env_error"),
    ]
)
def fixture(request):
    return request.param


def test_main(fixture):
    cmd, pkgs, env, expected_diff, expected_error = fixture
    request = {
        "pangeo_forge_runner": {"cmd": cmd},
        "install": {"pkgs": pkgs, "env": env},
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
