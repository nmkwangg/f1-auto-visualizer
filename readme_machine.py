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
    is_sprint = pd.notna(ev.get("SprintShootoutDate"))
    gp       = ev["EventName"].replace(" ", "_")
    year_gp  = f"{year}_{gp}"

    session_plots = {
        "FP1":       [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "FP2":       [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "FP3":       [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
        "SPRINT":    [pos_change, tyre_strategy, team_pace, tyre_deg],
        "RACE":      [pos_change, tyre_strategy, team_pace, tyre_deg],
    }

    if is_sprint:
        sessions = [
            ("FP1",       "FP1"),
            ("SPRINT QUALIFYING",  "SQ"),
            ("SPRINT",    "S"),
            ("QUALIFYING","Q"),
            ("RACE",      "R")
        ]
    else:
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

            if tag == "QUALIFYING":
                # 1) pick top-2 fastest laps
                bests = []
                for drv in sess.laps["Driver"].unique():
                    fl = sess.laps.pick_drivers(drv).pick_fastest()
                    if fl is not None:
                        bests.append((drv, fl["LapTime"].total_seconds()))
                bests.sort(key=lambda x: x[1])
                d1, d2 = bests[0][0], bests[1][0]

                # 2) draw in THIS exact order:
                qual_funcs = [
                    (quali_result,         (sess, os.path.join(folder, "quali_result.png"))),
                    (telemetry_comparison, (sess, d1, d2,   os.path.join(folder, "telemetry.png"))),
                    (track_domination,     (sess, d1, d2,   os.path.join(folder, "track_domination.png"))),
                    (sector_gap,           (sess, os.path.join(folder, "sector_gap.png"))),
                    (top_speed_comparison, (sess, os.path.join(folder, "top_speed_comparison.png"))),
                    (aero_performance,     (sess, os.path.join(folder, "aero_performance.png"))),
                ]
                for fn, args in qual_funcs:
                    fn(*args)
                    imgs.append(args[-1])
                    
            elif tag == "SPRINT QUALIFYING":
                # 1) pick top-2 fastest laps
                bests = []
                for drv in sess.laps["Driver"].unique():
                    fl = sess.laps.pick_drivers(drv).pick_fastest()
                    if fl is not None:
                        bests.append((drv, fl["LapTime"].total_seconds()))
                bests.sort(key=lambda x: x[1])
                d1, d2 = bests[0][0], bests[1][0]

                # 2) draw in THIS exact order:
                qual_funcs = [
                    (quali_result,         (sess, os.path.join(folder, "quali_result.png"))),
                    (telemetry_comparison, (sess, d1, d2,   os.path.join(folder, "telemetry.png"))),
                    (track_domination,     (sess, d1, d2,   os.path.join(folder, "track_domination.png"))),
                    (sector_gap,           (sess, os.path.join(folder, "sector_gap.png"))),
                    (top_speed_comparison, (sess, os.path.join(folder, "top_speed_comparison.png"))),
                    (aero_performance,     (sess, os.path.join(folder, "aero_performance.png"))),
                ]
                for fn, args in qual_funcs:
                    fn(*args)
                    imgs.append(args[-1])

            else:
                # all other sessions use the generic mapping
                for fn in session_plots[tag]:
                    out = os.path.join(folder, f"{fn.__name__}.png")
                    print(f"▶️ Running {fn.__name__} for {tag} ...")
                    try:
                        fn(sess, out)
                        imgs.append(out)
                        print(f"✅ {fn.__name__} completed for {tag}")
                    except Exception as e:
                        print(f"⚠️ {fn.__name__} FAILED for {tag}: {e}")

            update_readme_section(tag, imgs)

        except Exception as e:
            print(f"⚠️ Skipping {tag}: {e}")

    #Cleanup for normal weekends
    if not is_sprint:
        text = open("README.md","r",encoding="utf-8").read()
        # remove the SHOOTOUT block
        text = re.sub(
            r"<details>\s*<summary><strong>Sprint Shootout.*?</details>\s*",
            "", text, flags=re.DOTALL
        )
        # remove the SPRINT block
        text = re.sub(
            r"<details>\s*<summary><strong>Sprint Race.*?</details>\s*",
            "", text, flags=re.DOTALL
        )
        open("README.md","w",encoding="utf-8").write(text)
        
if __name__ == "__main__":
    main()
