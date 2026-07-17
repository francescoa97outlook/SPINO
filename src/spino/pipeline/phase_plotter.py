"""
Phase Plotter
=============
All plotting functions for the phase scheduler:
  - plot_event: altitude-vs-time for a single observable event
  - plot_calendar: calendar summary (phase bars per night)
  - plot_PR_landscape: P-R desert landscape with KDE background
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from datetime import datetime, timedelta
import pytz

# ================================================================== #
#  CONSTANTS                                                          #
# ================================================================== #
RJUP_TO_REARTH = 11.209

_TWILIGHT_COLORS = [
    (0,    '#87CEEB'),   # daylight
    (-6,   '#6495C8'),   # civil
    (-12,  '#3A5FA0'),   # nautical
    (-18,  '#1E3A6E'),   # astronomical
    (None, '#111111'),   # night
]

_EVENT_COLORS = {
    'transit':      '#4169E1',
    'pre_eclipse':  '#4169E1',
    'post_eclipse': '#4169E1',
}


# ================================================================== #
#  HELPER: twilight background                                        #
# ================================================================== #
def _draw_twilight(ax, times_plot, sun_alt):
    """Fill background with twilight colour bands."""
    for i in range(len(times_plot) - 1):
        s = sun_alt[i]
        if s >= 0:
            color = _TWILIGHT_COLORS[0][1]
        elif s >= -6:
            color = _TWILIGHT_COLORS[1][1]
        elif s >= -12:
            color = _TWILIGHT_COLORS[2][1]
        elif s >= -18:
            color = _TWILIGHT_COLORS[3][1]
        else:
            color = _TWILIGHT_COLORS[4][1]
        ax.axvspan(times_plot[i], times_plot[i + 1],
                   facecolor=color, alpha=0.3, edgecolor='none', zorder=0)


def _phase_in_windows(phases, windows_list):
    """Boolean mask: True where phase falls inside any of the intervals."""
    mask = np.zeros(len(phases), dtype=bool)
    for s, e in windows_list:
        if s <= e:
            mask |= (phases >= s) & (phases <= e)
        else:
            mask |= (phases >= s) | (phases <= e)
    return mask


# ================================================================== #
#  1. INDIVIDUAL EVENT PLOT                                           #
# ================================================================== #
def plot_event(event, obs, output_path=None, pdf=None):
    """
    Altitude-vs-time plot for one observable event.

    Exactly one of ``output_path`` or ``pdf`` must be provided:
      - ``output_path`` writes a single-page PDF (legacy mode).
      - ``pdf`` is a ``matplotlib.backends.backend_pdf.PdfPages`` instance
        and the figure is appended as a page (used by the scheduler to
        bundle every event of one type into one multi-page PDF per
        planet).

    Parameters
    ----------
    event : dict with _night, _geom, _target, _windows, event_type, etc.
    obs   : dict with lat, lon, alt, name, timezone
    output_path : str or None
    pdf   : PdfPages or None
    """
    if (output_path is None) == (pdf is None):
        raise ValueError("plot_event: provide exactly one of output_path / pdf")
    night = event["_night"]
    geom = event["_geom"]
    target = event["_target"]
    windows = event["_windows"]
    event_type = event["event_type"]
    from phase_config import CONSTRAINTS
    min_alt = CONSTRAINTS['min_target_alt']

    # --- Time axis in local timezone ---
    tz = pytz.timezone(obs["timezone"])
    times_utc = night["times_utc"]
    times_dt_utc = [t.to_datetime(timezone=pytz.utc) for t in times_utc]
    times_dt_local = [t.astimezone(tz) for t in times_dt_utc]

    target_alt = np.array(night["target_alt"], dtype=float)
    sun_alt = np.array(night["sun_alt"], dtype=float)
    moon_alt = np.array(night["moon_alt"], dtype=float)
    phases = np.array(night["phases"], dtype=float)
    obs_mask = np.array(night["obs_mask"], dtype=bool)

    # Event window for this event type
    evt_intervals = windows.get(event_type, [])
    in_event = obs_mask & _phase_in_windows(phases, evt_intervals)

    # --- Figure ---
    fig, ax = plt.subplots(figsize=(12, 7), facecolor='#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    # Twilight bands
    _draw_twilight(ax, times_dt_utc, sun_alt)

    # Altitude threshold line
    ax.axhline(min_alt, color='green', ls=':', lw=1, alpha=0.5, zorder=1)

    # 1) Full trajectory — yellow
    ax.plot(times_dt_utc, target_alt,
            color='#FFD700', lw=2.5, zorder=3, label='Target trajectory')

    # 2) Above threshold — green
    above = target_alt.copy()
    above[target_alt < min_alt] = np.nan
    ax.plot(times_dt_utc, above,
            color='#00FF00', lw=3.5, zorder=4, label=f'Alt > {min_alt:.0f}°')

    # 3) In-event — blue
    event_alt = target_alt.copy()
    event_alt[~in_event] = np.nan
    ax.plot(times_dt_utc, event_alt,
            color=_EVENT_COLORS.get(event_type, '#4169E1'),
            lw=4.5, zorder=5, label=event_type.replace('_', ' ').title())

    # 4) Moon — white dashed
    ax.plot(times_dt_utc, moon_alt,
            '--', color='white', lw=1.5, alpha=0.7, zorder=2, label='Moon')

    # 5) Sun — gray dashed
    ax.plot(times_dt_utc, sun_alt,
            '--', color='gray', lw=1.5, alpha=0.5, zorder=2, label='Sun')

    # --- Event start/end vertical lines (red dashed) ---
    in_event_idx = np.where(in_event)[0]
    if len(in_event_idx) > 0:
        i_evt_start = in_event_idx[0]
        i_evt_end = in_event_idx[-1]
        for i_line, label_pos in [(i_evt_start, 'left'), (i_evt_end, 'right')]:
            t_line = times_dt_utc[i_line]
            ax.axvline(t_line, color='red', ls='--', lw=1.5, alpha=0.8,
                       zorder=6)
            time_str = t_line.strftime('%H:%M')
            ha = 'right' if label_pos == 'left' else 'left'
            offset = -4 if label_pos == 'left' else 4
            ax.annotate(time_str, xy=(t_line, 85),
                        xytext=(offset, 0), textcoords='offset points',
                        color='red', fontsize=9, fontweight='bold',
                        ha=ha, va='top', zorder=7)

    # --- Axes ---
    ax.set_ylim(0, 90)
    ax.set_ylabel("Altitude [deg]", color='white', fontsize=12)
    ax.set_xlabel("UTC", color='white', fontsize=12)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=pytz.utc))
    ax.tick_params(colors='white', labelsize=10)

    # Top axis: Local time
    ax2_top = ax.twiny()
    ax2_top.set_xlim(ax.get_xlim())
    ax2_top.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=tz))
    ax2_top.set_xlabel(f"Local Time ({obs['timezone']})", color='white',
                       fontsize=11)
    ax2_top.tick_params(colors='white', labelsize=9)

    # Right axis: Airmass
    ax2 = ax.twinx()
    ax2.set_ylim(ax.get_ylim())
    am_ticks = [1.0, 1.1, 1.2, 1.5, 2.0, 3.0, 5.6]
    am_alts = [np.degrees(np.arcsin(1.0 / am)) for am in am_ticks]
    ax2.set_yticks(am_alts)
    ax2.set_yticklabels(
        [f"{am:.1f}" if am < 3 else f"{am:.0f}" for am in am_ticks])
    ax2.set_ylabel("Airmass", color='white', fontsize=12)
    ax2.tick_params(colors='white', labelsize=10)

    # Title
    date_str = night["date_str"]
    ax.set_title(
        f"{target['name']}  —  {event_type.replace('_', ' ').title()}"
        f"  @  {obs['name']}  —  {date_str}",
        color='white', fontsize=14, pad=30)

    # Footer info
    cov_pct = event["coverage"] * 100
    moon_info = (f"Moon illum: {night['moon_illum']:.0%}  "
                 f"sep: {night['moon_sep']:.1f}°  "
                 f"{'OK' if night['moon_ok'] else 'TOO CLOSE'}")
    footer = (f"Coverage: {cov_pct:.0f}%  |  "
              f"P = {target['period']:.6f} d  |  "
              f"T14 = {geom['t14_h']:.2f} h  |  {moon_info}")
    fig.text(0.5, 0.01, footer, ha='center', color='#AAAAAA', fontsize=9)

    # Legend
    ax.legend(loc='upper right', fontsize=9, facecolor='#333333',
              edgecolor='#555555', labelcolor='white')

    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    if pdf is not None:
        pdf.savefig(fig, dpi=150, facecolor=fig.get_facecolor(),
                    bbox_inches='tight')
    else:
        fig.savefig(output_path, dpi=150, facecolor=fig.get_facecolor(),
                    bbox_inches='tight')
    plt.close(fig)


# ================================================================== #
#  2. CALENDAR SUMMARY PLOT                                           #
# ================================================================== #
def plot_calendar(events, event_type, planet_name, event_windows,
                  output_path):
    """
    Calendar summary: one horizontal bar per night, coloured by Moon
    illumination, with the event phase window highlighted.

    Parameters
    ----------
    events       : list of event dicts (all same event_type)
    event_type   : str
    planet_name  : str
    event_windows: dict from compute_event_windows
    output_path  : str
    """
    if not events:
        return

    # Sort by date
    sorted_events = sorted(events, key=lambda e: e["date"])
    dates = [e["date"] for e in sorted_events]
    n = len(dates)

    fig_h = max(6, n * 0.22 + 2)
    fig, ax = plt.subplots(figsize=(14, fig_h))

    # Event phase bands (blue vertical)
    for ws, we in event_windows.get(event_type, []):
        ax.axvspan(ws, we, color='#4169E1', alpha=0.20, zorder=0)

    cmap = plt.get_cmap('turbo')

    for i, evt in enumerate(sorted_events):
        ps = evt["phase_start"]
        pe = evt["phase_end"]
        color = cmap(evt["moon_illum"])
        edgecolor = 'red' if not evt["moon_ok"] else 'none'
        lw = 2.0 if not evt["moon_ok"] else 0.5

        if ps <= pe:
            ax.barh(i, pe - ps, left=ps, height=0.7,
                    color=color, edgecolor=edgecolor, linewidth=lw)
        else:
            # Wrapped bar: draw two segments
            ax.barh(i, 1.0 - ps, left=ps, height=0.7,
                    color=color, edgecolor=edgecolor, linewidth=lw)
            ax.barh(i, pe, left=0.0, height=0.7,
                    color=color, edgecolor=edgecolor, linewidth=lw)

        # Coverage text
        ax.text(min(pe, 0.99) + 0.01, i,
                f"{evt['coverage']:.0%}", va='center', fontsize=7,
                color='#555555')

    ax.set_yticks(range(n))
    ax.set_yticklabels(dates, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Orbital Phase", fontsize=12)
    ax.set_title(
        f"{planet_name}  —  {event_type.replace('_', ' ').title()} Calendar",
        fontsize=14)

    # Colorbar (Moon illumination)
    sm = ScalarMappable(cmap=cmap, norm=Normalize(0, 1))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.02, aspect=30)
    cbar.set_label("Moon illumination", fontsize=10)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


# ================================================================== #
#  3. P-R DESERT LANDSCAPE                                            #
# ================================================================== #
def plot_PR_landscape(df_all, df_filtered, boundary_file, kde_file,
                      P_max=100, R_max=20, output_dir="."):
    """
    Period-Radius landscape with KDE background and CG24 boundary.

    Parameters
    ----------
    df_all      : DataFrame with one row per planet (all planets)
    df_filtered : DataFrame with only filtered/scheduled planets
    boundary_file : str, path to desert_boundaries.txt
    kde_file      : str, path to kde_points_NEA.npz
    P_max, R_max  : axis limits
    output_dir    : str
    """
    import os
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(10, 8))

    # --- KDE background ---
    try:
        npz = np.load(kde_file)
        keys = list(npz.keys())
        logP_kde = npz[keys[0]]
        logR_kde = npz[keys[1]] if len(keys) > 1 else None
        if logR_kde is not None:
            sns.kdeplot(x=logP_kde, y=logR_kde, ax=ax,
                        cmap='Greys', fill=True, alpha=0.4,
                        levels=15, bw_adjust=0.6)
    except Exception:
        pass

    # --- All planets (gray) ---
    mask_all = ((df_all["pl_orbper"] > 0) & (df_all["pl_orbper"] <= P_max) &
                (df_all["pl_rade"] > 0) & (df_all["pl_rade"] <= R_max))
    df_plot = df_all[mask_all]
    ax.scatter(np.log10(df_plot["pl_orbper"]),
               np.log10(df_plot["pl_rade"]),
               s=8, c='gray', alpha=0.35, zorder=1, label='All planets')

    # --- CG24 boundary ---
    try:
        bdata = np.loadtxt(boundary_file, skiprows=1)
        bx, by = bdata[:, 0], bdata[:, 1]
        if not (np.isclose(bx[0], bx[-1]) and np.isclose(by[0], by[-1])):
            bx = np.append(bx, bx[0])
            by = np.append(by, by[0])
        ax.plot(bx, by, color='#FF6347', lw=2.0, ls='--', zorder=2,
                label='CG24 boundary')
    except Exception:
        pass

    # --- Filtered planets (cyan with labels) ---
    if not df_filtered.empty:
        mask_f = ((df_filtered["pl_orbper"] > 0) &
                  (df_filtered["pl_rade"] > 0))
        df_f = df_filtered[mask_f]
        ax.scatter(np.log10(df_f["pl_orbper"]),
                   np.log10(df_f["pl_rade"]),
                   s=80, c='cyan', edgecolors='black', linewidths=0.8,
                   zorder=5, label='Scheduled planets')
        for _, row in df_f.iterrows():
            ax.annotate(
                row["pl_name"],
                (np.log10(row["pl_orbper"]), np.log10(row["pl_rade"])),
                textcoords="offset points", xytext=(6, 6),
                fontsize=8, color='cyan', fontweight='bold', zorder=6)

    # --- Axes ---
    ax.set_xlim(np.log10(0.1), np.log10(P_max))
    ax.set_ylim(np.log10(0.3), np.log10(R_max))

    # X ticks (Period)
    p_ticks = [0.1, 0.3, 1, 3, 10, 30, 100]
    p_ticks = [t for t in p_ticks if t <= P_max]
    ax.set_xticks([np.log10(t) for t in p_ticks])
    ax.set_xticklabels([str(t) for t in p_ticks])
    ax.set_xlabel("Orbital Period [days]", fontsize=13)

    # Y left: R_Earth
    r_ticks = [0.5, 1, 2, 4, 8, 15]
    r_ticks = [t for t in r_ticks if t <= R_max]
    ax.set_yticks([np.log10(t) for t in r_ticks])
    ax.set_yticklabels([str(t) for t in r_ticks])
    ax.set_ylabel("Planet Radius [R$_\\oplus$]", fontsize=13)

    # Y right: R_Jupiter
    ax2 = ax.twinx()
    ax2.set_ylim(ax.get_ylim())
    rj_ticks = [0.05, 0.1, 0.2, 0.5, 1.0]
    rj_alts = [np.log10(rj * RJUP_TO_REARTH) for rj in rj_ticks]
    rj_alts_in = [a for a, rj in zip(rj_alts, rj_ticks)
                  if ax.get_ylim()[0] <= a <= ax.get_ylim()[1]]
    rj_ticks_in = [rj for a, rj in zip(rj_alts, rj_ticks)
                   if ax.get_ylim()[0] <= a <= ax.get_ylim()[1]]
    ax2.set_yticks(rj_alts_in)
    ax2.set_yticklabels([str(rj) for rj in rj_ticks_in])
    ax2.set_ylabel("Planet Radius [R$_J$]", fontsize=13)

    ax.legend(loc='upper left', fontsize=10)
    ax.set_title("Period — Radius Landscape", fontsize=15)

    fig.tight_layout()
    out_path = os.path.join(output_dir, "PR_landscape.pdf")
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out_path}")
