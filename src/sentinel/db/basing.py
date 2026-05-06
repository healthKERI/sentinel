# -*- encoding: utf-8 -*-
"""
locksmith.ui.vault.healthKERI.db.basing module

Sentinel-specific  database (SentinelBaser).

"""
from keri import core
from keri.db import dbing, subing


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

        super(SentinelBaser, self).__init__(name=name, headDirPath=headDirPath, reopen=reopen, **kwa)

    def reopen(self, **kwa):
        super(SentinelBaser, self).reopen(**kwa)

        self.watched_poll = subing.CesrSuber(
            db=self,
            subkey='watched.',
            klas=core.Dater
        )

        return self.env