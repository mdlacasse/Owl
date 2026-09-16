# LP-only exploration: scripts and results

Experiments from the `lp-only` breakaway (2026-09-12/13). The branch strips every binary from the
engine and keeps the self-consistent (SC) loop over a pure LP. Scripts that need the MILP engine run
against the unchanged clone at `~/Owl` with `PYTHONPATH=/Users/mdlacasse/Owl/src`.

All figures below are copied from the printed output of the runs that wrote the files in `results/`.

## Scripts

| script | engine | purpose |
|---|---|---|
| `loop_baseline.py` | either (`SOLVER`, `PYTHONPATH`) | Loop-mode invariant: 17 example cases + `Case_dana` windows 1928/1965/1966/1969/1999, both objectives. Records status, convergence, LP build count, bequest, basis, first-year conversions, total taxes. |
| `nowarm_wrapper.py` | MILP engine | Runs `loop_baseline.py` with the HiGHS warm-start hint disabled. |
| `family_residuals.py` | lp-only (`plan.scTrace`) | Per-family fixed-point residual at the accepted iterate, and parameter movement over the last iterates. Configs `dana` (base) and `p12` (pia_ladder.py rung: (150, 937, 100)$k, PIA 4152 at 70). |
| `attribute_dana.py` | MILP engine | Base `Case_dana` maxBequest (netSpending 58k, gap 1e-4, maxTime 1800): loop, SS-only, IRMAA-only, LTCG-only, NIIT-only and all-four MILP arms, each audited by recomputing every tax and premium from the solution's own incomes. Env: `SOLVER`, `WORKERS`, `ARMS_ONLY`. Checkpoints and resumes. |
| `regime_flips.py` | MILP engine | Loop vs all-four MILP for one Case_dana window: per-year regime flips for SS, IRMAA (labelled by premium year), LTCG, with the loop's distance to the nearest boundary. |
| `rins_probe.py` | MILP engine | Two-stage hybrid on one Case_dana window: loop, LP relaxation of the all-four model, then the all-four MILP with SS binaries pinned outside a neighborhood (`NEIGHBORHOOD=rins` with `RINS_TOL`, or `irmaa:R`); audits the hybrid answer. |
| `illuminated_box.py` | lp-only (`plan.scTrace`) | Per-year [min, max] regime over the loop's iterates, checked against the MILP flips in `regime_flips_*.json`. |
| `hybrid_ladder.py` | MILP engine | Two-stage hybrid across the wealth ladder (`RUNGS`, `YEARS`, `ARMS` = loop, h:R, full; `MAXTIME`); records regime occupancy and audits every MILP arm. Checkpoints and resumes. |

Mind the machine: 16 GB RAM, shared with a manuscript session in `~/Owl`. Default to one worker;
a MOSEK SS-only MILP on 1928 ran past 1h40m and the OS killed jobs for low memory.

## Results

### Strip invariant (`baseline_*.json`, `highs_*.json`)
- MOSEK: `baseline_pre` vs `baseline_post1` (engine stripped) and `baseline_post2` (pinned `m_n`
  column removed): 27 cases x 7 fields, **0 exact differences**.
- HiGHS: MILP engine vs lp-only, 41 of 189 fields differ; MILP engine run twice, 0 differences.
  Disabling only the warm start on the MILP engine (`highs_main_nowarm`) leaves 13; restoring the
  MIP options on lp-only (`highs_dev_mipopts`) still 13, so those follow the column reorder (by
  elimination). `Case_dana` 1966 maxBequest bequest: 415,446.79 (MILP engine, HiGHS), 422,043.75
  (no warm start), 423,390.25 (lp-only, HiGHS), 432,517.68 (MOSEK): tie-breaking alone moves the SC
  fixed point.

### Family residuals (`resid_dana.json`, `resid_p12.json`), MOSEK, 72 windows 1928-1999
- `dana`: residuals IRMAA/NIIT/ACA/LTCG 0 in all 72; SS > $10 in 16/72 (median 0, max 5,125 of
  taxable income). All-four MILP (`milp_all72.json`) minus loop: median 5,146 (0.27%), max 40,986,
  max relative 4.64%. 42 windows have SS residual <= $10 yet a gap > $1,000: the loop sits at a
  fixed point that is not optimal.
- `p12`: convergence oscillatory 66 / cycle-2 4 / monotonic 2. SS residual > $10 in 72/72 (median
  1,092, max 18,846); IRMAA 7/72 (max 3,445); NIIT 1/72. SS-exact (`ssx_pia4152.json`) minus loop:
  median 46,668 (1.53%), max 141,657, min 13,174.

### Attribution of the base `Case_dana` gap (`attr_*.json`)
Single-family MILP minus loop, today's $ (all-four gap from `milp_all72.json`):

