from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from automation.forward_validation.market_outcomes import update_checkpoint


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--checkpoint",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--now")
    args=p.parse_args()
    checkpoint=json.loads(Path(args.checkpoint).read_text(encoding="utf-8"))
    now=(
        datetime.fromisoformat(args.now.replace("Z","+00:00"))
        if args.now else datetime.now(tz=ZoneInfo("UTC"))
    )
    updated,reads=update_checkpoint(checkpoint,now=now,allow_outcome_reads=False)
    if reads!=0:
        raise RuntimeError("P45_ENTRY_BINDING_READ_OUTCOME")
    if not updated.get("entry_binding_complete"):
        raise RuntimeError("P45_ENTRY_BINDING_INCOMPLETE")
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(
        json.dumps(updated,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "checkpoint_id":updated["checkpoint_id"],
        "entry_binding_complete":True,
        "outcome_reads":0,
        "orders":0,
        "trade_authority":"NONE",
    },ensure_ascii=False))

if __name__=="__main__":
    main()
