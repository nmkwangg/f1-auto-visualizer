

# In[1]:


import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import colormaps
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import fastf1 as ff1
import fastf1.plotting 
from fastf1.core import Laps
from timple.timedelta import strftimedelta
import logging, warnings
from matplotlib.patches import Patch
import os


# In[2]:


# ── silence FastF1 INFO/DEBUG messages ───────────────────────────────────
logging.getLogger('fastf1').setLevel(logging.WARNING)   # or logging.ERROR

# ── hide matplotlib / pandas FutureWarnings etc. ─────────────────────────
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)   # optional


# In[3]:


# Use the cache folder in the repo root
ff1.Cache.enable_cache("cache")

# In[5]:


# Driver's color
helmet_colors = {
    'NOR': '#FEF300',  # Lando Norris: bright fluorescent yellow
    'PIA': '#FF8700',  # Oscar Piastri: papaya/orange
    'LEC': '#DC0000',  # Charles Leclerc: Ferrari red
    'HAM': '#FFF500',  # Lewis Hamilton: neon yellow
    'VER': '#1E41FF',  # Max Verstappen: navy/blue (Red Bull style)
    'LAW': '#6B0000',  # Liam Lawson: deep red
    'RUS': '#77DDE7',  # George Russell: baby blue accent
    'ANT': '#FF1C1C',  # Andrea Kimi Antonelli: bright red accent
    'ALO': '#0082FA',  # Fernando Alonso: metallic/royal blue
    'STR': '#006F62',  # Lance Stroll: Aston Martin green
    'GAS': '#F596C8',  # Pierre Gasly: pink (Alpine/BWT theme)
    'DOO': '#FFB6C1',  # Jack Doohan: light pink
    'OCO': '#F596C8',  # Esteban Ocon: pink (Alpine/BWT theme)
    'BEA': '#DC0000',  # Ollie Bearman: Ferrari academy red
    'TSU': '#363636',  # Yuki Tsunoda: dark/black theme
    'HAD': '#5A7AFF',  # Isack Hadjar: RB Junior derivative
    'SAI': '#DC0000',  # Carlos Sainz: Ferrari red
    'ALB': '#E50000',  # Alex Albon: bright red accent (Thai theme)
    'HUL': '#E20387',  # Nico Hulkenberg: pink accent
    'BOR': '#0015BC'   # Gabriel Bortoleto: deep blue
}


# In[6]:


# helpers
def _lap_filter_sc(row: pd.Series) -> bool:
    return "4" in row["TrackStatus"]          # SC

def _lap_filter_vsc(row: pd.Series) -> bool:
    st = row["TrackStatus"]
    return (("6" in st) or ("7" in st)) and ("4" not in st)   # VSC but not SC

def find_sc_laps(df_laps: pd.DataFrame):
    sc = df_laps[df_laps.apply(_lap_filter_sc, axis=1)]["LapNumber"].unique()
    vsc = df_laps[df_laps.apply(_lap_filter_vsc, axis=1)]["LapNumber"].unique()
    return np.sort(sc), np.sort(vsc)

def shade_periods(ax, sc_laps, vsc_laps,
                  color="orange", alpha=0.45, hatch_vsc='-'):
    """Shade SC (solid) and VSC (hatched) lap ranges on *ax*."""
    def _shade(ax_, laps, label, hatch=None):
        if len(laps) == 0:
            return
        laps = np.asarray(laps, int)
        starts = np.insert(laps[np.diff(np.insert(laps, 0, laps[0]-2)) > 1],
                           0, laps[0])
        ends   = np.append(starts[1:]-1, laps[-1])
        for i, (s, e) in enumerate(zip(starts, ends)):
            ax_.axvspan(s-1, e, color=color, alpha=alpha,
                        hatch=hatch, label=label if i == 0 else "_")
    _shade(ax, sc_laps,  "SC")                      # solid
    _shade(ax, vsc_laps, "VSC", hatch=hatch_vsc)    # hatched


# In[7]:


