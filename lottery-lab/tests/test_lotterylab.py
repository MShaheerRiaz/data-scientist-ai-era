"""Test suite for lotterylab.

The statistical functions are cross-checked against SciPy where it is
available (SciPy is a *test-only* dependency — the library itself has
none).  The combinatorics are checked against the operators' own published
odds, and the covering designs against known optimal values.
"""

from __future__ import annotations

import itertools
import math
import random

import pytest

from lotterylab import PRESETS, DIGIT_PRESETS, synthesize, SynthBias
from lotterylab import combinatorics as C
from lotterylab import mathx as M
from lotterylab.config import BonusMode, LotteryConfig, PrizeTier

try:
    from scipy import special as _sp
    from scipy import stats as _st
    HAVE_SCIPY = True
except ImportError:  # pragma: no cover
    HAVE_SCIPY = False

needs_scipy = pytest.mark.skipif(not HAVE_SCIPY, reason="SciPy not installed")


# ---------------------------------------------------------------------------
# mathx
# ---------------------------------------------------------------------------


@needs_scipy
@pytest.mark.parametrize("a,x", [(0.5, 0.3), (1.0, 1.0), (3.7, 2.2), (25.0, 30.0), (60.0, 45.0)])
def test_incomplete_gamma_matches_scipy(a, x):
    assert M.gammainc_lower(a, x) == pytest.approx(_sp.gammainc(a, x), rel=1e-11)
    assert M.gammainc_upper(a, x) == pytest.approx(_sp.gammaincc(a, x), rel=1e-11)


@needs_scipy
@pytest.mark.parametrize("df", [1, 2, 5, 48, 81, 499])
@pytest.mark.parametrize("x", [0.5, 5.0, 48.0, 120.0])
def test_chi2_sf_matches_scipy(df, x):
    assert M.chi2_sf(x, df) == pytest.approx(_st.chi2.sf(x, df), rel=1e-10, abs=1e-300)


@needs_scipy
@pytest.mark.parametrize("z", [-8, -3, -0.5, 0, 0.5, 3, 8])
def test_normal_matches_scipy(z):
    assert M.norm_cdf(z) == pytest.approx(_st.norm.cdf(z), rel=1e-12, abs=1e-300)
    assert M.norm_sf(z) == pytest.approx(_st.norm.sf(z), rel=1e-12, abs=1e-300)


@needs_scipy
@pytest.mark.parametrize("p", [1e-9, 0.001, 0.025, 0.5, 0.975, 1 - 1e-9])
def test_norm_ppf_matches_scipy(p):
    assert M.norm_ppf(p) == pytest.approx(_st.norm.ppf(p), rel=1e-8, abs=1e-9)


def test_norm_ppf_roundtrip():
    for p in (0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99):
        assert M.norm_cdf(M.norm_ppf(p)) == pytest.approx(p, abs=1e-12)


