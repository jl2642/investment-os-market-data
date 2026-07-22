from __future__ import annotations

from fmdl6b_core import *  # noqa: F401,F403
from fmdl6b_fetch import *  # noqa: F401,F403
from fmdl6b_sec_access import install_sec_request_adapter

install_sec_request_adapter()

import fmdl6b_release as _release  # noqa: E402
from fmdl6b_access_policy import install_controlled_access_policy  # noqa: E402

install_controlled_access_policy(_release)

from fmdl6b_release import *  # noqa: E402,F401,F403
from fmdl6b_access_policy import controlled_normalize_observations as normalize_observations  # noqa: E402,F401


if __name__ == "__main__":
    raise SystemExit(main())
