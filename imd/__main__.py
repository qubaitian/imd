"""Start or restart the local IMD service."""

import argparse

from imd.service import restart_service


def main():
    parser = argparse.ArgumentParser(
        description="Start or restart the local Markdown editor in the background."
    )
    parser.parse_args()
    try:
        restart_service()
        print("IMD service ready at http://localhost:8000.")
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
