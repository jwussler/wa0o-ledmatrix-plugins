#!/usr/bin/env python3
"""
Test script for Weather Alerts plugin v2.0

TIER 1 (full takeover):  tornado, severe, flood
TIER 2 (3 cards):        watch, winter
TIER 3 (1 card):         advisory

Usage:
  python3 test_alerts.py tornado     # T1 - tornado warning (FULL TAKEOVER)
  python3 test_alerts.py severe      # T1 - severe t-storm warning (FULL TAKEOVER)
  python3 test_alerts.py flood       # T1 - flash flood warning (FULL TAKEOVER)
  python3 test_alerts.py watch       # T2 - tornado watch (3 cards)
  python3 test_alerts.py winter      # T2 - winter storm warning (3 cards)
  python3 test_alerts.py advisory    # T3 - wind advisory (1 card)
  python3 test_alerts.py multi       # Mix of T1 + T2 + T3
  python3 test_alerts.py clear       # Remove test alerts
  python3 test_alerts.py status      # Check status
"""
import json
import sys
import os
from datetime import datetime, timezone, timedelta

TEST_FILE = "/tmp/weather_alert_test.json"
PRIORITY_FILE = "/tmp/ledmatrix_weather_alert_active"


def make_alert(event, severity, urgency, headline, description, instruction, hours_left=4):
    now = datetime.now(timezone.utc)
    return {
        "event": event,
        "severity": severity,
        "urgency": urgency,
        "certainty": "Observed" if severity in ("Extreme", "Severe") else "Likely",
        "headline": headline,
        "description": description,
        "instruction": instruction,
        "onset": (now - timedelta(hours=1)).isoformat(),
        "expires": (now + timedelta(hours=hours_left)).isoformat(),
        "sender": "NWS St. Louis MO",
        "areas": "Your County",
    }


SCENARIOS = {
    # ===== TIER 1 - FULL TAKEOVER =====
    "tornado": [
        make_alert(
            "Tornado Warning", "Extreme", "Immediate",
            "Tornado Warning issued for Your County until 8:00 PM CST",
            "At 4:15 PM CST a severe thunderstorm capable of producing a tornado "
            "was located near Your Area moving northeast at 45 mph. Flying debris "
            "will be dangerous to those caught without shelter.",
            "TAKE SHELTER NOW! Move to a basement or interior room on the lowest "
            "floor of a sturdy building. Avoid windows.",
            hours_left=1,
        )
    ],
    "severe": [
        make_alert(
            "Severe Thunderstorm Warning", "Severe", "Immediate",
            "Severe Thunderstorm Warning for Your County until 9:00 PM CST",
            "At 5:30 PM a severe thunderstorm near Weldon Spring moving east at "
            "35 mph. 70 mph wind gusts and ping pong ball size hail.",
            "Move to an interior room on the lowest floor of a building.",
            hours_left=3,
        )
    ],
    "flood": [
        make_alert(
            "Flash Flood Warning", "Severe", "Immediate",
            "Flash Flood Warning for Your County until 11:00 PM CST",
            "Flash flooding occurring along Dardenne Creek. Up to 4 inches of "
            "rain has fallen with additional heavy rain expected.",
            "Turn around dont drown. Move to higher ground now.",
            hours_left=5,
        )
    ],

    # ===== TIER 2 - 3 CARDS =====
    "watch": [
        make_alert(
            "Tornado Watch", "Severe", "Expected",
            "Tornado Watch for eastern Missouri until 10:00 PM CST",
            "Conditions are favorable for tornadoes and severe thunderstorms "
            "in the watch area.",
            "Be prepared to move to shelter if a warning is issued.",
            hours_left=6,
        )
    ],
    "winter": [
        make_alert(
            "Winter Storm Warning", "Moderate", "Expected",
            "Winter Storm Warning in effect Friday evening through Saturday",
            "Heavy snow expected. Total accumulations of 5 to 8 inches. "
            "Travel could be very difficult to impossible.",
            "If you must travel keep extra supplies in your vehicle.",
            hours_left=18,
        )
    ],

    # ===== TIER 3 - 1 CARD =====
    "advisory": [
        make_alert(
            "Wind Advisory", "Minor", "Expected",
            "Wind Advisory in effect until 6 PM CST Saturday",
            "Southwest winds 25 to 35 mph with gusts up to 55 mph.",
            "Secure outdoor objects. Use caution when driving.",
            hours_left=8,
        )
    ],

    # ===== MIXED =====
    "multi": [
        make_alert(
            "Tornado Warning", "Extreme", "Immediate",
            "Tornado Warning for Your County",
            "Tornado producing storm near OFallon moving northeast at 40 mph.",
            "TAKE SHELTER NOW!",
            hours_left=1,
        ),
        make_alert(
            "Severe Thunderstorm Watch", "Severe", "Expected",
            "Severe Thunderstorm Watch until 10 PM CST",
            "Conditions favorable for severe storms with large hail.",
            "Monitor conditions and be ready to shelter.",
            hours_left=6,
        ),
        make_alert(
            "Wind Advisory", "Minor", "Expected",
            "Wind Advisory through Saturday morning",
            "Gusts up to 50 mph expected.",
            "Secure loose objects.",
            hours_left=12,
        ),
    ],

    # ===== DUAL T1 - shows priority weighting =====
    "dual": [
        make_alert(
            "Tornado Warning", "Extreme", "Immediate",
            "Tornado Warning for Your County until 7:00 PM CST",
            "At 5:15 PM CST a confirmed tornado was located near OFallon "
            "moving northeast at 40 mph. This is a particularly dangerous "
            "situation. Flying debris will be dangerous to those caught "
            "without shelter. Mobile homes will be destroyed.",
            "TAKE SHELTER NOW! Move to a basement or interior room on the "
            "lowest floor. If in a mobile home GET OUT and find sturdy shelter.",
            hours_left=1,
        ),
        make_alert(
            "Severe Thunderstorm Warning", "Severe", "Immediate",
            "Severe Thunderstorm Warning for Your County until 8:30 PM",
            "A severe thunderstorm was located near Wentzville moving east "
            "at 35 mph. 70 mph wind gusts and golf ball size hail expected.",
            "Move to an interior room on the lowest floor of a building.",
            hours_left=3,
        ),
    ],
}

