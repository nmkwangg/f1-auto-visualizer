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
    year, ev = get_latest_event()
    gp       = ev["EventName"].replace(" ", "_")
    year_gp  = f"{year}_{gp}"

    # define which plots for each session
    session_plots = {
        "FP1":         [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "FP2":         [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "FP3":         [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "QUALIFYING":  [quali_result, sector_gap, top_speed_comparison, aero_performance],
        "RACE":        [pos_change, tyre_strategy, team_pace, tyre_deg],
    }

    # list of sessions to run
    sessions = [
        ("FP1",       "FP1"),
        ("FP2",       "FP2"),
        ("FP3",       "FP3"),
        ("QUALIFYING","Q"),
        ("RACE",      "R")
    ]

    for tag, code in sessions:
        try:
            sess = get_session(year, ev["EventName"], code)
            sess.load()
            folder = create_folder(year_gp, tag)
            imgs = []

            # 1) run all simple plots for this session
            for fn in session_plots[tag]:
                out = os.path.join(folder, f"{fn.__name__}.png")
                fn(sess, out)
                imgs.append(out)

            # 2) Quali only: compare top-2 qualifiers
            if tag == "QUALIFYING":
                # pick top 2 by fastest lap (fallback regardless of Q3Time)
                bests = []
                for drv in sess.laps["Driver"].unique():
                    fl = sess.laps.pick_drivers(drv).pick_fastest()
                    if fl is not None:
                        bests.append((drv, fl["LapTime"].total_seconds()))
                bests.sort(key=lambda x: x[1])
                if len(bests) >= 2:
                    d1, d2 = bests[0][0], bests[1][0]
                    p = os.path.join(folder, "telemetry.png")
                    telemetry_comparison(sess, d1, d2, p)
                    imgs.append(p)

            # 3) update README for this section
            update_readme_section(tag, imgs)

        except Exception as e:
            print(f"⚠️ Skipping {tag}: {e}")


if __name__ == "__main__":
    main()