@needs_scipy
@pytest.mark.parametrize("n,p", [(20, 0.2), (100, 0.5), (1000, 0.02), (5000, 0.12)])
def test_binomial_matches_scipy(n, p):
    for k in (0, 1, int(n * p), n // 2, n):
        assert M.binom_pmf(k, n, p) == pytest.approx(_st.binom.pmf(k, n, p), rel=1e-9, abs=1e-300)
        assert M.binom_cdf(k, n, p) == pytest.approx(_st.binom.cdf(k, n, p), rel=1e-8, abs=1e-300)
        assert M.binom_test(k, n, p) == pytest.approx(
            _st.binomtest(k, n, p).pvalue, rel=1e-7, abs=1e-12
        )


@needs_scipy
@pytest.mark.parametrize("lam", [0.1, 1.0, 10.0, 200.0])
def test_poisson_matches_scipy(lam):
    for k in (0, 1, 5, 50, 300):
        assert M.poisson_pmf(k, lam) == pytest.approx(_st.poisson.pmf(k, lam), rel=1e-10, abs=1e-300)
        assert M.poisson_cdf(k, lam) == pytest.approx(_st.poisson.cdf(k, lam), rel=1e-8, abs=1e-300)


@needs_scipy
def test_benjamini_hochberg_matches_scipy():
    rng = random.Random(3)
    pvals = [rng.random() for _ in range(80)]
    mine = M.benjamini_hochberg(pvals)
    theirs = _st.false_discovery_control(pvals, method="bh")
    for a, b in zip(mine, theirs):
        assert a == pytest.approx(b, rel=1e-12)


def test_benjamini_hochberg_is_monotone_and_bounded():
    pvals = [0.001, 0.01, 0.02, 0.2, 0.5, 0.9]
    q = M.benjamini_hochberg(pvals)
    assert all(0.0 <= v <= 1.0 for v in q)
    assert all(a <= b + 1e-12 for a, b in zip(sorted(pvals), sorted(q)))


def test_ks_sf_is_monotone():
    values = [M.ks_sf(d, 100) for d in (0.02, 0.05, 0.1, 0.2, 0.3)]
    assert values == sorted(values, reverse=True)


def test_wilson_interval_contains_point_estimate():
    lo, hi = M.wilson_interval(30, 100)
    assert lo < 0.30 < hi
    assert (0.0, 1.0) == M.wilson_interval(0, 0)


# ---------------------------------------------------------------------------
# Combinatorics vs published odds
# ---------------------------------------------------------------------------

PUBLISHED_JACKPOT = {
    "powerball": 292_201_338,
    "megamillions": 290_472_336,
    "euromillions": 139_838_160,
    "uk_lotto": 45_057_474,
    "canada_649": 13_983_816,
    "lotto_max": 99_884_400,
}


@pytest.mark.parametrize("key,expected", sorted(PUBLISHED_JACKPOT.items()))
def test_jackpot_odds_match_operator_published_figures(key, expected):
    cfg = PRESETS[key]
    assert round(1 / C.jackpot_probability(cfg)) == expected


PUBLISHED_TIERS = {
    "powerball": {"5": 11_688_054, "4 + Powerball": 913_129, "3": 579.76, "0 + Powerball": 38.32},
    "euromillions": {"5 + 1 star": 6_991_908, "4 + 1 star": 31_075, "2": 21.9},
    # UK/Canada lower tiers pay on main matches regardless of the bonus ball.
    "uk_lotto": {"5 + bonus": 7_509_579, "4": 2_180, "3": 96.2, "2": 10.26},
    "canada_649": {"5 + bonus": 2_330_636, "4": 1_033, "3": 56.7, "2 + bonus": 81.2},
}


@pytest.mark.parametrize("key", sorted(PUBLISHED_TIERS))
def test_tier_odds_match_published(key):
    cfg = PRESETS[key]
    expected = PUBLISHED_TIERS[key]
    for tier, p in C.all_tier_probabilities(cfg):
        if tier.name in expected:
            assert 1 / p == pytest.approx(expected[tier.name], rel=2e-3)


@pytest.mark.parametrize("key", sorted(PRESETS))
def test_outcome_matrix_sums_to_one(key):
    """Every possible (main, bonus) outcome must account for all probability."""
    cfg = PRESETS[key]
    if cfg.bonus_mode is BonusMode.SEPARATE_POOL:
        max_bonus = cfg.bonus_pick
    elif cfg.bonus_mode is BonusMode.FROM_REMAINING:
        max_bonus = 1
    else:
        max_bonus = 0
    total = sum(
        C.tier_probability(cfg, m, b)
        for m in range(cfg.main_pick + 1)
        for b in range(max_bonus + 1)
    )
    assert total == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("key", sorted(PRESETS))
def test_tiers_are_disjoint(key):
    """Prize tiers must not double-count probability."""
    assert C.any_prize_probability(PRESETS[key]) <= 1.0


def test_canada_649_overall_odds_match_published():
    """Including the Match-2 free play reproduces the published 1-in-6.6."""
    assert 1 / C.any_prize_probability(PRESETS["canada_649"]) == pytest.approx(6.6, rel=0.02)


def test_powerball_overall_odds_match_published():
    assert 1 / C.any_prize_probability(PRESETS["powerball"]) == pytest.approx(24.87, rel=0.01)


@pytest.mark.parametrize("n,k", [(49, 6), (69, 5), (59, 6)])
def test_rank_unrank_roundtrip(n, k):
    rng = random.Random(11)
    total = C.comb(n, k)
    for idx in [0, 1, total // 2, total - 1] + [rng.randrange(total) for _ in range(100)]:
        combo = C.unrank_combination(idx, n, k)
        assert len(set(combo)) == k
        assert C.rank_combination(combo, n) == idx


def test_unrank_is_lexicographic():
    previous = None
    for idx in range(500):
        combo = C.unrank_combination(idx, 20, 5)
        if previous is not None:
            assert combo > previous
        previous = combo


def test_unrank_rejects_out_of_range():
    with pytest.raises(IndexError):
        C.unrank_combination(C.comb(10, 3), 10, 3)


@pytest.mark.parametrize("n,k", [(15, 4), (20, 5), (14, 6)])
def test_sum_distribution_matches_brute_force(n, k):
    brute: dict[int, int] = {}
    for combo in itertools.combinations(range(1, n + 1), k):
        brute[sum(combo)] = brute.get(sum(combo), 0) + 1
    assert C.sum_distribution(n, k) == brute


def test_sum_distribution_totals_and_symmetry():
    dist = C.sum_distribution(49, 6)
    assert sum(dist.values()) == C.comb(49, 6)
    assert max(dist, key=dist.get) == 150  # symmetric about 6*(49+1)/2


def test_classify_ticket_from_remaining_bonus():
    """UK-style 'Match 4' pays whether or not the bonus was also hit."""
    cfg = PRESETS["uk_lotto"]
    drawn = (1, 2, 3, 4, 5, 6)
    tier, mains, bonus = C.classify_ticket(cfg, (1, 2, 3, 4, 50, 51), drawn, (50,))
    assert mains == 4 and bonus == 1
    assert tier is not None and tier.name == "4"


# ---------------------------------------------------------------------------
# Fairness
# ---------------------------------------------------------------------------


def test_haigh_correction_is_applied():
    """Without-replacement draws need the (pool-1)/(pool-k) scaling.

    Without it the ball-frequency test is badly conservative and misses
    real bias.  Checked by confirming the reported statistic equals the
    corrected value, not the raw Pearson sum.
    """
    from lotterylab.fairness import ball_frequency_test

    cfg = PRESETS["canada_649"]
    history = synthesize(cfg, 1500, seed=4)
    result = ball_frequency_test(history)

    counts = history.main_counts()[1:]
    expected = 1500 * cfg.main_pick / cfg.main_pool
    raw = sum((c - expected) ** 2 / expected for c in counts)
    factor = (cfg.main_pool - 1) / (cfg.main_pool - cfg.main_pick)

    assert result.statistic == pytest.approx(raw * factor, rel=1e-12)
    assert factor == pytest.approx(48 / 43, rel=1e-12)


def test_ball_frequency_calibration_on_fair_data():
    """False-positive rate must sit near 5%, not 1% or 20%."""
    from lotterylab.fairness import ball_frequency_test

    cfg = PRESETS["canada_649"]
    fires = sum(
        1 for s in range(120)
        if ball_frequency_test(synthesize(cfg, 800, seed=6000 + s)).pvalue < 0.05
    )
    assert 0.005 < fires / 120 < 0.16


def test_sum_test_calibration_on_fair_data():
    """The binned chi-square must be calibrated where a KS test was not."""
    from lotterylab.fairness import sum_distribution_test

    cfg = PRESETS["canada_649"]
    fires = sum(
        1 for s in range(120)
        if sum_distribution_test(synthesize(cfg, 800, seed=7000 + s)).pvalue < 0.05
    )
    assert fires / 120 < 0.16


def test_audit_detects_a_strongly_biased_ball():
    """A battery that never fires on known-bad data proves nothing."""
    from lotterylab.fairness import audit

    cfg = PRESETS["canada_649"]
    biased = synthesize(cfg, 2500, seed=21, bias=SynthBias(weights={17: 2.5}))
    report = audit(biased, include_pair_test=False)
    assert report.flagged_balls, "audit missed a ball weighted 2.5x"
    assert 17 in [b.ball for b in report.flagged_balls]


def test_audit_detects_serial_dependence():
    from lotterylab.fairness import audit

    cfg = PRESETS["canada_649"]
    sticky = synthesize(cfg, 2000, seed=22, bias=SynthBias(sticky=0.30))
    report = audit(sticky, include_pair_test=False)
    names = [t.name for t in report.tests if t.significant]
    assert any("serial" in n or "overlap" in n for n in names)


def test_audit_is_quiet_on_fair_data():
    from lotterylab.fairness import audit

    cfg = PRESETS["canada_649"]
    report = audit(synthesize(cfg, 2000, seed=31), include_pair_test=False)
    assert "No detectable departure" in report.verdict()


def test_power_analysis_is_sane():
    from lotterylab.fairness import power_analysis

    cfg = PRESETS["canada_649"]
    small = power_analysis(cfg, 500)
    large = power_analysis(cfg, 20000)
    # More data detects smaller biases.
    assert large["min_detectable_lift"] < small["min_detectable_lift"]
    # Detecting a 5% bias needs an unrealistic amount of history.
    assert power_analysis(cfg, 3000)["draws_required"][1.05] > 20000


# ---------------------------------------------------------------------------
# EV and sharing
# ---------------------------------------------------------------------------


def test_share_factor_closed_form():
    """E[1/(1+K)] for Poisson K equals (1-e^-lam)/lam."""
    from lotterylab.popularity import share_factor

    for lam in (0.05, 0.5, 1.0, 3.0, 8.0):
        brute = sum(M.poisson_pmf(k, lam) / (k + 1) for k in range(0, 400))
        assert share_factor(lam) == pytest.approx(brute, rel=1e-9)


def test_share_factor_limits():
    from lotterylab.popularity import share_factor

    assert share_factor(0.0) == 1.0
    assert share_factor(1e-12) == pytest.approx(1.0, abs=1e-11)
    assert share_factor(1.0) == pytest.approx(0.6321, rel=1e-3)


def test_powerball_ev_never_reaches_break_even_with_realistic_sales():
    """Sales grow with the jackpot, so sharing cancels the prize growth."""
    from lotterylab.ev import EVAssumptions, break_even_jackpot, ticket_ev

    cfg = PRESETS["powerball"]
    assumptions = EVAssumptions(cash_value_ratio=0.52, tax_rate=0.37,
                                sales_base=20e6, sales_per_jackpot_unit=0.39)
    assert break_even_jackpot(cfg, assumptions) is None

    huge = EVAssumptions(jackpot=1e12, cash_value_ratio=0.52, tax_rate=0.37,
                         sales_base=20e6, sales_per_jackpot_unit=0.39)
    assert ticket_ev(cfg, huge).net_ev < 0


def test_ignoring_sharing_produces_the_naive_positive_result():
    """The common mistake: EV looks positive once you drop the sharing term."""
    from lotterylab.ev import EVAssumptions, break_even_jackpot

    cfg = PRESETS["powerball"]
    naive = break_even_jackpot(cfg, EVAssumptions(tickets_sold=0))
    assert naive is not None and naive < 1e9


def test_rolldown_scales_tiers_by_a_common_multiplier():
    """Roll-down money must lift every eligible tier by the same factor."""
    from lotterylab.ev import rolldown_ev

    winfall = LotteryConfig(
        name="Cash WinFall", main_pool=46, main_pick=6, ticket_price=2.0,
        tiers=(PrizeTier("6", 6, 0, 0.0, is_jackpot=True, is_parimutuel=True),
               PrizeTier("5", 5, 0, 4000.0),
               PrizeTier("4", 4, 0, 150.0),
               PrizeTier("3", 3, 0, 5.0)),
    )
    result = rolldown_ev(winfall, rolldown_pool=2_000_000, tickets_sold=1_000_000,
                         eligible_tiers=["5", "4", "3"])
    multipliers = [row.gross_payout / row.tier.payout
                   for row in result.tiers if row.tier.payout > 0]
    assert len(multipliers) == 3
    assert max(multipliers) - min(multipliers) < 1e-9
    # And the play is genuinely positive-EV, as history recorded.
    assert result.net_ev > 0


def test_ziemba_break_even_factor():
    from lotterylab.ev import ziemba_break_even_factor, ziemba_expected_return

    factor = ziemba_break_even_factor(6, 0.45)
    assert factor == pytest.approx(1.1423, rel=1e-3)
    assert ziemba_expected_return([factor] * 6, 0.45) == pytest.approx(1.0, rel=1e-9)


def test_kelly_is_negative_for_negative_ev():
    from lotterylab.ev import kelly_fraction

    assert kelly_fraction(1 / 292_201_338, 100e6) < 0
    assert kelly_fraction(1 / 292_201_338, 600e6) > 0


# ---------------------------------------------------------------------------
# Popularity
# ---------------------------------------------------------------------------


def test_popularity_ranks_known_patterns_correctly():
    from lotterylab.popularity import PopularityModel

    cfg = PRESETS["canada_649"]
    model = PopularityModel(cfg)
    sequential = model.multiplier((1, 2, 3, 4, 5, 6))
    birthdays = model.multiplier((3, 7, 12, 19, 24, 31))
    obscure = model.multiplier((38, 41, 43, 45, 47, 49))
    assert sequential > birthdays > obscure
    assert obscure < 1.0 < birthdays


def test_consecutive_runs_are_under_picked():
    """Proximity aversion: players avoid adjacent numbers.

    Compared on a matched pair — both combinations sit entirely above the
    calendar range and span a similar spread, so they differ only in
    whether a run is present.  Comparing a low consecutive block against a
    high scattered one would confound the run effect with the much larger
    birthday effect and give the wrong answer.
    """
    from lotterylab.popularity import PopularityModel

    model = PopularityModel(PRESETS["canada_649"])
    without_run = (35, 38, 41, 44, 47, 49)
    with_run = (35, 36, 41, 44, 47, 49)
    assert model.multiplier(with_run) < model.multiplier(without_run)

    hits = {h.name: h.weight for h in model.features(with_run)}
    assert hits["consecutive run"] < 0

    # A long run carries a correspondingly larger penalty.
    long_run = {h.name: h.weight for h in model.features((21, 22, 23, 24, 25, 26))}
    assert long_run["consecutive run"] < hits["consecutive run"]


def test_quickpick_dilution_pulls_toward_one():
    from lotterylab.popularity import PopularityModel

    model = PopularityModel(PRESETS["canada_649"])
    combo = (1, 2, 3, 4, 5, 6)
    assert 1.0 < model.effective_multiplier(combo) < model.multiplier(combo)


def test_recently_drawn_numbers_score_as_under_bet():
    from lotterylab.popularity import PopularityModel

    cfg = PRESETS["canada_649"]
    history = synthesize(cfg, 30, seed=2)
    aware = PopularityModel.with_recent_draws(cfg, history, lookback=3)
    naive = PopularityModel(cfg)
    combo = tuple(sorted(list(aware.recent_numbers)[:6]))
    assert aware.multiplier(combo) < naive.multiplier(combo)


# ---------------------------------------------------------------------------
# Wheels
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("v,k,t", [(6, 3, 2), (7, 3, 2), (9, 4, 2), (8, 5, 3), (10, 6, 3)])
def test_covering_designs_are_valid(v, k, t):
    """Verified independently of the constructor."""
    from lotterylab.wheels import covering_design

    wheel = covering_design(range(1, v + 1), k, t, seed=1, restarts=2, local_search_rounds=400)
    blocks = [set(b) for b in wheel.blocks]
    for target in itertools.combinations(range(1, v + 1), t):
        assert any(set(target) <= block for block in blocks)


@pytest.mark.parametrize("v,k,t,expected", [
    (49, 6, 2, 82),        # known to meet the Schoenheim bound exactly
    (49, 6, 5, 325_205),   # ditto
    (7, 3, 2, 7),
    (10, 3, 2, 17),
])
def test_schonheim_bound_matches_known_values(v, k, t, expected):
    """The nested ceilings must be evaluated innermost-first."""
    from lotterylab.wheels import schonheim_bound

    assert schonheim_bound(v, k, t) == expected


def test_covering_never_beats_its_lower_bound():
    from lotterylab.wheels import covering_design, schonheim_bound

    for v, k, t in [(9, 4, 3), (10, 6, 3), (12, 6, 4)]:
        wheel = covering_design(range(1, v + 1), k, t, seed=2,
                                restarts=2, local_search_rounds=400)
        assert wheel.size >= schonheim_bound(v, k, t)


def test_full_wheel_size_and_guarantee():
    from lotterylab.wheels import full_wheel

    wheel = full_wheel(range(1, 13), 6)
    assert wheel.size == C.comb(12, 6) == 924
    assert wheel.verified


def test_key_number_wheel_size():
    from lotterylab.wheels import key_number_wheel

    wheel = key_number_wheel(range(1, 13), 6, [3, 7])
    assert wheel.size == C.comb(10, 4)
    assert all(3 in b and 7 in b for b in wheel.blocks)


# ---------------------------------------------------------------------------
# Digit games
# ---------------------------------------------------------------------------

# Twelve historical records from two independent public data sources.
TWOD_RECORDS = [
    (1444.12, 19306.60, 26), (1443.79, 24221.65, 91), (1439.86, 31494.42, 64),
    (1441.11, 38177.16, 17), (1317.17, 12027.17, 77), (1315.86, 16002.01, 62),
    (1311.77, 23982.35, 72), (1313.08, 34650.56, 80), (1457.23, 26026.10, 36),
    (1458.28, 30711.62, 81), (1454.54, 42050.54, 40), (1451.69, 67537.63, 97),
]


@pytest.mark.parametrize("index,value,expected", TWOD_RECORDS)
def test_myanmar_2d_derivation_matches_history(index, value, expected):
    from lotterylab.digits import derive_myanmar_2d

    assert derive_myanmar_2d(index, value) == expected


def test_myanmar_2d_folklore_rule_is_wrong():
    """'Last two digits of the index' contradicts the real results."""
    from lotterylab.digits import derive_myanmar_2d

    index, value, actual = 1441.11, 38177.16, 17
    assert derive_myanmar_2d(index, value) == actual
    assert int(index) % 100 != actual


def test_digit_house_edges():
    assert DIGIT_PRESETS["myanmar_2d"].house_edge == pytest.approx(0.20, abs=1e-9)
    assert DIGIT_PRESETS["pick3"].house_edge == pytest.approx(0.50, abs=1e-9)
    assert DIGIT_PRESETS["myanmar_2d"].fair_payout == 100


def test_multi_tier_games_report_full_structure_rtp():
    """4D pays 23 winning numbers; scoring it from the first prize is wrong.

    Using the 2000x top prize alone would imply an 80% house edge; the real
    figure from the full prize structure is 34.1%.
    """
    sg = DIGIT_PRESETS["sg_4d"]
    assert sg.is_multi_tier
    assert sg.expected_return == pytest.approx(0.659, abs=1e-9)
    assert sg.house_edge == pytest.approx(0.341, abs=1e-9)
    # The naive first-prize-only calculation would be badly wrong.
    assert sg.payout_straight / sg.outcomes == pytest.approx(0.20, abs=1e-9)

    assert DIGIT_PRESETS["my_4d"].house_edge == pytest.approx(0.36, abs=1e-9)
    # Single-payout games are unaffected.
    assert not DIGIT_PRESETS["pick3"].is_multi_tier


def test_digit_audit_quiet_on_uniform_data():
    from lotterylab.digits import DigitHistory, digit_audit

    rng = random.Random(9)
    history = DigitHistory.from_values(
        DIGIT_PRESETS["myanmar_2d"], [rng.randrange(100) for _ in range(4000)]
    )
    report = digit_audit(history)
    assert not report.any_flag


def test_digit_audit_detects_a_skewed_position():
    from lotterylab.digits import DigitHistory, digit_audit

    rng = random.Random(10)
    values = []
    for _ in range(4000):
        top = 7 if rng.random() < 0.25 else rng.randrange(10)
        values.append(top * 10 + rng.randrange(10))
    history = DigitHistory.from_values(DIGIT_PRESETS["myanmar_2d"], values)
    assert digit_audit(history).any_flag


def test_kelly_for_digit_game_is_negative():
    from lotterylab.digits import kelly_for_digit_game

    for cfg in DIGIT_PRESETS.values():
        assert kelly_for_digit_game(cfg) < 0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def test_csv_roundtrip(tmp_path):
    from lotterylab.data import load_csv, save_csv

    cfg = PRESETS["canada_649"]
    original = synthesize(cfg, 60, seed=5)
    path = tmp_path / "draws.csv"
    save_csv(original, path)
    reloaded = load_csv(path, cfg)
    assert reloaded.n_draws == original.n_draws
    assert not reloaded.warnings
    assert [d.sorted_main() for d in reloaded] == [d.sorted_main() for d in original]


def test_csv_single_column_layout(tmp_path):
    cfg = PRESETS["canada_649"]
    path = tmp_path / "compact.csv"
    path.write_text("date,numbers\n2024-01-01,\"1 2 3 4 5 6\"\n2024-01-04,\"7 8 9 10 11 12\"\n")
    from lotterylab.data import load_csv

    history = load_csv(path, cfg)
    assert history.n_draws == 2
    assert history.draws[0].sorted_main() == (1, 2, 3, 4, 5, 6)


def test_bad_rows_are_reported_not_silently_dropped(tmp_path):
    cfg = PRESETS["canada_649"]
    path = tmp_path / "broken.csv"
    path.write_text("date,numbers\n2024-01-01,\"1 2 3 4 5 6\"\n2024-01-04,\"7 8 9\"\n")
    from lotterylab.data import load_csv

    history = load_csv(path, cfg)
    assert history.n_draws == 1
    assert history.warnings


def test_draw_rejects_duplicate_numbers():
    from lotterylab.data import Draw

    with pytest.raises(ValueError):
        Draw(main=(1, 1, 2, 3, 4, 5))


def test_synthesize_respects_structure():
    for key in ("powerball", "uk_lotto", "canada_649"):
        cfg = PRESETS[key]
        history = synthesize(cfg, 40, seed=1)
        assert not history.validate()


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def test_unpopular_generator_beats_random_on_popularity():
    from lotterylab.generate import generate_random, generate_unpopular

    cfg = PRESETS["canada_649"]
    plain = generate_random(cfg, 10, salt=1)
    smart = generate_unpopular(cfg, 10, salt=1)
    assert smart.mean_effective_popularity < plain.mean_effective_popularity
    assert smart.payout_uplift() > 1.0


def test_salt_changes_the_output():
    """Two users of the tool must not converge on identical tickets."""
    from lotterylab.generate import generate_unpopular

    cfg = PRESETS["canada_649"]
    a = generate_unpopular(cfg, 5, salt="alice")
    b = generate_unpopular(cfg, 5, salt="bob")
    assert [t.main for t in a.tickets] != [t.main for t in b.tickets]


def test_generated_tickets_are_valid():
    from lotterylab.generate import generate_diverse

    cfg = PRESETS["powerball"]
    result = generate_diverse(cfg, 6, salt=3, iterations=200)
    for ticket in result.tickets:
        assert len(set(ticket.main)) == cfg.main_pick
        assert all(1 <= v <= cfg.main_pool for v in ticket.main)
        assert len(ticket.bonus) == cfg.bonus_pick


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------


def test_no_strategy_beats_theory_on_mean_matches():
    """Every strategy must land on the theoretical match rate."""
    from lotterylab.backtest import STRATEGIES, backtest

    cfg = PRESETS["canada_649"]
    history = synthesize(cfg, 700, seed=77)
    theoretical = cfg.main_pick * cfg.main_pick / cfg.main_pool
    for name in ("random", "hot", "cold", "due"):
        result = backtest(history, STRATEGIES[name], name=name,
                          tickets_per_draw=5, warmup=100, seed=4)
        assert result.mean_matches == pytest.approx(theoretical, abs=0.06)


def test_permutation_test_finds_no_edge_in_hot_numbers():
    from lotterylab.backtest import STRATEGIES, permutation_test

    cfg = PRESETS["canada_649"]
    history = synthesize(cfg, 400, seed=88)
    result = permutation_test(history, STRATEGIES["hot"], name="hot",
                              reps=25, tickets_per_draw=3, warmup=60)
    assert result["pvalue"] > 0.01


def test_permutation_null_absorbs_the_finite_history_artifact():
    """The permutation null must sit above the theoretical rate for 'hot'.

    Within a fixed finite history the empirically hot balls appear more
    often by construction, so walk-forward testing correlates "hot by draw
    t" with "appears at draw t".  Measured against the *theoretical* rate
    this manufactures an edge on data known to be fair.  A correct null
    reproduces the artifact rather than crediting it to the strategy, so
    the null mean should exceed the theoretical rate.
    """
    from lotterylab.backtest import STRATEGIES, permutation_test

    cfg = PRESETS["canada_649"]
    theoretical = cfg.main_pick * cfg.main_pick / cfg.main_pool
    history = synthesize(cfg, 600, seed=99)
    result = permutation_test(history, STRATEGIES["hot"], name="hot",
                              reps=25, tickets_per_draw=4, warmup=80)
    assert result["null_mean"] > theoretical
    assert result["pvalue"] > 0.01


def test_unpopular_strategy_is_not_pathologically_slow():
    """Regression: the model must not be rebuilt on every draw.

    Constructing a PopularityModel per call re-ran its Monte Carlo
    normalisation each time, making this strategy ~75x slower than the
    others and stalling any realistic backtest.
    """
    import time

    from lotterylab.backtest import STRATEGIES, backtest

    cfg = PRESETS["canada_649"]
    history = synthesize(cfg, 200, seed=1)
    start = time.time()
    backtest(history, STRATEGIES["unpopular"], tickets_per_draw=3, warmup=60, seed=1)
    assert time.time() - start < 15.0


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", [
    ["games"],
    ["odds", "powerball"],
    ["power", "canada_649", "--draws", "3000"],
    ["ev", "powerball", "--jackpot", "500000000"],
    ["generate", "canada_649", "-n", "3"],
    ["explain", "canada_649", "1", "2", "3", "4", "5", "6"],
    ["2d", "1443.79", "24221.65"],
    ["digits", "--compare"],
])
def test_cli_commands_run(argv, capsys):
    from lotterylab.cli import main

    assert main(argv) == 0
    assert capsys.readouterr().out.strip()


