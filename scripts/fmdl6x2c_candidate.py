from __future__ import annotations

import shutil
from collections import defaultdict, Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fmdl6x2c_common import (
    CONTRACT_PATH, EXIT_STATUS, NEXT_GATE, PHASE_ID, bucket_hex, copytree_replace,
    deterministic_gzip, deterministic_zip, discover_identity_releases, load_json,
    read_gzip_jsonl, read_zip_jsonl, record_hash, sha256_bytes, sha256_file,
    stable_json, validate_contract, write_json,
)

def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")

def _date_before(value: str) -> str:
    return (date.fromisoformat(value) - timedelta(days=1)).isoformat()

def load_inputs(repo_root: Path) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    releases = discover_identity_releases(repo_root, contract)
    if not releases:
        raise RuntimeError("NO_ACCEPTED_IDENTITY_RELEASES")
    by_date: dict[str, dict[str, Any]] = {}
    for item in releases:
        obs = item["decision"]["observation_date"]
        prior = by_date.get(obs)
        if prior is None or item["decision"]["accepted_at"] > prior["decision"]["accepted_at"]:
            by_date[obs] = item
    selected = [by_date[key] for key in sorted(by_date)]
    current_root = repo_root / contract["input_contract"]["current_identity_root"]
    inherited = read_zip_jsonl(current_root / "FMDL6X2B_REVIEW_QUEUES.zip", "INHERITED_SOURCE_SCOPE_QUARANTINE")
    evidence_bundles = []
    for path in sorted(repo_root.glob(contract["input_contract"]["optional_official_evidence_glob"])):
        bundle = load_json(path)
        _validate_evidence_bundle(bundle, contract)
        bundle["_path"] = str(path.relative_to(repo_root))
        bundle["_sha256"] = sha256_file(path)
        evidence_bundles.append(bundle)
    return {"contract":contract, "releases":selected, "current_root":current_root,
            "inherited_quarantine":inherited, "evidence_bundles":evidence_bundles}

def _validate_evidence_bundle(bundle: dict[str, Any], contract: dict[str, Any]) -> None:
    evidence = contract["official_evidence_contract"]
    for field in evidence["required_bundle_fields"]:
        if field not in bundle:
            raise RuntimeError("EVIDENCE_BUNDLE_MISSING_" + field)
    if bundle["source_authority"] not in evidence["allowed_source_authorities"]:
        raise RuntimeError("EVIDENCE_SOURCE_AUTHORITY")
    if bundle.get("no_silent_replacement_assertion") is not True:
        raise RuntimeError("EVIDENCE_SILENT_REPLACEMENT")
    for event in bundle.get("events", []):
        for field in evidence["required_event_fields"]:
            if not event.get(field):
                raise RuntimeError("EVIDENCE_EVENT_MISSING_" + field)
        date.fromisoformat(event["official_effective_date"])

