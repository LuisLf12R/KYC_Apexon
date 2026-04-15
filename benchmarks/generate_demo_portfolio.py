"""
generate_demo_portfolio.py
Generates a synthetic KYC portfolio for demo and testing.

Produces TWO outputs:
1. scenario_manifest.jsonl  — the archetype blueprint (unchanged)
2. raw_kyc_tables/          — intentionally messy CSVs that simulate real-world
                              dirty data, designed to test Claude's cleaning pipeline.

The messy tables contain:
- Inconsistent column names (abbreviations, typos, mixed casing)
- Mixed date formats (6+ formats randomly distributed)
- Value normalisation problems (mixed case, abbreviations, garbage strings)
- Randomly nullified optional fields (blank, N/A, null, —, TBD, ?)
- Extra junk columns that don't belong in the engine schema
- Leading/trailing whitespace in values
- Boolean fields as Y/N, yes/no, 1/0, True/False
- Percentage fields formatted inconsistently
"""

import argparse
import csv
import json
import random
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.config_loader import (
    load_constraint_catalog,
    load_generator_matrix,
    load_scenario_archetypes,
)


# Anchor to project root regardless of where the process is launched from
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = _PROJECT_ROOT / "benchmarks" / "output"
OUTPUT_FILE = OUTPUT_DIR / "scenario_manifest.jsonl"


def _default_run_id() -> str:
    return f"demo_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _priority_weight(priority: str) -> int:
    p = (priority or "").upper()
    if p == "HIGH":
        return 3
    if p == "MEDIUM":
        return 2
    return 1


