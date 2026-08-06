# How lottery numbers are actually generated

Understanding the generation mechanism is the prerequisite for every other question, because it determines *where* a lottery can be attacked. The short answer, established below and reinforced by every documented case in history: **the entropy source is almost never the weak point.**

---

## 1. Physical draw machines

Two families dominate, both supplied by a handful of vendors (Smartplay International is the largest).

**Gravity-mix machines.** Rotating paddles agitate balls inside a transparent chamber; gravity drops selected balls into a display rack. Smartplay's *Halogen* (100-ball mix capacity, 50mm foam balls) is described by the manufacturer as standard for traditional lotteries in Australia, New Zealand, Hong Kong and the UK, and is used by US Powerball. The *Magnum* holds 300.

**Air-mix machines.** A blower drives balls turbulently; a ball is "trapped" in a display position at the top of the chamber. Typically 40mm foam or table-tennis balls, and preferred for fast single-digit games.

The UK National Lottery uses gravity-pick machines named after Arthurian figures (Arthur, Guinevere, Lancelot, Merlin), with multiple live ball sets, and the machine/ball-set pairing chosen at random shortly before broadcast.

### Ball manufacture and tolerance

Balls are produced in matched sets under tight weight and size tolerances and stored in foam-lined, lockable cases. Vendors do not publish numeric tolerances; those live in state drawing rules.

### The control regime

Florida's published drawing-procedure rule is the clearest legally binding description of a real regime, and it is worth reading as a specification of what the industry considers necessary:

- Drawings are public and video-recorded, witnessed by an accountant from an independent CPA firm.
- **Ball sets and machines are selected at random**, with a primary *and* a secondary of each chosen per draw.
- Every ball in a set carries the same **security code**, verified before and after.
- The primary set is **weighed**; out-of-tolerance sets are rejected and cycled.
- **Scripted test draws** run with pre-committed abort criteria — e.g. for FLORIDA LOTTO, six test draws; if the same digit appears four times in six, four more are run; two further recurrences force the secondary ball set.
- **Post-draw weighing**: a deviation of more than **1 gram** from the pre-draw weight sends the set to the security division for investigation.

The design intent is that a physical bias large enough to exploit would have to survive random set-and-machine selection *and* pass both weight gates *and* the test-draw screen.

### Does physical bias actually exist?

The honest answer is: **it has been proven exactly once in a high-stakes draw, and that draw was not a modern lottery.**

The **1969 US draft lottery** is the reference case. 366 capsules were loaded month by month (January→December), tipped into a jar, and drawn. Mixing was insufficient to destroy the loading order, and November and December birth dates drew disproportionately low (early-call) numbers. Fienberg's 1971 *Science* analysis established the non-randomness. This is precisely the failure mode — inadequate mixing preserving load order — that modern test-draw regimes exist to catch.

For **modern ball-drawn lotteries, no peer-reviewed study has established non-uniformity.** Haigh (1997, *JRSS-A*) found the first 96 UK Lotto draws consistent with randomness in both frequencies and waiting times. Genest, Lockhart & Stephens (2002) analysed ~20 years of Canadian 6/49 and concluded that neither Pearson's statistic nor Joe's test gave "any serious ground for suspecting a lack of uniformity" (p-values above 0.66). Cambridge's Winton Programme analysed ~1,240 UK draws in groups of 50 and found all 24 group statistics inside the central 95% interval.

That last analysis also disposes of the most-cited "anomaly": ball 17 once went **72 draws** without appearing. The naive probability of a specific 72-draw gap is 0.000082 — but across 7,440 observed gaps, the chance that *some* gap reaches 72 is about **0.46**, and simulation gives a mean largest gap of exactly 72. Entirely unremarkable.

