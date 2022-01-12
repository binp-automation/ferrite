from __future__ import annotations
from typing import List, Optional

import shutil
from pathlib import Path, PurePosixPath
import logging

from ferrite.utils.run import capture, run
from ferrite.components.base import Artifact, Task, Context
from ferrite.components.toolchains import Target, Toolchain, HostToolchain


def epics_host_arch(epics_base_dir: Path) -> str:
    return capture([
        "perl",
        epics_base_dir / "src" / "tools" / "EpicsHostArch.pl",
    ])


def epics_arch_by_target(target: Target) -> str:
    if target.api == "linux":
        if target.isa == "arm":
            return "linux-arm"
        elif target.isa == "aarch64":
            return "linux-aarch64"
    # TODO: Add some other archs
    raise Exception(f"Unknown target for EPICS: {str(target)}")


def epics_arch(epics_base_dir: Path, toolchain: Toolchain) -> str:
    if isinstance(toolchain, HostToolchain):
        return epics_host_arch(epics_base_dir)
    else:
        return epics_arch_by_target(toolchain.target)


class EpicsBuildTask(Task):

    def __init__(
        self,
        src_dir: Path,
        build_dir: Path,
        install_dir: Path,
        clean: bool = False,
        mk_target: Optional[str] = None,
        deps: List[Task] = [],
        cached: bool = False,
    ):
        super().__init__()
        self.src_dir = src_dir
        self.build_dir = build_dir
        self.install_dir = install_dir
        self.clean = clean
        self.mk_target = mk_target
        self.deps = deps
        self.cached = cached

    def _configure(self) -> None:
        raise NotImplementedError()

    def _install(self) -> None:
        raise NotImplementedError()

    def run(self, ctx: Context) -> None:
        if self.clean:
            shutil.rmtree(self.build_dir, ignore_errors=True)
            shutil.rmtree(self.install_dir, ignore_errors=True)

        shutil.copytree(self.src_dir, self.build_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))

        logging.info(f"Configure {self.build_dir}")
        self._configure()

        logging.info(f"Build {self.build_dir}")
        run([
            "make",
            "--jobs",
            *([self.mk_target] if self.mk_target is not None else []),
        ],
            cwd=self.build_dir,
            quiet=ctx.capture)

        logging.info(f"Install {self.build_dir} to {self.install_dir}")
        self.install_dir.mkdir(exist_ok=True)
        self._install()

    def dependencies(self) -> List[Task]:
        return self.deps

    def artifacts(self) -> List[Artifact]:
        return [
            Artifact(self.build_dir, cached=self.cached),
            Artifact(self.install_dir, cached=self.cached),
        ]


class EpicsDeployTask(Task):

    def __init__(
        self,
        install_dir: Path,
        deploy_dir: PurePosixPath,
        deps: List[Task] = [],
    ):
        super().__init__()
        self.install_dir = install_dir
        self.deploy_dir = deploy_dir
        self.deps = deps

    def _pre(self, ctx: Context) -> None:
        pass

    def _post(self, ctx: Context) -> None:
        pass

    def run(self, ctx: Context) -> None:
        assert ctx.device is not None
        self._pre(ctx)
        logging.info(f"Deploy {self.install_dir} to {ctx.device.name()}:{self.deploy_dir}")
        ctx.device.store(
            self.install_dir,
            self.deploy_dir,
            recursive=True,
        )
        self._post(ctx)

    def dependencies(self) -> List[Task]:
        return self.deps
