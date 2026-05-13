# -*- encoding: utf-8 -*-
"""
locksmith.ui.vault.healthKERI.db.basing module

Sentinel-specific  database (SentinelBaser).

"""
from collections import namedtuple
from dataclasses import dataclass

from keri import core
from keri.db import dbing, subing, koming

Stateage = namedtuple("Stateage", 'even ahead behind duplicitous unresponsive')
States = Stateage(even="even", ahead="ahead", behind="behind", duplicitous="duplicitous", unresponsive="unresponsive")


class WitnessState:
    """
    State of an AID according to a particular
    """
    wit: str
    state: Stateage
    sn: int
    dig: str


@dataclass
class WitnessQuery:
    """
        Witness query record
    """
    watcher_id: str
    aid: str
    wit: str
    query_timestamp: str
    response_received: bool
    state: str
    keystate: str = None
    sn: int = None
    dig: str = None
    error: str = None

class SentinelBaser(dbing.LMDBer):
    """Plugin-owned database for healthKERI state.

    Manages healthKERI accounts, teams, and witness provisioning state
    in a separate LMDB from the core LocksmithBaser.
    """

    TailDirPath = "keri/hk"
    AltTailDirPath = ".keri/hk"
    TempPrefix = "hk"

    def __init__(self, name="sentinel", headDirPath=None, reopen=True, **kwa):
        self.watched_poll = None
        self.witq = None

        super(SentinelBaser, self).__init__(
            name=name, headDirPath=headDirPath, reopen=reopen, **kwa
        )

    def reopen(self, **kwa):
        super(SentinelBaser, self).reopen(**kwa)

        # Most recent watched events
        self.watched_poll = subing.CesrSuber(db=self, subkey="watched.", klas=core.Dater)

        # Most recent witness query records
        self.witq = koming.Komer(db=self, subkey='witq.', schema=WitnessQuery)

        return self.env