def build_history(inputs: dict[str, Any]) -> dict[str, Any]:
    snapshots: list[dict[str, Any]] = []
    observations_by_date: dict[str, list[dict[str, Any]]] = {}
    for item in inputs["releases"]:
        decision = item["decision"]
        rows = read_gzip_jsonl(item["root"] / "FMDL6X2B_IDENTITY_LINEAGE.jsonl.gz")
        obs_date = decision["observation_date"]
        normalized = []
        for row in rows:
            normalized.append({
                "observation_id":"USHOB-" + record_hash("HISTORY_OBSERVATION", obs_date, row["canonical_listing_id"], row["source_row_id"])[:24],
                "observation_date":obs_date,
                "canonical_issuer_id":row["canonical_issuer_id"],
                "canonical_security_id":row["canonical_security_id"],
                "canonical_listing_id":row["canonical_listing_id"],
                "venue":row["venue"],
                "symbol":row["symbol"],
                "official_security_name":row["official_security_name"],
                "source_row_id":row["source_row_id"],
                "source_snapshot_id":row["source_snapshot_id"],
                "source_authority":row["source_authority"],
                "identity_release_id":decision["release_id"],
                "identity_manifest_sha256":item["manifest_sha256"],
                "trade_authority":"NONE",
            })
        normalized.sort(key=lambda row:(row["venue"], row["symbol"], row["canonical_listing_id"]))
        observations_by_date[obs_date] = normalized
        snapshots.append({
            "snapshot_registry_id":"USHSP-" + record_hash("SNAPSHOT", obs_date, decision["release_id"], item["manifest_sha256"])[:24],
            "observation_date":obs_date,
            "identity_release_id":decision["release_id"],
            "identity_manifest_sha256":item["manifest_sha256"],
            "listing_observation_count":len(normalized),
            "source_grade":"OFFICIAL_DIRECTORY_VIA_ACCEPTED_FMDL6X2B",
            "quality_status":"PASS",
        })
    snapshots.sort(key=lambda row:row["observation_date"])
    dates = [row["observation_date"] for row in snapshots]
    latest_date = dates[-1]

    conflicts = []
    for obs_date, rows in observations_by_date.items():
        seen: dict[str, str] = {}
        for row in rows:
            listing_id = row["canonical_listing_id"]
            security_id = row["canonical_security_id"]
            if listing_id in seen and seen[listing_id] != security_id:
                conflicts.append({"observation_date":obs_date,"canonical_listing_id":listing_id,
                                  "security_ids":sorted({seen[listing_id],security_id}),"reason":"LISTING_ID_MAPS_TO_MULTIPLE_SECURITIES"})
            seen[listing_id] = security_id

    listing_dates: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, obs_date in enumerate(dates):
        for row in observations_by_date[obs_date]:
            listing_dates[row["canonical_listing_id"]].append((index,row))

    intervals: list[dict[str, Any]] = []
    for listing_id, items in sorted(listing_dates.items()):
        run: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            if run and item[0] != run[-1][0] + 1:
                intervals.append(_make_interval(run, dates, latest_date))
                run = []
            run.append(item)
        if run:
            intervals.append(_make_interval(run, dates, latest_date))
    intervals.sort(key=lambda row:row["effective_listing_interval_id"])

    events: list[dict[str, Any]] = []
    seen_listing_ids: set[str] = set()
    for row in observations_by_date[dates[0]]:
        events.append(_observation_event("LISTING_FIRST_OBSERVED_ACTIVE", dates[0], row))
        seen_listing_ids.add(row["canonical_listing_id"])

    for prior_date, current_date in zip(dates, dates[1:]):
        previous = {row["canonical_listing_id"]:row for row in observations_by_date[prior_date]}
        current = {row["canonical_listing_id"]:row for row in observations_by_date[current_date]}
        disappeared = {key:value for key,value in previous.items() if key not in current}
        appeared = {key:value for key,value in current.items() if key not in previous}
        previous_by_security: dict[str,list[dict[str,Any]]] = defaultdict(list)
        current_by_security: dict[str,list[dict[str,Any]]] = defaultdict(list)
        for row in disappeared.values():
            previous_by_security[row["canonical_security_id"]].append(row)
        for row in appeared.values():
            current_by_security[row["canonical_security_id"]].append(row)
        paired_old: set[str] = set()
        paired_new: set[str] = set()
        for security_id in sorted(set(previous_by_security) & set(current_by_security)):
            if len(previous_by_security[security_id]) == 1 and len(current_by_security[security_id]) == 1:
                old = previous_by_security[security_id][0]
                new = current_by_security[security_id][0]
                if old["venue"] == new["venue"] and old["symbol"] != new["symbol"]:
                    event_type = "SYMBOL_CHANGE_CANDIDATE"
                elif old["venue"] != new["venue"] and old["symbol"] == new["symbol"]:
                    event_type = "VENUE_TRANSFER_CANDIDATE"
                else:
                    event_type = "SYMBOL_AND_VENUE_CHANGE_CANDIDATE"
                events.append(_bounded_event(event_type, prior_date, current_date, old, new))
                paired_old.add(old["canonical_listing_id"])
                paired_new.add(new["canonical_listing_id"])
        for listing_id,row in sorted(disappeared.items()):
            if listing_id not in paired_old:
                events.append(_bounded_event("LISTING_DISAPPEARANCE_CANDIDATE", prior_date, current_date, row, None))
        for listing_id,row in sorted(appeared.items()):
            if listing_id not in paired_new:
                event_type = "LISTING_REAPPEARANCE_CANDIDATE" if listing_id in seen_listing_ids else "LISTING_FIRST_OBSERVED_ACTIVE"
                events.append(_observation_event(event_type, current_date, row))
            seen_listing_ids.add(listing_id)

    evidence_registry = []
    for bundle in inputs["evidence_bundles"]:
        evidence_registry.append({
            "evidence_bundle_path":bundle["_path"],"evidence_bundle_sha256":bundle["_sha256"],
            "source_authority":bundle["source_authority"],"official_source_url":bundle["official_source_url"],
            "retrieved_at":bundle["retrieved_at"],"event_count":len(bundle["events"]),
        })
        for item in bundle["events"]:
            events.append({
                "lifecycle_event_id":"USHEV-" + record_hash("OFFICIAL_EVENT", item["evidence_id"], item["event_type"], item["official_effective_date"])[:24],
                "event_type":item["event_type"],
                "effective_date":item["official_effective_date"],
                "effective_date_confidence":"OFFICIAL_EFFECTIVE_DATE",
                "canonical_listing_id":item.get("canonical_listing_id"),
                "canonical_security_id":item.get("canonical_security_id"),
                "prior_listing_id":item.get("prior_listing_id"),
                "new_listing_id":item.get("new_listing_id"),
                "cause_status":"OFFICIAL_CAUSE_EVIDENCE_PRESENT",
                "evidence_id":item["evidence_id"],
                "source_authority":bundle["source_authority"],
                "official_source_url":bundle["official_source_url"],
            })
    events.sort(key=lambda row:row["lifecycle_event_id"])

    coverage = _coverage_records(inputs["contract"], dates)
    queues = {
        "HISTORICAL_EFFECTIVE_DATE_CONFIDENCE_QUEUE":[
            {"effective_listing_interval_id":row["effective_listing_interval_id"],
             "canonical_listing_id":row["canonical_listing_id"],
             "first_observed_date":row["first_observed_date"],
             "required_action":"OBTAIN_OFFICIAL_LISTING_EFFECTIVE_DATE",
             "current_confidence":row["start_date_confidence"]}
            for row in intervals if row["start_date_confidence"] != "OFFICIAL_EFFECTIVE_DATE"
        ],
        "LIFECYCLE_CAUSE_CONFIRMATION_QUEUE":[
            {"lifecycle_event_id":row["lifecycle_event_id"],"event_type":row["event_type"],
             "window_start":row.get("window_start"),"window_end":row.get("window_end"),
             "canonical_security_id":row.get("canonical_security_id"),
             "required_action":"OBTAIN_OFFICIAL_CAUSE_AND_EFFECTIVE_DATE"}
            for row in events if row["effective_date_confidence"] == "BOUNDED_EVENT_WINDOW"
        ],
        "HISTORICAL_IDENTITY_CONFLICT_QUEUE":conflicts,
        "COVERAGE_GAP_QUEUE":[row for row in coverage if row["coverage_status"] != "OFFICIAL_SNAPSHOT_OBSERVED"],
        "INHERITED_SOURCE_SCOPE_QUARANTINE":list(inputs["inherited_quarantine"]),
    }
    for rows in queues.values():
        rows.sort(key=stable_json)
    return {"snapshots":snapshots,"observations":[row for obs_date in dates for row in observations_by_date[obs_date]],
            "intervals":intervals,"events":events,"coverage":coverage,"queues":queues,
            "evidence_registry":evidence_registry,"latest_date":latest_date}