> **A methodological warning.** Because balls are drawn *without replacement*, the naive Pearson statistic does **not** follow χ²(M−1). Haigh's correction is `X² = [(M−1)/(M−m)]·X²_naive` — a factor of 48/43 ≈ 1.12 for a 6/49 game. Any analysis applying a plain χ²(48) to lotto ball frequencies is mis-specified and badly conservative. This library implements the correction (`lotterylab/fairness.py`), and omitting it dropped the test's false-positive rate from 5% to 1.3% in calibration.

### Beware fabricated statistics

Searches for lottery bias surface a widely reposted claim that "a 2024 analysis of 10,000 North American draw events found 32% exhibited mechanical drift, with balls appearing 1.8 standard deviations from expectation," alongside claims about multi-spectral imaging of draw footage. **This appears only on AI-generated content sites with no primary study, author, or dataset, and it is not internally coherent** — you would expect roughly 7% of numbers to exceed ±1.8σ by chance anyway, so the figure describes nothing. Treat it as fabricated.

---

## 2. Certified RNG draws

Migration off balls is real but concentrated in **daily games**, not the big jackpot games. Maryland replaced ball machines with an RNG for all five of its draw games in December 2022 and stated that more than 30 other US and Canadian lotteries already used RNG systems. **Powerball and Mega Millions still use physical draws.**

### Standards

- **GLI-11** (gaming devices) Chapter 3 carries the RNG requirements most lottery certification anchors to; **GLI-19** covers interactive gaming systems.
- **WLA Security Control Standard** layers lottery-specific controls on ISO/IEC 27001; Level 2 requires ISO 27001 certification. The 2024 edition added a dedicated RNG section covering cloud deployments.
- **BMM Testlabs** is the other major independent lab.

**A correction to a common assumption:** GLI does *not* simply mandate Diehard, NIST SP 800-22 or TestU01 BigCrush by name. It specifies its own enumerated battery — chi-square, equidistribution, gap, overlaps, poker, coupon collector, permutation, Kolmogorov–Smirnov, adjacency, order statistic, runs, interplay correlation, serial correlation, subsequence tests, Poisson — and **the lab selects which apply case by case**. The public batteries are used as supplementary evidence, not as regulatory requirements.

GLI's substantive requirement is the right one: knowledge of numbers from one draw must yield no information about a future draw, and within a multi-value draw, knowing one value must not reveal another.

### Architecture

