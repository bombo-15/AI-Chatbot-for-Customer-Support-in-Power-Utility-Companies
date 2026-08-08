"""
Seed a realistic demo dataset into the ecg_outages table (the "live scraped
data" side of the Outage Status board).

Why this exists: ECG's site (ecg.com.gh) sits behind an Imperva WAF that
currently 403s the scraper on every request (see ecg_scraper.py / main.py's
_background_scrape). Until that's resolved, the live table stays empty and
the board only shows the 5 static rows seeded in database.py's init_db(),
frozen at March 2026. This fills ecg_outages with a hand-built set of entries
shaped exactly like what scrape_outages() would return, dated relative to
"now" so the board looks current whenever build_demo_outages() is called.

Safe to re-run: it goes through db.sync_ecg_outages(), the same path the
real scraper uses, so it fully replaces whatever demo/live data is there.
Once seeded, the hourly scrape loop's failure-safe logic (log_scrape_failure)
will NOT wipe this data just because ECG's WAF is still blocking requests —
it only gets replaced by a future successful scrape or another seed call.

Usage:
    python seed_demo_outages.py                       (local CLI)
    POST /admin/seed-demo-outages  (Bearer admin token) — same effect, remote
"""

from datetime import datetime, timedelta

import database as db


def build_demo_outages(now: datetime | None = None) -> list[dict]:
    """Returns the demo outage list with all dates computed relative to `now`
    (defaults to the current time), so it looks current whenever it's called."""
    now = now or datetime.now()

    def iso(delta: timedelta) -> str:
        return (now + delta).strftime("%Y-%m-%dT%H:%M:%S")

    return [
        {
            "area": "Accra East",
            "type": "unplanned",
            "start_time": iso(timedelta(hours=-3)),
            "estimated_restoration": iso(timedelta(hours=2)),
            "affected_customers": 2400,
            "status": "active",
            "cause": "Broken high-tension (HT) pole",
            "source_title": "Emergency Notice: Broken HT Pole Affecting Parts Of Accra East Region",
        },
        {
            "area": "Accra West",
            "type": "unplanned",
            "start_time": iso(timedelta(hours=-1, minutes=-20)),
            "estimated_restoration": iso(timedelta(hours=4)),
            "affected_customers": 1850,
            "status": "active",
            "cause": "Fault on Dansoman feeder",
            "source_title": "Power Outage Notice: Fault On The Dansoman Feeder",
        },
        {
            "area": "Tema",
            "type": "scheduled",
            "start_time": iso(timedelta(days=1, hours=6)),
            "estimated_restoration": iso(timedelta(days=1, hours=14)),
            "affected_customers": 960,
            "status": "scheduled",
            "cause": "Scheduled maintenance",
            "source_title": "Planned Maintenance Notice: Tema Industrial Area Substation Upgrade",
        },
        {
            "area": "Ashanti",
            "type": "unplanned",
            "start_time": iso(timedelta(hours=-18)),
            "estimated_restoration": iso(timedelta(hours=-2)),
            "affected_customers": 3100,
            "status": "resolved",
            "cause": "Transformer fault",
            "source_title": "Update: Kumasi Ridge Transformer Fault Restored",
        },
        {
            "area": "Eastern",
            "type": "unplanned",
            "start_time": iso(timedelta(hours=-6)),
            "estimated_restoration": iso(timedelta(hours=6)),
            "affected_customers": 1420,
            "status": "active",
            "cause": "Upstream network issue (GRIDCo)",
            "source_title": "Power Outage Due To Technical Challenges From GRIDCo Affecting Eastern Region BSPs",
        },
        {
            "area": "Western",
            "type": "scheduled",
            "start_time": iso(timedelta(days=2)),
            "estimated_restoration": iso(timedelta(days=2, hours=8)),
            "affected_customers": 780,
            "status": "scheduled",
            "cause": "Scheduled maintenance",
            "source_title": "Planned Maintenance Notice: Takoradi District Network Upgrade",
        },
        {
            "area": "Volta",
            "type": "unplanned",
            "start_time": iso(timedelta(hours=-30)),
            "estimated_restoration": iso(timedelta(hours=-20)),
            "affected_customers": 640,
            "status": "resolved",
            "cause": "Cable fault repaired",
            "source_title": "Update: Ho Township Underground Cable Fault Restored",
        },
        {
            "area": "Central",
            "type": "unplanned",
            "start_time": iso(timedelta(minutes=-45)),
            "estimated_restoration": iso(timedelta(hours=3)),
            "affected_customers": 1100,
            "status": "active",
            "cause": "Fire outbreak near equipment",
            "source_title": "Emergency Notice: Fire Outbreak Near Cape Coast Substation Equipment",
        },
    ]


def main() -> None:
    db.init_db()
    demo_outages = build_demo_outages()
    count = db.sync_ecg_outages(
        demo_outages,
        error_detail="Demo dataset (ECG site blocked by WAF — seeded via seed_demo_outages.py)",
    )
    print(f"Seeded {count} demo outages into ecg_outages")
    for o in demo_outages:
        print(f"  [{o['status']:9s}] {o['area']:12s} — {o['cause']}")


if __name__ == "__main__":
    main()
