"""Pages for the channel-by-channel EEG app (entry point: app.py).

Importing this module has no side effects beyond what channel_plots does (creating its output folders)."""
from pathlib import Path

import altair as alt
import matplotlib.pyplot as plt
import mne
import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import wilcoxon

import channel_plots as cp

HERE = Path(__file__).parent
TEAL, CORAL, GREY, INK = "#0E9F8E", "#E4572E", "#8A94A6", "#E8ECF2"
BAND_LABELS = {"delta": "Delta (1-4 Hz)", "theta": "Theta (4-8 Hz)", "alpha": "Alpha (8-13 Hz)", "beta": "Beta (13-30 Hz)", "gamma": "Gamma (30-45 Hz)"}
DEFAULT_SUBJECT = "S09"  # the largest baseline-vs-music change of the 18 subjects


# ------------------------------------------------------------------ cached data access
@st.cache_data
def subjects():
    return sorted(p.name for p in cp.DATA.glob("S*") if p.is_dir())


@st.cache_data
def recordings(sub):
    return ["BS"] + [f.name[len(sub):].split("_")[0] for f in sorted((cp.DATA / sub).glob("*_filtered.edf")) if cp.TRIAL.match(f.name)]


def rec_path(sub, rec):
    return cp.DATA / sub / f"{sub}{rec}_filtered.edf"


@st.cache_data(show_spinner="Loading the recording...", max_entries=40)
def load_recording(sub, rec):
    """Scalp traces (18 x samples, volts), the six other channels, dropped channel names, sampling rate. None if unusable."""
    p = cp.prepare(rec_path(sub, rec), crop=rec != "BS")
    if p is None:
        return None
    data, dropped, sf, raw = p
    other = raw.copy().pick(cp.OTHER).reorder_channels(cp.OTHER).get_data()
    wins, _ = cp.clean_windows(data, sf, dropped)
    return {"data": data, "other": other, "dropped": dropped, "sf": sf, "duration": data.shape[1] / sf, "clean_windows": len(wins)}


@st.cache_data(show_spinner="Computing band power per channel...", max_entries=80)
def band_power(sub, rec):
    r = cp.channel_band_power(rec_path(sub, rec), crop=rec != "BS")
    return None if r is None else r["rel"]


@st.cache_data
def cleanest_start(sub, rec, length):
    r = load_recording(sub, rec)
    sf, data = r["sf"], r["data"]
    keep = [i for i, c in enumerate(cp.SCALP) if c not in r["dropped"]]
    lo, hi, win = int(cp.EDGE_S * sf), data.shape[1] - int(cp.EDGE_S * sf), int(length * sf)
    best = min(range(lo, hi - win + 1, int(sf)), key=lambda a: np.ptp(data[keep, a:a + win], axis=1).max())
    return round(best / sf)


@st.cache_data
def group_data():
    z = np.load(cp.RES / "subject_channel_band.npz")
    return {"subjects": list(z["subjects"]), "base": z["base"], "music": z["music"], "drops": z["drops"], "n_rec": int(z["n_rec"])}


@st.cache_data
def group_table(band):
    """Per-channel baseline vs music for one band, across people (paired Wilcoxon, Holm-corrected over the 18 channels)."""
    d, bi = group_data(), cp.BAND_NAMES.index(band)
    rows = []
    for ci, c in enumerate(cp.SCALP):
        b, m = d["base"][:, ci, bi], d["music"][:, ci, bi]
        ok = ~np.isnan(b) & ~np.isnan(m)
        p = wilcoxon(m[ok] - b[ok]).pvalue if ok.sum() >= 6 else np.nan
        rows.append({"channel": c, "region": cp.REGION[c], "people": int(ok.sum()), "baseline": b[ok].mean(), "music": m[ok].mean(),
                     "change": (m[ok] - b[ok]).mean(), "higher_in_music": int((m[ok] > b[ok]).sum()), "p": p})
    t = pd.DataFrame(rows)
    t["p_holm"] = cp.holm(t["p"].fillna(1).to_numpy())
    t["significant"] = t["p_holm"] < 0.05
    return t


@st.cache_resource
def montage_info(names):
    new = [cp.OLD_TO_NEW.get(c, c) for c in names]
    info = mne.create_info(list(new), 300.0, "eeg")
    info.set_montage(mne.channels.make_standard_montage("standard_1020"), match_case=False)
    return info


