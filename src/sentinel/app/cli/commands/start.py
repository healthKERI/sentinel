# -*- encoding: utf-8 -*-
"""
KERI
watopnet.app.cli module

Watcher command line interface
"""

import argparse
import asyncio
import logging
import signal

from keri import __version__
from keri import help
from sentinel.app import sentineling

d = "Runs healthKERI Sentinel"
parser = argparse.ArgumentParser(description=d)
parser.set_defaults(handler=lambda args: launch(args))
parser.add_argument(
    "--name", "-n", help="Name of the database environment", required=True
)
parser.add_argument(
    "--alias",
    "-a",
    help="human readable alias for the new identifier prefix",
    required=True,
)
parser.add_argument(
    "--passcode",
    "-p",
    help="22 character encryption passcode for keystore (is not saved)",
    dest="bran",
    default=None,
)  # passcode => bran
parser.add_argument(
    "--base",
    "-b",
    help="additional optional prefix to file location of KERI keystore",
    required=False,
    default="",
)
parser.add_argument(
    "-l",
    "--local",
    action="store_true",
    help="Run local watcher services instead of using healthKERI Watcher Network",
)
parser.add_argument(
    "-u",
    "--uxd",
    action="store_true",
    help="Listen on Unix Domain Sockets interface instead of TCP",
)
parser.add_argument(
    "--loglevel",
    action="store",
    required=False,
    default="INFO",
    help="Set log level to DEBUG | INFO | WARNING | ERROR | CRITICAL. Default is INFO",
)
parser.add_argument(
    "--logfile",
    action="store",
    required=False,
    default=None,
    help="path of the log file. If not defined, logs will not be written to the file.",
)
parser.add_argument(
    "--export-dir",
    "-e",
    action="store",
    required=False,
    default="/usr/local/sentinel",
    help="Directory for exporting CESR files. Default is /usr/local/sentinel.",
)
parser.add_argument(
    "--registrar-url",
    "-r",
    action="store",
    required=False,
    default=None,
    help="URL for Registrar if available.",
)
parser.add_argument(
    "-V",
    "--version",
    action="version",
    version=__version__,
    help="Prints out version of script runner.",
)

FORMAT = "%(asctime)s [sentinel] %(levelname)-8s %(message)s"


def launch(args):
    help.ogler.level = logging.getLevelName(args.loglevel)
    base_formatter = logging.Formatter(FORMAT)  # basic format
    base_formatter.default_msec_format = None
    help.ogler.baseConsoleHandler.setFormatter(base_formatter)
    help.ogler.level = logging.getLevelName(args.loglevel)

    if args.logfile is not None:
        help.ogler.headDirPath = args.logfile
        help.ogler.reopen(name="sentinel", temp=False, clear=True)

    logger = help.ogler.getLogger()

    logger.info("******* Starting local Sentinel sidecar")

    run_sentinel(args)

    logger.info("******* Ended local Sentinel sidecar")


def run_sentinel(args):
    """
    Setup and run sentinel services using asyncio.
    """
    asyncio.run(async_run_sentinel(args))


async def async_run_sentinel(args):
    """
    Async runner for sentinel services.

    Starts all services returned from setup_hk/setup_local and keeps the asyncio loop
    running until all tasks are complete or interrupted.
    """
    logger = help.ogler.getLogger()

    # Setup services
    if args.local:
        services = await sentineling.setup_local(
            name=args.name,
            alias=args.alias,
            base=args.base,
            bran=args.bran,
            uxd=args.uxd,
            export_dir=args.export_dir,
            registrar_url=args.registrar_url,
        )
    else:
        services = await sentineling.setup_hk(
            name=args.name,
            alias=args.alias,
            base=args.base,
            bran=args.bran,
            uxd=args.uxd,
            export_dir=args.export_dir,
            registrar_url=args.registrar_url,
        )

    # Start all services and collect their tasks
    tasks = []
    for service in services:
        if hasattr(service, "start"):
            task = service.start()

            if isinstance(task, list):
                tasks.extend(task)
            else:
                tasks.append(task)
                logger.info(f"Started service: {service.__class__.__name__}")

        else:
            logger.warning(
                f"Service {service.__class__.__name__} does not have a start() method"
            )

    if not tasks:
        logger.error("No tasks were started")
        return

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        # Wait for shutdown signal or all tasks to complete
        done, pending = await asyncio.wait(
            tasks + [asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # If shutdown was requested, stop all services
        if shutdown_event.is_set():
            logger.info("Stopping all services...")
            for service in services:
                if hasattr(service, "stop"):
                    service.stop()
                    logger.info(f"Stopped service: {service.__class__.__name__}")

            # Wait for all tasks to complete with a timeout
            if pending:
                await asyncio.wait(pending, timeout=5.0)

    except Exception as e:
        logger.exception(f"Error in async_run_sentinel: {e}")
        # Stop all services on error
        for service in services:
            if hasattr(service, "stop"):
                await service.stop()
        raise
    finally:
        # Cancel any remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
