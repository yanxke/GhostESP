"""Decode one complete `sd read <path> --base64` serial transfer log."""

import argparse
import base64
from pathlib import Path


def decode_capture(lines, output):
    started = False
    encoded = False
    expected = None
    requested = None
    offset = None
    received = 0
    ended = False
    for raw in lines:
        # Allow console timestamps/prompt prefixes before protocol messages.
        marker = raw.find("SD:")
        if marker < 0:
            continue
        line = raw[marker:].strip()
        if line.startswith("SD:ERR:"):
            raise ValueError(line)
        if line.startswith("SD:READ:BEGIN:"):
            if started:
                raise ValueError("Log contains multiple or restarted transfers")
            started = True
        elif started and line.startswith("SD:READ:SIZE:"):
            expected = int(line.removeprefix("SD:READ:SIZE:"))
        elif started and line.startswith("SD:READ:LENGTH:"):
            requested = int(line.removeprefix("SD:READ:LENGTH:"))
        elif started and line.startswith("SD:READ:OFFSET:"):
            offset = int(line.removeprefix("SD:READ:OFFSET:"))
        elif started and line == "SD:READ:ENCODING:base64":
            encoded = True
        elif started and line.startswith("SD:READ:DATA:"):
            if not encoded or ended:
                raise ValueError("Unexpected data outside a base64 transfer")
            data = base64.b64decode(line.removeprefix("SD:READ:DATA:"), validate=True)
            output.write(data)
            received += len(data)
        elif started and line.startswith("SD:READ:END:bytes="):
            reported = int(line.removeprefix("SD:READ:END:bytes="))
            if not encoded or offset != 0 or not (reported == received == expected == requested):
                raise ValueError("Incomplete transfer or byte count mismatch")
            ended = True
        elif started and line == "SD:OK" and ended:
            return received
    raise ValueError("No complete, successful base64 transfer found")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    # Keep failed downloads visibly partial and never overwrite an existing file.
    partial = args.output.with_name(args.output.name + ".part")
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    try:
        with args.log.open(encoding="utf-8-sig", errors="replace") as lines, partial.open("xb") as output:
            count = decode_capture(lines, output)
        # Exclusive create also protects against an output appearing during decode.
        with args.output.open("xb") as output, partial.open("rb") as source:
            import shutil
            shutil.copyfileobj(source, output)
        partial.unlink()
    except (OSError, ValueError) as error:
        parser.exit(1, f"Download decode failed: {error}\nPartial data, if any: {partial}\n")
    print(f"Saved {count} bytes to {args.output}")


if __name__ == "__main__":
    main()