# ------------------------------------------------------------------ figures
def trace_figure(r, t0, length, spacing):
    names = cp.SCALP + cp.OTHER
    gap = 110
    yp = lambda i: (len(names) - 1 - i) * spacing - (gap if i >= len(cp.SCALP) else 0)
    sf, a, b = r["sf"], int(t0 * r["sf"]), int((t0 + length) * r["sf"])
    other = r["other"][:, a:b]
    seg = np.vstack([r["data"][:, a:b], other - other.mean(axis=1, keepdims=True)]) * 1e6
    t = np.arange(seg.shape[1]) / sf + t0
    fig, ax = plt.subplots(figsize=(11, 8.5))
    fig.patch.set_facecolor("#0F1420")
    ax.set_facecolor("#0F1420")
    for i, c in enumerate(names):
        col = CORAL if c in r["dropped"] else (GREY if c in cp.OTHER else "#E8ECF2")
        ax.plot(t, seg[i] + yp(i), color=col, lw=0.6)
    ax.set_yticks([yp(i) for i in range(len(names))])
    ax.set_yticklabels(names)
    for lab, c in zip(ax.get_yticklabels(), names):
        lab.set_color(CORAL if c in r["dropped"] else (GREY if c in cp.OTHER else INK))
    ax.axhline((yp(len(cp.SCALP) - 1) + yp(len(cp.SCALP))) / 2, color=GREY, lw=0.8, ls=":")
    ax.plot([t0 + length - 0.5] * 2, [yp(len(names) - 1) - 75, yp(len(names) - 1) - 25], color=INK, lw=2)
    ax.text(t0 + length - 0.65, yp(len(names) - 1) - 50, "50 µV", ha="right", va="center", fontsize=9, color=INK)
    ax.set_ylim(yp(len(names) - 1) - 90, len(names) * spacing)
    ax.set_xlim(t0, t0 + length)
    ax.set_xlabel("Time in the recording (s)", color=INK)
    ax.tick_params(colors=INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GREY)
    fig.tight_layout()
    return fig


def scalp_maps(maps):
    """maps: list of (title, values over the 18 scalp channels (NaN = missing), vlim, cmap)."""
    fig, axes = plt.subplots(1, len(maps), figsize=(4.4 * len(maps), 4.3))
    fig.patch.set_facecolor("#0F1420")
    for ax, (title, vals, vlim, cmap) in zip(np.atleast_1d(axes), maps):
        ok = ~np.isnan(vals)
        names = [c for c, o in zip(cp.SCALP, ok) if o]
        im, _ = mne.viz.plot_topomap(vals[ok], montage_info(tuple(names)), axes=ax, show=False, cmap=cmap, vlim=vlim, names=names, sensors="k.",
                                     contours=0, sphere=0.095, extrapolate="local")
        ax.set_title(title, color=INK, fontsize=11)
        cb = fig.colorbar(im, ax=ax, shrink=0.7)
        cb.ax.yaxis.set_tick_params(color=INK)
        plt.setp(cb.ax.get_yticklabels(), color=INK)
    fig.tight_layout()
    return fig


def heatmap_chart(rel):
    df = pd.DataFrame([{"channel": c, "band": b, "share": rel[i, j]} for i, c in enumerate(cp.SCALP) for j, b in enumerate(cp.BAND_NAMES)]).dropna()
    base = alt.Chart(df).encode(x=alt.X("band:N", sort=cp.BAND_NAMES, title=None, axis=alt.Axis(labelAngle=0, labelExpr="upper(datum.label)")),
                                y=alt.Y("channel:N", sort=cp.SCALP, title=None))
    rect = base.mark_rect().encode(color=alt.Color("share:Q", scale=alt.Scale(range=["#1A2233", TEAL, "#E8FFFB"], domain=[0, 0.8]), legend=alt.Legend(title="Share")),
                                   tooltip=["channel", "band", alt.Tooltip("share:Q", format=".3f")])
    text = base.mark_text(fontSize=10).encode(text=alt.Text("share:Q", format=".2f"), color=alt.condition("datum.share > 0.45", alt.value("#0F1420"), alt.value("#E8ECF2")))
    return (rect + text).properties(height=520)


def scalp_values_for(sub, rec, bi):
    rel = band_power(sub, rec)
    return None if rel is None else rel[:, bi]