def tyre_strategy(session, save_path):
    # gather stint table (incl. FreshTyre) ...............................
    laps = session.laps
    stints = (laps[["Driver","Stint","Compound","FreshTyre","LapNumber"]]
              .groupby(["Driver","Stint","Compound","FreshTyre"])
              .count()
              .reset_index()
              .rename(columns={"LapNumber":"StintLength"}))

    drivers = [session.get_driver(d)["Abbreviation"] for d in session.drivers]

    # find SC / VSC laps once
    sc_laps, vsc_laps = find_sc_laps(laps)

    # plotting ..........................................................
    fig, ax = plt.subplots(figsize=(14, 8), constrained_layout=True)
    ax.set_title(f"{session.event['EventName']} {session.event.year}  –  Tyre Strategy",
                 color='white')
    ax.set_facecolor("#202020"); fig.patch.set_facecolor("#202020")
    ax.invert_yaxis(); ax.grid(False)

    # 1) shade neutral zones first
    shade_periods(ax, sc_laps, vsc_laps)

    # 2) draw bars
    for drv in drivers:
        drv_stints = stints[stints["Driver"] == drv]
        x0 = 0
        for _, s in drv_stints.iterrows():
            ax.barh(drv, s["StintLength"], left=x0,
                    color=fastf1.plotting.COMPOUND_COLORS[s["Compound"]],
                    edgecolor="black",
                    hatch="" if s["FreshTyre"] else "//",
                    label=f"{s['Compound']} {'Fresh' if s['FreshTyre'] else 'Used'}")
            x0 += s["StintLength"]

    # legend: keep unique labels + SC/VSC patches
    h, l = ax.get_legend_handles_labels()
    uniq = {lab: han for han, lab in zip(h, l) if lab != "_"}
    uniq["SC"]  = Patch(facecolor="orange", alpha=0.45)
    uniq["VSC"] = Patch(facecolor="orange", alpha=0.45, hatch='-')
    leg = ax.legend(uniq.values(), uniq.keys(), ncol=5, frameon=False, fontsize=8)
    for t in leg.get_texts(): t.set_color("white")

    ax.tick_params(axis='both', colors='white')
    fig.savefig(save_path)
    plt.close(fig)


# In[8]:


def sector_gap(session, save_path):
    laps = session.laps.copy()
    mask_valid = laps[['Sector1Time', 'Sector2Time', 'Sector3Time']].notna().all(axis=1)
    laps = laps[mask_valid]

    for sec in (1, 2, 3):
        laps[f"S{sec}_s"] = laps[f"Sector{sec}Time"].dt.total_seconds()

    best_s1, best_s2, best_s3 = laps['S1_s'].min(), laps['S2_s'].min(), laps['S3_s'].min()

    rows = []
    for sec, best in zip((1, 2, 3), (best_s1, best_s2, best_s3)):
        col = f"S{sec}_s"
        idx = laps.groupby('Driver')[col].idxmin()
        sec_df = laps.loc[idx, ['Driver', col, 'Team']].copy()
        sec_df.rename(columns={col: 'Time'}, inplace=True)
        sec_df['Gap'] = sec_df['Time'] - best
        sec_df['Sector'] = sec
        rows.append(sec_df[['Driver', 'Team', 'Sector', 'Gap']])

    gap_df = pd.concat(rows, ignore_index=True)

    # ------------------ driver → colour palette ------------------------------
    driver_palette = {
        abbr: fastf1.plotting.get_team_color(team, session=session)
        for abbr, team in session.results.set_index('Abbreviation')['TeamName'].items()
    }

    sns.set_style("dark")
    plt.rcParams['figure.facecolor'] = '#202020'
    fig, axes = plt.subplots(3, 1, figsize=(11, 11), sharex=False)

    global_max = gap_df['Gap'].max()
    step = 0.2
    yticks = np.arange(0, np.ceil(global_max/step)*step + step, step)
    title_txt = {1: "Sector 1 (s)", 2: "Sector 2 (s)", 3: "Sector 3 (s)"}

    for ax, sec in zip(axes, [1, 2, 3]):
        ax.set_facecolor('#303030')
        for s in ax.spines.values(): s.set_visible(False)

        data = gap_df[gap_df['Sector'] == sec].sort_values('Gap')
        sns.barplot(
            data=data, x='Driver', y='Gap',
            palette=[driver_palette[d] for d in data['Driver']],
            ax=ax, edgecolor='black', linewidth=0.6)

        # dotted grid on every y‑tick
        ax.set_yticks(yticks); ax.set_ylim(0, yticks[-1])
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, linestyle='--', color='black', alpha=0.7)

        # annotate each bar
        for bar, g in zip(ax.patches, data['Gap']):
            ax.text(bar.get_x()+bar.get_width()/2, g+0.01,
                    f"+{g:.3f}", ha='center', va='bottom',
                    fontsize=9, color='white')

        # ------ vertical sector label (no overlap) --------------------------
        ax.text(-0.05, 0.50, title_txt[sec],
                transform=ax.transAxes,
                rotation=90, ha='center', va='center',
                color='white', fontsize=12, fontweight='bold',
                clip_on=False)

        ax.set_xlabel(None); ax.set_ylabel(None)
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')

    fig.suptitle(f"Best Sector Gap ({session})",
                 fontsize=16, fontweight='bold', color='white', y=0.94)
    fig.subplots_adjust(left=0.15, right=0.85, top=0.92, bottom=0.04)
    fig.savefig(save_path)
    plt.close(fig)

