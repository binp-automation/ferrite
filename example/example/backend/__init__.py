from __future__ import annotations
from typing import Optional

import os
from pathlib import Path
from dataclasses import dataclass
from random import Random
import asyncio

import numpy as np
from numpy.typing import NDArray

from ferrite.utils.asyncio.task import with_background
from ferrite.utils.asyncio.net import TcpListener, MsgWriter, MsgReader
from ferrite.utils.epics.pv import Context as Ca, PvType
from ferrite.utils.epics.ioc import AsyncIoc
import ferrite.utils.epics.ca as ca

import example.protocol as proto
from example.protocol import InMsg, OutMsg
from example.backend.test import TestCase, WriteTestCase, ReadTestCase, dispatch, assert_eq, assert_array_eq

import logging

logger = logging.getLogger(__name__)


def random_i32(rng: Random) -> int:
    return rng.randrange(-(2**31), (2**31) - 1)


def random_i32_array(rng: np.random.Generator, max_size: int) -> NDArray[np.int32]:
    return rng.integers(
        -(2**31),
        (2**31) - 1,
        rng.integers(1, max_size + 1),
        dtype=np.int32,
    )


@dataclass
class RandomTest(TestCase):
    attempts: int = 32
    seed: int = 0xdeadbeef


@dataclass
class AiTest(RandomTest, WriteTestCase[proto.Ai]):

    async def run(self) -> None:
        record = await self.ca.connect("ai", PvType.FLOAT)

        async def test(x: int) -> None:
            assert int(await record.get()) != x

            async with record.monitor() as mon:
                await self.write_msg(InMsg.Ai(x))
                logger.debug(f"Msg sent: {x}")

                async for y in mon:
                    logger.debug(f"Pv get: {y}")
                    assert_eq(x, int(y))
                    break

        rng = Random(self.seed + 1)
        for _ in range(self.attempts):
            await test(random_i32(rng))


@dataclass
class AoTest(RandomTest, ReadTestCase[proto.Ao]):

    def _take_msg(self, msg: OutMsg) -> Optional[proto.Ao]:
        if isinstance(msg.variant, OutMsg.Ao):
            return msg.variant
        else:
            return None

    async def run(self) -> None:
        record = await self.ca.connect("ao", PvType.FLOAT)

        async def test(x: int) -> None:
            await record.put(float(x))
            logger.debug(f"Pv put: {x}")

            msg = await self.read_msg()
            y = msg.value
            logger.debug(f"Msg received: {y}")

            assert_eq(x, y)

        rng = Random(self.seed + 2)
        for _ in range(self.attempts):
            await test(random_i32(rng))


class BiTest(WriteTestCase[proto.Bi]):

    async def run(self) -> None:
        record = await self.ca.connect("bi", PvType.INT)

        async def test(x: bool) -> None:
            assert int(await record.get()) != x

            async with record.monitor() as mon:
                await self.write_msg(InMsg.Bi(int(x)))
                logger.debug(f"Msg sent: {int(x)}")

                async for y in mon:
                    logger.debug(f"Pv get: {y}")
                    assert_eq(int(x), y)
                    break

        await test(True)
        await test(False)


class BoTest(ReadTestCase[proto.Bo]):

    def _take_msg(self, msg: OutMsg) -> Optional[proto.Bo]:
        if isinstance(msg.variant, OutMsg.Bo):
            return msg.variant
        else:
            return None

    async def run(self) -> None:
        record = await self.ca.connect("bo", PvType.INT)

        async def test(x: bool) -> None:
            await record.put(int(x))
            logger.debug(f"Pv put: {int(x)}")

            msg = await self.read_msg()
            y = msg.value
            logger.debug(f"Msg received: {y}")

            assert_eq(int(x), y)

        await test(True)
        await test(False)


@dataclass
class AaiTest(RandomTest, WriteTestCase[proto.Aai]):

    async def run(self) -> None:
        record = await self.ca.connect("aai", PvType.ARRAY_INT)

        async def test(ax: NDArray[np.int32]) -> None:
            async with record.monitor() as mon:
                await self.write_msg(InMsg.Aai(ax))
                logger.debug(f"Msg sent:\n{ax}")

                async for ay in mon:
                    logger.debug(f"Pv get:\n{ay}")
                    assert_array_eq(ax, ay)
                    break

        rng = np.random.default_rng(self.seed + 5)
        for _ in range(self.attempts):
            await test(random_i32_array(rng, record.nelm))