def test_cli_rejects_wrong_number_count():
    from lotterylab.cli import main

    with pytest.raises(SystemExit):
        main(["explain", "canada_649", "1", "2", "3"])


def test_unknown_preset_raises():
    from lotterylab.config import get_preset

    with pytest.raises(KeyError):
        get_preset("not_a_real_lottery")


# ---------------------------------------------------------------------------
# UK games
# ---------------------------------------------------------------------------

UK_PUBLISHED = {
    "uk_lotto": {"jackpot": 45_057_474, "any": 9.3},
    "euromillions": {"jackpot": 139_838_160, "any": 13.0},
    "thunderball": {"jackpot": 8_060_598, "any": 12.4},
    "set_for_life": {"jackpot": 15_339_390, "any": 20.1},
}


@pytest.mark.parametrize("key", sorted(UK_PUBLISHED))
def test_uk_game_odds(key):
    cfg = PRESETS[key]
    assert round(1 / C.jackpot_probability(cfg)) == UK_PUBLISHED[key]["jackpot"]
    assert 1 / C.any_prize_probability(cfg) == pytest.approx(
        UK_PUBLISHED[key]["any"], rel=0.03
    )


def test_thunderball_subtier_odds_are_exact():
    """The previous implementation shipped wrong sub-tier odds.

    Match 4 + Thunderball is 1 in 47,415, not the 1 in 114,008 that was
    hard-coded before. Verified by exact hypergeometric computation and
    cross-checked by simulation.
    """
    cfg = PRESETS["thunderball"]
    # Exact values. The operator publishes these rounded (1 in 35, 1 in 29),
    # so the reference here is the exact figure, cross-checked by simulation.
    expected = {
        "5 + Thunderball": 8_060_598.0, "5": 620_046.0,
        "4 + Thunderball": 47_415.28, "4": 3_647.33,
        "3 + Thunderball": 1_436.83, "3": 110.53,
        "2 + Thunderball": 134.70, "1 + Thunderball": 34.76, "0 + Thunderball": 28.97,
    }
    for tier, p in C.all_tier_probabilities(cfg):
        assert 1 / p == pytest.approx(expected[tier.name], rel=1e-3)


