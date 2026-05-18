#!/usr/bin/env python3
"""List available macOS TTS voices.

Usage:
    python list_voices.py              # print to stdout
    python list_voices.py voices.txt   # write to file
"""

import subprocess
import sys


def main():
    try:
        result = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        print("Error: 'say' command not found. This script requires macOS.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: 'say -v ?' timed out.", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"Error: 'say -v ?' exited with code {result.returncode}", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) > 1:
        output_path = sys.argv[1]
        with open(output_path, "w") as f:
            f.write(result.stdout)
        print(f"Wrote {len(result.stdout)} bytes to {output_path}")
    else:
        print(result.stdout, end="")


if __name__ == "__main__":
    main()
