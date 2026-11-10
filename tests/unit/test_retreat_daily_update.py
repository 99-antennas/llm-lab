import pytest

from hermes_scripts import retreat_daily_update as upd

KAS = {"id": "U0GEPK3FW", "name": "kas", "real_name": "Kas Stohr", "handle": "kas"}
RAY = {"id": "U0577L3CTT9", "name": "Ray McLendon", "handle": "ray"}
NICK1 = {"id": "U0N1", "name": "Nick Muoh", "handle": "nmuoh"}
NICK2 = {"id": "U0N2", "name": "Nick Spelger", "handle": "nspelger"}
PEOPLE = [KAS, RAY, NICK1, NICK2]


@pytest.mark.parametrize(("line", "expected"), [
    ('*Co-hosts:* Kas Stohr & Ray McLendon — when instructions reference "co-hosts", they refer to these two.',
     ["Kas Stohr", "Ray McLendon"]),
    ("Co-hosts: Kas, Ray McLendon and Nick Muoh", ["Kas", "Ray McLendon", "Nick Muoh"]),
    ("**Co-host:** Ray McLendon (backup: Kas)", ["Ray McLendon"]),
    ("- cohosts: Kas Stohr + Ray McLendon - TBD", ["Kas Stohr", "Ray McLendon"]),
])
def test_cohosts_from_plan(line, expected):
    plan = f"# Retreat Plan\n\n{line}\n\n## Decisions\n- hosts will pick dates\n"
    assert upd.cohosts_from_plan(plan) == expected


def test_no_cohosts_line():
    assert upd.cohosts_from_plan("# Retreat Plan\n## Attendees\n") == []


def test_env_override(monkeypatch):
    monkeypatch.setenv("RETREAT_COHOSTS", "U0N1, Nick Spelger")
    assert upd.cohosts("*Co-hosts:* Kas Stohr & Ray McLendon") == ["U0N1", "Nick Spelger"]
    monkeypatch.delenv("RETREAT_COHOSTS")
    assert upd.cohosts("*Co-hosts:* Kas Stohr & Ray McLendon") == ["Kas Stohr", "Ray McLendon"]


def test_resolve_cohosts_by_real_name_display_name_or_id():
    resolved, unresolved = upd.resolve_cohosts(["Kas Stohr", "Ray McLendon", "U0N2"], PEOPLE)
    assert resolved == {"U0GEPK3FW": "kas", "U0577L3CTT9": "Ray McLendon", "U0N2": "Nick Spelger"}
    assert unresolved == []


def test_resolve_cohosts_reports_ambiguous_and_unknown():
    resolved, unresolved = upd.resolve_cohosts(["Nick", "Stephanie"], PEOPLE)
    assert resolved == {}
    assert unresolved == ["Nick", "Stephanie"]


def test_build_output_contains_instructions_plan_and_activity():
    out = upd.build_output("Tuesday, November 10", "retreat-planning", "C0CF5QW6YM6",
                           {"U0GEPK3FW": "kas", "U0577L3CTT9": "Ray McLendon"},
                           "# Retreat Plan\n*Co-hosts:* Kas Stohr & Ray McLendon", "- Tue 18:00 kas: hi")
    assert "*Retreat planning update: Tuesday, November 10*" in out
    assert 'mention=[\'U0GEPK3FW\', \'U0577L3CTT9\']' in out
    assert "Co-hosts to tag in step 3: kas (U0GEPK3FW), Ray McLendon (U0577L3CTT9)" in out
    assert "WITHOUT an @" in out and "[SILENT]" in out
    assert "=== PLAN.md (shared retreat plan) ===\n# Retreat Plan" in out
    assert out.endswith("- Tue 18:00 kas: hi")


def test_build_output_empty_activity():
    out = upd.build_output("Tuesday", "retreat-planning", "C1", {"U1": "kas"}, "", "")
    assert "(PLAN.md is empty or missing)" in out
    assert out.endswith("No messages in the last 24 hours.")
