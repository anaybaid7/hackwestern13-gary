#!/usr/bin/env python3
"""check_db.py - is the database ready for Gary, and is Tiger Data really in use?

    export DATABASE_URL='postgres://tsdbadmin:...@...tsdb.cloud.timescale.com:.../tsdb?sslmode=require'
    python3 backend/check_db.py

It creates Gary's tables if they are missing and changes nothing else. Run it
once after you get the connection string, and paste the output into issue #16.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import app  # noqa: E402  (reads .env, the labels and the timezone)
import store as stores  # noqa: E402


def main():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("DATABASE_URL is not set. Put it in backend/.env or export it, then run this again.")
        return 1
    try:
        store = stores.PostgresStore(url, app.CONTRACT / "examples" / "quests.json") if app.store.kind != "postgres" else app.store
    except Exception as exc:
        print("Could not connect or set up the tables: %s" % exc)
        return 1
    ok = True
    with store.conn.cursor() as cur:
        cur.execute("SELECT version()")
        print("Connected: %s" % cur.fetchone()[0].split(",")[0])
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        row = cur.fetchone()
    print("TimescaleDB extension: %s" % (row[0] if row else "NOT INSTALLED (this is a plain Postgres)"))
    print("events is a hypertable on ts: %s" % ("yes" if store.hypertable else "NO"))
    ok = ok and bool(row) and store.hypertable
    try:
        days = store._outdoor(store.OUTDOOR_TIME_BUCKET, {"tz": app.TZ_NAME, "labels": app.OUTDOOR_LABELS})
        print("time_bucket query for outdoor minutes per day: ok (%d day%s of data)"
              % (len(days), "" if len(days) == 1 else "s"))
    except Exception as exc:
        ok = False
        print("time_bucket query: FAILED (%s)" % str(exc).strip().splitlines()[0])
    counts = store.counts()
    print("Rows: %d events, %d quests, %d mood check-ins" % (counts["events"], counts["quests"], len(store.moods())))
    print()
    if ok:
        print("Ready. With DATABASE_URL set, the API keeps everything here and a restart keeps Gary's state.")
    else:
        print("The API will still work on this database: events stays an ordinary table and the outdoor "
              "minutes use plain SQL. But it is not using Tiger Data's hypertable or time_bucket yet.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