| window | all four | SS only | IRMAA only | LTCG only | NIIT only |
|---|---|---|---|---|---|
| 1966 | 20,080 | 19,571 | 2 | 2 | 2 |
| 1928 | 40,986 | >= 16,396 (HiGHS, gap 5.6e-2, time limit) | 3,027 | -383 | -383 |
| 1983 | 30,640 | 0 | 30,637 | 0 | -10,925 |
| 1982 | 29,441 | 0 | 29,411 | 0 | -3,226 |
| 1932 | 24,534 | -17,267 | 20,962 | 11,826 | 0 |

- Over all 72 windows: IRMAA-only recovers 60.2% of the summed gap, LTCG-only 9.6%, NIIT-only -2.56%.
- All-four 1966 reproduces `milp_all72.json` exactly (452,598.00).
- Negative arms are fixed-point selection, not formulation error: 1983 IRMAA+NIIT minus IRMAA-only
  is +3.78; the NIIT-only run pays +1,722 more Medicare than the loop.
- Medicare audit flags on IRMAA-only arms (whole $1,148 steps) are a rounding artifact: the MILP puts
  MAGI exactly on the IRMAA threshold (+$0.0055 and +$0.0033 in 1932) and the strict `>` recompute
  moves it up a bracket.
- The state tax row uses the lagged Psi_n for the SS exclusion in every mode; it shows in the audit
  only on unsettled runs (1928 HiGHS SS-only $303, 1932 $40).
- Solve cost is almost all SS binaries: over 72 windows IRMAA-/LTCG-/NIIT-only MILPs take median
  0.1/0.2/0.1 s (max 0.6/0.9/1.3 s); SS-only 23.1 s (1983), 23.4 s (1982), 157.9 s (1932),
  3,587 s (1966), >4,686 s (1928, HiGHS, time limit). All-four 1966: 3,640 s.

### Regime flips, loop vs all-four MILP (`regime_flips.py`, `regime_flips_*.json`)
Distance = the loop's income distance to the nearest boundary of that family, today's $.
- 1983 (all-four 4,368,666.23, 87.3 s): SS 0 flips, LTCG 0; IRMAA 8 of 27, all bracket 1 -> 0, at
  distances 112 to 12,830; 7 of 8 moves go exactly to the threshold. Unflipped IRMAA years min 3,374.
- 1932 (all-four 4,190,654.04, 1,013.2 s): IRMAA 4 of 27 (distances 1,423 to 12,628); SS 3 of 23,
  capped -> 85% ramp in 2032-2034 at distances 25,438-26,271 while unflipped SS years start at
  16,706; LTCG 0 flips although LTCG-only recovered 11,826.
- Label caveat: `regime_flips.py` reports IRMAA flips by PREMIUM year n; the income that moved is
  MAGI in year n-2. The 1932 IRMAA flips are income years 2026, 2027, 2030, 2031; the SS flips are
  income years 2032-2034. An earlier note that the SS flips "coincide with IRMAA flips" matched
  labels, not income years, and is retracted.

### Two-stage hybrid probes (`rins_probe.py`, `rins_probe_*`)
Stage 1 loop, stage 2 all-four MILP with some SS binaries pinned at the loop's regime; IRMAA/LTCG/NIIT
binaries all free. 1932 references: loop 4,166,120.26 (0.1 s); full all-four 4,190,654.04 (1,013.2 s).
- RINS rule (pin SS years whose LP-relaxation binaries agree with the loop), tolerance 1e-6: the
  big-M relaxation returns 1.000/0.999/0.001 values, so nothing agrees and nothing is pinned.
- RINS rule, tolerance 0.01: 8 SS years pinned (2030-2034, 2041, 2046, 2047), 15 free.
  4,189,842.89 in 72.0 s, gap 0: +23,722.63 of the +24,533.78 gap (96.7%), 14x faster. It pins
  2032-2034, the MILP's SS flips, which cost only the remaining 811.15.
- IRMAA-coupled rule (`NEIGHBORHOOD=irmaa:R`: free SS binaries of income year n when the loop's
  MAGI_n is within R of an IRMAA threshold for premium year n+2):
  - R = 30,000: 14 SS years free, 4,190,654.04 in 136.2 s, gap 0 -- the full MILP to the cent, 7.4x faster.
  - R = 13,000: 3 SS years free (2030-2032), 4,191,503.92 in 1.5-1.6 s, gap 0 -- $849.88 ABOVE the
    full MILP. Audit clean except Medicare 3,445, which is the sub-cent threshold artifact (MAGI over
    the IRMAA threshold by +0.0015, +0.0008, +0.0033). A restriction beating the "full" MILP means
    the full MILP is exact only relative to the quantities it still iterates in the SC loop
    (I_n, gain fractions, OBBBA MAGI, lagged Psi in the state row): different neighborhoods settle
    on different outer fixed points. Which quantity is responsible is not determined.

