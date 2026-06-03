# readme_machine.py
import os
import re
import pandas as pd
import fastf1
from fastf1 import get_session
from visualization import (
    tyre_strategy, sector_gap, top_speed_comparison,
    quali_result, pos_change, team_pace, tyre_deg,
    telemetry_comparison, track_domination,
    plot_top_speed_heatmap, aero_performance
)

# Use a local cache folder
fastf1.Cache.enable_cache("cache")


def create_folder(year_gp, session):
    folder = os.path.join("visualization", year_gp, session)
    os.makedirs(folder, exist_ok=True)
    return folder


def update_readme_section(tag, image_paths):
    with open("README.md", "r", encoding="utf-8") as f:
        txt = f.read()
    md = "\n".join(f"![{os.path.basename(p)}]({p})" for p in image_paths)
    section = f"<!-- {tag}_START -->\n{md}\n<!-- {tag}_END -->"
    new = re.sub(
        rf"<!-- {tag}_START -->.*?<!-- {tag}_END -->",
        section,
        txt,
        flags=re.DOTALL
    )
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new)


def get_latest_event():
    # auto‐pick current year
    year = pd.Timestamp.utcnow().year
    sched = fastf1.get_event_schedule(year, include_testing=False)
    done  = sched[sched["Session1Date"] < pd.Timestamp.utcnow()]
    return year, done.iloc[-1]

def get_latest_event_with_fastf1_data(year):
    now = pd.Timestamp.now(tz="UTC")
    sched = fastf1.get_event_schedule(year, include_testing=False).copy()

    session_cols = [c for c in sched.columns if re.fullmatch(r"Session\d+Date", str(c))]
    for c in session_cols:
        sched[c] = pd.to_datetime(sched[c], errors="coerce", utc=True)

    sched["__last_session_dt"] = sched[session_cols].max(axis=1)

    done = (
        sched[sched["__last_session_dt"].notna() & (sched["__last_session_dt"] < now)]
        .sort_values("__last_session_dt", ascending=False)
    )

    for _, ev in done.iterrows():
        try:
            test_sess = get_session(year, ev["EventName"], "R")
            test_sess.load(laps=True, telemetry=False, weather=False, messages=False)

            if has_lap_data(test_sess):
                return ev

            print(f"Skipping {ev['EventName']}: no usable race lap data yet.")
        except Exception as e:
            print(f"Skipping {ev['EventName']}: {e}")

    return None

def get_top_two_drivers(sess):
    try:
        res = sess.results
        if res is not None and not res.empty and "Abbreviation" in res.columns:
            drivers = res["Abbreviation"].dropna().astype(str).tolist()
            if len(drivers) >= 2:
                return drivers[0], drivers[1]
    except Exception as e:
        print(f"Could not use session results: {e}")

    try:
        laps = sess.laps
        if laps is not None and not laps.empty and {"Driver", "LapTime"}.issubset(laps.columns):
            best = (
                laps.dropna(subset=["LapTime"])
                    .sort_values("LapTime")
                    .drop_duplicates("Driver")
            )
            drivers = best["Driver"].dropna().astype(str).tolist()

            if len(drivers) >= 2:
                return drivers[0], drivers[1]
    except Exception as e:
        print(f"Could not use lap data for top-two drivers: {e}")

    return None, None

def has_lap_data(sess):
    try:
        laps = sess.laps
        return laps is not None and not laps.empty
    except Exception:
        return False


def has_result_data(sess):
    try:
        res = sess.results
        return res is not None and not res.empty
    except Exception:
        return False

