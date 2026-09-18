"""
Expected Value calculator for EuroMillions.

Sources:
  - Abrams & Garibaldi (2010): jackpot must be ~€150-220M for gross positive EV
  - Matheson & Grote: ~1% of draws offer positive expected return after tax
  - EuroMillions prize pool = ~50% of ticket revenue
  - Non-jackpot tier prize contributions ≈ €0.90–1.00 per ticket
  - EuroMillions jackpot cap: €250M (best EV scenario)
  - Jackpot splitting adjustment: as jackpot grows, more tickets sold → more splitting

Friday 29 May 2026: jackpot estimated €125–135M (10th consecutive rollover).
"""

import math

TICKET_PRICE_EUR = 2.50
JACKPOT_ODDS = 139_838_160
NON_JACKPOT_EV_PER_TICKET = 0.95  # fixed prize tiers contribution (€)
EST_TICKETS_PER_DRAW_NORMAL = 50_000_000   # typical draw
EST_TICKETS_PER_DRAW_LARGE = 90_000_000    # large jackpot surge


def expected_value(jackpot_eur: float, tickets_sold: int = None) -> dict:
    """
    Calculate expected value per ticket given jackpot size.

    Returns dict with EV, jackpot_ev_component, splitting_factor, verdict.
    """
    if tickets_sold is None:
        # Estimate ticket sales based on jackpot size (surge at large jackpots)
        if jackpot_eur > 100_000_000:
            tickets_sold = int(EST_TICKETS_PER_DRAW_LARGE * (jackpot_eur / 100_000_000) ** 0.3)
        else:
            tickets_sold = EST_TICKETS_PER_DRAW_NORMAL

    # Probability of jackpot win per ticket
    p_win = 1.0 / JACKPOT_ODDS

    # Expected number of OTHER winners (Poisson approximation)
    expected_other_winners = (tickets_sold - 1) * p_win
    # E[jackpot share] = jackpot / E[N_winners] where N_winners ~ Poisson(λ+1)
    # Using E[1/(N+1)] ≈ (1 - e^-λ) / λ for Poisson(λ)
    lam = expected_other_winners
    if lam > 0:
        sharing_factor = (1 - math.exp(-lam)) / lam
    else:
        sharing_factor = 1.0

    jackpot_ev = p_win * jackpot_eur * sharing_factor
    total_ev = jackpot_ev + NON_JACKPOT_EV_PER_TICKET

    is_positive_ev = total_ev > TICKET_PRICE_EUR

    if is_positive_ev:
        verdict = "POSITIVE EV — mathematically worth playing"
    elif total_ev > TICKET_PRICE_EUR * 0.75:
        verdict = "Near break-even — best conditions to play"
    elif total_ev > TICKET_PRICE_EUR * 0.50:
        verdict = "Below average loss — large jackpot improves it"
    else:
        verdict = "Standard negative EV — entertainment value only"

    return {
        "jackpot_eur": jackpot_eur,
        "ticket_price_eur": TICKET_PRICE_EUR,
        "estimated_tickets_sold": tickets_sold,
        "p_win_jackpot": p_win,
        "sharing_factor": round(sharing_factor, 4),
        "jackpot_ev_component": round(jackpot_ev, 4),
        "non_jackpot_ev": NON_JACKPOT_EV_PER_TICKET,
        "total_ev": round(total_ev, 4),
        "ev_per_pound_spent": round(total_ev / TICKET_PRICE_EUR, 4),
        "is_positive_ev": is_positive_ev,
        "verdict": verdict,
    }


def break_even_jackpot() -> float:
    """Jackpot size at which EV per ticket = ticket price (pre-splitting)."""
    required_jackpot_ev = TICKET_PRICE_EUR - NON_JACKPOT_EV_PER_TICKET
    return required_jackpot_ev * JACKPOT_ODDS


def format_ev_report(jackpot_eur: float) -> str:
    ev = expected_value(jackpot_eur)
    lines = [
        f"\n  Jackpot:          €{jackpot_eur/1_000_000:.0f}M",
        f"  Ticket cost:      €{TICKET_PRICE_EUR:.2f}",
        f"  Est. tickets sold: ~{ev['estimated_tickets_sold']/1_000_000:.0f}M",
        f"  Jackpot splitting: {ev['sharing_factor']:.3f}× (accounts for shared wins)",
        f"  EV from jackpot:  €{ev['jackpot_ev_component']:.4f}",
        f"  EV from prizes:   €{ev['non_jackpot_ev']:.2f}",
        f"  Total EV/ticket:  €{ev['total_ev']:.4f}  "
        f"({ev['ev_per_pound_spent']*100:.1f}p return per £1 spent)",
        f"  Verdict:          {ev['verdict']}",
    ]
    return "\n".join(lines)
