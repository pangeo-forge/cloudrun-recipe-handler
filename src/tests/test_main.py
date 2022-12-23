from ..main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_main():
    request = {
        "pangeo_forge_runner": {"cmd": ["--help"]},
        "install": {"pkgs": ["pangeo-forge-runner==0.7.1"], "env": "cloudrun"},
    }
    response = client.post("/", json=request)
    assert response.status_code == 202
    assert response.json()["install_result"] == {
        "diff": {"added": [], "changed": []}, "stderr": None
    }
    assert response.json()["pangeo_forge_runner_result"].startswith(
        "This is an application.\n\n"
    )