### Illuminated box (`illuminated_box.py`)
Box = per-year [min, max] ordered regime over the loop's iterates (lp-only `scTrace`).
- 1983 and 1932: 5 iterates each; years visiting more than one regime: SS 0/23, IRMAA 1/25, LTCG
  0/27 (the one IRMAA year only through the zero-initialized iterates). MILP flips inside the box:
  0 of 8 (1983), 0 of 7 (1932). Every MILP flip is one step DOWN (IRMAA 1->0, SS capped->85% ramp),
  a side the loop never visits: the box of the recursion collapses to the loop's own regimes.

### Wealth ladder, stage A (`hybrid_ladder.py`, `hybrid_ladder.json`, `hybrid_ladder_stageA.log`)
Rungs from ladders.py (floors 34/58/99/166/277k), windows 1928/1932/1966/1973/1983/1999, MOSEK gap 1e-4,
maxTime 600, arms loop and hybrid irmaa:13000. Peak RSS 2,640 MB.
- Occupancy at the loop solution (all six windows): W0.5 SS on the ramps (1928: 13 on the 50% ramp,
  8 on the 85% ramp, 2 capped), IRMAA bracket 0; dana SS mostly capped, IRMAA 0-1; W2 IRMAA 0-4;
  devon IRMAA mostly 3-4, NIIT 21-27 years; W8 IRMAA 4-5, LTCG 20% band, NIIT all 27 years.
- Hybrid gain over loop: W0.5 +939..+24,463 (0/23 SS free, 0.1-0.3 s); dana +2,226..+30,625
  (0.4-1.9 s); W2 -5,703 (1973)..+79,722 (2.7-1,195 s); devon +5,798..+86,399 (14-893 s);
  W8 +1,243..+61,703 (5-105 s).
- dana share of the full-MILP gain (milp_all72): 1932 103.5%, 1983 99.9%, 1966 79.9% (0 SS free),
  1999 44.7%, 1973 39.7%, 1928 19.6%.
- Problems: (1) from W2 up SS is capped every year yet the rule frees up to 20/23 SS years (cost);
  (2) at W0.5 IRMAA never leaves bracket 0 so nothing is freed where SS sits on the ramps;
  (3) unexplained: W2/1973 below loop by 5,703; Medicare audit beyond $1 tolerance 1,148 (W2/1928),
  1,722 (W2/1983, devon/1973); NIIT audit 422 (devon/1973). No full-MILP reference off the dana rung.
- 1973 (all-four 1,394,532.87, 1,136.7 s, peak 1,835 MB): SS 2 flips (2032, 2034, capped -> 85% ramp)
  at distances 4,576 and 7,588 (unflipped min 1,130, median 10,684); IRMAA 0 flips (unflipped min
  9,000); LTCG 7 flips, six UP 0 -> 1 (+5,901..+10,022 income) and 2034 down (-38,670).
  SS flips here are near their own threshold and IRMAA plays no part.
- Memory limits (MOSEK, 2 threads, 16 GB machine): full all-four MILP 1999 reached 8,367 MB RSS at
  2,087 s (stopped); 1928 was killed by the OS within ~13 min. The earlier one-step-down (`d1`) stop was a
  false trigger on residual swap (process RSS 738 MB, peak 4,883 MB) -- not evidence that d1 cannot run.
  Watch process RSS and `memory_pressure` free %, not swap used (macOS does not release swap).

### HiGHS vs MOSEK on the full all-four MILP (`regime_flips_highs_*.log/json`)
Same setup (gap 1e-4, maxTime 1800 per SC iteration); free-memory watchdog never fired (min free >= 49%).
| window | MOSEK | HiGHS |
|---|---|---|
| 1973 | 1,835 MB, 1,137 s, gap 0, 1,394,532.87 | 1,456 MB, 27,463 s, gap 8.8e-2 (max iteration), 1,394,540.35 |
| 1999 | 8,367 MB at 2,087 s (stopped) | 4,943 MB, 28,533 s, gap 9.0e-2, 1,344,639.54 -- below its own loop (1,345,053.04) and 5,019.74 below milp_all72 (1,349,659.28) |
| 1928 | OS-killed within ~13 min | 5,184 MB, 9,882 s, gap 6.9e-2, 1,977,853.67 -- 2,095.96 below milp_all72 (1,979,949.63) |
- HiGHS uses less memory but is 9-25x slower and stops with unproven gaps; not usable as a reference.
- HiGHS loops land elsewhere (1973 loop 1,367,304.33 vs MOSEK 1,376,556.17), so flips below are relative
  to a different loop plan and to unconverged MILP answers.
- SS flips: 1928 12/23 (11 within 9,646 of the SS boundary, one at 24,977; unflipped median 6,109,
  min 1,314); 1999 12/23 (11 within 9,100, one at 10,636; unflipped median 7,667, min 5,127). LTCG 12-14
  flips per window; IRMAA 1 (1928) or 0. An SS own-distance radius of ~10k would free most SS years in
  these windows: it contains the flips but barely shrinks the SS binary set.