def test_set_for_life_subtier_odds_are_exact():
    cfg = PRESETS["set_for_life"]
    expected = {
        "5 + Life Ball": 15_339_390, "5": 1_704_377,
        "4 + Life Ball": 73_045, "4": 8_116,
        "3 + Life Ball": 1_782, "3": 198,
        "2 + Life Ball": 134, "1 + Life Ball": 27.4,
    }
    for tier, p in C.all_tier_probabilities(cfg):
        assert 1 / p == pytest.approx(expected[tier.name], rel=5e-3)


def test_uk_games_listed():
    from lotterylab.config import UK_GAMES

    assert set(UK_GAMES) == {"uk_lotto", "euromillions", "thunderball", "set_for_life"}
    assert all(PRESETS[g].currency in ("GBP", "EUR") for g in UK_GAMES)


# ---------------------------------------------------------------------------
# Lucky Dip generator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["uk_lotto", "euromillions", "thunderball", "set_for_life"])
def test_lucky_dip_produces_valid_lines(key):
    from lotterylab.luckydip import lucky_dip

    cfg = PRESETS[key]
    slip = lucky_dip(cfg, 5)
    assert len(slip.lines) == 5
    for line in slip.lines:
        assert len(set(line.main)) == cfg.main_pick
        assert all(1 <= v <= cfg.main_pool for v in line.main)
        assert line.main == tuple(sorted(line.main))
        if cfg.bonus_mode is BonusMode.SEPARATE_POOL:
            assert len(set(line.bonus)) == cfg.bonus_pick
            assert all(1 <= v <= cfg.bonus_pool for v in line.bonus)


