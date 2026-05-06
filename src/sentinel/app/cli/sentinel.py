# -*- encoding: utf-8 -*-
"""
kept.app.cli module

"""

import multicommand
from keri import help

from sentinel.app.cli import commands

logger = help.ogler.getLogger()


def main():
    parser = multicommand.create_parser(commands)
    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        return -1

    try:
        args.handler(args)

    except Exception as ex:
        import os

        if os.getenv("DEBUG_SENTINEL"):
            import traceback

            traceback.print_exc()
        else:
            print(f"ERR: {ex}")
        return -1


if __name__ == "__main__":
    main()
