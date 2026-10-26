# Channel-by-channel EEG: plots and observations

**Data.** 18 people, one baseline recording and several music trials each (157 recordings used). 24 channels were recorded; 18 are scalp electrodes and are analysed (see observation 2). Everything below is computed from the raw files by `channel_plots.py` and `extra_checks.py`.

**Terms.**
- *Relative power* of a band = that band's share of a channel's total 1-45 Hz power. The five bands add up to 1.
- *Alpha* (8-13 Hz) is the rhythm linked to relaxed wakefulness. *Delta* (1-4 Hz) is slow activity.
- *Baseline* is each person's baseline recording. *Music* is the average over their music trials.

**In one paragraph.** Looking channel by channel, the music recordings show a steady 10 Hz alpha rhythm that is strongest at the back of the head (O1, O2, T5, T6, P3), with a second hotspot at the front midline (Fz). The baseline recordings show no such pattern. The change is similar on the left and right sides. Alpha rose at all 18 channels, and the rise is statistically reliable at 13 of them. The forehead and temple channels are the weakest, and they are also the noisiest.

---

## Figure 1: raw traces, all 24 channels (S09)
File: `figures/fig1_traces_S09.png`. Ten seconds of baseline (left) and of music (right), on the same scale. The cleanest 10 s window of each recording was chosen.

**Observations**
1. **Music has a clear rhythm; baseline does not.** During music, the channels at the back (T5, P3, P4, T6, O1, O2) show a regular wave about ten times per second. At baseline the same channels are slow and irregular. The power spectrum agrees: averaged over these six channels, the music recording peaks at **10.0 Hz**, while the baseline has no alpha peak (its highest point between 6 and 14 Hz is at the 6 Hz edge).
2. **A blink-like spike at baseline.** At about 5 s, Fp1, Fp2 and F7 show the same sharp spike at the same moment, and the back channels do not. This is the usual look of an eye blink.
3. **Some individual channels are poor.** C4 wanders slowly (drift) at baseline, T4 and F8 show high-frequency fuzz, and Fp2 was dropped as noisy in that recording.
4. **Because I picked the cleanest 10 s of each recording, this plot cannot be used to compare how many blinks happen in each condition.**

## Observation 2: the six channels that are not scalp electrodes
Shown in grey at the bottom of Figure 1.

- **X1, X2, X3** are flat lines. Their standard deviation is about 0.03 µV, which is effectively zero. They carry no signal.
- **CM** (common-mode) is large and noisy: standard deviation 70-84 µV, several times larger than any scalp channel.
- **A1 and A2** are ear channels, 10-20 µV.
- None of the six is a scalp electrode, so they are left out of every analysis below. That is why the analysis uses 18 of the 24 channels.

## Figure 2: band power by channel (S09)
File: `figures/fig2_channel_band_heatmap_S09.png`. Each row is a channel and each column a band. The number is the share of that channel's power in that band.

**Observations**
1. **At baseline, slow delta activity dominates everywhere.** Its share runs from 0.42 to 0.91 across channels. Alpha is the largest band at **0 of 17** channels.
2. **During music, alpha takes over in most places.** Alpha is the largest band at **13 of 18** channels. The shares are highest at the back (O1 0.75, O2 0.77) and across the front (Fz 0.66, Fp1 0.62, F3 0.62).
3. **A few channels do not follow.** T3 and C4 stay delta-heavy during music (0.72 and 0.79 delta), and T4 keeps relatively high beta and gamma at both times (about 0.19 and 0.13). The C4 and T4 traces in Figure 1 suggest slow drift and muscle-type noise at those sites, not a real lack of alpha.
4. Fp2 was dropped as noisy in the baseline, so it is blank in that panel.

## Figure 3 and `results/channel_stats.csv`: alpha by channel, all 18 people
File: `figures/fig3_alpha_by_channel_group.png`. Bars show mean relative alpha per channel. Stars mark channels where the rise is significant after correcting for testing 18 channels (paired Wilcoxon across people, Holm).