def _make_interval(run: list[tuple[int,dict[str,Any]]], dates: list[str], latest_date: str) -> dict[str, Any]:
    first_index, first = run[0]
    last_index, last = run[-1]
    active_latest = last["observation_date"] == latest_date
    first_absent = None if active_latest or last_index + 1 >= len(dates) else dates[last_index + 1]
    return {
        "effective_listing_interval_id":"USHLI-" + record_hash("LISTING_INTERVAL", first["canonical_listing_id"], first["observation_date"], last["observation_date"])[:24],
        "canonical_issuer_id":first["canonical_issuer_id"],
        "canonical_security_id":first["canonical_security_id"],
        "canonical_listing_id":first["canonical_listing_id"],
        "venue":first["venue"],"symbol":first["symbol"],
        "first_observed_date":first["observation_date"],"last_observed_date":last["observation_date"],
        "effective_start_date":None,"effective_end_date":None,
        "start_date_confidence":"OBSERVATION_ONLY",
        "end_date_confidence":None if active_latest else "BOUNDED_EVENT_WINDOW",
        "first_absent_observation_date":first_absent,
        "active_at_latest_snapshot":active_latest,
        "observation_count":len(run),
        "continuity_basis":"CONSECUTIVE_ACCEPTED_IDENTITY_SNAPSHOTS",
        "trade_authority":"NONE",
    }