def test_secure_random_is_uniform():
    """The generator must not favour any ball."""
    from lotterylab.luckydip import SecureRandom

    rng = SecureRandom()
    counts = [0] * 40
    draws = 40_000
    for _ in range(draws):
        for v in rng.sample(range(1, 40), 5):
            counts[v] += 1
    expected = draws * 5 / 39
    raw = sum((counts[v] - expected) ** 2 / expected for v in range(1, 40))
    stat = raw * (39 - 1) / (39 - 5)          # Haigh correction
    assert M.chi2_sf(stat, 38) > 0.001


def test_secure_random_sample_has_no_duplicates():
    from lotterylab.luckydip import SecureRandom

    rng = SecureRandom()
    for _ in range(500):
        picked = rng.sample(range(1, 60), 6)
        assert len(set(picked)) == 6


def test_lucky_dip_include_and_exclude():
    from lotterylab.luckydip import lucky_dip

    cfg = PRESETS["uk_lotto"]
    slip = lucky_dip(cfg, 6, include=[7, 13], exclude=[1, 2, 3, 4, 5])
    for line in slip.lines:
        assert 7 in line.main and 13 in line.main
        assert not ({1, 2, 3, 4, 5} & set(line.main))


def test_lucky_dip_rejects_contradictory_constraints():
    from lotterylab.luckydip import lucky_dip

    cfg = PRESETS["uk_lotto"]
    with pytest.raises(ValueError):
        lucky_dip(cfg, 1, include=[7], exclude=[7])
    with pytest.raises(ValueError):
        lucky_dip(cfg, 1, include=list(range(1, 9)))
    with pytest.raises(ValueError):
        lucky_dip(cfg, 1, include=[99])


