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


def main():
    year = pd.Timestamp.utcnow().year
    # load schedule and pick the last completed event
    sched = fastf1.get_event_schedule(year, include_testing=False)
    done  = sched[sched["Session1Date"] < pd.Timestamp.utcnow()]
    ev    = done.iloc[-1]

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
            ("SPRINT QUALIFYING",  "SQ"),
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
            sess.load()
            print(f"Loaded {tag}")
        except Exception as e:
            print(f"Could not load {tag}: {e}")
            # clear out that section so old images disappear
            update_readme_section(tag, [])
            continue

        # create the folder & images list
        folder = create_folder(year_gp, tag)
        imgs = []

        # QUALI and SPRINT QUALIFYING both follow the same “top-2 + custom order” logic
        if tag in ("QUALIFYING", "SPRINT QUALIFYING"):
            # pick top-2 fastest laps
            bests = []
            for drv in sess.laps["Driver"].unique():
                fl = sess.laps.pick_drivers(drv).pick_fastest()
                if fl is not None:
                    bests.append((drv, fl["LapTime"].total_seconds()))
            bests.sort(key=lambda x: x[1])
            d1, d2 = bests[0][0], bests[1][0]
            bespoke = [
                (quali_result,         (sess, os.path.join(folder, "quali_result.png"))),
                (telemetry_comparison, (sess, d1, d2,   os.path.join(folder, "telemetry.png"))),
                (track_domination,     (sess, d1, d2,   os.path.join(folder, "track_domination.png"))),
                (sector_gap,           (sess, os.path.join(folder, "sector_gap.png"))),
                (top_speed_comparison, (sess, os.path.join(folder, "top_speed_comparison.png"))),
                (aero_performance,     (sess, os.path.join(folder, "aero_performance.png"))),
            ]
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
        text = open("README.md", "r", encoding="utf-8").read()
        text = re.sub(
            r"<details>\s*<summary><strong>Sprint Shootout.*?</details>\s*",
            "", text, flags=re.DOTALL
        )
        text = re.sub(
            r"<details>\s*<summary><strong>Sprint Race.*?</details>\s*",
            "", text, flags=re.DOTALL
        )
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(text)

    # Clear out FP2 & FP3 on sprint weekends
    if is_sprint:
        print("Clearing FP2 section for sprint weekend")
        update_readme_section("FP2", [])
        print("Clearing FP3 section for sprint weekend")
        update_readme_section("FP3", [])
        

if __name__ == "__main__":
    main()
