#!/usr/bin/env python3
"""
KERI Analyzer Example - Standalone Sentinel Framework Application with KERI Integration

This example demonstrates using the framework WITH KERI infrastructure.
It accesses the Habery instance to perform deep inspection of KEL events.

Usage:
    # Terminal 1: Start sentinel with export directory
    sentinel start -n mydb -a myalias --export-dir /tmp/sentinel-export

    # Terminal 2: Run this application (will create its own KERI database)
    python examples/keri_analyzer.py
"""
import requests
from keri.app import habbing

from sentinel.framework import EventHandler, register_handler, run, KELEvent
from sentinel.framework.watching import LocalWatcherConnector


class KERIAnalyzer(EventHandler):
    """Analyze KEL events using KERI infrastructure"""

    async def on_kel(self, event: KELEvent):
        print(f"\n=== Analyzing KEL: {event.aid} ===")
        print(f"File: {event.filepath}")
        print(f"Size: {len(event.data)} bytes")
        print(f"Time: {event.timestamp}")

        # Access KERI infrastructure if provided
        if event.hby:
            print("\nKERI Analysis:")
            kever = event.hby.kevers.get(event.aid)
            if kever:
                print(f"  Sequence: {kever.sner.num}")
                print(f"  Witnesses: {len(kever.wits)}")
                print(f"  Witness list: {kever.wits}")
                print(f"  Keys: {', '.join([verfer.qb64 for verfer in kever.verfers])}")
            else:
                print(f"  AID {event.aid} not found in local database")
                print(f"  (May need to sync from network)")
        else:
            print("\nKERI infrastructure not available")
            print("Run with name= parameter to enable KERI analysis")

        print("=" * 50 + "\n")


if __name__ == "__main__":
    print("Starting KERI Analyzer...")
    print("This will create a KERI database at /tmp/keri-analyzer")
    print("Watching /tmp/sentinel-export for KEL changes")
    print("Press Ctrl+C to stop\n")

    hby = habbing.Habery(name="analyzer_db", base="keri-analyzer", bran=None)
    if (hab := hby.habByName(hby.name)) is None:
        hab = hby.makeHab(name=hby.name, transferable=True)
    response = requests.get("http://127.0.0.1:5643/oobi/EOVB5igm-Qpcr1aRRNcCEeIMELys8USWsYNBwqOT0LWI/witness")
    hby.psr.parse(ims=response.content)

    local_watcher_connector = LocalWatcherConnector(hby=hby, hab=hab,
                                                    watcher="ENcoAna5CwrqJW1wXwitGag5h3ZFoIVPocHL8b9nIelg")
    local_watcher_connector.watch("EOVB5igm-Qpcr1aRRNcCEeIMELys8USWsYNBwqOT0LWI",
                                  "http://127.0.0.1:5643/oobi/EOVB5igm-Qpcr1aRRNcCEeIMELys8USWsYNBwqOT0LWI/witness")

    # Register the handler
    register_handler(KERIAnalyzer())

    # Run the framework WITH KERI infrastructure
    # This will initialize a Habery instance and pass it to handlers
    run(
        export_dir="/tmp/sentinel-export",
        poll_interval=2.0,
        name="analyzer_db",  # Framework will initialize Habery with this name
        base="keri-analyzer",  # Database location
        hby=hby
    )