TIER_MAP = {
    "tornado": "TIER 1 - FULL TAKEOVER  (weight 6 = ~25 cards)",
    "severe": "TIER 1 - FULL TAKEOVER  (weight 2 = ~10 cards)",
    "flood": "TIER 1 - FULL TAKEOVER  (weight 4 = ~18 cards)",
    "watch": "TIER 2 - Significant (3 cards)",
    "winter": "TIER 2 - Significant (3 cards)",
    "advisory": "TIER 3 - Minor (1 card)",
    "multi": "MIXED - T1 + T2 + T3",
    "dual": "DUAL T1 - Tornado(w6) + SVR Tstorm(w2) - shows weighting",
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == "clear":
        for f in [TEST_FILE, PRIORITY_FILE]:
            try:
                os.remove(f)
                print(f"Removed {f}")
            except FileNotFoundError:
                print(f"{f} already clear")
            except PermissionError:
                # Priority file may be owned by root (ledmatrix service)
                import subprocess
                subprocess.run(["sudo", "rm", "-f", f])
                print(f"Removed {f} (sudo)")
        print("\nTest alerts cleared!")
        print("Restart: sudo systemctl restart ledmatrix")
        return

    if cmd == "status":
        print("=== Weather Alert Status ===")
        if os.path.exists(TEST_FILE):
            with open(TEST_FILE) as f:
                alerts = json.load(f)
            print(f"TEST MODE: {len(alerts)} alert(s)")
            for a in alerts:
                print(f"  {a['event']} ({a['severity']})")
        else:
            print("No test alerts active")
        if os.path.exists(PRIORITY_FILE):
            with open(PRIORITY_FILE) as f:
                print(f"Priority: {json.load(f)}")
        else:
            print("Priority: inactive")
        return

    if cmd not in SCENARIOS:
        print(f"Unknown: {cmd}")
        print(f"Options: {', '.join(list(SCENARIOS.keys()) + ['clear', 'status'])}")
        return

    alerts = SCENARIOS[cmd]
    with open(TEST_FILE, "w") as f:
        json.dump(alerts, f, indent=2)

    print(f"Injected: {cmd} -> {TIER_MAP.get(cmd, '?')}")
    for a in alerts:
        print(f"  {a['event']} ({a['severity']})")
    print(f"\nRestart: sudo systemctl restart ledmatrix")
    print(f"Clear:   python3 {sys.argv[0]} clear")


if __name__ == "__main__":
    main()
