from __future__ import annotations

from fmdl6b_core import *  # noqa: F401,F403
from fmdl6b_fetch import *  # noqa: F401,F403
from fmdl6b_sec_access import install_sec_request_adapter

install_sec_request_adapter()

from fmdl6b_release import *  # noqa: E402,F401,F403


if __name__ == "__main__":
    raise SystemExit(main())