def test_unpopular_mode_lowers_popularity():
    from lotterylab.luckydip import lucky_dip

    cfg = PRESETS["uk_lotto"]
    fair = lucky_dip(cfg, 8, mode="fair")
    smart = lucky_dip(cfg, 8, mode="unpopular")
    assert smart.mean_popularity < fair.mean_popularity


def test_fixed_prize_games_are_flagged_as_unshared():
    """Thunderball prizes are never shared, so popularity is irrelevant."""
    from lotterylab.luckydip import _prizes_are_shared, lucky_dip

    assert not _prizes_are_shared(PRESETS["thunderball"])
    assert _prizes_are_shared(PRESETS["uk_lotto"])
    text = lucky_dip(PRESETS["thunderball"], 2, mode="unpopular").to_text()
    assert "gains you nothing" in text


def test_jackpot_chance_scales_with_lines():
    from lotterylab.luckydip import lucky_dip

    cfg = PRESETS["thunderball"]
    one = lucky_dip(cfg, 1).jackpot_chance
    ten = lucky_dip(cfg, 10).jackpot_chance
    assert ten == pytest.approx(1 - (1 - C.jackpot_probability(cfg)) ** 10, rel=1e-9)
    assert ten > one


# ---------------------------------------------------------------------------
# UK data parsing
# ---------------------------------------------------------------------------