# ------------------------------------------------------------------ pages
def explore_page():
    st.header("Explore a recording")
    st.write("Pick a person and a recording. The traces show the electrical activity of every channel; the heatmap and the scalp maps show how much "
             "of each channel's activity falls in each frequency band.")
    subs = subjects()
    if not subs:
        st.info("The raw EEG files were not found, so this page is unavailable. Set the EEG_DATA environment variable to the folder that "
                "holds the subject folders (see the README). The other pages work without them.")
        return
    c1, c2 = st.columns(2)
    sub = c1.selectbox("Subject", subs, index=subs.index(DEFAULT_SUBJECT), key="exp_sub", help="S09 has the biggest baseline-vs-music change; S01 has almost none.")
    recs = recordings(sub)
    rec = c2.selectbox("Recording", recs, index=recs.index("E01") if "E01" in recs else 0, key=f"exp_rec_{sub}",
                       format_func=lambda r: "Baseline" if r == "BS" else f"Music trial {r}")
    r = load_recording(sub, rec)
    if r is None:
        st.warning("This music trial has less than 40 s of music marked in the file, so it is skipped (as in the main analysis).")
        st.stop()

    m1, m2, m3 = st.columns(3)
    m1.metric("Length analysed", f"{r['duration']:.0f} s", border=True, help="For music trials, only the part between the start and end markers.")
    m2.metric("Clean 2 s windows", r["clean_windows"], border=True, help="Windows with no swing above 200 µV on any kept channel.")
    m3.metric("Channels dropped as noisy", ", ".join(r["dropped"]) or "none", border=True)

    st.subheader("Raw traces, all 24 channels")
    lengths = [n for n in (5, 10, 20) if n <= r["duration"] - 2 * cp.EDGE_S]
    if not lengths:
        st.warning("This recording is too short to show a trace window.")
        st.stop()
    a, b, c = st.columns([1, 3, 1])
    length = a.select_slider("Window (s)", lengths, value=10 if 10 in lengths else lengths[-1], key=f"len_{sub}_{rec}")
    lo, hi = cp.EDGE_S, int(r["duration"] - cp.EDGE_S - length)
    default = int(np.clip(cleanest_start(sub, rec, length), lo, max(lo, hi)))
    t0 = b.slider("Start of the window (s)", lo, max(lo, hi), default, key=f"t0_{sub}_{rec}_{length}", disabled=hi <= lo,
                  help="Starts on the cleanest stretch. Drag to look elsewhere.")
    spacing = c.slider("Spacing (µV)", 40, 150, 70, 10, key="spacing")
    st.pyplot(trace_figure(r, t0, length, spacing), width="stretch")
    st.caption("White = scalp channels (referenced to the average of the kept channels). Grey = reference, ear and auxiliary channels (CM, A1, A2, X1-X3), not scalp "
               "electrodes. Red = dropped as noisy in the analysis. X1-X3 are flat because they carry no signal.")

    st.subheader("Band power in each channel")
    rel = band_power(sub, rec)
    if rel is None:
        st.warning("Too little clean data to compute band power for this recording.")
        st.stop()
    left, right = st.columns([3, 2])
    with left:
        st.altair_chart(heatmap_chart(rel), width="stretch")
        st.caption("Each number is the share of that channel's 1-45 Hz power in that band; the five shares in a row add up to 1. Dropped channels are blank.")
    with right:
        top = np.array(cp.BAND_NAMES)[np.nanargmax(np.where(np.isnan(rel), -1, rel), axis=1)]
        n_ok = int((~np.isnan(rel[:, 0])).sum())
        st.markdown("**How to read this**")
        st.write("Darker cells mean a smaller share, brighter cells a larger one. Look for the brightest column: that band dominates.")
        st.info(f"In this recording, **alpha** is the largest band at {int((top == 'alpha').sum())} of {n_ok} channels, "
                f"and **delta** at {int((top == 'delta').sum())}.")
        band = st.selectbox("Band for the scalp maps below", cp.BAND_NAMES, index=2, format_func=BAND_LABELS.get, key="exp_band")

    bi = cp.BAND_NAMES.index(band)
    vals = rel[:, bi]
    maps = []
    base_vals = scalp_values_for(sub, "BS", bi) if rec != "BS" else None
    vmax = float(np.nanmax(np.concatenate([vals] + ([base_vals] if base_vals is not None else []))))
    if base_vals is not None:
        maps.append(("Baseline", base_vals, (0, vmax), "viridis"))
    maps.append(("Baseline" if rec == "BS" else f"Trial {rec}", vals, (0, vmax), "viridis"))
    if base_vals is not None:
        diff = vals - base_vals
        lim = float(np.nanmax(np.abs(diff))) or 0.01
        maps.append(("Trial minus baseline", diff, (-lim, lim), "RdBu_r"))
    st.subheader(f"{BAND_LABELS[band]} on the scalp")
    st.pyplot(scalp_maps(maps), width="stretch")
    st.caption(f"Relative {band} power (nose at the top). Colour is drawn only inside the area covered by electrodes.")