@dataclass
class AaoTest(RandomTest, ReadTestCase[proto.Aao]):

    def _take_msg(self, msg: OutMsg) -> Optional[proto.Aao]:
        if isinstance(msg.variant, OutMsg.Aao):
            return msg.variant
        else:
            return None

    async def run(self) -> None:
        record = await self.ca.connect("aao", PvType.ARRAY_INT)

        async def test(ax: NDArray[np.int32]) -> None:
            await record.put(ax)
            logger.debug(f"Pv put:\n{ax}")

            msg = await self.read_msg()
            ay = msg.values
            logger.debug(f"Msg received:\n{ay}")

            assert_array_eq(ax, ay)

        rng = np.random.default_rng(self.seed + 6)
        for _ in range(self.attempts):
            await test(random_i32_array(rng, record.nelm))


@dataclass
class WaveformTest(RandomTest, WriteTestCase[proto.Waveform]):

    async def run(self) -> None:
        record = await self.ca.connect("waveform", PvType.ARRAY_INT)

        async def test(ax: NDArray[np.int32]) -> None:
            async with record.monitor() as mon:
                await self.write_msg(InMsg.Waveform(ax))
                logger.debug(f"Msg sent:\n{ax}")

                async for ay in mon:
                    logger.debug(f"Pv get:\n{ay}")
                    assert_array_eq(ax, ay)
                    break

        rng = np.random.default_rng(self.seed + 7)
        for _ in range(self.attempts):
            await test(random_i32_array(rng, record.nelm))


class MbbiDirectTest(WriteTestCase[proto.MbbiDirect]):

    async def run(self) -> None:

        nbits = 16
        records = list(await asyncio.gather(*[self.ca.connect(f"mbbiDirect.B{i:X}", PvType.INT) for i in range(nbits)]))

        async def test(x: int, i: int, b: bool) -> int:
            x = x | (1 << i) if b else x & ~(1 << i)

            async with records[i].monitor() as mon:
                await self.write_msg(InMsg.MbbiDirect(x))
                logger.debug(f"Msg sent: {x}")

                async for y in mon:
                    logger.debug(f"Pv[{i}] get: {y}")
                    assert_eq(int(b), y)
                    break

                return x

        x = 0
        for i in range(nbits):
            x = await test(x, i, True)
        for i in range(nbits):
            x = await test(x, i, False)


class MbboDirectTest(ReadTestCase[proto.MbboDirect]):

    def _take_msg(self, msg: OutMsg) -> Optional[proto.MbboDirect]:
        if isinstance(msg.variant, OutMsg.MbboDirect):
            return msg.variant
        else:
            return None

    async def run(self) -> None:

        nbits = 16
        records = list(await asyncio.gather(*[self.ca.connect(f"mbboDirect.B{i:X}", PvType.INT) for i in range(nbits)]))

        async def test(x: int, i: int, b: bool) -> int:
            await records[i].put(int(b))
            logger.debug(f"Pv[{i}] put: {int(b)}")
            x = x | (1 << i) if b else x & ~(1 << i)

            msg = await self.read_msg()
            y = msg.value
            logger.debug(f"Msg received: {y}")
            assert_eq(x, y)

            return x

        x = 0
        for i in range(nbits):
            x = await test(x, i, True)
        for i in range(nbits):
            x = await test(x, i, False)


async def _async_test(epics_base_dir: Path, ioc_dir: Path, arch: str) -> None:
    async with TcpListener("127.0.0.1", 4884) as lis:
        async with AsyncIoc(epics_base_dir, ioc_dir, arch) as ioc:
            logger.info("IOC started")
            async for stream in lis:
                break
            writer = MsgWriter(InMsg, stream.writer)
            reader = MsgReader(OutMsg, stream.reader, 260)
            logger.info("Socket connected")

            ca = Ca()

            tests = [
                AiTest(ca, writer),
                AoTest(ca),
                BiTest(ca, writer),
                BoTest(ca),
                AaiTest(ca, writer),
                AaoTest(ca),
                WaveformTest(ca, writer),
                MbbiDirectTest(ca, writer),
                MbboDirectTest(ca),
            ]

            async def dispatcher() -> None:
                while True:
                    dispatch(tests, await reader.read_msg())

            await with_background(asyncio.gather(*[test.run() for test in tests]), dispatcher())

            ioc.stop()


def test(epics_base_dir: Path, ioc_dir: Path, arch: str) -> None:
    os.environ.update(ca.local_env())
    with ca.Repeater(epics_base_dir, arch):
        asyncio.run(_async_test(epics_base_dir, ioc_dir, arch))
