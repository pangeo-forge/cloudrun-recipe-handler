import json
import subprocess
from typing import List, Optional

from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI()

# we assume we're always working on top of a pangeo/forge image tag,
# in which the default env linked to PYTHONPATH is named "notebook"
CONDA_ENV = "notebook"


class Payload(BaseModel):
    pangeo_forge_runner_cmd: List[str]
    pip_install: Optional[List[str]] = None


class PipResult(BaseModel):
    before: List[dict]
    after: Optional[List[dict]] = None
    stderr: Optional[str] = None


class Response(BaseModel):
    pip_result: Optional[PipResult] = None
    pangeo_forge_runner_result: Optional[str] = None


def conda_list_json():
    return json.loads(
        subprocess.check_output(f"conda list -n {CONDA_ENV} --json".split())
    )


@app.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=Response)
async def main(payload: Payload):
    response = {}
    if payload.pip_install:
        response |= {"pip_result": {"before": conda_list_json()}}
        pip_proc = subprocess.run(
            f"mamba run -n {CONDA_ENV} pip install -U".split() + payload.pip_install,
            capture_output=True,
            text=True,
        )
        if pip_proc.returncode != 0:
            # our pip installations failed, so record the error and bail early
            response["pip_result"] |= {"stderr": pip_proc.stderr}
            return response
        # our pip installations succeeded! so record the altered env and move on
        response["pip_result"] |= {"after": conda_list_json()}

    pangeo_forge_runner_result = subprocess.check_output(
        ["pangeo-forge-runner"] + payload.pangeo_forge_runner_cmd,
    )
    return response | {"pangeo_forge_runner_result": pangeo_forge_runner_result}