_UK_FIXTURES = {
    "uk_lotto": (
        "DrawDate,Ball 1,Ball 2,Ball 3,Ball 4,Ball 5,Ball 6,Bonus Ball,Ball Set,Machine,DrawNumber",
        ["06-Aug-2026,3,13,26,34,48,55,21,Set 3,Arthur,3055",
         "02-Aug-2026,7,11,19,28,37,52,44,Set 1,Merlin,3054"],
        (3, 13, 26, 34, 48, 55), (21,),
    ),
    "euromillions": (
        "DrawDate,Ball 1,Ball 2,Ball 3,Ball 4,Ball 5,Lucky Star 1,Lucky Star 2,DrawNumber",
        ["06-Aug-2026,4,17,29,38,46,3,9,1712",
         "02-Aug-2026,1,12,22,35,50,5,11,1711"],
        (4, 17, 29, 38, 46), (3, 9),
    ),
    "thunderball": (
        "DrawDate,Ball 1,Ball 2,Ball 3,Ball 4,Ball 5,Thunderball,Ball Set,Machine,DrawNumber",
        ["06-Aug-2026,3,11,19,28,37,9,Set 2,Excalibur,1201"],
        (3, 11, 19, 28, 37), (9,),
    ),
    "set_for_life": (
        "DrawDate,Ball 1,Ball 2,Ball 3,Ball 4,Ball 5,Life Ball,Ball Set,Machine,DrawNumber",
        ["06-Aug-2026,5,14,23,31,44,7,Set 1,Merlin,540"],
        (5, 14, 23, 31, 44), (7,),
    ),
}


@pytest.mark.parametrize("game", sorted(_UK_FIXTURES))
def test_uk_csv_parses_real_layouts(game):
    from lotterylab.uk_data import parse

    header, rows, first_main, first_bonus = _UK_FIXTURES[game]
    history = parse("\n".join([header] + rows), game)
    assert history.n_draws == len(rows)
    assert not history.warnings
    # Sorted oldest-first, so the last row of a newest-first file comes first.
    assert history.draws[-1].sorted_main() == first_main
    assert history.draws[-1].bonus == first_bonus


def test_uk_csv_sorts_oldest_first():
    from lotterylab.uk_data import parse

    header, rows, _, _ = _UK_FIXTURES["uk_lotto"]
    history = parse("\n".join([header] + rows), "uk_lotto")
    dates = [d.draw_date for d in history.draws]
    assert dates == sorted(dates)


def test_uk_csv_survives_renamed_and_reordered_columns():
    from lotterylab.uk_data import parse

    text = ("DrawNumber,Machine,Draw Date,BALL_1,ball 2,Ball  3,Ball 4,Ball 5,THUNDERBALL\n"
            "1201,Excalibur,06-Aug-2026,3,11,19,28,37,9")
    history = parse(text, "thunderball")
    assert history.n_draws == 1
    assert history.draws[0].sorted_main() == (3, 11, 19, 28, 37)


def test_uk_csv_reports_a_wrong_game_rather_than_guessing():
    from lotterylab.uk_data import parse

    header, rows, _, _ = _UK_FIXTURES["thunderball"]
    history = parse("\n".join([header] + rows), "uk_lotto")
    assert history.n_draws == 0
    assert history.warnings and "main-ball columns" in history.warnings[0]


def test_uk_source_urls():
    from lotterylab.uk_data import source_url

    assert source_url("uk_lotto").endswith("/results/lotto/draw-history/csv")
    assert source_url("set_for_life").endswith("/results/set-for-life/draw-history/csv")
    with pytest.raises(KeyError):
        source_url("not_a_game")


def test_uk_download_reports_failure_without_raising():
    """A blocked network must produce a message, not a traceback."""
    from lotterylab.uk_data import download

    result = download("uk_lotto", "/tmp/should-not-exist.csv", timeout=1)
    assert isinstance(result.ok, bool)
    if not result.ok:
        assert result.error


# ---------------------------------------------------------------------------
# Winners
# ---------------------------------------------------------------------------


def test_expected_winners_scales_with_sales():
    from lotterylab.winners import expected_winners

    cfg = PRESETS["uk_lotto"]
    small = expected_winners(cfg, 1_000_000, game_key="uk_lotto")
    large = expected_winners(cfg, 20_000_000, game_key="uk_lotto")
    assert large.expected_above(1_000_000) == pytest.approx(
        small.expected_above(1_000_000) * 20, rel=1e-9
    )


def test_millionaire_summary_mentions_the_guarantee():
    from lotterylab.winners import uk_millionaire_summary

    text = uk_millionaire_summary(your_lines_per_week=1)
    assert "Millionaire Maker" in text
    assert "guaranteed" in text


def test_lotto_million_tier_produces_multiple_winners_per_draw():
    """The flat GBP 1m tier is hit routinely - that is the design."""
    from lotterylab.winners import expected_winners

    forecast = expected_winners(PRESETS["uk_lotto"], 15_000_000, game_key="uk_lotto")
    match5bonus = [t for t in forecast.tiers if t.tier_name == "5 + bonus"][0]
    assert match5bonus.expected_winners > 1.0
    assert match5bonus.p_at_least_one > 0.8