def _observation_event(event_type: str, obs_date: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "lifecycle_event_id":"USHEV-" + record_hash("OBS_EVENT", event_type, obs_date, row["canonical_listing_id"])[:24],
        "event_type":event_type,"observation_date":obs_date,"effective_date":None,
        "effective_date_confidence":"OBSERVATION_ONLY",
        "canonical_listing_id":row["canonical_listing_id"],
        "canonical_security_id":row["canonical_security_id"],
        "venue":row["venue"],"symbol":row["symbol"],
        "cause_status":"OBSERVATION_NOT_LEGAL_EFFECTIVE_DATE",
        "source_authority":row["source_authority"],
    }

def _bounded_event(event_type: str, start: str, end: str, old: dict[str, Any], new: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "lifecycle_event_id":"USHEV-" + record_hash("BOUNDED_EVENT", event_type, start, end, old["canonical_listing_id"], None if new is None else new["canonical_listing_id"])[:24],
        "event_type":event_type,"effective_date":None,
        "effective_date_confidence":"BOUNDED_EVENT_WINDOW",
        "window_start":start,"window_end":end,
        "canonical_security_id":old["canonical_security_id"],
        "prior_listing_id":old["canonical_listing_id"],
        "new_listing_id":None if new is None else new["canonical_listing_id"],
        "prior_venue":old["venue"],"new_venue":None if new is None else new["venue"],
        "prior_symbol":old["symbol"],"new_symbol":None if new is None else new["symbol"],
        "cause_status":"PENDING_OFFICIAL_CAUSE_CONFIRMATION",
    }

