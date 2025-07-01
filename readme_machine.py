# readme_machine.py
import os, re
import pandas as pd
import fastf1
from fastf1 import get_session
from visualization import (   # explicit imports for clarity
    tyre_strategy, sector_gap, top_speed_comparison,
    quali_result, pos_change, team_pace, tyre_deg,
    telemetry_comparison, track_domination, plot_top_speed_heatmap, aero_performance 
)

fastf1.Cache.enable_cache("cache")


def create_folder(year_gp, session):
    path = os.path.join("visualization", year_gp, session)
    os.makedirs(path, exist_ok=True)
    return path


def update_readme_section(tag, image_paths):
    with open("README.md","r",encoding="utf-8") as f:
        txt = f.read()
    md = "\n".join(f"![{os.path.basename(p)}]({p})" for p in image_paths)
    section = f"<!-- {tag}_START -->\n{md}\n<!-- {tag}_END -->"
    new = re.sub(rf"<!-- {tag}_START -->.*?<!-- {tag}_END -->",
                 section, txt, flags=re.DOTALL)
    with open("README.md","w",encoding="utf-8") as f:
        f.write(new)


def get_latest_event():
    sched = fastf1.get_event_schedule(2025, include_testing=False)
    done = sched[sched["Session1Date"] < pd.Timestamp.utcnow()]
    return done.iloc[-1]


def main():
    ev   = get_latest_event()
    year = ev["Year"]
    gp   = ev["EventName"].replace(" ","_")
    key  = f"{year}_{gp}"

    # define which plots go in which session
    session_plots = {
      "FP1": [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
      "FP2": [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
      "FP3": [sector_gap, top_speed_comparison, plot_top_speed_heatmap, aero_performance],
      "QUALIFYING": [quali_result, sector_gap, top_speed_comparison, aero_performance],    # plus two-driver plots below
      "RACE": [pos_change, tyre_strategy, team_pace, tyre_deg],
    }

    for tag, code in [("FP1","FP1"),("FP2","FP2"),("FP3","FP3"),
                      ("QUALIFYING","Q"),("RACE","R")]:
        try:
            sess = get_session(year, ev["EventName"], code)
            sess.load()
            folder = create_folder(key, tag)
            imgs = []

            # 1) run all the simple plots for this session
            for fn in session_plots[tag]:
                out = os.path.join(folder, fn.__name__ + ".png")
                # all functions take (session, save_path)
                fn(sess, out)
                imgs.append(out)

            # 2) handle the 2-driver plots only in Quali
            if tag == "QUALIFYING":
                # pick the two fastest qualifiers by Q3 time
                qr = sess.results[sess.results["Q3Time"].notna()]
                top2 = qr.sort_values("Q3Time")["Abbreviation"].tolist()[:2]
                d1, d2 = top2

                # telemetry comparison
                path = os.path.join(folder, "telemetry.png")
                telemetry_comparison(sess, d1, d2, path)
                imgs.append(path)

                # track domination
                path = os.path.join(folder, "track_domination.png")
                track_domination(sess, d1, d2, path)
                imgs.append(path)

            # 3) update README
            update_readme_section(tag, imgs)

        except Exception as e:
            print(f"⚠️ Skipping {tag}: {e}")

if __name__=="__main__":
    main()