# In[9]:


def top_speed_comparison(session, save_path):
    """Draw a top‑speed bar chart, cropping the first *cut* km/h."""
    cut = 310
    # -------- gather fastest‑lap top speeds --------------------------------
    rows = []
    for drv in session.laps['Driver'].unique():
        # 1) pick only that driver’s laps
        drv_laps = session.laps.pick_drivers(drv)
        if drv_laps.empty:
            continue

        # 2) find their fastest lap (could be None)
        try:
            best = drv_laps.pick_fastest()
        except Exception:
            continue
        if best is None:
            continue

        # 3) get high-rate telemetry for that lap
        tel = best.get_telemetry()
        if tel is None or tel.empty:
            continue

        # 4) record top speed
        rows.append({
            'Driver':   drv,
            'Team':     best['Team'],
            'TopSpeed': tel['Speed'].max()
        })

    if not rows:
        raise RuntimeError("No valid fastest laps found in this session!")

    df = (pd.DataFrame(rows)
            .sort_values('TopSpeed', ascending=False)
            .reset_index(drop=True))

    # -------- team colours -------------------------------------------------
    palette = {d: fastf1.plotting.get_team_color(t, session=session)
               for d, t in session.results.set_index('Abbreviation')['TeamName'].items()}
    colours = [palette[d] for d in df['Driver']]

    # -------- plotting -----------------------------------------------------
    dark_bg  = "#202020"
    grid_col = "#444444"
    sns.set_style("dark", {'axes.facecolor': dark_bg,
                           'figure.facecolor': dark_bg,
                           'grid.color': grid_col,
                           'grid.linestyle':'--'})

    fig, ax = plt.subplots(figsize=(12, 6), facecolor=dark_bg)
    ax.set_facecolor(dark_bg)

    sns.barplot(data=df, x='Driver', y='TopSpeed',
                palette=colours, edgecolor='black', linewidth=0.6, ax=ax)

    # annotate values above bars
    for bar, spd in zip(ax.patches, df['TopSpeed']):
        ax.text(bar.get_x()+bar.get_width()/2, spd+0.2,
                f"{spd:.0f}", ha='center', va='bottom', fontsize=9, color = 'white')

    # -------- crop the first *cut_at* km/h ---------------------------------
    ymax = df['TopSpeed'].max() + 3
    ax.set_ylim(cut, ymax)

    #draw a thin baseline at the cut
    ax.axhline(cut, color='black', lw=1)

    ax.set_ylabel("Top Speed (km/h)")
    ax.set_xlabel(None)
    ax.set_title(f"{session}  •  TOP SPEED (km/h)", fontsize=14, weight='bold', color = 'white')
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white', color=grid_col)
    ax.yaxis.grid(True, which='major', linestyle='--', color='gray', zorder=-1000)
    
    sns.despine(ax=ax, top=True, right=True)
    plt.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)

# In[10]:


def telemetry_comparison(d1, d2, save_path):
    # ---------- fastest laps ------------------------------------------------
    d1_lap = session.laps.pick_drivers(d1).pick_fastest()
    d2_lap = session.laps.pick_drivers(d2).pick_fastest()

    d1_tel = d1_lap.get_car_data().add_distance()   # add Distance column
    d2_tel = d2_lap.get_car_data().add_distance()

    d1_color = fastf1.plotting.get_team_color(d1_lap['Team'], session=session)
    d2_color = fastf1.plotting.get_team_color(d2_lap['Team'], session=session)
    # Check if drivers are on the same team.
    same_team = (d1_color == d2_color)
    if same_team:
        # Override the team color with the helmet color from our dictionary.
        d1_color = helmet_colors.get(d1, d1_color)
        d2_color = helmet_colors.get(d2, d2_color)

    # ---------- circuit‑corner information ---------------------------------
    ci = session.get_circuit_info()           # FastF1 CircuitInfo object
    corner_dist = ci.corners['Distance'].to_numpy()
    # map corner distances to times using the reference lap (d1)
    def dist_to_time(dist):
        idx = (d1_tel['Distance'] - dist).abs().idxmin()
        return d1_tel.loc[idx, 'Time']
    corner_times = [dist_to_time(d) for d in corner_dist]
    corner_labels = ci.corners['Number'].astype(str).tolist()

    # ---------- plotting setup ---------------------------------------------
    fastf1.plotting.setup_mpl(mpl_timedelta_support=True,
                              misc_mpl_mods=False, color_scheme='fastf1')

    fig, ax = plt.subplots(5, figsize=(25, 20), sharex=True)

    ax[0].plot(d1_tel['Time'], d1_tel['Speed'],    color=d1_color)
    ax[0].plot(d2_tel['Time'], d2_tel['Speed'],    color=d2_color)

    ax[1].plot(d1_tel['Time'], d1_tel['RPM'],      color=d1_color)
    ax[1].plot(d2_tel['Time'], d2_tel['RPM'],      color=d2_color)

    ax[2].plot(d1_tel['Time'], d1_tel['nGear'],    color=d1_color)
    ax[2].plot(d2_tel['Time'], d2_tel['nGear'],    color=d2_color)

    ax[3].plot(d1_tel['Time'], d1_tel['Throttle'], color=d1_color)
    ax[3].plot(d2_tel['Time'], d2_tel['Throttle'], color=d2_color)

    ax[4].plot(d1_tel['Time'], d1_tel['Brake'],    color=d1_color)
    ax[4].plot(d2_tel['Time'], d2_tel['Brake'],    color=d2_color)

    # ---------- vertical corner lines on every subplot ---------------------
    for a in ax:
        for t in corner_times:
            a.axvline(t, color='white', linestyle=':', linewidth=0.8, alpha=0.7)
    
    # ------- draw corner numbers on every subplot ----------------------------
    for a in ax:                                     # loop over all 5 axes
        for t, lbl in zip(corner_times, corner_labels):
            a.text(t, -0.08, lbl,                  # y = −0.08 axes‑fraction
                   ha='center', va='top',
                   transform=a.get_xaxis_transform(),
                   fontsize=8, color='white')
            
    # put corner number text below the last axis ( brake plot )
    for t, lbl in zip(corner_times, corner_labels):
        ax[-1].text(t, -0.08, lbl, ha='center', va='top',
                    transform=ax[-1].get_xaxis_transform(),
                    fontsize=8, color='white')

    # ---------- labels & styling -------------------------------------------
    ax[0].set_ylabel("Speed [km/h]")
    ax[1].set_ylabel("RPM")
    ax[2].set_ylabel("Gear")
    ax[3].set_ylabel("Throttle [%]")
    ax[4].set_ylabel("Brake [%]")

    for a in ax[:-1]:
        a.set_xticklabels([])

    fig.align_ylabels()
    fig.legend([d1, d2], loc='upper right')

    plt.subplots_adjust(left=0.06, right=0.99, top=0.9, bottom=0.07)
    plt.suptitle(f"Fastest Lap Comparison\n"
                 f"{session.event['EventName']} {session.event.year} Qualifying")
    fig.savefig(save_path)
    plt.close(fig)

# In[11]:


def track_domination(d1, d2, save_path):
    # Get fastest lap for each driver from the qualifying session.
    d1_lap = session.laps.pick_driver(d1).pick_fastest()
    d2_lap = session.laps.pick_driver(d2).pick_fastest()
    
    # Get telemetry data with added distance.
    telemetry_driver01 = d1_lap.get_telemetry().add_distance()
    telemetry_driver02 = d2_lap.get_telemetry().add_distance()
    
    telemetry_driver01['Driver'] = d1
    telemetry_driver02['Driver'] = d2
    telemetry_drivers = pd.concat(
    [telemetry_driver01, telemetry_driver02],
    ignore_index=True)
    
    # Define the number of mini-sectors (e.g., 21 mini-sectors)
    num_minisectors = 7 * 3
    total_distance = max(telemetry_drivers['Distance'])
    minisector_length = total_distance / num_minisectors
    
    telemetry_drivers['Minisector'] = telemetry_drivers['Distance'].apply(
        lambda dist: int((dist // minisector_length) + 1)
    )
    
    average_speed = telemetry_drivers.groupby(['Minisector', 'Driver'])['Speed'].mean().reset_index()
    fastest_driver = average_speed.loc[average_speed.groupby('Minisector')['Speed'].idxmax()]
    fastest_driver = fastest_driver[['Minisector', 'Driver']].rename(columns={'Driver': 'Fastest_driver'})
    telemetry_drivers = telemetry_drivers.merge(fastest_driver, on=['Minisector'])
    telemetry_drivers = telemetry_drivers.sort_values(by=['Distance'])
    
    # Assign integer codes: 1 for d1 and 2 for d2 based on fastest driver per minisector.
    telemetry_drivers.loc[telemetry_drivers['Fastest_driver'] == d1, 'Fastest_driver_int'] = 1
    telemetry_drivers.loc[telemetry_drivers['Fastest_driver'] == d2, 'Fastest_driver_int'] = 2
    
    # Extract (X, Y) coordinates and form segments.
    x = np.array(telemetry_drivers['X'].values)
    y = np.array(telemetry_drivers['Y'].values)
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    fastest_driver_array = telemetry_drivers['Fastest_driver_int'].to_numpy().astype(float)
    
    # Get team colors using FastF1's plotting function.
    d1_color = fastf1.plotting.get_team_color(d1_lap['Team'], session=session)
    d2_color = fastf1.plotting.get_team_color(d2_lap['Team'], session=session)
    
    # Check if drivers are on the same team.
    same_team = (d1_color == d2_color)
    if same_team:
        # Override the team color with the helmet color from our dictionary.
        d1_color = helmet_colors.get(d1, d1_color)
        d2_color = helmet_colors.get(d2, d2_color)
        # You might also decide to use a dash pattern for one driver if needed.
        d2_linestyle = 'solid'
    else:
        d2_linestyle = 'solid'
    
    # Create masks for segments belonging to each driver.
    fastest_driver_array_seg = fastest_driver_array[:-1]
    mask_d1 = fastest_driver_array_seg == 1
    mask_d2 = fastest_driver_array_seg == 2
    
    segments_d1 = segments[mask_d1]
    segments_d2 = segments[mask_d2]
    
    # Create LineCollections for each driver's segments.
    lc_d1 = LineCollection(segments_d1, colors=d1_color, linewidths=5)
    lc_d2 = LineCollection(segments_d2, colors=d2_color, linewidths=5, linestyles=d2_linestyle)

    # Plot the track domination.
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.add_collection(lc_d1)
    ax.add_collection(lc_d2)
    ax.axis('equal')
    ax.tick_params(labelleft=False, left=False, labelbottom=False, bottom=False)

    # Create a custom legend.
    legend_elements = [
        Line2D([0], [0], color=d1_color, lw=5, label=d1),
        Line2D([0], [0], color=d2_color, lw=5, label=d2)
    ]
    ax.legend(handles=legend_elements, title='Driver')

    plt.title(f"{session.event['EventName']} {session.event.year} Qualifying {d1} vs {d2}", color='silver', fontsize=16)
    fig.savefig(save_path)
    plt.close(fig)

# In[12]:


def aero_performance(session, save_path):
    best_laps = (session.laps.loc[session.laps.groupby("Team")["LapTime"].idxmin()].copy())

    rows = []
    for _, lap in best_laps.iterrows():
        tel = lap.get_telemetry()          
        mean_speed = tel['Speed'].mean()   
        top_speed  = tel['Speed'].max()    
        rows.append({"Team": lap["Team"],
                     "MeanSpeed": mean_speed,
                     "TopSpeed":  top_speed})

    df = pd.DataFrame(rows)
    df["Color"] = df["Team"].apply(
        lambda t: fastf1.plotting.get_team_color(t, session=session)
    )

    fig, ax = plt.subplots(figsize=(10, 10), constrained_layout=True, facecolor="white")
    ax.set_facecolor("white")

    team_rename = {
        "Aston Martin": "Aston",
        "Haas F1 Team": "Haas",
        "Kick Sauber": "Sauber",
        "Red Bull Racing": "RB",
        "Racing Bulls": "VCARB"
    }
    df['Team'] = df['Team'].replace(team_rename)

    for _, r in df.iterrows():
        ax.scatter(r["MeanSpeed"], r["TopSpeed"],
                   s=220, color=r["Color"], edgecolor="black", zorder=3)
        ax.text(r["MeanSpeed"], r["TopSpeed"] + 0.2, r["Team"],
                ha="center", va="bottom", fontsize=9, color="black")

    x_min, x_max = df["MeanSpeed"].min() - 1, df["MeanSpeed"].max() + 1
    y_min, y_max = df["TopSpeed"].min()  - 1, df["TopSpeed"].max()  + 1

    mid_x = (x_min + x_max) / 2           # exact centre of the plot
    mid_y = (y_min + y_max) / 2

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    # axes
    ax.plot([x_min, x_max],[y_min,  y_max], 
            color="black", ls="--", lw=1)
    ax.plot([x_min, x_max],[y_max,  y_min], 
            color="black", ls="--", lw=1)
    ax.plot([mid_x, mid_x],[y_min, y_max], 
            color="black", ls="--", lw=1)
    ax.plot([x_min, x_max],[mid_y,  mid_y], 
            color="black", ls="--", lw=1)

    # axes labels
    dx = 0.5 * (df["MeanSpeed"].max() - df["MeanSpeed"].min())
    dy = 0.5 * (df["TopSpeed"].max()  - df["TopSpeed"].min())

    ax.text(mid_x + dx*0.6, mid_y + dy*0.6, "Quick &\nLow Drag",
            ha="center", va="center", fontsize=11, color="black")
    ax.text(mid_x - dx*0.6, mid_y + dy*0.6,"Fast Straights\nSlow Corners",  
            ha='center', va='center', fontsize=11, color='black')
    ax.text(mid_x - dx*0.6, mid_y - dy*0.6, "Underperforming",
            ha="center", va="center", fontsize=11, color="black")
    ax.text(mid_x + dx*0.6, mid_y - dy*0.6, "High Downforce",
            ha="center", va="center", fontsize=11, color="black")
    ax.text(x_min+0.6, mid_y + 0.1, "Low Speed",
            ha="center", va="center", fontsize=11, color="black")
    ax.text(x_max-0.6, mid_y + 0.1, "High Speed",
            ha="center", va="center", fontsize=11, color="black")
    ax.text(mid_x, y_min+0.2, "High Drag",
            ha="center", va="center", fontsize=11, color="black")
    ax.text(mid_x, y_max-0.2, "Low Drag",
            ha="center", va="center", fontsize=11, color="black")


    ax.set_xlabel("Mean Speed (km/h)", fontsize=12, color="black")
    ax.set_ylabel("Top Speed (km/h)",  fontsize=12, color="black")
    ax.set_title(f"{session} \nAreo Performance (Best Lap of Each Team)",
                 fontsize=14, pad=15, color="black")

    ax.set_xlim(df["MeanSpeed"].min()-1, df["MeanSpeed"].max()+1)
    ax.set_ylim(df["TopSpeed"].min()-1,  df["TopSpeed"].max()+1)
    ax.grid(ls=":", alpha=0.4)
    ax.tick_params(axis='x', colors='black', color='grey')
    ax.tick_params(axis='y', colors='black', color='grey')

    for side in ['top','bottom','left','right']:
        ax.spines[side].set_visible(True)
        ax.spines[side].set_color('black')
        ax.spines[side].set_linewidth(1)

    ax.set_axisbelow(True)
    ax.grid(True,
            which='major',
            axis='both',
            color='grey',
            linestyle=':',
            linewidth=0.8,
            alpha=0.7)

    plt.tight_layout()
    
    plt.tight_layout()
    
    fig.savefig(save_path)
    plt.close(fig)

# In[13]:


def quali_result(session, save_path):
    # Get unique list of drivers
    drivers = pd.unique(session.laps['Driver'])

    # Build list of each driver's fastest lap.
    list_fastest_laps = []
    for drv in drivers:
        drvs_fastest_lap = session.laps.pick_drivers(drv).pick_fastest()
        list_fastest_laps.append(drvs_fastest_lap)

    # Create a Laps object from the fastest laps and sort them by LapTime.
    fastest_laps = Laps(list_fastest_laps).sort_values(by='LapTime').reset_index(drop=True)

    # Identify the pole lap (fastest overall) and calculate the LapTimeDelta.
    pole_lap = fastest_laps.pick_fastest()
    fastest_laps['LapTimeDelta'] = fastest_laps['LapTime'] - pole_lap['LapTime']

    # Convert the LapTimeDelta to seconds.
    fastest_laps['LapTimeDelta_sec'] = fastest_laps['LapTimeDelta'].dt.total_seconds()

    # Get team colors for each fastest lap.
    team_colors = []
    for index, lap in fastest_laps.iterlaps():
        color = fastf1.plotting.get_team_color(lap['Team'], session=session)
        team_colors.append(color)

    # Plot the horizontal bar chart using the seconds values.
    fig, ax = plt.subplots()
    ax.barh(fastest_laps.index, fastest_laps['LapTimeDelta_sec'],
            color=team_colors, edgecolor='grey')
    ax.set_yticks(fastest_laps.index)
    ax.set_yticklabels(fastest_laps['Driver'])
    ax.invert_yaxis()  # Fastest (lowest delta) at the top

    # Draw vertical grid lines behind the bars.
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, which='major', linestyle='--', color='black', zorder=-1000)
    ax.yaxis.grid(False)
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')
    # Annotate each bar with the lap time delta (in seconds, formatted to 4 decimal places).
    offset = 0.02  # Seconds to offset the annotation to the right of the bar.
    for i, delta_sec in fastest_laps['LapTimeDelta_sec'].items():
        # Format the delta value as a float with four decimals.
        label = f"+ {delta_sec:.4f} s"
        ax.text(delta_sec + offset, i, label, va='center', ha='left', color='white', fontsize=10)
    # remove all four spines = no white rectangle
    for spine in ax.spines.values():
        spine.set_visible(False)
    # Format the plot title using the pole lap's time.
    lap_time_string = strftimedelta(pole_lap['LapTime'], '%m:%s.%ms')
    plt.suptitle(f"{session}\n"
                 f"Fastest Lap: {lap_time_string} ({pole_lap['Driver']})", color='white')

    
    fig.savefig(save_path)
    plt.close(fig)

# In[14]:


def pos_change(session, save_path):
    # --- find SC / VSC laps BEFORE plotting ------------------------------
    sc_laps, vsc_laps = find_sc_laps(session.laps)

    fig, ax = plt.subplots(figsize=(9, 5.2), constrained_layout=True)
    ax.set_facecolor("#202020")                       # dark bg (optional)
    fig.patch.set_facecolor("#202020")

    # Shade SC / VSC periods first so lines sit on top
    shade_periods(ax, sc_laps, vsc_laps, color="orange")

    # --- driver position traces -----------------------------------------
    for drv in session.drivers:
        laps = session.laps.pick_drivers(drv)
        abb  = laps["Driver"].iloc[0]
        style = fastf1.plotting.get_driver_style(
            identifier=abb, style=["color", "linestyle"], session=session
        )
        ax.plot(laps["LapNumber"], laps["Position"], label=abb, **style, lw=1.5)

    # --- cosmetics -------------------------------------------------------
    ax.set_ylim(20.5, 0.5)
    ax.set_yticks([1, 5, 10, 15, 20])
    ax.set_xlabel("Lap", color="white")
    ax.set_ylabel("Position", color="white")
    ax.tick_params(axis='both', colors='white')
    ax.set_title(f"{session}  •  Position Changes", color="white", pad=10)
    ax.legend(bbox_to_anchor=(1.0, 1.02))
    leg = ax.legend(bbox_to_anchor=(1.0, 1.02))
    # make all legend texts white
    for txt in leg.get_texts():
        txt.set_color("white")
    # also ensure the axis ticks & labels are white
    ax.tick_params(axis='both', colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')

    
    fig.savefig(save_path)
    plt.close(fig)

# In[23]:


#Team Pace Comparison
def team_pace(session, save_path):
    laps = session.laps.pick_quicklaps()

    transformed_laps = laps.copy()
    transformed_laps["LapTime (s)"] = laps["LapTime"].dt.total_seconds()

    # order the team from the fastest (lowest median lap time) tp slower
    team_order = (
        transformed_laps[["Team", "LapTime (s)"]]
          .groupby("Team").median()["LapTime (s)"]
          .sort_values()
          .index
    )

    # make a color palette associating team names to hex codes
    team_palette = {t: fastf1.plotting.get_team_color(t, session=session)
                    for t in team_order}

    fig, ax = plt.subplots(figsize=(15, 10),  facecolor="#202020")
    ax.set_facecolor("#202020")

    sns.boxplot(
        data=transformed_laps,
        x="Team",
        y="LapTime (s)",
        order=team_order,
        palette=team_palette,   
        width=0.6,             
        dodge=False,            # keep each box centred on its tick
        whiskerprops=dict(color="white"),
        boxprops=dict(edgecolor="white"),
        medianprops=dict(color="white"),
        capprops=dict(color="white"),
        flierprops  =dict(marker="o",
                          markeredgecolor="white",
                          markersize=4,
                          linestyle="none")
    )
    

    ax.set_title(f"{session} Team Pace Comparison", color="white")
    ax.set_xlabel("")
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')
    ax.margins(x=0.02)         
    ax.xaxis.grid(False)
    plt.tight_layout()
    
    fig.savefig(save_path)
    plt.close(fig)

# In[16]:


#Tyre Deg
def tyre_deg(session, save_path):
    laps = (session.laps.pick_quicklaps().reset_index(drop=True))

    # Tyre age (lap‑counter within each stint)
    laps["TyreAge"] = laps.groupby(["Driver", "Stint"]).cumcount() + 1

    # Lap time in seconds
    laps["LapTime_s"] = laps["LapTime"].dt.total_seconds()

    # VERY simple fuel correction
    #  Rule of thumb:  0.03 s per kg  →  ~1.6 kg fuel burnt per lap
    #  (10 kg ≈ 0.3 s)  
    FUEL_PER_LAP = 1.6        # kg
    PENALTY_PER_KG = 0.03     # s

    laps["FuelCorrLapTime"] = (laps["LapTime_s"] - laps["LapNumber"] * FUEL_PER_LAP * PENALTY_PER_KG)

    # Average lap‑time by tyre age & compound
    deg = (laps.groupby(["Compound", "TyreAge"])["FuelCorrLapTime"].mean().reset_index())

    # Order compounds as they appear on the legend
    compound_order = ["SOFT", "MEDIUM", "HARD"]
    colours = {"SOFT": "red", "MEDIUM": "yellow", "HARD": "white"}


    # Plot
    plt.style.use("dark_background")        # black backdrop like your sample
    fig, ax = plt.subplots(figsize=(10, 6))

    for comp in compound_order:
        df = deg[deg["Compound"] == comp]
        ax.plot(df["TyreAge"], df["FuelCorrLapTime"],
                color=colours[comp], marker="o", lw=2, label=comp)

    # Cosmetic tweaks ------------------------------------------------
    ax.set_title(f"Tyre Degradation ({session})", pad=15, fontsize=16)
    ax.set_xlabel("Tyre Age (Laps)")
    ax.set_ylabel("Fuel‑Corrected LapTime (s)")
    ax.set_xlim(left=0)
    ax.grid(ls="--", lw=0.4, color="grey", alpha=0.4)
    ax.legend(frameon=False, loc="upper right", fontsize=11)

    plt.tight_layout()
    
    fig.savefig(save_path)
    plt.close(fig)

# In[17]:


#Top Speed
def plot_top_speed_heatmap(session, save_path, n_top=15, cut_at=None):
    """
    Draw a heatmap of each driver’s top n_top lap speeds,
    boxing DRS-on points, with a dark background and white text.
    """
    # 1) Gather per-lap max speed + DRS
    rows = []
    for _, lap in session.laps.iterlaps():
        tel = lap.get_telemetry()
        if tel.empty:
            continue
        idx = tel['Speed'].idxmax()
        rows.append({
            'Driver': lap['Driver'],
            'TopSpeed': tel.at[idx, 'Speed'],
            'DRS':      'on' if int(tel.at[idx, 'DRS']) % 2 == 0 else 'off'
        })

    df = pd.DataFrame(rows)

    # 2) Keep top n_top per driver
    df = (
        df.sort_values(['Driver','TopSpeed'], ascending=[True, False])
          .groupby('Driver', group_keys=False)
          .head(n_top)
          .assign(Rank=lambda d: d.groupby('Driver').cumcount()+1)
    )

    # 3) Pivot to wide form
    speed_mat = df.pivot(index='Driver', columns='Rank', values='TopSpeed')
    drs_mat   = df.pivot(index='Driver', columns='Rank', values='DRS')

    # 4) Plot setup
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#202020')
    ax.set_facecolor('#202020')
    for spine in ax.spines.values():
        spine.set_visible(False)

    im = ax.imshow(speed_mat, aspect='auto', cmap='plasma', origin='lower')

    # 5) White axis labels & ticks
    ax.set_xticks(np.arange(speed_mat.shape[1]))
    ax.set_xticklabels(speed_mat.columns, color='white')
    ax.set_yticks(np.arange(speed_mat.shape[0]))
    ax.set_yticklabels(speed_mat.index, color='white')
    ax.set_xlabel(f"Top {n_top} Lap Speeds\n(black: DRS On; white: DRS Off)", color='white')
    ax.set_ylabel("Driver", color='white')
    ax.set_title(f"{session.event['EventName']} {session.event.year}\nTop Speed Heatmap",
                 color='white')
    #cbar = fig.colorbar(im, ax=ax)
    #cbar.ax.yaxis.set_tick_params(color='white')
    #cbar.outline.set_edgecolor('white')
    #cbar.set_label('Top Speed (km/h)', color='white')
    #plt.setp(cbar.ax.get_yticklabels(), color='white')

    # 8) Annotate speeds; bold if DRS was on
    for i, drv in enumerate(speed_mat.index):
        for j, rk in enumerate(speed_mat.columns):
            val = speed_mat.at[drv, rk]
            if pd.isna(val):
                continue
            drs_on = (drs_mat.at[drv, rk] == 'on')
            ax.text(j, i, f"{val:.0f}",
                    ha='center', va='center',
                    color='black' if drs_on else 'white', fontsize = 10)

    plt.tight_layout()
    
    fig.savefig(save_path)
    plt.close(fig)



# In[33]:


