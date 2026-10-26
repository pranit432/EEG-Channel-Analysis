"""Channel-by-channel view of the EEG: traces, band power per channel, group results and scalp maps.

Reads the EDF files from the music project (read-only) and writes everything into this folder:
  figures/*.png, results/channel_stats.csv, results/channel_band_means.csv

Run:  python channel_plots.py
"""
import os
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from scipy.signal import welch
from scipy.stats import wilcoxon

mne.set_log_level("ERROR")
HERE = Path(__file__).parent
# Read-only source: set the EEG_DATA environment variable, or keep the music project's data folder next to this one.
DATA = Path(os.environ.get("EEG_DATA", HERE.parent / "eeg-music-project" / "data" / "tempo" / "music1"))
FIG, RES = HERE / "figures", HERE / "results"
FIG.mkdir(exist_ok=True)
RES.mkdir(exist_ok=True)

BANDS = {"delta": (1, 4), "theta": (4, 8), "alpha": (8, 13), "beta": (13, 30), "gamma": (30, 45)}
BAND_NAMES = list(BANDS)
SCALP = ["Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8", "T3", "C3", "Cz", "C4", "T4", "T5", "P3", "P4", "T6", "O1", "O2"]  # front to back
OTHER = ["CM", "A1", "A2", "X1", "X2", "X3"]  # common-mode, ear references and auxiliary inputs, not scalp electrodes
REGION = {"Fp1": "Frontal", "Fp2": "Frontal", "F7": "Frontal", "F3": "Frontal", "Fz": "Frontal", "F4": "Frontal", "F8": "Frontal",
          "T3": "Temporal", "T4": "Temporal", "T5": "Temporal", "T6": "Temporal", "C3": "Central", "Cz": "Central", "C4": "Central",
          "P3": "Parietal", "P4": "Parietal", "O1": "Occipital", "O2": "Occipital"}
REGION_COL = {"Frontal": "#E4572E", "Central": "#C98A00", "Temporal": "#7C5CBF", "Parietal": "#2B6CB0", "Occipital": "#0E9F8E"}
OLD_TO_NEW = {"T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8"}  # 10-20 names used by the headset vs the standard montage
EDGE_S, WIN_S, REJECT_UV, BAD_MAD, MIN_WIN, MIN_MUSIC_S = 2, 2, 200, 3, 8, 40
TRIAL = re.compile(r"^S\d+E\d+_filtered\.edf$")  # excludes duplicate parts such as S05E02_0001
GREY, TEAL, CORAL, INK = "#8A94A6", "#0E9F8E", "#E4572E", "#1F2430"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK,
                     "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 200, "savefig.bbox": "tight"})


# ------------------------------------------------------------------ loading and cleaning
def load(path):
    raw = mne.io.read_raw_edf(path, preload=True, verbose="error")
    raw.rename_channels({c: c.replace("EEG ", "").replace("-Pz", "") for c in raw.ch_names})
    return raw


def music_span(raw):
    a = raw.annotations
    start = [o for o, d in zip(a.onset, a.description) if "start" in d]
    end = [o for o, d in zip(a.onset, a.description) if "end" in d and o > 0]
    return (start[0], end[-1]) if start and end and end[-1] - start[0] >= MIN_MUSIC_S else None


def noisy_channels(data):
    """Channels whose std exceeds 3x the median (on an average-referenced signal, repeated up to 3 times). data: (ch, samples)."""
    keep = list(range(data.shape[0]))
    for _ in range(3):
        x = data[keep] - data[keep].mean(axis=0)
        std = x.std(axis=1)
        bad = [k for k, s in zip(keep, std) if s > BAD_MAD * np.median(std)]
        if not bad:
            break
        keep = [k for k in keep if k not in bad]
    return [SCALP[i] for i in range(len(SCALP)) if i not in keep], keep


def prepare(path, crop):
    """-> (scalp data in volts (18, samples) average-referenced on the kept channels, dropped names, sfreq, raw) or None."""
    raw = load(path)
    if crop:
        span = music_span(raw)
        if span is None:
            return None
        raw.crop(*span)
    data = raw.copy().pick(SCALP).reorder_channels(SCALP).get_data()
    dropped, keep = noisy_channels(data)
    data = data - data[keep].mean(axis=0)
    return data, dropped, raw.info["sfreq"], raw


def clean_windows(data, sf, dropped):
    """Windows (n, ch, samples) of the kept channels with no peak-to-peak swing above 200 uV."""
    keep = [i for i, c in enumerate(SCALP) if c not in dropped]
    x = data[keep, int(EDGE_S * sf): data.shape[1] - int(EDGE_S * sf)]
    w = int(WIN_S * sf)
    wins = [x[:, i * w:(i + 1) * w] for i in range(x.shape[1] // w)]
    return [v for v in wins if np.ptp(v, axis=1).max() * 1e6 < REJECT_UV], keep


def channel_band_power(path, crop):
    """-> dict(rel=(18, 5) relative power with NaN for dropped channels, dropped=[...], kept=n windows) or None if unusable."""
    p = prepare(path, crop)
    if p is None:
        return None
    data, dropped, sf, _ = p
    wins, keep = clean_windows(data, sf, dropped)
    if len(wins) < MIN_WIN:
        return None
    f, psd = welch(np.stack(wins), fs=sf, nperseg=int(WIN_S * sf))
    psd = psd.mean(axis=0)  # (kept channels, freqs)
    df = f[1] - f[0]
    bp = np.stack([psd[:, (f >= lo) & (f < hi)].sum(axis=1) * df for lo, hi in BANDS.values()], axis=1)
    rel = np.full((len(SCALP), len(BANDS)), np.nan)
    rel[keep] = bp / bp.sum(axis=1, keepdims=True)
    return {"rel": rel, "dropped": dropped, "kept": len(wins)}


# ------------------------------------------------------------------ group computation
def group_results():
    subjects = sorted(d.name for d in DATA.glob("S*") if d.is_dir())
    base, music, drops, n_rec = {}, {}, {c: 0 for c in SCALP}, 0
    for s in subjects:
        b = channel_band_power(DATA / s / f"{s}BS_filtered.edf", crop=False)
        trials = [channel_band_power(f, crop=True) for f in sorted((DATA / s).glob("*_filtered.edf")) if TRIAL.match(f.name)]
        trials = [t for t in trials if t is not None]
        if b is None or not trials:
            print(s, "skipped")
            continue
        base[s] = b["rel"]
        with np.errstate(all="ignore"):
            music[s] = np.nanmean(np.stack([t["rel"] for t in trials]), axis=0)
        for rec in [b] + trials:
            n_rec += 1
            for c in rec["dropped"]:
                drops[c] += 1
        print(s, "ok", len(trials), "trials", flush=True)
    return base, music, drops, n_rec


def holm(p):
    order = np.argsort(p)
    adj, running = np.empty(len(p)), 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(p) - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


# ------------------------------------------------------------------ figures
def fig_traces(subject="S09", rec="E01"):
    """All 24 channels, 10 s of baseline next to 10 s of music, same scale. Cleanest 10 s window of each."""
    panels = []
    for label, fname, crop in (("Baseline", f"{subject}BS_filtered.edf", False), (f"Music ({rec})", f"{subject}{rec}_filtered.edf", True)):
        data, dropped, sf, raw = prepare(DATA / subject / fname, crop)
        other = raw.copy().pick(OTHER).reorder_channels(OTHER).get_data()
        lo, hi, step, win = int(EDGE_S * sf), data.shape[1] - int(EDGE_S * sf), int(2 * sf), int(10 * sf)
        keep = [i for i, c in enumerate(SCALP) if c not in dropped]
        best = min(range(lo, hi - win, step), key=lambda a: np.ptp(data[keep, a:a + win], axis=1).max())
        seg = np.vstack([data[:, best:best + win], other[:, best:best + win] - other[:, best:best + win].mean(axis=1, keepdims=True)]) * 1e6
        panels.append((label, seg, dropped, best / sf))
    names = SCALP + OTHER
    spacing, gap = 70, 110
    yp = lambda i: (len(names) - 1 - i) * spacing - (gap if i >= len(SCALP) else 0)
    fig, axes = plt.subplots(1, 2, figsize=(14, 10.5), sharey=True)
    t = np.arange(panels[0][1].shape[1]) / sf
    for ax, (label, seg, dropped, t0) in zip(axes, panels):
        for i, c in enumerate(names):
            y = yp(i)
            col = CORAL if c in dropped else (GREY if c in OTHER else INK)
            ax.plot(t, seg[i] + y, color=col, lw=0.6)
        ax.set_title(f"{label}: 10 s starting {t0:.0f} s into the recording", fontsize=11, loc="left")
        ax.set_xlabel("Time (s)")
        ax.set_yticks([yp(i) for i in range(len(names))])
        ax.set_yticklabels(names)
        for lab, c in zip(ax.get_yticklabels(), names):
            lab.set_color(CORAL if c in dropped else (GREY if c in OTHER else INK))
        ax.plot([9.2, 9.2], [yp(len(names) - 1) - 75, yp(len(names) - 1) - 25], color=INK, lw=2)
        ax.text(9.1, yp(len(names) - 1) - 50, "50 µV", ha="right", va="center", fontsize=8.5)
        ax.set_ylim(yp(len(names) - 1) - 90, len(names) * spacing)
        ax.axhline((yp(len(SCALP) - 1) + yp(len(SCALP))) / 2, color=GREY, lw=0.8, ls=":")
    fig.suptitle(f"{subject}: all 24 channels (dark = scalp, grey = reference/auxiliary, red = dropped as noisy)", fontsize=12, x=0.02, ha="left")
    fig.tight_layout()
    fig.savefig(FIG / f"fig1_traces_{subject}.png")
    plt.close(fig)
    return panels


def fig_heatmap(subject="S09", rec="E01"):
    cmap = LinearSegmentedColormap.from_list("t", ["#F6F8FB", "#0E9F8E", "#0F172A"])
    res = {"Baseline": channel_band_power(DATA / subject / f"{subject}BS_filtered.edf", False),
           f"Music ({rec})": channel_band_power(DATA / subject / f"{subject}{rec}_filtered.edf", True)}
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 7.2), sharey=True)
    for ax, (label, r) in zip(axes, res.items()):
        im = ax.imshow(r["rel"], aspect="auto", cmap=cmap, vmin=0, vmax=0.75)
        ax.set_xticks(range(5), [b.capitalize() for b in BAND_NAMES])
        ax.set_yticks(range(len(SCALP)), SCALP)
        ax.set_title(label, fontsize=11, loc="left")
        for i in range(len(SCALP)):
            for j in range(5):
                v = r["rel"][i, j]
                ax.text(j, i, "dropped" if np.isnan(v) and j == 2 else ("" if np.isnan(v) else f"{v:.2f}"), ha="center", va="center", fontsize=7.5,
                        color="white" if (not np.isnan(v) and v > 0.4) else INK)
        for sp in ax.spines.values():
            sp.set_visible(False)
    fig.colorbar(im, ax=axes, shrink=0.6, label="Relative power (share of 1-45 Hz)")
    fig.suptitle(f"{subject}: share of each channel's power in each band", fontsize=12, x=0.02, ha="left")
    fig.savefig(FIG / f"fig2_channel_band_heatmap_{subject}.png")
    plt.close(fig)
    return res


def channel_table(base, music):
    subs = sorted(base)
    rows = []
    for ci, c in enumerate(SCALP):
        b = np.array([base[s][ci, 2] for s in subs]); m = np.array([music[s][ci, 2] for s in subs])
        ok = ~np.isnan(b) & ~np.isnan(m)
        p = wilcoxon(m[ok] - b[ok]).pvalue if ok.sum() >= 6 else np.nan
        rows.append({"channel": c, "region": REGION[c], "n_subjects": int(ok.sum()), "alpha_baseline": b[ok].mean(), "alpha_music": m[ok].mean(),
                     "alpha_change": (m[ok] - b[ok]).mean(), "n_higher_in_music": int((m[ok] > b[ok]).sum()), "p": p})
    t = pd.DataFrame(rows)
    t["p_holm"] = holm(t["p"].fillna(1).to_numpy())
    return t


def fig_group_alpha(t):
    fig, ax = plt.subplots(figsize=(8.2, 7))
    y = np.arange(len(t))[::-1]
    h = 0.38
    ax.barh(y + h / 2, t.alpha_baseline, h, color=GREY, label="Baseline")
    ax.barh(y - h / 2, t.alpha_music, h, color=TEAL, label="Music")
    for yi, (_, r) in zip(y, t.iterrows()):
        star = "***" if r.p_holm < 0.001 else "**" if r.p_holm < 0.01 else "*" if r.p_holm < 0.05 else ""
        if star:
            ax.text(max(r.alpha_baseline, r.alpha_music) + 0.006, yi, star, va="center", color=CORAL, fontweight="bold")
    ax.set_yticks(y, [f"{c}  (n={n})" for c, n in zip(t.channel, t.n_subjects)])
    for lab, c in zip(ax.get_yticklabels(), t.channel):
        lab.set_color(REGION_COL[REGION[c]])
    ax.set_xlabel("Relative alpha power (mean over subjects)")
    ax.legend(frameon=False, loc="upper right")
    ax.set_xlim(0, 0.27)
    ax.set_title("Alpha by channel, front (top) to back (bottom)", fontsize=11, loc="left")
    fig.text(0.01, -0.02, "Label colour = region. * Holm-corrected p < 0.05, ** < 0.01, *** < 0.001 (paired Wilcoxon across subjects).", fontsize=8)
    fig.savefig(FIG / "fig3_alpha_by_channel_group.png")
    plt.close(fig)


def fig_topomaps(base, music):
    names_new = [OLD_TO_NEW.get(c, c) for c in SCALP]
    info = mne.create_info(names_new, 300.0, "eeg")
    info.set_montage(mne.channels.make_standard_montage("standard_1020"), match_case=False)
    subs = sorted(base)
    mb = np.nanmean(np.stack([base[s][:, 2] for s in subs]), axis=0)
    mm = np.nanmean(np.stack([music[s][:, 2] for s in subs]), axis=0)
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.6))
    vmax = max(mb.max(), mm.max())
    for ax, vals, title, vlim, cmap in ((axes[0], mb, "Baseline", (0, vmax), "viridis"), (axes[1], mm, "Music", (0, vmax), "viridis"),
                                        (axes[2], mm - mb, "Music minus baseline", (-(mm - mb).max(), (mm - mb).max()), "RdBu_r")):
        im, _ = mne.viz.plot_topomap(vals, info, axes=ax, show=False, cmap=cmap, vlim=vlim, names=SCALP, sensors="k.", contours=0,
                                     sphere=0.095, extrapolate="local")
        ax.set_title(title, fontsize=11)
        fig.colorbar(im, ax=ax, shrink=0.7)
    fig.suptitle("Relative alpha power across the scalp (mean of 18 subjects; nose at top)", fontsize=12, x=0.02, ha="left")
    fig.savefig(FIG / "fig4_topomaps_alpha.png")
    plt.close(fig)
    return mb, mm


def fig_quality(drops, n_rec):
    pct = [100 * drops[c] / n_rec for c in SCALP]
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    ax.bar(SCALP, pct, color=[REGION_COL[REGION[c]] for c in SCALP])
    ax.set_ylabel("Recordings where the channel\nwas dropped as noisy (%)")
    for i, v in enumerate(pct):
        ax.text(i, v + 0.6, f"{v:.0f}", ha="center", fontsize=8)
    ax.set_title(f"Channel quality across {n_rec} recordings", fontsize=11, loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in REGION_COL.values()]
    ax.legend(handles, REGION_COL.keys(), frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=8.5)
    fig.savefig(FIG / "fig5_channel_quality.png")
    plt.close(fig)
    return dict(zip(SCALP, pct))


if __name__ == "__main__":
    panels = fig_traces("S09", "E01")
    print("trace windows (s):", [(p[0], round(p[3])) for p in panels], "dropped:", [p[2] for p in panels])
    s09 = fig_heatmap("S09", "E01")
    base, music, drops, n_rec = group_results()
    t = channel_table(base, music)
    t["pct_recordings_dropped"] = [100 * drops[c] / n_rec for c in t.channel]
    t.to_csv(RES / "channel_stats.csv", index=False)
    band_rows = []
    subs = sorted(base)
    for bi, b in enumerate(BAND_NAMES):
        for ci, c in enumerate(SCALP):
            bb = np.nanmean([base[s][ci, bi] for s in subs]); mm_ = np.nanmean([music[s][ci, bi] for s in subs])
            band_rows.append({"channel": c, "band": b, "baseline": bb, "music": mm_, "change": mm_ - bb})
    pd.DataFrame(band_rows).to_csv(RES / "channel_band_means.csv", index=False)
    np.savez(RES / "subject_channel_band.npz", subjects=np.array(subs), base=np.stack([base[x] for x in subs]),
             music=np.stack([music[x] for x in subs]), drops=np.array([drops[c] for c in SCALP]), n_rec=n_rec)  # used by the app
    fig_group_alpha(t)
    fig_topomaps(base, music)
    fig_quality(drops, n_rec)
    print("subjects:", len(subs), "recordings:", n_rec)
    print(t.round(4).to_string(index=False))