def _coverage_records(contract: dict[str, Any], dates: list[str]) -> list[dict[str, Any]]:
    target = contract["history_contract"]["target_start_date"]
    first = dates[0]
    rows = []
    if target < first:
        rows.append({
            "coverage_interval_id":"USHCV-" + record_hash("COVERAGE_GAP", target, _date_before(first))[:24],
            "start_date":target,"end_date":_date_before(first),
            "coverage_status":"UNAVAILABLE_UNDER_CONFIRMED_ZERO_COST_OFFICIAL_ROUTES",
            "confidence":"OBSERVATION_ONLY",
            "historical_completion_claimed":False,
        })
    for value in dates:
        rows.append({
            "coverage_interval_id":"USHCV-" + record_hash("SNAPSHOT_DATE", value)[:24],
            "start_date":value,"end_date":value,
            "coverage_status":"OFFICIAL_SNAPSHOT_OBSERVED",
            "confidence":"OBSERVATION_ONLY",
            "historical_completion_claimed":False,
        })
    for left,right in zip(dates,dates[1:]):
        if (date.fromisoformat(right)-date.fromisoformat(left)).days > 1:
            rows.append({
                "coverage_interval_id":"USHCV-" + record_hash("INTER_SNAPSHOT_GAP", left, right)[:24],
                "start_date":(date.fromisoformat(left)+timedelta(days=1)).isoformat(),
                "end_date":(date.fromisoformat(right)-timedelta(days=1)).isoformat(),
                "coverage_status":"NO_ACCEPTED_DIRECTORY_SNAPSHOT",
                "confidence":"OBSERVATION_ONLY",
                "historical_completion_claimed":False,
            })
    return sorted(rows,key=lambda row:(row["start_date"],row["coverage_interval_id"]))

def build_shards(history: dict[str, Any], bucket_count: int, accepted_at: str) -> tuple[bytes,list[dict[str,Any]]]:
    entries: dict[str,bytes] = {}
    manifest: list[dict[str,Any]] = []
    def add(domain: str, rows: list[dict[str,Any]], key: str, venue_partition: bool=False) -> None:
        venues = ["XNAS","XNYS","XASE"] if venue_partition else [None]
        for venue in venues:
            selected = [row for row in rows if venue is None or row.get("venue") == venue]
            for bucket in range(bucket_count):
                bucket_id=f"{bucket:02X}"
                shard=[row for row in selected if bucket_hex(str(row[key]),bucket_count)==bucket_id]
                shard.sort(key=lambda row:str(row[key]))
                name=f"{domain}/" + (f"{venue}/" if venue else "") + f"{bucket_id}.jsonl"
                payload=_jsonl_bytes(shard)
                entries[name]=payload
                manifest.append({
                    "domain":domain,"shard_id":f"{domain}-{venue+'-' if venue else ''}{bucket_id}",
                    "zip_member":name,"venue":venue,"bucket":bucket_id,"row_count":len(shard),
                    "schema_version":"fmdl6x2c.listing_history.v1","payload_sha256":sha256_bytes(payload),
                    "generated_at":accepted_at,"min_effective_date":None,"max_effective_date":None,
                    "quality_status":"PASS",
                })
    add("EFFECTIVE_DATED_LISTING",history["intervals"],"effective_listing_interval_id",True)
    add("LIFECYCLE_EVENT",history["events"],"lifecycle_event_id")
    add("SNAPSHOT_REGISTRY",history["snapshots"],"snapshot_registry_id")
    add("COVERAGE_INTERVAL",history["coverage"],"coverage_interval_id")
    return deterministic_zip(entries),manifest