The standard design is a **hardware entropy source feeding or reseeding a cryptographic DRBG** — not a bare PRNG, and not a raw TRNG. Quantum RNG vendors (ID Quantique's Quantis) market specifically to the sector.

---

## 3. Every documented fraud, and what it tells you

### The 1980 Pennsylvania "Triple Six Fix"

The Daily Number, drawn live on three air-mix machines, came up **6-6-6 on 24 April 1980**, paying a record ~$3.5M. Ringleader Nick Perry was the TV announcer who hosted the draw. **All balls except those numbered 4 and 6 were weighted with white latex paint injected by syringe**, calibrated so they would still bounce in the air stream but not rise to be trapped. A stagehand swapped the sets before and after the broadcast; the rigged balls were burned in a paint can half an hour later.

**It was caught by anomalous betting patterns** — a flood of wagers on combinations of 4s and 6s — not by statistical analysis of the draw.

This is the origin of post-draw ball weighing and the 1-gram delta trigger.

### Eddie Tipton and the Hot Lotto rootkit

The defining modern case, and the one that should shape how you think about lottery security.

Tipton was **Information Security Director of the Multi-State Lottery Association** — the person responsible for securing the RNG. Admitted to the draw room on 20 November 2010 to adjust the clock for daylight saving, he installed self-deleting malware from a USB drive on a day when the security cameras were recording roughly **one second per minute**.

The technical core: forensic examination of a 2007 Wisconsin Megabucks draw showed the generator produced **knowable outcomes** when three conditions held simultaneously — the date was 27 May, 23 November or 29 December; it fell on a Wednesday or Saturday; and the draw ran after 8:00 p.m. On those draws the code **bypassed the random path entirely** and substituted a deterministic algorithm. Investigators reproduced the actual historical winning numbers by re-running it, and that reproduction was the breakthrough evidence.

He was **not caught by statistical detection**. The $14.3M prize went unclaimed for nearly a year; a lawyer tried to claim it anonymously through a Belize shell company two hours before the deadline; the claim was refused; investigators released convenience-store surveillance footage in October 2014, and co-workers recognised Tipton's voice and mannerisms. He confessed in 2017 to rigging draws in Iowa, Colorado, Wisconsin, Kansas and Oklahoma.

Discovery in related litigation surfaced a 2015 internal memo showing MUSL's own security officers **lacked confidence in the random number generation process** and had recommended suspending some games.

**The lesson generalises completely: the vulnerability was the insider with access to the number-producing system, not the entropy source.** The RNG had been audited. The attack came after certification.

### Ronald Dale Harris — the direct precedent

Harris was a **Nevada Gaming Control Board programmer whose job was auditing casino game source code**. He used that access to modify slot machines to pay on a coin-insertion sequence, and separately wrote a program predicting a keno PRNG's output. Caught in 1995 when his accomplice tried to redeem a $100,000 keno ticket and behaved suspiciously.

The person employed to verify randomness is the person best placed to defeat it. This pattern recurs.

### Weak-PRNG exploits

- **ASF Software / Planet Poker (1999)** — the canonical case. The vendor *published* its shuffle algorithm to demonstrate fairness. Two compounding flaws: a **32-bit PRNG** (~4.29 billion shuffles versus 52! ≈ 2²²⁶ real ones), and seeding from **milliseconds since midnight** — only 86,400,000 possible seeds. With the clock roughly synchronised and a few known cards, researchers reconstructed the full deck in real time.
- **Aristocrat Mark VI slots (~2009–2014)** — a linear congruential generator, invertible from a short output sequence. Operatives filmed ~20 spins, uploaded timing data to a server that recovered the state, and their phone vibrated a quarter-second before the profitable moment.
- **Ethereum lottery contracts** — CVE-2018-12454 (*1000 Guess*) derived randomness from a `private` state variable plus block variables. Solidity `private` is not confidential; the variable was readable via `getStorageAt`, making outcomes fully computable before entering.
- **Generic classes**: MT19937 state is fully recoverable from **624 consecutive 32-bit outputs**; `java.util.Random` is a 48-bit LCG whose seed falls to two outputs.

**No publicly documented case exists of a state lottery mobile app or official online instant-win game being broken via weak PRNG.** Claims to that effect circulate without named products, dates or researchers.

### Scratch tickets — a genuinely broken generation scheme

In 2003 Mohan Srivastava, a Toronto geostatistician, found that the *visible* numbers on Ontario tic-tac-toe scratch tickets carried information about the hidden ones. Digits appearing exactly once across the boards — **"singletons"** — were almost always repeated under the latex. He could identify winners **about 90% of the time**. He reported it; the game was pulled within days.

This is the exception that proves the rule: it was a flaw in how the *tickets were generated*, not in a draw.

---

## 4. The conclusion that matters

Tabulating every documented case:

| Case | Attack surface | Was it a statistical bias in the draw? |
|---|---|---|
| 1969 draft lottery | Procedure (mixing) | Bias yes, but no attacker |
| 1980 Triple Six Fix | Physical substitution | No — induced, not found |
| Hot Lotto | Insider code modification | No |
| Ronald Harris | Insider code access | No |
| Ontario scratch tickets | Ticket generation flaw | No — deterministic leak |
| Cash WinFall / Mandel / Texas 2023 | Game *design* | No — draw was perfectly fair |

> **In no documented case did an attacker profit by exploiting an undetected statistical bias in the draw itself.**

That is the single most defensible conclusion available, and it has a direct practical implication for anyone hoping to mine draw history: the thing you would be looking for has never once been the thing that worked.

---

*Next: [02 — The probability mathematics](02-probability.md)*
