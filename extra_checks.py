"""Numbers quoted in observations.md. Run: python extra_checks.py"""
import numpy as np
import pandas as pd
from scipy.signal import welch
import channel_plots as cp

# 1) auxiliary and reference channels, S09 baseline and music: standard deviation in microvolts
print("== std of non-scalp channels (uV), S09 ==")
for label, f in (("baseline", "S09BS_filtered.edf"), ("music E01", "S09E01_filtered.edf")):
    raw = cp.load(cp.DATA / "S09" / f)
    d = raw.copy().pick(cp.OTHER).reorder_channels(cp.OTHER).get_data() * 1e6
    print(label, {c: round(float(x.std()), 2) for c, x in zip(cp.OTHER, d)})

# 2) alpha peak frequency of S09's music trial at the back of the head, and at baseline
print("== alpha peak frequency (Hz), mean PSD of O1,O2,P3,P4,T5,T6 ==")
post = ["O1", "O2", "P3", "P4", "T5", "T6"]
for label, f, crop in (("baseline", "S09BS_filtered.edf", False), ("music E01", "S09E01_filtered.edf", True)):
    data, dropped, sf, raw = cp.prepare(cp.DATA / "S09" / f, crop)
    wins, keep = cp.clean_windows(data, sf, dropped)
    fr, psd = welch(np.stack(wins), fs=sf, nperseg=int(cp.WIN_S * sf))
    idx = [keep.index(cp.SCALP.index(c)) for c in post if cp.SCALP.index(c) in keep]
    p = psd.mean(axis=0)[idx].mean(axis=0)
    band = (fr >= 6) & (fr <= 14)
    print(label, "peak in 6-14 Hz at", round(float(fr[band][p[band].argmax()]), 1), "Hz")

# 3) region summaries from the group table
t = pd.read_csv(cp.RES / "channel_stats.csv")
def mean_of(chs, col): return t[t.channel.isin(chs)][col].mean()
groups = {"posterior (T5,T6,P3,P4,O1,O2)": ["T5", "T6", "P3", "P4", "O1", "O2"], "midline/near-midline frontal (F3,Fz,F4)": ["F3", "Fz", "F4"],
          "frontal pole and lateral (Fp1,Fp2,F7,F8)": ["Fp1", "Fp2", "F7", "F8"], "central (C3,Cz,C4)": ["C3", "Cz", "C4"], "temporal (T3,T4)": ["T3", "T4"]}
print("== group mean relative alpha by region ==")
for k, v in groups.items():
    print(f"{k}: baseline {mean_of(v, 'alpha_baseline'):.3f} -> music {mean_of(v, 'alpha_music'):.3f}  (change {mean_of(v, 'alpha_change'):+.3f})")
print("baseline alpha highest at:", t.sort_values("alpha_baseline", ascending=False).head(3)[["channel", "alpha_baseline"]].round(3).values.tolist())
print("music alpha highest at:", t.sort_values("alpha_music", ascending=False).head(4)[["channel", "alpha_music"]].round(3).values.tolist())
print("largest change:", t.sort_values("alpha_change", ascending=False).head(4)[["channel", "alpha_change", "n_higher_in_music"]].round(3).values.tolist())
print("smallest change:", t.sort_values("alpha_change").head(3)[["channel", "alpha_change", "p_holm"]].round(3).values.tolist())
print("channels significant after Holm (<0.05):", int((t.p_holm < 0.05).sum()), "of", len(t), "->", t[t.p_holm < 0.05].channel.tolist())
print("not significant after Holm:", t[t.p_holm >= 0.05].channel.tolist())
print("left-right pairs (music alpha): ", {a + "/" + b: (round(float(t.set_index('channel').alpha_music[a]), 3), round(float(t.set_index('channel').alpha_music[b]), 3)) for a, b in [("F3", "F4"), ("C3", "C4"), ("P3", "P4"), ("O1", "O2"), ("T3", "T4"), ("T5", "T6")]})

# 4) band-level change per channel group (all five bands)
b = pd.read_csv(cp.RES / "channel_band_means.csv")
b["region"] = b.channel.map(cp.REGION)
print("== mean change in relative power by region and band (music - baseline) ==")
print(b.groupby(["region", "band"]).change.mean().unstack()[cp.BAND_NAMES].round(3).to_string())