def build_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    checks, errors = validate_contract(repo_root)
    if errors:
        raise RuntimeError("CONTRACT_ERRORS:" + ",".join(errors))
    inputs=load_inputs(repo_root)
    history=build_history(inputs)
    contract=inputs["contract"]
    contract_sha=sha256_file(repo_root/CONTRACT_PATH)
    input_hashes=[release["manifest_sha256"] for release in inputs["releases"]]
    evidence_hashes=[bundle["_sha256"] for bundle in inputs["evidence_bundles"]]
    fingerprint=record_hash("FMDL6X2C_RELEASE",contract_sha,*sorted(input_hashes),*sorted(evidence_hashes))
    release_id=f"FMDL6X2C_{history['latest_date'].replace('-','')}_{fingerprint[:12]}"
    candidate_root.mkdir(parents=True,exist_ok=True)

    shard_zip,shard_manifest=build_shards(history,int(contract["storage_contract"]["bucket_count"]),accepted_at)
    (candidate_root/"FMDL6X2C_HISTORY_SHARDS.zip").write_bytes(shard_zip)
    (candidate_root/"FMDL6X2C_LISTING_OBSERVATIONS.jsonl.gz").write_bytes(deterministic_gzip(history["observations"]))
    (candidate_root/"FMDL6X2C_REVIEW_QUEUES.zip").write_bytes(
        deterministic_zip({name+".jsonl":_jsonl_bytes(rows) for name,rows in history["queues"].items()})
    )
    write_json(candidate_root/"FMDL6X2C_COVERAGE_REPORT.json",{
        "phase_id":PHASE_ID,"release_id":release_id,
        "target_start_date":contract["history_contract"]["target_start_date"],
        "first_accepted_snapshot_date":history["snapshots"][0]["observation_date"],
        "latest_accepted_snapshot_date":history["latest_date"],
        "accepted_snapshot_count":len(history["snapshots"]),
        "official_snapshot_observation_dates":[row["observation_date"] for row in history["snapshots"]],
        "coverage_intervals":history["coverage"],
        "historical_completion_claimed":False,
        "survivorship_complete_from_target_start":False,
        "daily_snapshot_accumulation_operational":True,
        "universal_zero_cost_official_route_confirmed":False,
    })
    write_json(candidate_root/"FMDL6X2C_BACKFILL_SUMMARY.json",{
        "phase_id":PHASE_ID,"release_id":release_id,
        "snapshot_count":len(history["snapshots"]),
        "listing_observation_records":len(history["observations"]),
        "effective_listing_intervals":len(history["intervals"]),
        "lifecycle_event_records":len(history["events"]),
        "event_confidence_counts":dict(sorted(Counter(row["effective_date_confidence"] for row in history["events"]).items())),
        "event_type_counts":dict(sorted(Counter(row["event_type"] for row in history["events"]).items())),
        "review_queue_counts":{key:len(value) for key,value in sorted(history["queues"].items())},
        "official_evidence_bundle_count":len(history["evidence_registry"]),
        "historical_completion_claimed":False,
    })
    write_json(candidate_root/"FMDL6X2C_SOURCE_BINDING.json",{
        "phase_id":PHASE_ID,"release_id":release_id,
        "identity_releases":[{"release_id":release["decision"]["release_id"],"observation_date":release["decision"]["observation_date"],
                              "manifest_sha256":release["manifest_sha256"]} for release in inputs["releases"]],
        "official_evidence_registry":history["evidence_registry"],
        "source_authority":"NASDAQ_OFFICIAL_VIA_ACCEPTED_FMDL6X2B_IDENTITY_RELEASES",
        "silent_source_substitution":False,
    })
    expected_shards=64*(3+1+1+1)
    latest_count=history["snapshots"][-1]["listing_observation_count"]
    entry_pointer=load_json(repo_root/contract["entry_gate"]["pointer_path"])
    exact_events=[row for row in history["events"] if row["effective_date_confidence"]=="OFFICIAL_EFFECTIVE_DATE"]
    quality={
        "phase_id":PHASE_ID,"release_id":release_id,"quality_status":"PASS",
        "accepted_identity_snapshot_count":len(history["snapshots"]),
        "latest_snapshot_listing_count":latest_count,
        "entry_pointer_listing_count":entry_pointer["listing_records"],
        "listing_observations_accounted":len(history["observations"]),
        "effective_listing_interval_count":len(history["intervals"]),
        "lifecycle_event_count":len(history["events"]),
        "exact_effective_date_event_count":len(exact_events),
        "bounded_event_window_count":sum(row["effective_date_confidence"]=="BOUNDED_EVENT_WINDOW" for row in history["events"]),
        "observation_only_event_count":sum(row["effective_date_confidence"]=="OBSERVATION_ONLY" for row in history["events"]),
        "identity_conflict_count":len(history["queues"]["HISTORICAL_IDENTITY_CONFLICT_QUEUE"]),
        "inherited_quarantine_expected":len(inputs["inherited_quarantine"]),
        "inherited_quarantine_preserved":len(history["queues"]["INHERITED_SOURCE_SCOPE_QUARANTINE"]),
        "expected_shard_count":expected_shards,"manifested_shard_count":len(shard_manifest),
        "historical_completion_claimed":False,
        "fabricated_effective_dates":0,
        "trade_authority":"NONE",
        "zero_mutation_proof":{"candidate_pool_mutations":0,"simulation_mutations":0,"real_account_mutations":0,"orders":0},
    }
    quality_errors=[]
    if latest_count != entry_pointer["listing_records"]:
        quality_errors.append("LATEST_LISTING_COUNT")
    if not history["snapshots"]:
        quality_errors.append("NO_SNAPSHOTS")
    if quality["inherited_quarantine_expected"] != quality["inherited_quarantine_preserved"]:
        quality_errors.append("INHERITED_QUARANTINE")
    if len(shard_manifest) != expected_shards:
        quality_errors.append("SHARD_COUNT")
    if len({row["effective_listing_interval_id"] for row in history["intervals"]}) != len(history["intervals"]):
        quality_errors.append("DUPLICATE_INTERVAL_ID")
    if len({row["lifecycle_event_id"] for row in history["events"]}) != len(history["events"]):
        quality_errors.append("DUPLICATE_EVENT_ID")
    if any(row.get("effective_date") and row["effective_date_confidence"]!="OFFICIAL_EFFECTIVE_DATE" for row in history["events"]):
        quality_errors.append("FABRICATED_EFFECTIVE_DATE")
    if quality_errors:
        quality["quality_status"]="FAIL"
        quality["errors"]=quality_errors
        write_json(candidate_root/"FMDL6X2C_QUALITY_REPORT.json",quality)
        raise RuntimeError("QUALITY_ERRORS:"+",".join(quality_errors))
    write_json(candidate_root/"FMDL6X2C_QUALITY_REPORT.json",quality)
    decision={
        "phase_id":PHASE_ID,"status":EXIT_STATUS,"release_id":release_id,
        "release_sequence":contract["storage_contract"]["release_sequence"],
        "accepted_at":accepted_at,"observation_date":history["latest_date"],
        "source_commit":source_commit,"input_release_id":entry_pointer["release_id"],
        "next_gate":NEXT_GATE,
        "history_status":"PARTIAL_OFFICIAL_EVIDENCE_BASELINE_WITH_DAILY_ACCUMULATION",
        "historical_completion_claimed":False,
        "target_start_date":contract["history_contract"]["target_start_date"],
        "first_accepted_snapshot_date":history["snapshots"][0]["observation_date"],
        "accepted_snapshot_count":len(history["snapshots"]),
        "effective_listing_intervals":len(history["intervals"]),
        "lifecycle_events":len(history["events"]),
        "research_production_gate":"OPEN_FOR_FMDL6X2_DATA_PRODUCTION",
        "brokerage_real_account_gate":"CLOSED_NO_CHANNEL",
        "trade_authority":"NONE","zero_mutation_proof":quality["zero_mutation_proof"],
    }
    write_json(candidate_root/"FMDL6X2C_DECISION.json",decision)
    manifest_files={}
    for path in sorted(candidate_root.iterdir()):
        if path.name=="FMDL6X2C_MANIFEST.json" or not path.is_file():
            continue
        manifest_files[path.name]={"bytes":path.stat().st_size,"sha256":sha256_file(path)}
    manifest={"phase_id":PHASE_ID,"release_id":release_id,"release_sequence":32,
              "generated_at":accepted_at,"contract_sha256":contract_sha,
              "input_manifest_sha256_values":sorted(input_hashes),
              "files":manifest_files,"shards":shard_manifest}
    write_json(candidate_root/"FMDL6X2C_MANIFEST.json",manifest)
    return {"release_id":release_id,"decision":decision,"quality":quality,"contract_checks":checks}

