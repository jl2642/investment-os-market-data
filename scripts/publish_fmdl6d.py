#!/usr/bin/env python3
from fmdl6d_minimal_chain import main

if __name__ == "__main__":
    raise SystemExit(main(["publish", *__import__("sys").argv[1:]]))