def main():
    year = pd.Timestamp.now(tz="UTC").year

    ev = get_latest_event_with_fastf1_data(year)
    if ev is None:
        print(f"No completed events yet for {year}. Leaving README unchanged.")
        return

    fmt   = str(ev.get("EventFormat", "")).strip().lower()
    is_sprint = "sprint" in fmt
    print(f"\n=== {year} {ev['EventName']} (format={ev['EventFormat']}) ===")
    print(f"Detected sprint weekend? {is_sprint}\n")

    gp      = ev["EventName"].replace(" ", "_")
    year_gp = f"{year}_{gp}"


    # which plots apply to each non-quali session
    session_plots = {
        "FP1":       [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "FP2":       [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "FP3":       [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "SPRINT":    [pos_change, tyre_strategy, team_pace, tyre_deg],
        "RACE":      [pos_change, tyre_strategy, team_pace, tyre_deg],
    }

    # pick the list of sessions based on sprint flag
    if is_sprint:
        sessions = [
            ("FP1",                "FP1"),
            ("SPRINT_QUALIFYING",  "SQ"),
            ("SPRINT",             "S"),
            ("QUALIFYING",         "Q"),
            ("RACE",               "R"),
        ]
    else:
        sessions = [
            ("FP1",       "FP1"),
            ("FP2",       "FP2"),
            ("FP3",       "FP3"),
            ("QUALIFYING","Q"),
            ("RACE",      "R"),
        ]

    for tag, code in sessions:
        print(f"── Attempting session: {tag}  (code={code})  ──")
        # try to load the session
        try:
            sess = get_session(year, ev["EventName"], code)
            sess.load(laps=True, telemetry=True, weather=True, messages=True)
            print(f"Loaded {tag}")
        except Exception as e:
            print(f"Could not load {tag}: {e}")
            update_readme_section(tag, [])
            continue
        
        if not has_lap_data(sess) and not has_result_data(sess):
            print(f"Skipping {tag}: FastF1 loaded metadata, but no usable laps/results are available.")
            update_readme_section(tag, [])
            continue

        # create the folder & images list
        folder = create_folder(year_gp, tag)
        imgs = []

        # QUALI and SPRINT QUALIFYING both follow the same “top-2 + custom order” logic
        if tag in ("QUALIFYING", "SPRINT_QUALIFYING"):
            d1, d2 = get_top_two_drivers(sess)
        
            bespoke = [
                (quali_result,         (sess, os.path.join(folder, "quali_result.png"))),
                (sector_gap,           (sess, os.path.join(folder, "sector_gap.png"))),
                (top_speed_comparison, (sess, os.path.join(folder, "top_speed_comparison.png"))),
                (aero_performance,     (sess, os.path.join(folder, "aero_performance.png"))),
            ]
        
            if d1 is not None and d2 is not None:
                bespoke.insert(1, (telemetry_comparison, (sess, d1, d2, os.path.join(folder, "telemetry.png"))))
                bespoke.insert(2, (track_domination,     (sess, d1, d2, os.path.join(folder, "track_domination.png"))))
            else:
                print(f"Skipping driver comparison plots for {tag}: fewer than 2 drivers available.")
        
            for fn, args in bespoke:
                print(f"  ▶️ {fn.__name__} for {tag} …")
                try:
                    fn(*args)
                    imgs.append(args[-1])
                    print("success")
                except Exception as e:
                    print(f"failed: {e}")
                    
        else:
            # all other sessions from session_plots
            for fn in session_plots.get(tag, []):
                out = os.path.join(folder, f"{fn.__name__}.png")
                print(f"  ▶️ {fn.__name__} for {tag} …")
                try:
                    fn(sess, out)
                    imgs.append(out)
                    print("success")
                except Exception as e:
                    print(f"failed: {e}")

        # finally, always update the README section
        update_readme_section(tag, imgs)
        print(f"★ README section {tag} updated with {len(imgs)} images\n")

    # cleanup empty sprint blocks on a normal weekend
    if not is_sprint:
        print("Clearing Sprint Quali section for sprint weekend")
        update_readme_section("SPRINT_QUALIFYING", [])
        print("Clearing Sprint section for sprint weekend")
        update_readme_section("SPRINT", [])

    # Clear out FP2 & FP3 on sprint weekends
    if is_sprint:
        print("Clearing FP2 section for sprint weekend")
        update_readme_section("FP2", [])
        print("Clearing FP3 section for sprint weekend")
        update_readme_section("FP3", [])
        

if __name__ == "__main__":
    main()
