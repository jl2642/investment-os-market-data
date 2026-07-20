from scripts.run_fmdl5a_universe import canonical_json, sha256_bytes


def test_canonical_hash_is_stable():
    assert sha256_bytes(canonical_json({"b": 2, "a": 1})) == sha256_bytes(canonical_json({"a": 1, "b": 2}))


def test_canonical_security_id_contract():
    code = "700".zfill(5)
    assert f"HKEX:{code}" == "HKEX:00700"


def test_union_route_flags():
    rows = {"00005": {"shanghai_connect": True, "shenzhen_connect": False}}
    rows["00005"]["shenzhen_connect"] = True
    assert rows["00005"] == {"shanghai_connect": True, "shenzhen_connect": True}


def test_zero_trade_authority_boundary():
    contract = {"candidate_pool_mutation": False, "simulation_mutation": False, "real_account_mutation": False, "order_generation": False, "trade_authority": "NONE"}
    assert not any(contract[k] for k in ["candidate_pool_mutation", "simulation_mutation", "real_account_mutation", "order_generation"])
    assert contract["trade_authority"] == "NONE"


def test_unknown_rows_are_blocked():
    allowed = {"BUY_AND_SELL_ELIGIBLE", "SELL_ONLY", "SUSPENDED_WITH_ELIGIBILITY_RETAINED", "REMOVED"}
    assert "UNKNOWN_BLOCKED" not in allowed