@pytest.mark.parametrize("argv", [
    ["dip", "uk_lotto", "-n", "3"],
    ["dip", "euromillions", "-n", "2", "--mode", "unpopular", "--salt", "x"],
    ["dip", "thunderball", "-n", "2"],
    ["dip", "set_for_life", "-n", "2"],
    ["winners"],
    ["winners", "uk_lotto"],
    ["fetch", "--urls"],
    ["odds", "thunderball"],
    ["odds", "set_for_life"],
])
def test_uk_cli_commands_run(argv, capsys):
    from lotterylab.cli import main

    assert main(argv) == 0
    assert capsys.readouterr().out.strip()


# ---------------------------------------------------------------------------
# HotPicks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("picks,expected", [
    (1, 10), (2, 122.5), (3, 1_960), (4, 46_060), (5, 2_118_760),
])
def test_euromillions_hotpicks_odds_match_published(picks, expected):
    """EuroMillions HotPicks matches the operator on all five tiers."""
    from lotterylab.config import HOTPICKS

    hp = HOTPICKS["euromillions_hotpicks"]
    assert 1 / hp.probability(picks) == pytest.approx(expected, rel=1e-3)


@pytest.mark.parametrize("picks,expected", [
    (3, 1_625.45), (4, 30_341.73), (5, 834_397.67),
])
def test_lotto_hotpicks_odds_match_published(picks, expected):
    from lotterylab.config import HOTPICKS

    hp = HOTPICKS["lotto_hotpicks"]
    assert 1 / hp.probability(picks) == pytest.approx(expected, rel=1e-3)


def test_hotpicks_formula_is_the_ratio_of_binomials():
    from lotterylab.config import HOTPICKS

    for hp in HOTPICKS.values():
        for picks in hp.payouts:
            assert hp.probability(picks) == pytest.approx(
                C.comb(hp.drawn, picks) / C.comb(hp.main_pool, picks), rel=1e-12
            )


def test_hotpicks_rejects_unsupported_pick_size():
    from lotterylab.config import HOTPICKS

    with pytest.raises(ValueError):
        HOTPICKS["lotto_hotpicks"].probability(6)


def test_hotpicks_house_edge_is_positive_everywhere():
    from lotterylab.config import HOTPICKS

    for hp in HOTPICKS.values():
        for picks in hp.payouts:
            assert 0.30 < hp.house_edge(picks) < 0.70


# ---------------------------------------------------------------------------
# Game comparison
# ---------------------------------------------------------------------------


def test_euromillions_hotpicks_pick3_is_best_route_to_1000():
    """The headline recommendation must hold."""
    from lotterylab.compare import best_for

    best = best_for(1_000, limit=1)[0]
    assert best.label == "EuroMillions HotPicks pick-3"
    assert best.prize == 1_500
    assert best.cost_per_shot == pytest.approx(2_940, rel=1e-3)


def test_lotto_hotpicks_pick4_is_best_route_to_10000():
    from lotterylab.compare import best_for

    best = best_for(10_000, limit=1)[0]
    assert best.label == "Lotto HotPicks pick-4"
    assert best.cost_per_shot == pytest.approx(30_342, rel=1e-3)


def test_hotpicks_pick3_beats_lotto_match5_by_a_wide_margin():
    """98x per pound is the number the recommendation rests on."""
    from lotterylab.compare import uk_options

    options = {o.label: o for o in uk_options()}
    hotpicks = options["EuroMillions HotPicks pick-3"]
    lotto5 = options["UK Lotto - 5"]
    ratio = lotto5.cost_per_shot / hotpicks.cost_per_shot
    assert ratio > 90
    # ...and it is better value too, which is the surprising part.
    assert hotpicks.expected_return > lotto5.expected_return


def test_all_uk_options_are_negative_ev():
    """No option in the library is a good bet in expectation."""
    from lotterylab.compare import uk_options

    for option in uk_options():
        assert option.expected_return < 1.0


def test_budget_outcome_matches_binomial():
    from lotterylab.compare import best_for, budget_outcome

    option = best_for(1_000, limit=1)[0]
    result = budget_outcome(option, 10.0, 52)
    lines = int(520 / option.ticket_price)
    assert result["lines"] == lines
    assert result["p_win"] == pytest.approx(
        1 - (1 - option.probability) ** lines, rel=1e-9
    )


def test_hotpicks_options_are_flagged_unshared():
    from lotterylab.compare import uk_options

    for option in uk_options():
        if "HotPicks" in option.label:
            assert not option.shared


@pytest.mark.parametrize("argv", [
    ["compare"],
    ["compare", "--target", "1000"],
    ["compare", "--target", "10000", "--weekly", "5"],
    ["compare", "--value"],
])
def test_compare_cli_runs(argv, capsys):
    from lotterylab.cli import main

    assert main(argv) == 0
    assert capsys.readouterr().out.strip()


# ---------------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------------

matplotlib = pytest.importorskip("matplotlib", reason="report needs matplotlib")


def test_report_builds_a_valid_pdf(tmp_path):
    from lotterylab.report import build_report

    out = build_report(tmp_path / "report.pdf")
    assert out.exists()
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 20_000


def test_report_money_formatting_keeps_meaningful_digits():
    """£1,500 must not be rounded to '£2k'."""
    from lotterylab.report import _odds_short, _short_money

    assert _short_money(1_500) == "£1,500"
    assert _short_money(13_000) == "£13k"
    assert _short_money(1_000_000) == "£1m"
    assert _odds_short(1 / 1_960) == "1 in 1,960"
    assert _odds_short(1 / 139_838_160) == "1 in 139.8m"


def test_report_uses_whole_game_rtp_not_one_tier():
    """Lotto's Match 5 tier alone returns ~1%; the whole game returns ~40%."""
    from lotterylab.report import _whole_game_rtp

    assert 0.35 < _whole_game_rtp("uk_lotto") < 0.50
    assert 0.30 < _whole_game_rtp("euromillions") < 0.45


def test_report_cli(tmp_path, capsys):
    from lotterylab.cli import main

    assert main(["report", "-o", str(tmp_path / "r.pdf")]) == 0
    assert (tmp_path / "r.pdf").exists()
