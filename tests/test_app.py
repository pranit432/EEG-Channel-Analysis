"""Page tests for the channel app. Run from the project folder:  python -m pytest tests -q

Each page is run on its own with Streamlit's AppTest. Widget changes that go through a selectbox are
checked in the browser instead of here.
"""
import sys
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))  # AppTest does not add the script folder


def run_page(page, **state):
    at = AppTest.from_string(f"import views\nviews.{page}()", default_timeout=180)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def metrics(at):
    return {m.label: m.value for m in at.metric}


def test_explore_defaults_to_s09_e01():
    at = run_page("explore_page")
    assert not at.exception
    assert at.selectbox(key="exp_sub").value == "S09"
    m = metrics(at)
    assert int(m["Clean 2 s windows"]) > 8
    assert m["Channels dropped as noisy"] == "none"  # S09 E01 has no noisy channel


def test_explore_baseline_of_s09_reports_the_noisy_channel():
    at = AppTest.from_string("import views\nviews.explore_page()", default_timeout=180).run()
    at.selectbox(key="exp_rec_S09").set_value("BS").run()
    assert not at.exception
    assert metrics(at)["Channels dropped as noisy"] == "Fp2"  # the red channel in the baseline traces


def test_group_page_alpha_matches_the_written_observations():
    at = run_page("group_page")
    assert not at.exception
    m = metrics(at)
    assert m["Channels with a reliable change"] == "13 of 18"
    assert m["Channels higher in music"] == "18 of 18"
    assert m["Biggest change"].startswith("O2")


def test_group_page_table_agrees_with_the_saved_csv():
    import views
    t = views.group_table("alpha").set_index("channel")
    saved = pd.read_csv(ROOT / "results/channel_stats.csv").set_index("channel")
    assert (t.change - saved.alpha_change).abs().max() < 1e-9
    assert (t.p_holm - saved.p_holm).abs().max() < 1e-9


def test_quality_page_runs():
    at = run_page("quality_page")
    assert not at.exception


def test_observations_page_shows_every_figure():
    at = run_page("observations_page")
    assert not at.exception
    assert len(at.markdown) >= 6


def test_about_page_counts_the_channels():
    at = run_page("about_page")
    assert not at.exception
    m = metrics(at)
    assert m["Channels recorded"] == "24" and m["Scalp channels analysed"] == "18"
