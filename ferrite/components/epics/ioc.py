from __future__ import annotations
from typing import List, Any

import shutil
import re
import time
from pathlib import Path, PurePosixPath

from ferrite.utils.path import TargetPath
from ferrite.utils.files import substitute
from ferrite.components.base import task, Task, Context
from ferrite.components.compiler import GccCross
from ferrite.components.epics.base import EpicsProject, EpicsProjectDeploy
from ferrite.components.epics.epics_base import AbstractEpicsBase, EpicsBaseCross, EpicsBaseHost
from ferrite.utils.epics.ioc_remote import IocRemoteRunner


class AbstractIoc(EpicsProject):

    def __init__(self, ioc_dir: Path, target_dir: TargetPath, epics_base: AbstractEpicsBase, **kws: Any):
        super().__init__(ioc_dir, target_dir, epics_base.cc)
        self.epics_base = epics_base

    @property
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def arch(self) -> str:
        return self.epics_base.arch

    def _configure(self, ctx: Context) -> None:
        build_path = ctx.target_path / self.build_dir
        install_path = ctx.target_path / self.install_dir
        substitute(
            [("^\\s*#*(\\s*EPICS_BASE\\s*=).*$", f"\\1 {ctx.target_path / self.epics_base.build_dir}")],
            build_path / "configure/RELEASE",
        )
        substitute(
            [("^\\s*#*(\\s*INSTALL_LOCATION\\s*=).*$", f"\\1 {install_path}")],
            build_path / "configure/CONFIG_SITE",
        )
        install_path.mkdir(exist_ok=True)

    @task
    def build(self, ctx: Context) -> None:
        self.epics_base.build(ctx)
        super().build(ctx, clean=True)

    def _install(self, ctx: Context) -> None:
        shutil.rmtree(
            ctx.target_path / self.install_dir / "iocBoot",
            ignore_errors=True,
        )
        shutil.copytree(
            ctx.target_path / self.build_dir / "iocBoot",
            ctx.target_path / self.install_dir / "iocBoot",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("Makefile"),
        )

    @task
    def run(self, ctx: Context) -> None:
        raise NotImplementedError()


class IocHost(AbstractIoc):

    def __init__(self, ioc_dir: Path, target_dir: TargetPath, epics_base: EpicsBaseHost):
        super().__init__(ioc_dir, target_dir, epics_base)


class IocCross(AbstractIoc, EpicsProjectDeploy):

    def __init__(self, ioc_dir: Path, target_dir: TargetPath, epics_base: EpicsBaseCross):
        super().__init__(ioc_dir, target_dir, epics_base, deploy_path=PurePosixPath("/opt/ioc"))
        self.epics_deploy_path = epics_base.deploy_path

    def _configure(self, ctx: Context) -> None:
        super()._configure(ctx)
        substitute(
            [("^\\s*#*(\\s*CROSS_COMPILER_TARGET_ARCHS\\s*=).*$", f"\\1 {self.arch}")],
            ctx.target_path / self.build_dir / "configure/CONFIG_SITE",
        )

    def _post_deploy(self, ctx: Context) -> None:
        assert ctx.device is not None
        boot_dir = ctx.target_path / self.install_dir / "iocBoot"
        for ioc_name in [path.name for path in boot_dir.iterdir()]:
            ioc_dirs = boot_dir / ioc_name
            if not ioc_dirs.is_dir():
                continue
            env_path = ioc_dirs / "envPaths"
            if not env_path.is_file():
                continue
            with open(env_path, "r") as f:
                text = f.read()
            text = re.sub(r'(epicsEnvSet\("TOP",)[^\n]+', f'\\1"{self.deploy_path}")', text)
            text = re.sub(r'(epicsEnvSet\("EPICS_BASE",)[^\n]+', f'\\1"{self.epics_deploy_path}")', text)
            ctx.device.store_mem(text, self.deploy_path / "iocBoot" / ioc_name / "envPaths")

    @task
    def deploy(self, ctx: Context) -> None:
        assert isinstance(self.epics_base, EpicsProjectDeploy)
        self.epics_base.deploy(ctx)
        super().deploy(ctx)

    @task
    def run(self, ctx: Context) -> None:
        self.deploy(ctx)

        assert ctx.device is not None
        assert isinstance(self.epics_base, EpicsBaseCross)
        with IocRemoteRunner(
            ctx.device,
            self.name,
            self.deploy_path,
            self.epics_base.deploy_path,
            self.epics_base.arch,
        ):
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
