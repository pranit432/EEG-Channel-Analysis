# EEG channel plots

Channel-by-channel view of the EEG from the music dataset: raw traces, band power per channel, group results and scalp maps, with written observations.

This folder is separate from the main project. It only **reads** the EEG files from `C:\Users\Pranit\eeg-music-project\data\tempo\music1` and writes everything here.

## Data

The EEG files are **not included** in this repository. Download the [Music Tempo Emotional Impact EEG Dataset](https://www.kaggle.com/datasets/aphros/music-tempo-emotional-impact-eeg-dataset) from Kaggle (by `aphros`, Apache-2.0), then set `DATA` near the top of `channel_plots.py` to the folder that contains the subject folders (`S01`, `S02`, ...) of the filtered `music1` recordings. The saved tables and figures in `results/` and `figures/` are included so the website runs without the raw data.

## Contents

| Path | What it is |
|---|---|
| `observations.md` | The observations, tied to each figure and number |
| `figures/fig1_traces_S09.png` | All 24 channels, 10 s of baseline next to 10 s of music |
| `figures/fig2_channel_band_heatmap_S09.png` | Share of each channel's power in each band (S09) |
| `figures/fig3_alpha_by_channel_group.png` | Alpha per channel, baseline vs music, 18 people |
| `figures/fig4_topomaps_alpha.png` | Alpha on the scalp: baseline, music, difference |
| `figures/fig5_channel_quality.png` | How often each channel was too noisy to use |
| `results/channel_stats.csv` | Per-channel alpha, change, p-values and drop rate |
| `results/channel_band_means.csv` | Per-channel mean for every band, baseline vs music |
| `results/subject_channel_band.npz` | Per-person, per-channel band power used by the app |
| `channel_plots.py` | Makes all figures and tables |
| `extra_checks.py` | Prints the extra numbers quoted in the observations |
| `app.py`, `views.py` | The Streamlit website |
| `tests/test_app.py` | Page tests for the website |
| `.streamlit/config.toml` | Dark theme |

## The website

```
cd C:\Users\Pranit\eeg-channel-plots
python -m streamlit run app.py --server.port 8503
```

Open `http://localhost:8503`. Pages:

- **Explore a recording**: pick any subject and recording. Raw traces of all 24 channels (with a window and spacing you can move), a band-power heatmap per channel, and scalp maps.
- **Baseline vs music**: pick a band and see every channel, baseline against music, with significance, scalp maps and a table you can download.
- **Channel quality**: how often each channel was too noisy to use.
- **Observations**: the write-up from `observations.md` with the figures inline.
- **About**: terms, cleaning, data and limits.

Tests (page checks, including that the app's numbers match the saved CSV):

```
python -m pytest tests -q
```

The app needs `results/subject_channel_band.npz`, which `channel_plots.py` creates.

## Make the figures and tables

```
cd C:\Users\Pranit\eeg-channel-plots
python channel_plots.py
python extra_checks.py
```

`channel_plots.py` takes about a minute. It needs `mne`, `numpy`, `scipy`, `pandas` and `matplotlib` (all already installed for the main project).

To use another subject for Figures 1 and 2, change `"S09", "E01"` in the last block of `channel_plots.py`.