**Observations**
1. **Alpha is higher during music at every one of the 18 channels.**
2. **13 of 18 channels are significant after correction:** F3, Fz, T3, C3, Cz, C4, T4, T5, P3, P4, T6, O1, O2. The strongest is T6 (higher in 17 of 18 people, Holm p = 0.0004).
3. **The biggest rises are at the back:** O1 and O2 (+0.14 each), T6 (+0.14), T5 (+0.13), P3 (+0.11), with Fz (+0.11) as the front-midline exception.
4. **The smallest rise is Fp2 (+0.02).**
5. **Not significant after correction:** Fp1, Fp2, F7, F4 and F8. "Not significant" does not mean "no change": Fp1, for example, still doubles from 0.054 to 0.107. These five also have the fewest people with usable data (13 to 16 instead of 17 or 18) because those channels were so often noisy, which weakens the test.

| Region | Baseline alpha | Music alpha | Change |
|---|---|---|---|
| Back (T5, T6, P3, P4, O1, O2) | 0.097 | 0.223 | +0.127 |
| Front midline (F3, Fz, F4) | 0.103 | 0.202 | +0.099 |
| Centre (C3, Cz, C4) | 0.106 | 0.164 | +0.058 |
| Forehead and outer front (Fp1, Fp2, F7, F8) | 0.057 | 0.111 | +0.054 |
| Temples (T3, T4) | 0.071 | 0.117 | +0.046 |

## Figure 4: scalp maps of alpha
File: `figures/fig4_topomaps_alpha.png`. Average of 18 people. Colour is drawn only inside the area covered by electrodes.

**Observations**
1. **Baseline is low and fairly flat** (about 0.05 to 0.13 everywhere). The highest baseline channels are C3, Fz and P3, so there is no obvious back-of-head peak.
2. **During music, a back-of-head peak appears:** O1 0.231, O2 0.230, P3 0.228 and T5, T6 about 0.22. A second hotspot sits at Fz (0.227).
3. **The pattern is left-right symmetric.** O1 and O2 are 0.231 and 0.230. T5 and T6 are 0.225 and 0.222. Frontal F3 and F4 differ only slightly (0.182 and 0.198).

## Other bands (`results/channel_band_means.csv`)
- Because the five shares add up to 1, the alpha rise comes with a fall in another band. The fall is mostly **delta**: occipital -0.12, parietal -0.09, central -0.06, temporal -0.05, frontal -0.02.
- Beta barely changes (between -0.03 and +0.01). Gamma falls slightly at frontal and temporal channels (about -0.02 to -0.03).
- So the headline change is "alpha takes a larger share and delta a smaller one", not "all activity went up". Relative power can't show whether the total signal grew.

## Figure 5: channel quality
File: `figures/fig5_channel_quality.png`. The share of the 157 recordings where each channel was removed as too noisy.

**Observations**
1. **The forehead and outer-front channels are the least reliable:** F8 23%, Fp1 20%, Fp2 19%, F7 17%.
2. **O1 and O2 are next (8% and 9%).**
3. **Most other channels are dropped in 6% of recordings or fewer,** and Fz and P3 in less than 1%.
4. The likely cause for the forehead channels is eye blinks and facial muscle activity, which is consistent with the blink-like spike in Figure 1, but this plot alone cannot prove the reason.

---

## What these plots suggest, and what they do not

**Suggested**
- During music the EEG shows a strong, symmetric alpha rhythm that peaks at the back of the head, plus a front-midline hotspot. At baseline this pattern is absent.
- The effect is spread over most of the scalp, not confined to one channel. The weak spots are the noisy forehead channels.

**Not shown**
- **That music caused it.** A back-of-head alpha peak is also the classic pattern of *closed eyes*, and the dataset does not say whether the baseline eyes were open or closed. The channel pattern fits that explanation as well as a music effect, so it cannot rule it out.
- **Anything about attention or how people felt.** Only EEG was recorded.
- **That every person behaves like the group.** Figures 1 and 2 show S09, whose change is the largest of the 18. Others, such as S01, barely change.

**Method notes**
- Every channel is average-referenced across the channels that were kept. This is the same cleaning as in the main project: noisy channels (standard deviation above 3 times the median) and 2 s windows above 200 µV are removed.
- Each channel has its own number of usable people (13 to 18), which is why the `n` is printed next to the channel names in Figure 3.
- The 18 per-channel tests are not independent, since neighbouring electrodes see similar activity.
