import json
import logging
import subprocess
import sys
import tempfile
from typing import List, Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator

app = FastAPI()

log = logging.getLogger()
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
log.setLevel(logging.DEBUG)
log.addHandler(handler)


class PangeoForgeRunner(BaseModel):
    cmd: List[str] = Field(
        ...,
        description="""
        Command to pass to the `pangeo-forge-runner` CLI. The command should be valid
        for the version of `pangeo-forge-runner` known to exist in the container.
        (This can be overided via the `install` field of the request Payload.)
        """,
    )
    config: dict = Field(
        default_factory=dict,
        description="""
        JSON traitlets config for `pangeo-forge-runner`. See `pangeo-forge-runner`
        docs for spec. Fields given here can be alternatively be passed as CLI options,
        but separating `cmd` and `config` fields may provide a useful cognitive distinction:
        the former typically vary more per-job than does the latter.
        """,
    )


class Install(BaseModel):
    pkgs: List[str] = Field(
        ...,
        description="""
        A list of extra dependencies to install prior to calling `pangeo-forge-runner`.
        (Can include `pangeo-forge-runner` itself!) List members can be strings of any
        format recognized as valid arguments to `pip install`.
        """,
    )
    env: str = Field(
        "notebook",
        description="""
        The name of the conda environment in which to pip install the `pkgs` list.
        """,
    )

    @validator("env")
    def env_must_exist(cls, v):
        conda_env_list = subprocess.check_output("conda env list --json".split())
        envs = [e.split("/")[-1] for e in json.loads(conda_env_list)["envs"]]
        if v not in envs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{v}' is not a conda env name on this system. Valid names: {envs}",
            )
        return v


class Payload(BaseModel):
    pangeo_forge_runner: PangeoForgeRunner = Field(
        ...,
        description="""
        A command and config for `pangeo-forge-runner`.
        """,
    )
    install: Optional[Install] = Field(
        None,
        description="""
        Optionally, use this field to pass a list of extra dependencies to install
        prior to calling `pangeo-forge-runner`.
        """,
    )


class Package(BaseModel):
    name: str = Field(..., description="The name of this package.")
    version: str = Field(..., description="The current version of this package.")


class AddedPackage(Package):
    pass


class ChangedPackage(Package):
    prior_version: str = Field(
        ...,
        description="""
        The version of this package prior to being changed by an install request.
        """,
    )


class CondaDiff(BaseModel):
    added: Optional[List[AddedPackage]] = Field(
        None,
        description="""
        Packages added by the install request, which were not present in the
        base image. Optional because the request might only ask to change package
        versions, and not add any new packages.
        """,
    )
    changed: Optional[List[ChangedPackage]] = Field(
        None,
        description="""
        Packages whose versions have been changed as a result of the install request.
        Optional because the request may only ask to add new packages, and not change
        the versions of any existing packages.
        """,
    )


class InstallResult(BaseModel):
    diff: CondaDiff = Field(
        None,
        description="""
        A record of changes made to the environment by the install request.
        """,
    )


class Response(BaseModel):
    install_result: Optional[InstallResult] = Field(
        None,
        description="""
        If an `install` array is passed as part of the request Payload, the results
        of resolving those dependencies is relayed back to the invoker here. Optional
        because if no `install` array is given in the request, this is left empty.
        """,
    )
    pangeo_forge_runner_result: Optional[str] = Field(
        None,
        description="""
        The result of the `pangeo-forge-runner` call as plain text, which the invoker
        can parse as they please. Optional because if an `install` array is given
        in the request, and there is an error attempting to resolve those additional
        dependencies, then we never make it to calling `pangeo-forge-runner`, and this
        field would be left empty in the response.
        """,
    )


def conda_list_json(env_name: str) -> dict:
    verbose_listing = json.loads(
        subprocess.check_output(f"conda list -n {env_name} --json".split())
    )
    return {p["name"]: p["version"] for p in verbose_listing}


@app.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=Response)
async def main(payload: Payload):
    log.info(f"Received {payload = }")
    response = {}
    if payload.install:
        log.info("Extra installs requested...")
        before = conda_list_json(payload.install.env)
        pip_cmd = (
            f"mamba run -n {payload.install.env} pip install -U".split()
            + payload.install.pkgs
        )
        log.debug(f"Running {pip_cmd = }")
        pip_proc = subprocess.run(pip_cmd, capture_output=True, text=True)
        if pip_proc.returncode != 0:
            # our installations failed, so record the error and bail early
            log.error(f"Installs failed with {pip_proc.stderr = }")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=pip_proc.stderr,
            )
        # our installations succeeded! so record the altered env and move on
        after = conda_list_json(payload.install.env)
        diff = dict(
            added=[
                {"name": name, "version": version}
                for name, version in after.items()
                if name not in before
            ],
            changed=[
                {"name": name, "version": new_version, "prior_version": before[name]}
                for name, new_version in after.items()
                if name in before and new_version != before[name]
            ],
        )
        log.debug(f"{payload.install.env = }; {diff = }")
        response["install_result"] = {"diff": diff}

    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        json.dump(payload.pangeo_forge_runner.config, f)
        f.flush()
        runner_cmd = (
            ["pangeo-forge-runner"] + payload.pangeo_forge_runner.cmd + [f"-f={f.name}"]
        )
        runner_proc = subprocess.run(runner_cmd, capture_output=True, text=True)

    if runner_proc.returncode != 0:
        log.error(f"Runner call failed with {runner_proc.stderr = }")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=runner_proc.stderr,
        )
    log.info("Sending response...")
    response |= {"pangeo_forge_runner_result": runner_proc.stdout}
    log.debug(f"{response = }")
    return response