def _build_weighted_archetypes(archetypes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    weighted: List[Dict[str, Any]] = []
    for archetype in archetypes:
        weighted.extend([archetype] * _priority_weight(archetype.get("demo_priority", "LOW")))
    return weighted


def _build_scenario(archetype: Dict[str, Any], scenario_number: int, run_id: str) -> Dict[str, Any]:
    defaults = archetype.get("default_states", {})
    scenario = {
        "scenario_id": f"SCENARIO_{scenario_number:04d}",
        "customer_id": f"SCENARIO_{scenario_number:04d}",
        "run_id": run_id,
        "archetype_id": archetype.get("archetype_id"),
        "archetype_name": archetype.get("archetype_name"),
        "customer_type": archetype.get("customer_type"),
        "risk_tier": archetype.get("risk_tier"),
        "aml_state": defaults.get("aml_state"),
        "identity_state": defaults.get("identity_state"),
        "poa_state": defaults.get("poa_state"),
        "ubo_state": defaults.get("ubo_state"),
        "activity_state": defaults.get("activity_state"),
        "data_quality_state": defaults.get("data_quality_state"),
        "expected_final_decision": archetype.get("expected_final_decision"),
        "is_remediable_case": bool(archetype.get("is_remediable_case", False)),
        "coverage_tags": archetype.get("coverage_tags", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if archetype.get("expected_post_remediation_decision") is not None:
        scenario["expected_post_remediation_decision"] = archetype.get("expected_post_remediation_decision")
    return scenario


def _matches_if_clause(scenario: Dict[str, Any], if_clause: Dict[str, Any]) -> bool:
    for field, expected in if_clause.items():
        if scenario.get(field) != expected:
            return False
    return True


def _apply_constraints(scenario: Dict[str, Any], constraints: List[Dict[str, Any]]) -> Dict[str, Any]:
    updated = dict(scenario)
    for constraint in constraints:
        if_clause = constraint.get("if", {})
        then_clause = constraint.get("then", {})
        if not isinstance(if_clause, dict) or not isinstance(then_clause, dict):
            continue
        if _matches_if_clause(updated, if_clause):
            updated.update(then_clause)
    return updated


# ── Mess generators ───────────────────────────────────────────────────────────

_FIRST_NAMES = [
    "James", "Maria", "Wei", "Fatima", "Carlos", "Anna", "Dmitri", "Aisha",
    "Luca", "Priya", "Omar", "Ingrid", "Kenji", "Amara", "Thomas", "Yuki",
    "Ibrahim", "Sofia", "Marcus", "Leila", "Raj", "Elena", "Samuel", "Nina",
]
_LAST_NAMES = [
    "Smith", "Gonzalez", "Chen", "Al-Rashid", "Fernandez", "Petrov", "Okonkwo",
    "Rossi", "Patel", "Hassan", "Larsson", "Tanaka", "Diallo", "Anderson",
    "Nakamura", "Mbeki", "Mueller", "Rodriguez", "Kim", "Johansson", "Nguyen",
]
_CORP_NAMES = [
    "Alpha Capital LLC", "Meridian Trading Co.", "Blue Ridge Investments",
    "Pacific Rim Holdings", "Zenith Financial Group", "Atlas Asset Management",
    "Orion Global Fund", "Summit Partners Ltd.", "Vertex Wealth Mgmt",
    "Pinnacle Ventures", "Horizon Capital Partners", "Crestwood Group",
]
_COUNTRIES = ["US", "GB", "DE", "FR", "SG", "AE", "CH", "CA", "AU", "NL"]
_JUNK_NOTES = [
    "reviewed by compliance", "auto-generated test record", "legacy migration",
    "flagged for review Q2", "pending verification", "", "n/a", "see file",
    "carry over from 2024", "periodic review due", "HOLD - awaiting docs",
]


def _rand_name(customer_type: str) -> str:
    if customer_type == "CORPORATE":
        return random.choice(_CORP_NAMES)
    return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"


def _rand_doc_number() -> str:
    prefix = random.choice(["P", "ID", "DL", "NI", "PP"])
    digits = "".join(random.choices(string.digits, k=8))
    letters = "".join(random.choices(string.ascii_uppercase, k=2))
    return f"{prefix}{digits}{letters}"


def _messy_date(base_date: datetime) -> str:
    """Return a date in one of 7 messy formats."""
    fmt = random.choice([
        "%d/%m/%Y",       # 15/04/2026
        "%m-%d-%Y",       # 04-15-2026
        "%d-%b-%Y",       # 15-Apr-2026
        "%B %d, %Y",      # April 15, 2026
        "%Y%m%d",         # 20260415
        "%d.%m.%y",       # 15.04.26
        "%d %b %Y",       # 15 Apr 2026
    ])
    return base_date.strftime(fmt)


def _null_or(value: str, null_chance: float = 0.12) -> str:
    """Randomly replace a value with a null-like string."""
    if random.random() < null_chance:
        return random.choice(["", "N/A", "null", "—", "unknown", "TBD", "n/a", "NULL", "-", "?"])
    return value


def _messy_whitespace(value: str) -> str:
    """Randomly add leading/trailing whitespace."""
    if random.random() < 0.2:
        spaces = " " * random.randint(1, 3)
        return random.choice([spaces + value, value + spaces, spaces + value + spaces])
    return value


def _messy_entity_type(customer_type: str) -> str:
    if customer_type == "CORPORATE":
        choices = ["CORP", "corporate", "COMPANY", "Corp.", "Corporate Entity",
                   "Legal Entity", "LE", "CO", "company", "CORPORATE"]
    else:
        choices = ["IND", "individual", "INDV", "Individual Person", "Individ.",
                   "PERSON", "natural person", "Individual", "INDIVIDUAL", "ind."]
    v = random.choice(choices)
    return _messy_whitespace(v)


def _messy_risk(risk_tier: str) -> str:
    mapping = {
        "LOW":      ["LO", "Low Risk", "low", "L", "Tier 1", "1-Low", "LOW RISK", " low ", "Low"],
        "MEDIUM":   ["MED", "Med", "Medium Risk", "M", "Tier 2", "2-Med", "MEDIUM", "medium", "Med Risk"],
        "HIGH":     ["HI", "High Risk", "high", "H", "Tier 3", "3-High", "HIGH RISK", "High", "HIGH"],
        "CRITICAL": ["CRIT", "Critical!", "CRITICAL RISK", "Cr.", "Tier 4", "4-Crit", "CRITICAL"],
    }
    choices = mapping.get(risk_tier, [risk_tier])
    return _messy_whitespace(random.choice(choices))


def _messy_aml_result(aml_state: str) -> str:
    mapping = {
        "NO_HIT_CURRENT": ["CLEAR", "No Hit Found", "clear", "no match", "NO HIT",
                           "Cleared - No Match", "PASS", "clean", "No Hit", "NHC"],
        "BLOCKED":        ["BLOCKED!", "Blocked", "blocked", "BLK", "BLOCK",
                           "Sanctioned", "ON LIST", "SANCTION HIT", "Blocked - Sanctioned"],
        "HIT_CURRENT":    ["HIT", "Hit - Review Reqd", "REVIEW", "Possible Match",
                           "hit", "UNDER REVIEW", "FLAG", "Potential Hit", "Hit"],
        "CLEARED":        ["Cleared", "CLEARED", "False Positive", "FP - Cleared",
                           "cleared ok", "FP", "Cleared/FP"],
    }
    choices = mapping.get(aml_state, [aml_state])
    return _messy_whitespace(random.choice(choices))


def _messy_aml_hit_status(aml_state: str) -> str:
    mapping = {
        "NO_HIT_CURRENT": ["CLEAR", "No Hit", "clean", "OK", "PASS", "not listed", "Clear"],
        "BLOCKED":        ["BLOCKED", "blocked", "YES - HIT", "ON SANCTION LIST", "HIT!", "Hit"],
        "HIT_CURRENT":    ["HIT", "Possible", "REVIEW", "match found", "Match", "Review"],
        "CLEARED":        ["CLEARED", "FP", "false positive", "Cleared", "Clear - FP"],
    }
    choices = mapping.get(aml_state, [aml_state])
    return _messy_whitespace(random.choice(choices))


def _messy_doc_status(identity_state: str) -> str:
    mapping = {
        "PRIMARY_CURRENT":  ["VERIFIED", "PASS", "OK", "Verified ok", "valid", "VALID",
                             "approved", "Verified", "ACTIVE"],
        "PRIMARY_EXPIRED":  ["EXPIRED!", "Expired", "exp", "PAST DUE", "Lapsed", "EXP",
                             "Expired - Renewal Required", "Out of Date"],
        "MISSING_PRIMARY":  ["MISSING", "Not Found", "NOT PROVIDED", "missing", "absent",
                             "N/P", "Not Submitted", "NO DOC"],
        "SECONDARY_ONLY":   ["PARTIAL", "Partial Match", "incomplete", "PART",
                             "Secondary Only", "Sec. Doc Only"],
    }
    choices = mapping.get(identity_state, ["PENDING"])
    return _messy_whitespace(random.choice(choices))


def _messy_poa_doc_type(poa_state: str) -> str:
    mapping = {
        "VALID_PRIMARY":  ["Utility Bill", "Bank Statement", "Council Tax",
                          "utility bill", "UTILITY", "Bank Stmt", "Utility"],
        "MISSING_POA":    ["MISSING", "Not Provided", "N/A", "Missing", "NOT SUBMITTED", "—"],
        "EXPIRED_POA":    ["Expired Utility Bill", "Expired Bank Stmt", "EXPIRED POA",
                          "exp. utility", "Lapsed POA"],
    }
    choices = mapping.get(poa_state, ["Other"])
    return _messy_whitespace(random.choice(choices))


def _messy_bool(value: bool) -> str:
    if value:
        return random.choice(["Y", "Yes", "TRUE", "true", "1", "yes", "True"])
    else:
        return random.choice(["N", "No", "FALSE", "false", "0", "no", "False"])


def _messy_ownership_pct() -> str:
    pct = random.choice([25, 30, 33, 40, 50, 51, 60, 75, 100])
    fmt = random.choice([
        f"{pct}%", f"{pct}.0%", f"{pct / 100:.2f}", f"{pct}",
        f"{pct:.1f}", f" {pct}% ", f"{pct}.00",
    ])
    return fmt


def _rand_legacy_id() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


def _rand_username() -> str:
    users = ["jsmith", "mrodriguez", "alee", "kpatel", "twilson",
             "compliance_bot", "sys_user", "legacy_import", "batch_proc"]
    return random.choice(users)


# ── Raw table builders ────────────────────────────────────────────────────────

def _build_customers_raw(scenarios: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Build messy customers rows.
    Column names chosen to be imperfect but recognisable.
    """
    rows = []
    for s in scenarios:
        base_dt = datetime.fromisoformat(s["generated_at"].replace("Z", "+00:00"))
        acct_open = base_dt - timedelta(days=random.randint(30, 1800))
        last_kyc = base_dt - timedelta(days=random.randint(0, 365))

        name = _rand_name(s.get("customer_type", "INDIVIDUAL"))
        country = _null_or(random.choice(_COUNTRIES), null_chance=0.08)

        rows.append({
            # Messy column names
            "Cust ID":          _messy_whitespace(s["customer_id"]),
            "Customer Name":    _messy_whitespace(name),
            "Entity":           _messy_entity_type(s.get("customer_type", "INDIVIDUAL")),
            "Country/Jur":      country,
            "Risk Lvl":         _messy_risk(s.get("risk_tier", "MEDIUM")),
            "Acct Open":        _null_or(_messy_date(acct_open), null_chance=0.05),
            "Last KYC Dt":      _null_or(_messy_date(last_kyc), null_chance=0.1),
            # Junk columns that don't belong
            "Legacy ID":        _null_or(_rand_legacy_id(), null_chance=0.3),
            "Notes":            _null_or(random.choice(_JUNK_NOTES), null_chance=0.2),
            "Created By":       _rand_username(),
            "Active?":          _messy_bool(True),
        })
    return rows


def _build_screenings_raw(scenarios: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Messy AML screening rows."""
    rows = []
    for s in scenarios:
        base_dt = datetime.fromisoformat(s["generated_at"].replace("Z", "+00:00"))
        screen_dt = base_dt - timedelta(days=random.randint(0, 30))
        aml = s.get("aml_state", "NO_HIT_CURRENT")

        # Occasionally generate a match name for hits
        match_name = ""
        if aml in ("BLOCKED", "HIT_CURRENT"):
            match_name = _null_or(
                _messy_whitespace(_rand_name("INDIVIDUAL")), null_chance=0.15
            )
        else:
            match_name = _null_or("", null_chance=0.7)

        list_ref = ""
        if aml in ("BLOCKED", "HIT_CURRENT"):
            list_ref = _null_or(
                random.choice(["OFAC SDN", "EU Sanctions", "HMT", "UN Consolidated",
                               "OFAC-SDN", "UK Sanctions List", "INTERPOL"]),
                null_chance=0.1
            )

        rows.append({
            "Client":       _messy_whitespace(s["customer_id"]),
            "Screen Dt":    _null_or(_messy_date(screen_dt), null_chance=0.05),
            "Result":       _messy_aml_result(aml),
            "Matched Name": match_name,
            "List Ref":     list_ref,
            "Hit?":         _messy_aml_hit_status(aml),
            # Junk columns
            "Screener":     _rand_username(),
            "Batch Ref":    _null_or(f"BATCH-{random.randint(1000, 9999)}", null_chance=0.3),
        })
    return rows


def _build_id_verifications_raw(scenarios: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Messy identity verification rows."""
    rows = []
    for s in scenarios:
        base_dt = datetime.fromisoformat(s["generated_at"].replace("Z", "+00:00"))
        issue_dt = base_dt - timedelta(days=random.randint(180, 3650))
        expiry_dt = issue_dt + timedelta(days=random.randint(365 * 5, 365 * 10))
        verify_dt = base_dt - timedelta(days=random.randint(0, 90))
        identity = s.get("identity_state", "PRIMARY_CURRENT")

        doc_types = {
            "PRIMARY_CURRENT":  ["Passport", "National ID", "Driver's Licence",
                                 "passport", "NAT ID", "DL", "Nat. ID Card"],
            "PRIMARY_EXPIRED":  ["Passport (Expired)", "Expired National ID",
                                 "Expired DL", "EXP Passport", "Expired Passport"],
            "MISSING_PRIMARY":  ["N/A", "", "MISSING", "Not Provided", "—"],
            "SECONDARY_ONLY":   ["Birth Certificate", "Utility Bill (ID)",
                                 "Secondary Doc", "Sec. ID"],
        }
        doc_type = _messy_whitespace(
            random.choice(doc_types.get(identity, ["Unknown"]))
        )

        rows.append({
            "customer":     _messy_whitespace(s["customer_id"]),
            "Doc Type":     doc_type,
            "Doc#":         _null_or(_rand_doc_number(), null_chance=0.12),
            "Issued":       _null_or(_messy_date(issue_dt), null_chance=0.08),
            "Expires":      _null_or(_messy_date(expiry_dt), null_chance=0.08),
            "Verify Date":  _null_or(_messy_date(verify_dt), null_chance=0.1),
            "Status":       _messy_doc_status(identity),
            # Junk columns
            "issuing_auth": _null_or(
                random.choice(["DVLA", "Home Office", "IRS", "State Dept", "Gov UK",
                               "Passport Agency", "DMV", "Federal", "n/a"]),
                null_chance=0.25
            ),
            "manual_override": _null_or(random.choice(["Y", "N", "", "yes", "no"]),
                                         null_chance=0.5),
        })
    return rows


def _build_documents_raw(scenarios: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Messy proof-of-address document rows."""
    rows = []
    for s in scenarios:
        base_dt = datetime.fromisoformat(s["generated_at"].replace("Z", "+00:00"))
        issue_dt = base_dt - timedelta(days=random.randint(0, 90))
        expiry_dt = issue_dt + timedelta(days=365)
        poa = s.get("poa_state", "VALID_PRIMARY")

        categories = ["POA", "Proof of Address", "proof of addr", "Address Document",
                      "UTILITY", "Address Verification", "POA Doc", "Address Proof"]
        cat = _null_or(_messy_whitespace(random.choice(categories)), null_chance=0.08)

        rows.append({
            "cust":          _messy_whitespace(s["customer_id"]),
            "document_type": _messy_poa_doc_type(poa),
            "issue_dt":      _null_or(_messy_date(issue_dt), null_chance=0.1),
            "exp_dt":        _null_or(_messy_date(expiry_dt), null_chance=0.1),
            "doc_category":  cat,
            # Junk columns
            "uploaded_by":   _rand_username(),
            "file_ref":      _null_or(f"FILE-{_rand_legacy_id()}", null_chance=0.3),
        })
    return rows


def _build_transactions_raw(scenarios: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Messy transaction summary rows."""
    rows = []
    for s in scenarios:
        base_dt = datetime.fromisoformat(s["generated_at"].replace("Z", "+00:00"))
        last_txn = base_dt - timedelta(days=random.randint(0, 60))
        activity = s.get("activity_state", "NORMAL")

        txn_counts = {"NORMAL": (1, 50), "ELEVATED": (51, 200),
                      "HIGH_VOLUME": (201, 1000), "DORMANT": (0, 5)}
        lo, hi = txn_counts.get(activity, (1, 50))
        count = random.randint(lo, hi)
        volume = round(count * random.uniform(500, 50000), 2)

        # Messy volume formatting
        vol_str = random.choice([
            f"{volume:,.2f}", f"${volume:,.0f}", f"{volume:.0f}",
            f"USD {volume:,.2f}", f"{volume / 1000:.1f}K",
        ])

        rows.append({
            "client_id":  _messy_whitespace(s["customer_id"]),
            "last_txn":   _null_or(_messy_date(last_txn), null_chance=0.05),
            "txn_count":  _null_or(str(count), null_chance=0.08),
            "volume_$":   _null_or(vol_str, null_chance=0.08),
            "currency":   _null_or(
                random.choice(["USD", "USD", "USD", "GBP", "EUR", "SGD", "AED", "CHF"]),
                null_chance=0.05
            ),
            # Junk
            "flags":      _null_or(
                random.choice(["", "", "", "REVIEW", "STR Filed", "PEP",
                               "High Value", "Cross-border", "n/a"]),
                null_chance=0.3
            ),
        })
    return rows


def _build_beneficial_owners_raw(scenarios: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Messy beneficial ownership rows — only for corporates or UBO_DECLARED."""
    rows = []
    for s in scenarios:
        is_corp = s.get("customer_type") == "CORPORATE"
        ubo = s.get("ubo_state", "NOT_APPLICABLE")
        if not is_corp and ubo == "NOT_APPLICABLE":
            continue

        base_dt = datetime.fromisoformat(s["generated_at"].replace("Z", "+00:00"))
        identified_dt = base_dt - timedelta(days=random.randint(0, 365))

        n_ubos = random.randint(1, 3) if is_corp else 1
        for _ in range(n_ubos):
            nationality = _null_or(random.choice(_COUNTRIES), null_chance=0.1)
            rows.append({
                "cust":          _messy_whitespace(s["customer_id"]),
                "Owner Name":    _null_or(_messy_whitespace(_rand_name("INDIVIDUAL")),
                                          null_chance=0.05),
                "Ownership %":   _null_or(_messy_ownership_pct(), null_chance=0.1),
                "nationality":   nationality,
                "identified":    _null_or(_messy_date(identified_dt), null_chance=0.08),
                # Junk
                "verified_by":   _rand_username(),
                "pep_flag":      _null_or(random.choice(["Y", "N", "N", "N", ""]),
                                          null_chance=0.2),
            })
    return rows


# ── CSV writer ────────────────────────────────────────────────────────────────

def _write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        path.write_text("no_data\n", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_demo_portfolio(size: int, run_id: Optional[str] = None) -> str:
    """
    Generate a demo portfolio.

    Returns the absolute path to scenario_manifest.jsonl (unchanged behaviour).
    Also writes messy raw KYC CSVs to benchmarks/output/raw_kyc_tables/.
    """
    run_id = run_id or _default_run_id()
    out_file = OUTPUT_FILE

    _ = load_generator_matrix()
    constraints_cfg = load_constraint_catalog()
    archetypes_cfg  = load_scenario_archetypes()

    constraints = constraints_cfg.get("constraints", [])
    archetypes  = archetypes_cfg.get("archetypes", [])
    if not archetypes:
        raise ValueError("No archetypes found in benchmarks/config/kyc_scenario_archetypes.json")

    print(f"Loaded {len(archetypes)} archetypes.")

    weighted = _build_weighted_archetypes(archetypes)
    weighted  = _build_weighted_archetypes(archetypes)
    scenarios: List[Dict[str, Any]] = []
    for i in range(1, size + 1):
        selected = random.choice(weighted)
        scenario = _build_scenario(selected, i, run_id)
        scenario = _apply_constraints(scenario, constraints)
        scenarios.append(scenario)

    # For validation convenience in v1: ensure at least one BLOCKED sample if S021 exists.
    has_s021 = any(c.get("constraint_id") == "S021" for c in constraints)
    if has_s021 and scenarios and not any(s.get("aml_state") == "BLOCKED" for s in scenarios):
        scenarios[0]["aml_state"] = "BLOCKED"
        scenarios[0] = _apply_constraints(scenarios[0], constraints)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for scenario in scenarios:
            f.write(json.dumps(scenario) + "\n")
    print(f"Wrote {len(scenarios)} scenarios to {out_file}")

    # ── Write messy raw KYC tables ────────────────────────────────────────────
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    tables = {
        "customers_raw.csv":          _build_customers_raw(scenarios),
        "screenings_raw.csv":         _build_screenings_raw(scenarios),
        "id_verifications_raw.csv":   _build_id_verifications_raw(scenarios),
        "documents_raw.csv":          _build_documents_raw(scenarios),
        "transactions_raw.csv":       _build_transactions_raw(scenarios),
        "beneficial_owners_raw.csv":  _build_beneficial_owners_raw(scenarios),
    }

    for filename, rows in tables.items():
        path = RAW_DIR / filename
        _write_csv(path, rows)
        print(f"Wrote {len(rows)} rows to {path.name}")

    return str(out_file.resolve())


def get_raw_table_paths() -> Dict[str, Path]:
    """Return paths to the raw messy CSVs (if they exist)."""
    return {
        p.stem: p
        for p in RAW_DIR.glob("*_raw.csv")
        if p.exists()
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate demo KYC scenario portfolio with messy raw tables."
    )
    parser.add_argument("--size",   type=int, default=30,  help="Number of scenarios.")
    parser.add_argument("--run-id", type=str, default=None, help="Optional run identifier.")
    args = parser.parse_args()
    generate_demo_portfolio(size=args.size, run_id=args.run_id)


if __name__ == "__main__":
    main()