def validate_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str, acceptance_path: Path) -> dict[str, Any]:
    replay=candidate_root.parent/(candidate_root.name+"_replay")
    if replay.exists():
        shutil.rmtree(replay)
    build_candidate(repo_root,replay,accepted_at,source_commit)
    left={path.name:sha256_file(path) for path in candidate_root.iterdir() if path.is_file()}
    right={path.name:sha256_file(path) for path in replay.iterdir() if path.is_file()}
    errors=[]
    if left!=right:
        errors.append("SAME_INPUT_REPLAY_MISMATCH")
    manifest=load_json(candidate_root/"FMDL6X2C_MANIFEST.json")
    for name,metadata in manifest["files"].items():
        path=candidate_root/name
        if not path.is_file() or path.stat().st_size!=metadata["bytes"] or sha256_file(path)!=metadata["sha256"]:
            errors.append("MANIFEST_FILE:"+name)
    if load_json(candidate_root/"FMDL6X2C_QUALITY_REPORT.json").get("quality_status")!="PASS":
        errors.append("QUALITY")
    if load_json(candidate_root/"FMDL6X2C_DECISION.json").get("historical_completion_claimed") is not False:
        errors.append("COMPLETION_CLAIM")
    result={"phase_id":PHASE_ID,"status":"PASS" if not errors else "FAIL",
            "same_input_replay":"PASS" if left==right else "FAIL","errors":errors}
    write_json(acceptance_path,result)
    if errors:
        raise RuntimeError("ACCEPTANCE_ERRORS:"+",".join(errors))
    return result

