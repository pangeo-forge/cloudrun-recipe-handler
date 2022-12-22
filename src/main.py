import json
import subprocess
import tempfile
from typing import List, Optional

from fastapi import FastAPI, status
from pydantic import BaseModel, Field

app = FastAPI()


class PangeoForgeRunner(BaseModel):
    cmd: List[str] = Field(
        ...,
        description="""
        Command to pass to the `pangeo-forge-runner` CLI. The command should be valid
        for the version of `pangeo-forge-runner` known to exist in the container.
        (This can be overided via the `install` field of the request Payload.)
        """
    )
    config: dict = Field(
        default_factory=dict,
        description="""
        JSON traitlets config for `pangeo-forge-runner`. See `pangeo-forge-runner`
        docs for spec. Fields given here can be alternatively be passed as CLI options,
        but separating `cmd` and `config` fields may provide a useful cognitive distinction:
        the former typically varys more per-job than does the latter.
        """
    )


class Install(BaseModel):
    pkgs: List[str] = Field(
        ...,
        description="""
        A list of extra dependencies to install prior to calling `pangeo-forge-runner`.
        (Can include `pangeo-forge-runner` itself!) List members can be strings of any
        format recognized as valid arguments to `pip install`.
        """
    )
    env: str = Field(
        "notebook",
        description="""
        The name of the conda environment in which to pip install the `pkgs` list.
        """
    )


class Payload(BaseModel):
    pangeo_forge_runner: PangeoForgeRunner = Field(
        ...,
        description="""
        A command and config for `pangeo-forge-runner`.
        """
    ) 
    install: Optional[Install] = Field(
        None,
        description="""
        Optionally, use this field to pass a list of extra dependencies to install
        prior to calling `pangeo-forge-runner`.
        """
    )


class InstallResult(BaseModel):
    before: List[dict] = Field(
        ...,
        description="""
        The result of calling `conda list --json` before any additional
        dependencies are resolved via pip.
        """
    )
    after: Optional[List[dict]] = Field(
        None,
        description=""""
        The result of `conda list --json` after additional dependencies are installed
        via pip. Optional because if the call to `pip install` fails, this is not
        included in the response.
        """
    )
    stderr: Optional[str] = Field(
        None,
        description="""
        If the call to `pip install` fails, this field relays the Traceback.
        Optional because if the `pip install` succeeds, this is left empty.
        """
    )


class Response(BaseModel):
    install_result: Optional[InstallResult] = Field(
        None,
        description="""
        If an `install` array is passed as part of the request Payload, the results
        of resolving those dependencies is relayed back to the invoker here. Optional
        because if no `install` array is given in the request, this is left empty. 
        """
    )
    pangeo_forge_runner_result: Optional[str] = Field(
        None,
        description="""
        The result of the `pangeo-forge-runner` call as plain text, which the invoker
        can parse as they please. Optional because if an `install` array is given
        in the request, and there is an error attempting to resolve those additional
        dependencies, then we never make it to calling `pangeo-forge-runner`, and this
        field would be left empty in the response.
        """
    )


def conda_list_json(env_name):
    return json.loads(
        subprocess.check_output(f"conda list -n {env_name} --json".split())
    )


@app.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=Response)
async def main(payload: Payload):
    response = {}
    if payload.install:
        response |= {
            "install_result": {"before": conda_list_json(payload.install.env)}
        }
        cmd = (
            f"mamba run -n {payload.install.env} pip install -U".split()
            + payload.install.pkgs
        )
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            # our installations failed, so record the error and bail early
            response["install_result"] |= {"stderr": proc.stderr}
            return response
        # our installations succeeded! so record the altered env and move on
        response["install_result"] |= {"after": conda_list_json(payload.install.env)}

    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        json.dump(payload.pangeo_forge_runner.config, f)
        f.flush()
        pangeo_forge_runner_result = subprocess.check_output(
            ["pangeo-forge-runner"]
            + payload.pangeo_forge_runner.cmd
            + [f"-f={f.name}"]
        )
    
    return response | {"pangeo_forge_runner_result": pangeo_forge_runner_result}