def group_page():
    st.header("Baseline vs music, channel by channel")
    d = group_data()
    st.write(f"Each person's baseline is compared with the average of their own music trials, for every channel. {len(d['subjects'])} people; "
             "channels that were noisy in a recording are left out of that comparison, so the number of people differs a little per channel.")
    band = st.selectbox("Band", cp.BAND_NAMES, index=2, format_func=BAND_LABELS.get, key="grp_band")
    t = group_table(band)
    sig = t[t.significant]
    biggest = t.loc[t.change.abs().idxmax()]
    m1, m2, m3 = st.columns(3)
    m1.metric("Channels with a reliable change", f"{len(sig)} of {len(t)}", border=True, help="Holm-corrected p below 0.05 (paired Wilcoxon across people).")
    m2.metric("Biggest change", f"{biggest.channel}  {biggest.change:+.3f}", border=True)
    m3.metric("Channels higher in music", f"{int((t.change > 0).sum())} of {len(t)}", border=True)

    long = pd.concat([t.assign(condition="Baseline", value=t.baseline), t.assign(condition="Music", value=t.music)])
    bars = alt.Chart(long).mark_bar().encode(
        y=alt.Y("channel:N", sort=cp.SCALP, title=None), yOffset="condition:N", x=alt.X("value:Q", title=f"Relative {band} power (mean over people)"),
        color=alt.Color("condition:N", scale=alt.Scale(domain=["Baseline", "Music"], range=[GREY, TEAL]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["channel", "condition", alt.Tooltip("value:Q", format=".3f"), "people"])
    stars = alt.Chart(t[t.significant]).mark_text(align="left", dx=6, color=CORAL, fontWeight="bold", fontSize=13).encode(
        y=alt.Y("channel:N", sort=cp.SCALP), x=alt.X("music:Q"), text=alt.value("★"))
    left, right = st.columns([3, 2])
    with left:
        st.altair_chart((bars + stars).properties(height=560), width="stretch")
        st.caption("Channels run front (top) to back (bottom). A star marks a reliable difference after correcting for testing 18 channels.")
    with right:
        up = t.sort_values("change", ascending=False)
        st.markdown("**How to read this**")
        st.write("Each pair of bars is one channel: grey is baseline, teal is music. A longer teal bar means that band takes a larger share of the channel's activity during music.")
        st.info(f"Biggest rises in {band}: " + ", ".join(f"**{c}** ({v:+.3f})" for c, v in zip(up.channel.head(3), up.change.head(3))) +
                f". Smallest: **{up.channel.iloc[-1]}** ({up.change.iloc[-1]:+.3f}).")
        weak = t[~t.significant]
        if len(weak):
            drop = {c: 100 * x / d["n_rec"] for c, x in zip(cp.SCALP, d["drops"])}
            st.write("Not reliable after correction: " + ", ".join(f"{c} ({drop[c]:.0f}% of recordings dropped)" for c in weak.channel) +
                     ". That is not the same as no change. A channel that is dropped often has fewer people in the comparison, which weakens the test.")

    bi = cp.BAND_NAMES.index(band)
    mb, mm = np.nanmean(d["base"][:, :, bi], axis=0), np.nanmean(d["music"][:, :, bi], axis=0)
    diff = mm - mb
    lim = float(np.abs(diff).max())
    vmax = float(max(mb.max(), mm.max()))
    st.subheader(f"{BAND_LABELS[band]} on the scalp")
    st.pyplot(scalp_maps([("Baseline", mb, (0, vmax), "viridis"), ("Music", mm, (0, vmax), "viridis"), ("Music minus baseline", diff, (-lim, lim), "RdBu_r")]),
              width="stretch")
    st.caption(f"Mean relative {band} power across people (nose at the top).")

    st.subheader("Numbers")
    shown = t.assign(significant=t.significant).rename(columns={"p": "p (uncorrected)", "p_holm": "p (Holm)", "higher_in_music": "people higher in music"})
    st.dataframe(shown, hide_index=True, width="stretch", column_config={
        "baseline": st.column_config.NumberColumn(format="%.3f"), "music": st.column_config.NumberColumn(format="%.3f"),
        "change": st.column_config.NumberColumn(format="%+.3f"), "p (uncorrected)": st.column_config.NumberColumn(format="%.4f"),
        "p (Holm)": st.column_config.NumberColumn(format="%.4f"), "significant": st.column_config.CheckboxColumn("reliable")})
    st.download_button("Download this table (CSV)", shown.to_csv(index=False).encode(), f"channel_{band}_baseline_vs_music.csv", "text/csv", icon=":material/download:")
    st.caption("Relative power is a share, so a rise in one band comes with a fall in another. The 18 channel tests are not independent, since neighbouring "
               "electrodes see similar activity.")


def quality_page():
    st.header("Channel quality")
    d = group_data()
    st.write(f"A channel is dropped from a recording when its signal is much noisier than the others (standard deviation above 3 times the median). "
             f"This shows how often that happened across {d['n_rec']} recordings.")
    df = pd.DataFrame({"channel": cp.SCALP, "region": [cp.REGION[c] for c in cp.SCALP], "dropped_pct": 100 * d["drops"] / d["n_rec"]})
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("channel:N", sort=cp.SCALP, title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y("dropped_pct:Q", title="Recordings where it was dropped (%)"),
        color=alt.Color("region:N", scale=alt.Scale(domain=list(cp.REGION_COL), range=list(cp.REGION_COL.values())), legend=alt.Legend(orient="top", title=None)),
        tooltip=["channel", "region", alt.Tooltip("dropped_pct:Q", format=".1f")])
    labels = chart.mark_text(dy=-8, fontSize=11, color=INK).encode(text=alt.Text("dropped_pct:Q", format=".0f"))
    st.altair_chart((chart + labels).properties(height=380), width="stretch")
    worst = df.sort_values("dropped_pct", ascending=False).head(4)
    st.info("The least reliable channels are on the forehead and outer front: " + ", ".join(f"{c} ({p:.0f}%)" for c, p in zip(worst.channel, worst.dropped_pct)) +
            ". Eye blinks and facial muscle activity are the likely cause. The channels at the back (O1, O2) are dropped in about 8-9% of recordings, and most others in 6% or fewer.")
    st.caption("Six more channels are never analysed because they are not scalp electrodes: CM, A1, A2 (reference and ear channels) and X1, X2, X3 (auxiliary inputs, flat).")


def observations_page():
    st.header("Observations")
    text = (HERE / "observations.md").read_text(encoding="utf-8")
    figs = {f"Figure {i}": next((HERE / "figures").glob(f"fig{i}_*.png"), None) for i in range(1, 6)}
    sections = text.split("\n## ")
    st.markdown(sections[0].split("\n---")[0].replace("# Channel-by-channel EEG: plots and observations\n", ""))
    for sec in sections[1:]:
        head, _, body = sec.partition("\n")
        st.markdown(f"## {head}\n{body.split(chr(10) + '---')[0]}")
        key = next((k for k in figs if head.startswith(k)), None)
        if key and figs[key]:
            st.image(str(figs[key]), width="stretch")
    st.markdown("---")


def about_page():
    st.header("About")
    st.markdown("**What this is.** A channel-by-channel look at EEG recorded while 18 people listened to music, compared with each person's baseline recording. "
                "It shows what every sensor on the head recorded, and where on the scalp the activity changes.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("People", 18, border=True)
    m2.metric("Channels recorded", 24, border=True, help="Plus a Trigger marker channel.")
    m3.metric("Scalp channels analysed", 18, border=True, help="CM, A1, A2 and X1-X3 are reference, ear or auxiliary channels.")
    m4.metric("Sampling rate", "300 Hz", border=True)
    st.markdown("**Frequency bands.** Delta 1-4 Hz (slow), theta 4-8 Hz, alpha 8-13 Hz (relaxed wakefulness), beta 13-30 Hz (alert), gamma 30-45 Hz (fast). "
                "*Relative power* is a band's share of a channel's total 1-45 Hz power.")
    st.markdown("**Cleaning.** Channels much noisier than the rest are dropped, the remaining channels are average-referenced, the signal is cut into 2 s windows, and any "
                "window with a swing above 200 µV is rejected. Music trials are cut to the part between the start and end markers stored in the file.")
    st.markdown("**Data.** Music Tempo Emotional Impact EEG Dataset (Kaggle, aphros, Apache-2.0), DSI-24 headset. The EEG files are read from the main project folder and never changed.")
    st.warning("**Limits**\n"
               "- The baseline protocol (eyes open or closed) is not documented. A back-of-head alpha peak is also what closed eyes look like, so the channel pattern "
               "cannot separate a music effect from that.\n"
               "- Trial tempo labels are not in the files, so all music trials are pooled.\n"
               "- Only EEG was recorded, so nothing here says how people felt or performed.\n"
               "- Forehead channels are often noisy, so the comparison there rests on fewer people.")