def publish(repo_root: Path, candidate_root: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    decision=load_json(candidate_root/"FMDL6X2C_DECISION.json")
    quality=load_json(candidate_root/"FMDL6X2C_QUALITY_REPORT.json")
    if quality.get("quality_status")!="PASS":
        raise RuntimeError("QUALITY_NOT_PASS")
    release_id=decision["release_id"]
    contract=load_json(repo_root/CONTRACT_PATH)
    current=repo_root/contract["storage_contract"]["current_root"]
    release=repo_root/contract["storage_contract"]["release_root"].replace("<release_id>",release_id)
    normalized=repo_root/contract["storage_contract"]["normalized_root"].replace("<release_id>",release_id)
    if release.exists():
        raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    archive=repo_root/"outputs/fmdl6x2/archive/listing_history"
    if current.exists():
        archive_target=archive/(current.name+"_"+published_at.replace(":","").replace("-",""))
        copytree_replace(current,archive_target)
    copytree_replace(candidate_root,current)
    copytree_replace(candidate_root,release)
    copytree_replace(candidate_root,normalized)
    manifest_sha=sha256_file(current/"FMDL6X2C_MANIFEST.json")
    pointer={
        "phase_id":PHASE_ID,"status":EXIT_STATUS,"release_id":release_id,"release_sequence":32,
        "published_at":published_at,"source_commit":source_commit,
        "current_path":str(current.relative_to(repo_root)),"release_path":str(release.relative_to(repo_root)),
        "normalized_path":str(normalized.relative_to(repo_root)),
        "manifest_sha256":manifest_sha,"next_gate":NEXT_GATE,
        "history_status":decision["history_status"],
        "historical_completion_claimed":False,
        "accepted_snapshot_count":decision["accepted_snapshot_count"],
        "effective_listing_intervals":decision["effective_listing_intervals"],
        "lifecycle_events":decision["lifecycle_events"],
        "research_production_gate":"OPEN_FOR_FMDL6X2_DATA_PRODUCTION",
        "brokerage_real_account_gate":"CLOSED_NO_CHANNEL","trade_authority":"NONE",
    }
    write_json(repo_root/contract["storage_contract"]["last_success"],pointer)
    lkg=dict(pointer)
    lkg.update({"lkg_scope":"LISTING_HISTORY_DOMAIN","lkg_reason":"LATEST_ACCEPTED_LISTING_HISTORY_BASELINE"})
    write_json(repo_root/contract["storage_contract"]["last_known_good"],lkg)
    return pointer
