"""Static charts for the GBP/JPY report, using the validated reference palette."""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
SURF = "#fcfcfb"
BLUE = "#2a78d6"
RED = "#e34948"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "sans-serif", "text.color": INK, "axes.edgecolor": BASE,
    "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "font.size": 11,
})

r = json.load(open("results.json"))


def style(ax, title, sub=None):
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=14)
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9.5, color=MUTED)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    ax.grid(axis="x", visible=False)


def signed_bars(ax, vals, fmt="{:+.3f}%"):
    colors = [BLUE if v >= 0 else RED for v in vals]
    bars = ax.bar(DOW, vals, width=0.55, color=colors, zorder=3)
    ax.axhline(0, color=BASE, lw=1, zorder=2)
    for b, v in zip(bars, vals):
        ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2,
                    v + (0.004 if v >= 0 else -0.004) * max(abs(min(vals)), max(vals)) / 0.12),
                    ha="center", va="bottom" if v >= 0 else "top", fontsize=10, color=INK2)


# 1. mean daily return by weekday, 5y
by = r["daily_5y"]["by_dow"]
fig, ax = plt.subplots(figsize=(7.2, 4.2))
signed_bars(ax, [by[d]["mean_ret"] for d in DOW])
style(ax, "GBP/JPY average daily return by weekday",
      f"Close-to-close log return, {r['daily_5y']['span'][0]} to {r['daily_5y']['span'][1]} · FRED + currency-api")
ax.set_ylabel("mean return (%)")
fig.tight_layout(); fig.savefig("charts/dow_mean_return_5y.png", dpi=150); plt.close(fig)

# 2. % up days by weekday, 5y
fig, ax = plt.subplots(figsize=(7.2, 4.2))
vals = [by[d]["pct_up"] for d in DOW]
bars = ax.bar(DOW, vals, width=0.55, color=[BLUE if v >= 50 else RED for v in vals], zorder=3)
ax.axhline(50, color=INK2, lw=1, ls=(0, (4, 3)), zorder=4)
ax.text(4.45, 50, "50% (coin flip)", fontsize=9, color=INK2, va="center")
for b, v in zip(bars, vals):
    ax.annotate(f"{v:.0f}%", (b.get_x() + b.get_width() / 2, v + 0.6), ha="center", fontsize=10, color=INK2)
ax.set_ylim(35, 68)
style(ax, "Share of up days by weekday", "Same 5-year daily series · above 50% = day tends to close higher")
ax.set_ylabel("% of days closing up")
fig.tight_layout(); fig.savefig("charts/dow_pct_up_5y.png", dpi=150); plt.close(fig)

# 3. year-by-year mean return heatmap (consistency)
years = sorted(r["daily_5y"]["yearly_mean_ret"])
mat = np.array([r["daily_5y"]["yearly_mean_ret"][y] for y in years], dtype=float)
cmap = LinearSegmentedColormap.from_list("div", [RED, "#f0efec", BLUE])
fig, ax = plt.subplots(figsize=(7.2, 4.4))
im = ax.imshow(mat, cmap=cmap, norm=TwoSlopeNorm(vcenter=0), aspect="auto")
ax.set_xticks(range(5), DOW); ax.set_yticks(range(len(years)), years)
for i in range(len(years)):
    for j in range(5):
        ax.text(j, i, f"{mat[i, j]:+.2f}", ha="center", va="center", fontsize=9.5,
                color=INK if abs(mat[i, j]) < 0.16 else "#ffffff")
ax.grid(False)
style(ax, "Average daily return per weekday, year by year",
      "Mean % return per weekday and calendar year · blue = positive, red = negative")
fig.tight_layout(); fig.savefig("charts/dow_yearly_consistency.png", dpi=150); plt.close(fig)

# 4. day x London-hour range heatmap (2017-2022)
heat = np.array(r["h1"]["recent_2017_2022"]["heat_range"], dtype=float)
cmap_seq = LinearSegmentedColormap.from_list("seq", SEQ)
fig, ax = plt.subplots(figsize=(10.5, 3.9))
im = ax.imshow(heat, cmap=cmap_seq, aspect="auto")
ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)], fontsize=8.5)
ax.set_yticks(range(5), DOW)
ax.grid(False)
cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.015)
cb.set_label("mean hourly range (pips)", fontsize=9, color=INK2)
cb.outline.set_visible(False)
style(ax, "Volatility map: weekday × hour of day (London time)",
      "Mean 1-hour high–low range in pips, 2017–2022 hourly data (Dukascopy)")
ax.set_xlabel("hour of day, London time")
fig.tight_layout(); fig.savefig("charts/heatmap_dow_hour_range.png", dpi=150); plt.close(fig)

# 5. mean daily range by weekday (2017-2022) — magnitude, single hue
rec = r["d1"]["recent_2017_2022"]["by_dow"]
fig, ax = plt.subplots(figsize=(7.2, 4.2))
vals = [rec[d]["mean_range_pips"] for d in DOW]
bars = ax.bar(DOW, vals, width=0.55, color=BLUE, zorder=3)
for b, v in zip(bars, vals):
    ax.annotate(f"{v:.0f}", (b.get_x() + b.get_width() / 2, v + 1.5), ha="center", fontsize=10, color=INK2)
ax.set_ylim(0, 155)
style(ax, "Average daily range by weekday", "High–low range in pips, 2017–2022 daily data (Dukascopy)")
ax.set_ylabel("pips")
fig.tight_layout(); fig.savefig("charts/dow_range.png", dpi=150); plt.close(fig)

# 6. hourly range profile (London time)
prof = r["h1"]["recent_2017_2022"]["hourly_range"]
fig, ax = plt.subplots(figsize=(9.5, 4.0))
bars = ax.bar(range(24), prof, width=0.6, color=BLUE, zorder=3)
for spans, label in [((8, 16), "London session"), ((13, 17), None)]:
    pass
ax.axvspan(7.5, 16.5, color="#2a78d6", alpha=0.06, zorder=1)
ax.text(11.9, max(prof) + 2.2, "London session 08–16", ha="center", fontsize=9, color=INK2)
ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)], fontsize=8.5)
peak = int(np.argmax(prof))
ax.annotate(f"{prof[peak]:.0f} pips", (peak, prof[peak] + 0.6), ha="center", fontsize=9.5, color=INK)
style(ax, "Average hourly range across the day (London time)",
      "Mean 1-hour high–low range in pips, 2017–2022 · quietest 03–06, busiest 08–16")
ax.set_ylabel("pips"); ax.set_xlabel("hour of day, London time")
ax.set_ylim(0, max(prof) + 6)
fig.tight_layout(); fig.savefig("charts/hourly_range_profile.png", dpi=150); plt.close(fig)

print("charts written")
