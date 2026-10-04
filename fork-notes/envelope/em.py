"""Envelope model (EM): a separable reformulation of Owl.

The collapse needs only three assumptions:
  (a) in each year, every account earns the same return R_n (any sequence: historical,
      stochastic, glide paths are fine as long as all accounts hold the same mix that year);
  (b) no tax inside the taxable account (no dividends or interest taxed yearly, no LTCG on
      its growth);
  (c) the taxable, tax-free and HSA accounts are pooled as one liquid balance, which (a) and
      (b) make exact.
Inflation, scheduled bracket changes, indexed and unindexed thresholds, filing-status changes
and every per-year parameter are kept: they only change the per-year cost functions tau_n.

Under (a)-(c) a dollar is worth the same in every account up to taxes, so the only decision
that matters is x_n, the tax-deferred dollars recognized as ordinary income in year n
(withdrawals plus Roth conversions). Discounting with d_n = prod_{m<n} 1/R_m (nominal),

    maxSpending:  basis = (W - sum_n d_n tau_n(x_n) - nu L - d_N gamma_N B) / sum_n d_n xi_n gamma_n
    maxBequest:   bequest = (W - sum_n d_n tau_n(x_n) - nu L - sum_n d_n g_n) / (d_N gamma_N)

with L = D - sum_n d_n x_n the PV of tax-deferred money left to heirs. Both reduce to

    min  sum_n d_n [tau_n(x_n) - nu x_n]   s.t.  sum_n d_n x_n <= D,   x_n >= rmd_n,   liquidity

a separable resource-allocation problem with ONE scalar state (PV recognized so far), solved
exactly up to a grid by dynamic programming (solve_dp). Each year's cost is tabulated over a
grid of x (federal ordinary and LTCG tax, SS taxability, OBBBA senior deduction, NIIT, state
and local tax, IRMAA two years later, ACA), so the non-convex pieces are priced exactly,
including their marginal effect. RMDs are a constraint on the state. Cash liquidity (pooled
liquid balance never negative) is a floor on the state, iterated because it depends on
spending and taxes.

Exogenous series (SS, pensions, wages, contributions, QCDs, spending profile, fixed assets,
debts, brackets, state parameters, returns, inflation) are read from an Owl Plan after its own
setup, so the two models see the same inputs.
"""
import os
import time
from datetime import date
import numpy as np
from owlplanner import tax_federal as tx
from owlplanner import utils as u

THISYEAR = date.today().year


def _bracket_tax(ti, theta, delta):
    """ti: (G,), theta/delta: (T,) -> (G,) tax from filling brackets in order."""
    tops = np.cumsum(delta)
    bots = tops - delta
    fill = np.clip(ti[:, None] - bots[None, :], 0, delta[None, :])
    return fill @ theta


def inputs(p, opts=None):
    """Read everything the EM needs from a Plan that has been set up (solved once)."""
    opts = opts or {}
    N, Ni = p.N_n, p.N_i
    gam = np.array(p.gamma_n[: N + 1], dtype=float)
    inp = dict(N=N, Ni=Ni, n_d=min(p.n_d, N), i_d=p.i_d, nu=p.nu, objective=p.objective, gamma=gam)
    inp["xi"] = np.array(p.xi_n[:N], dtype=float)
    inp["ss"] = p.zetaBar_in.sum(axis=0)
    ord_in = p.omega_in + p.other_inc_in + p.netinv_in + p.piBar_in + p.spiaBar_in
    inp["ord"] = ord_in.sum(axis=0) + p.fixed_assets_ordinary_income_n
    inp["Q"] = np.array(p.fixed_assets_capital_gains_n, dtype=float)
    inp["I"] = p.netinv_in.sum(axis=0)
    inp["pension"] = p.piBar_in.sum(axis=0)
    inp["cash"] = (inp["ord"] + inp["ss"] + inp["Q"] + p.Lambda_in.sum(axis=0) + p.fixed_assets_tax_free_n
                   - p.debt_payments_n)
    kap = p.kappa_ijn[:, :, :N]
    # contributions arrive mid-year in Owl (grow by half a year's return); QCDs and SPIA
    # premiums leave the tax-deferred account at the start of the year
    inp["kap_def_c"] = kap[:, 1, :].sum(axis=0)
    inp["qcd"] = p.qcd_in.sum(axis=0)
    inp["kap_def_out"] = inp["qcd"] + p.spia_premiums_in.sum(axis=0)
    inp["kap_liq_c"] = kap[:, 0, :].sum(axis=0) + kap[:, 2, :].sum(axis=0) + kap[:, 3, :].sum(axis=0)
    beta = np.array(p.beta_ij, dtype=float)  # (Ni, Nj) initial balances
    inp["D0_i"] = beta[:, 1].copy()
    inp["L0"] = beta[:, [0, 2, 3]].sum()
    inp["rho_in"] = np.array(p.rho_in[:, :N], dtype=float)
    inp["debt_end"] = float(p.remaining_debt_balance)
    # Returns per account and year; the EM uses their balance-weighted mean and reports the spread.
    tau_ijn = np.sum(p.alpha_ijkn[:, :, :, :N] * np.asarray(p.tau_kn)[np.newaxis, np.newaxis, :, :N], axis=2)
    used = (beta > 0) | (kap.sum(axis=2) > 0)
    # an account exists in year n if it has an allocation (a deceased spouse's do not)
    live = used[:, :, np.newaxis] & (p.alpha_ijkn[:, :, :, :N].sum(axis=2) > 0.5)
    w = np.where(live, np.maximum(beta, 1.0)[:, :, np.newaxis], 0.0)
    inp["R"] = 1 + np.sum(w * tau_ijn, axis=(0, 1)) / np.maximum(w.sum(axis=(0, 1)), 1e-9)
    hi_ = np.where(live, tau_ijn, -np.inf).max(axis=(0, 1))
    lo_ = np.where(live, tau_ijn, np.inf).min(axis=(0, 1))
    inp["R_spread"] = float(np.max(hi_ - lo_))
    inp["mu"] = float(p.mu)
    # taxable account, for the taxable-account state: balance, basis, yearly taxed yield
    w0 = np.maximum(beta[:, 0], 0.0)
    wt = w0 / w0.sum() if w0.sum() > 0 else np.full(Ni, 1.0 / Ni)
    tau_k = np.asarray(p.tau_kn)[:, :N]
    fak_in = np.sum(np.maximum(0, tau_k[np.newaxis, 1:, :]) * p.alpha_ijkn[:, 0, 1:, :N], axis=1)
    inp["fak"] = wt @ fak_in                      # interest-like yield, taxed as ordinary income
    inp["alpha0"] = wt @ p.alpha_ijkn[:, 0, 0, :N]  # equity share (dividends, realized gains)
    inp["T0"] = float(w0.sum())
    basis = getattr(p, "taxable_basis_i", None)
    inp["K0"] = float(np.sum(basis)) if basis is not None and np.all(np.asarray(basis) > 0) else None
    tau0_prev = np.roll(tau_k[0], 1)
    inp["cgr_legacy"] = np.maximum(0.0, tau0_prev - p.mu)  # Owl's fallback without a cost basis
    inp["kap_tax_c"] = kap[:, 0, :].sum(axis=0)
    # 10% penalty on tax-deferred withdrawals: years in which no living holder is 59.5 yet
    holders = [i for i in range(Ni) if beta[i, 1] > 0 or kap[i, 1].sum() > 0] or list(range(Ni))
    pen = np.zeros(N, dtype=bool)
    for n in range(N):
        alive = [i for i in holders if n < p.horizons[i]] or [i for i in range(Ni) if n < p.horizons[i]]
        if Ni == 2 and n >= inp["n_d"]:
            alive = [1 - p.i_d]
        pen[n] = all(n < p.n595[i] for i in alive) if alive else False
    inp["penalized"] = pen
    # Roth conversion caps (nominal dollars per year, summed over the people allowed to convert),
    # as Owl bounds x_in: maxRothConversion per person, noRothConversions, start/stop years
    cap = u.get_monetary_option(opts, "maxRothConversion", 0) if "maxRothConversion" in opts else np.inf
    if cap < 0:
        cap = np.inf
    excl = opts.get("noRothConversions", "none")
    i_x = list(p.inames).index(excl) if excl not in ("none", "None", None) else -1
    n0 = max(int(u.get_numeric_option(opts, "startRothConversions", 0)) - THISYEAR, 0) if "startRothConversions" in opts else 0
    n1 = max(int(u.get_numeric_option(opts, "stopRothConversions", 0)) - THISYEAR, 0) if "stopRothConversions" in opts else N
    ccap = np.zeros(N)
    for i in range(Ni):
        if i == i_x:
            continue
        for n in range(min(p.horizons[i], N)):
            if n0 <= n < n1:
                ccap[n] += cap
    inp["conv_cap"] = ccap
    # federal: brackets and rates per year (nominal), standard deduction without the senior
    # bonus, and the count of bonus-eligible seniors (the bonus itself is not indexed)
    big = np.full(N, 1e15)
    s_inf = tx.taxParams(p.yobs, p.i_d, p.n_d, N, gam[:N], big, p.yOBBBA)[0]
    s_zero, theta, Delta = tx.taxParams(p.yobs, p.i_d, p.n_d, N, gam[:N], np.zeros(N), p.yOBBBA)
    inp["sigma0"] = s_inf
    inp["seniors"] = np.round((s_zero - s_inf) / 6000.0)
    inp["theta"], inp["Delta"] = theta, Delta * gam[np.newaxis, :N]
    status = np.full(N, Ni - 1)
    if Ni == 2:
        status[inp["n_d"]:] = 0
    inp["status"] = status
    # state / local
    inp["N_st"] = p.N_st
    if p.N_st:
        inp["st_theta"], inp["st_Delta"] = p.st_theta_tn, p.st_DeltaBar_tn
        inp["st_sigma"] = p.st_sigmaBar_n
        inp["st_tax_ss"] = np.asarray(p.st_tax_ss, dtype=bool) & np.ones(N, dtype=bool)
        inp["pe_adj"] = np.minimum(p.piBar_in, p.st_pe_cap_in).sum(axis=0)
        cap = np.where(np.isfinite(p.st_re_cap_in), p.st_re_cap_in, 1e9)
        inp["re_cap"] = cap.sum(axis=0)
        inp["re_pooled"] = np.asarray(getattr(p, "st_pe_pooled", False), dtype=bool) & np.ones(N, dtype=bool)
        inp["st_credit"] = p.st_credit_n
        inp["surch"] = getattr(p, "lt_surcharge_n", np.zeros(N))  # local tax: fork only
        inp["N_lt"] = getattr(p, "N_lt", 0)
        if inp["N_lt"]:
            inp["lt_theta"], inp["lt_Delta"] = p.lt_theta_tn, p.lt_DeltaBar_tn
    inp["medicare"] = str(opts.get("withMedicare", "loop")).lower() != "none"
    inp["aca"] = str(opts.get("withACA", "loop")).lower() != "none" and p.slcsp_annual > 0
    ssv = opts.get("withSSTaxability", "loop")
    inp["fixed_psi"] = float(ssv) if isinstance(ssv, (int, float)) else None
    # Medicare / ACA eligibility, for the vectorized versions of tx.mediCosts / tx.acaCosts
    inp["yobs"], inp["horizons"] = np.asarray(p.yobs), np.asarray(p.horizons)
    inp["prevMAGI"] = np.asarray(p.prevMAGI, dtype=float)
    inp["part_d"] = getattr(p, "_include_medicare_part_d", True)
    inp["part_d_base"] = getattr(p, "_medicare_part_d_base_annual_per_person", 0.0)
    inp["slcsp"] = float(p.slcsp_annual)
    inp["n_aca"] = max(0, p.aca_start_year - int(p.year_n[0])) if p.aca_start_year > 0 else 0
    return inp


def _set_returns(inp, r):
    """r=None: the plan's own per-year returns; a number: that return every year."""
    N = inp["N"]
    R = inp["R"] if r is None else np.full(N, 1.0 + r)
    d = np.concatenate([[1.0], np.cumprod(1.0 / R)])
    half = (1 + (R - 1) / 2) / R
    inp["kap_def"] = inp["kap_def_c"] * half - inp["kap_def_out"]
    inp["kap_liq"] = inp["kap_liq_c"] * half
    inp["d"] = d
    return d


def _medicare_row(inp, n, magi):
    """tx.mediCosts for year n, vectorized over the MAGI that sets its IRMAA."""
    gam, yobs, hor = inp["gamma"], inp["yobs"], inp["horizons"]
    Ni = len(yobs)
    fees_b = tx.partB_irmaa_fees
    fees_d = tx.partD_irmaa_fees if inp["part_d"] else np.zeros_like(fees_b)
    status = 0 if Ni == 1 else 1 if n < hor[0] and n < hor[1] else 0
    k = sum(1 for i in range(Ni) if THISYEAR + n - yobs[i] >= 65 and n < hor[i])
    if k == 0:
        return np.zeros_like(magi)
    base = gam[n] * fees_b[0] + (gam[n] * inp["part_d_base"] if inp["part_d"] else 0.0)
    tiers = np.zeros_like(magi)
    for q in range(1, 6):
        tiers = tiers + (magi > gam[n] * tx.irmaaBrackets[status][q]) * gam[n] * (fees_b[q] + fees_d[q])
    return k * (base + tiers)


def _medicare(inp, magi_prev):
    """Vectorized tx.mediCosts: magi_prev[n] is the MAGI that sets year n's IRMAA (row = year)."""
    return np.array([_medicare_row(inp, n, magi_prev[n]) for n in range(inp["N"])])


def _aca_row(inp, n, m):
    """tx.acaCosts (2026+ rules) for year n, vectorized over MAGI."""
    gam, yobs, hor = inp["gamma"], inp["yobs"], inp["horizons"]
    Ni = len(yobs)
    if n < inp["n_aca"]:
        return np.zeros_like(m)
    elig = [i for i in range(Ni) if THISYEAR + n - yobs[i] < 65 and n < hor[i]]
    if not elig:
        return np.zeros_like(m)
    cy = THISYEAR + n
    if cy < 2026:
        raise NotImplementedError("2025 ACA rules")
    fpl_max = max(tx._ACA_FPL.keys())
    hh = min(len(elig), 2)
    fpl = tx._ACA_FPL[cy if cy in tx._ACA_FPL else fpl_max][hh - 1] * gam[n]
    scale = tx.couple_to_individual_fraction(THISYEAR + n - yobs[elig[0]]) if (Ni == 2 and hh == 1) else 1.0
    slcsp = inp["slcsp"] * scale * gam[n]
    ratio = m / fpl
    bp, cp = tx._ACA_BREAKPOINTS_2026, tx._ACA_CONTRIB_PCT_2026
    ip = getattr(tx, "_ACA_CONTRIB_INITIAL_2026", cp)  # fork: 133-150% band starts at 3.14%
    idx = np.clip(np.searchsorted(bp, ratio, side="right") - 1, 0, len(bp) - 2)
    t = (ratio - bp[idx]) / (bp[idx + 1] - bp[idx])
    pct = ip[idx] + t * (cp[idx + 1] - ip[idx])
    pct = np.where(ratio < bp[0], cp[0], pct)
    cost = np.minimum(slcsp, pct * m)
    cost = np.where(ratio >= bp[-1], slcsp, cost)
    return np.where(m < 1.38 * fpl, slcsp, cost)


def _aca(inp, magi):
    return np.array([_aca_row(inp, n, magi[n]) for n in range(inp["N"])])


def row_cost(inp, n, xg, eo=0.0, eq=0.0, parts=None):
    """Cost, in year-n dollars, of recognizing xg in year n with extra ordinary income eo
    (taxable-account interest) and extra LTCG/qualified income eq (dividends, realized gains):
    that year's taxes and ACA plus the IRMAA two years later, discounted to year n."""
    N, d, gam = inp["N"], inp["d"], inp["gamma"]
    xg = np.asarray(xg, dtype=float)
    st = inp["status"][n]
    O = inp["ord"][n] + eo
    ss = inp["ss"][n]
    Q = inp["Q"][n] + eq
    lo, hi = tx.ssTaxabilityLo[st], tx.ssTaxabilityHi[st]  # not indexed
    pi = O + xg + Q + 0.5 * ss
    a50 = 0.5 * np.minimum(ss, np.minimum(hi - lo, np.maximum(0, pi - lo)))
    tss = np.where(pi < lo, 0, np.where(pi < hi, a50, np.minimum(a50 + 0.85 * np.maximum(0, pi - hi), 0.85 * ss)))
    if inp["fixed_psi"] is not None:
        tss = np.full_like(pi, inp["fixed_psi"] * ss)
    agi = O + xg + tss + Q
    sigma = inp["sigma0"][n]
    if THISYEAR + n <= tx.OBBBA_BONUS_EXPIRATION_YEAR and inp["seniors"][n] > 0:
        sigma = sigma + inp["seniors"][n] * np.maximum(0, 6000 - 0.06 * np.maximum(0, agi - tx.bonusThreshold[st]))
    Gt = np.maximum(0, O + xg + tss - sigma)
    shape = Gt.shape
    fed = _bracket_tax(Gt.ravel(), inp["theta"][:, n], inp["Delta"][:, n]).reshape(shape)
    T15, T20 = gam[n] * tx.capGainRates[st][0], gam[n] * tx.capGainRates[st][1]
    Qb = np.broadcast_to(Q, shape)
    q0 = np.minimum(Qb, np.maximum(0, T15 - Gt))
    q1 = np.minimum(Qb - q0, np.maximum(0, T20 - Gt) - q0)
    ltcg = 0.15 * q1 + 0.20 * (Qb - q0 - q1)
    thr = tx.niitThreshold[st]  # not indexed
    niit = np.where(agi > thr, tx.niitRate * np.minimum(agi - thr, inp["I"][n] + eo + Q), 0)
    state = 0
    if inp["N_st"]:
        st_agi = agi - (0 if inp["st_tax_ss"][n] else tss) - inp["pe_adj"][n]
        re = np.minimum(inp["re_cap"][n], xg + (inp["pension"][n] if inp["re_pooled"][n] else 0))
        st_ti = np.maximum(0, st_agi - inp["st_sigma"][n] - re)
        stt = _bracket_tax(st_ti.ravel(), inp["st_theta"][:, n], inp["st_Delta"][:, n]).reshape(shape)
        stt = (stt - np.minimum(inp["st_credit"][n], stt)) * (1 + inp["surch"][n])
        if inp.get("N_lt") and np.any(inp["lt_Delta"][:, n] > 0):
            stt = stt + _bracket_tax(st_ti.ravel(), inp["lt_theta"][:, n], inp["lt_Delta"][:, n]).reshape(shape)
        state = stt
    c = fed + ltcg + niit + state
    if parts is not None:
        for key, val in (("fed", fed), ("ltcg", ltcg), ("niit", niit), ("state", state), ("agi", agi), ("tss", tss)):
            parts.setdefault(key, {})[n] = val
    if inp["medicare"] and n + 2 < N:
        c = c + _medicare_row(inp, n + 2, agi) * (d[n + 2] / d[n])
    if inp["aca"]:
        c = c + _aca_row(inp, n, agi + (ss - tss))
    return c


def medicare_const(inp):
    """PV of the Medicare cost of years 0 and 1, set by prevMAGI."""
    if not inp["medicare"]:
        return 0.0
    d = inp["d"]
    v = _medicare_row(inp, 0, np.array([inp["prevMAGI"][0]]))[0]
    if inp["N"] > 1:
        v += _medicare_row(inp, 1, np.array([inp["prevMAGI"][1]]))[0] * d[1]
    return float(v)


def cost_table(inp, xg, parts=None, eo=None, eq=None):
    """C[n, k] = row_cost(n, X[n, k]) for every year, plus the constant Medicare PV."""
    N = inp["N"]
    X = np.broadcast_to(np.asarray(xg, dtype=float), (N, np.shape(xg)[-1]))
    eo = np.zeros(N) if eo is None else eo
    eq = np.zeros(N) if eq is None else eq
    C = np.array([row_cost(inp, n, X[n], eo[n], eq[n], parts) for n in range(N)])
    return C, medicare_const(inp)


def _taxable_extras(inp, t_after, draw, cgr, n=None):
    """Taxable-account income in year-n dollars, as Owl taxes it: interest-like yield on the
    balance after withdrawals (ordinary), dividends on its equity share and the gain on the
    equity share of withdrawals (qualified/LTCG)."""
    fak, a0 = (inp["fak"], inp["alpha0"]) if n is None else (inp["fak"][n], inp["alpha0"][n])
    eo = fak * t_after
    eq = inp["mu"] * a0 * t_after + cgr * a0 * np.maximum(draw, 0.0)  # draw < 0 is a deposit
    return eo, eq


def _gain_fraction(inp):
    """Equity gain fraction per year (Owl's _update_gain_fraction). With average-cost basis a
    withdrawal scales basis and balance alike, so K/b does not depend on the draws: it evolves as
    (K/b + taxed yield) / R. The path is computed with no draws; contributions (new basis) make
    it approximate."""
    N, R = inp["N"], inp["R"][:inp["N"]]
    if inp["K0"] is None:
        return inp["cgr_legacy"].copy()
    cgr = np.zeros(N)
    K, b = inp["K0"], inp["T0"]
    for n in range(N):
        a0, kc = inp["alpha0"][n], inp["kap_tax_c"][n]
        cgr[n] = min(1.0, max(0.0, (1 - K / b) / a0)) if (b > 0 and a0 > 0) else 0.0
        taxed = (inp["mu"] * a0 + inp["fak"][n]) * (b + 0.5 * kc)
        K = K + kc + max(0.0, taxed)
        b = b * R[n] + kc * (1 + (R[n] - 1) / 2)
    return cgr


def solve_dp(inp, r=None, h=None, netSpending=None, bequest=0.0, liquidity=True, fast=True,
             penalty=True, taxable=True, K_t=16, K_max=41, max_iter=30, tax_fixed=None):
    """Solution by dynamic programming over the PV recognized so far.

    The choice in year n is y_n = d_n x_n on a grid of step h (PV dollars), so the budget
    accounting is exact; each year's cost is the tax and premium bill at x_n = y_n / d_n.
    F_{n+1}(s + j) = min_j F_n(s) + d_n tau_n(j h / d_n) - nu j h, a min-plus convolution.
    r=None uses the plan's own per-year returns.

    Liquidity is a constraint inside the DP: the liquid pool after year n, in PV, is
    L0 + s h - (PV of spending net of fixed cash so far) - (F + nu s h), and F + nu s h is the
    PV of taxes paid so far. For a given state, the cheapest path is also the most liquid one,
    so the constraint keeps the DP exact for a given spending path (iterated for maxSpending).

    penalty: tax-deferred withdrawals that fund cash needs in years before 59.5 pay 10%; Roth
      conversions are locked for 5 years (Owl's maturation rule), so cash in those years can
      only come from the liquid pool, matured conversions and penalized withdrawals. The
      penalized withdrawals are found by simulating the cash plan and iterated to a fixed point.
    taxable: the taxable account is a second DP state (its PV balance on K_t levels), with the
      yearly draw as a second decision; its interest, dividends and realized gains enter each
      year's tax. Draws cannot exceed the year's cash need, and the taxable balance cannot exceed
      the liquid pool (Roth >= 0). Solved coarse in 2-D, then the recognition schedule is refined
      in 1-D with the taxable path fixed.
    """
    t0 = time.time()
    d = _set_returns(inp, r)
    N, nu = inp["N"], inp["nu"]
    budget = inp["D0_i"].sum() + float(np.sum(d[:N] * inp["kap_def"]))
    if h is None:
        h = max(250.0, 500.0 * np.ceil(budget / 2000 / 500.0)) if budget > 0 else 500.0
    B = int(np.floor(budget / h + 1e-9))
    J = np.arange(B + 1)
    X = (J[None, :] * h) / d[:N, None]  # year-n dollars for each PV step
    const = medicare_const(inp)
    avail = inp["D0_i"].sum() + np.concatenate([[0.0], np.cumsum(d[:N] * inp["kap_def"])])
    share = inp["D0_i"] / max(inp["D0_i"].sum(), 1e-9)
    rho_n = np.zeros(N)
    for n in range(N):
        rho = inp["rho_in"][:, n]
        if inp["Ni"] == 2 and n >= inp["n_d"]:
            rho_n[n] = rho[1 - inp["i_d"]] if rho[1 - inp["i_d"]] > 0 else rho.max()
        else:
            rho_n[n] = float(np.dot(share, rho))
    caps = np.array([min(B, int(np.floor(avail[n + 1] / h + 1e-9))) for n in range(N)])
    L0 = inp["L0"]
    tol = 1e-6

    def jmin_of(n, states, wmin):
        # RMD (a QCD counts toward it) and the withdrawal the cash plan needs this year
        req = rho_n[n] * np.maximum(0.0, avail[n] - states * h) - d[n] * inp["qcd"][n]
        jm = np.where(req > 0, np.ceil(req / h - 1e-9), 0).astype(np.int64)
        return np.maximum(jm, wmin[n])

    def req_pv(n, states):
        # RMD still to be withdrawn in year n (PV); it cannot be converted, so it is cash
        return np.maximum(0.0, rho_n[n] * np.maximum(0.0, avail[n] - states * h) - d[n] * inp["qcd"][n])

    cap_pv = d[:N] * inp["conv_cap"]

    def cash_floor(n, sp, y_pv):
        # recognized dollars that cannot go to the Roth (RMD, or beyond the conversion cap) are
        # cash; together with fixed cash they must fund the year's need or be deposited
        return np.maximum(req_pv(n, sp), y_pv - cap_pv[n])

    def draw_ok(dlim, n, sp, jc):
        # net taxable draw <= cash need - RMD: the Roth takes only conversions, so cash beyond
        # the need (an RMD, a windfall) must go to the taxable account
        if dlim is None:
            return True
        Cf, Gd_, dpv = dlim
        return (Gd_[n] + d[n] * Cf[n][jc] - cash_floor(n, sp[:, None], jc * h)) >= dpv[n] - tol

    def liquid_after(n, states, Fnew, G):
        # PV of the liquid pool at the end of year n
        return L0 + states * h * (1 - nu) - G[n] - Fnew

    def dp_window(cost, wmin, lo, hi, G, floor, dcap):
        prev_lo, F = 0, np.zeros(1)
        args = []
        for n in range(N):
            sp = prev_lo + np.arange(len(F))
            tt = np.arange(lo[n], hi[n] + 1)
            j = tt[None, :] - sp[:, None]
            jc = np.clip(j, 0, B)
            ok = (j >= jmin_of(n, sp, wmin)[:, None]) & (tt[None, :] <= caps[n]) & draw_ok(dcap, n, sp, jc)
            T = np.where(ok, F[:, None] + cost[n, jc], np.inf)
            if liquidity:
                T = np.where(liquid_after(n, tt[None, :], T, G) >= floor[n] - tol, T, np.inf)
            k = np.argmin(T, axis=0)
            F = T[k, np.arange(len(tt))]
            args.append(sp[k])
            prev_lo = lo[n]
        if not np.isfinite(F).any():
            return None
        t_cur = lo[N - 1] + int(np.argmin(F))
        jn = np.zeros(N, dtype=np.int64)
        for n in range(N - 1, -1, -1):
            s_prev = args[n][t_cur - lo[n]]
            jn[n] = t_cur - s_prev
            t_cur = s_prev
        return jn

    def dp_1d(cost, wmin, G, floor, dcap, path=None):
        """Coarse pass over all states (unless a starting path is given), then the exact DP in a
        band around it, widened whenever the optimum touches its edge (fast=False: full band)."""
        ratio = max(1, B // 200) if fast else 1
        if ratio == 1:
            jn = dp_window(cost, wmin, np.zeros(N, dtype=np.int64), np.full(N, B, dtype=np.int64), G, floor, dcap)
            if jn is None:
                raise RuntimeError("EM infeasible")
            return jn
        def coarse():
            Sc = np.arange(0, B + 1, ratio)
            F, prev_states, args = np.zeros(1), np.array([0]), []
            for n in range(N):
                j = Sc[None, :] - prev_states[:, None]
                jc = np.clip(j, 0, B)
                ok = (j >= jmin_of(n, prev_states, wmin)[:, None]) & (Sc[None, :] <= caps[n]) & draw_ok(dcap, n, prev_states, jc)
                T = np.where(ok, F[:, None] + cost[n, jc], np.inf)
                if liquidity:
                    # one coarse step of slack, so the coarse grid does not miss a narrow feasible set
                    T = np.where(liquid_after(n, Sc[None, :], T, G) >= floor[n] - ratio * h, T, np.inf)
                k = np.argmin(T, axis=0)
                F = T[k, np.arange(len(Sc))]
                args.append(prev_states[k])
                prev_states = Sc
            if not np.isfinite(F).any():
                return None
            t_cur = int(Sc[np.argmin(F)])
            p_ = np.zeros(N, dtype=np.int64)
            for n in range(N - 1, -1, -1):
                p_[n] = t_cur
                t_cur = int(args[n][np.searchsorted(Sc, t_cur)])
            return p_

        given = path is not None
        if not given:
            path = coarse()
        W = 4 * ratio
        if path is None:  # infeasible even with slack on the coarse grid
            raise RuntimeError("EM infeasible")
        while True:
            lo, hi = np.maximum(0, path - W), np.minimum(B, path + W)
            jn = dp_window(cost, wmin, lo, hi, G, floor, dcap)
            if jn is None:
                if given:  # the hint does not fit these constraints: start over from the coarse pass
                    given, path, W = False, coarse(), 4 * ratio
                    if path is None:
                        raise RuntimeError("EM infeasible")
                    continue
                if W >= B:
                    raise RuntimeError("EM infeasible")
                W = B if W >= 16 * ratio else 2 * W
                continue
            fp = np.cumsum(jn)
            touch = ((fp == lo) & (lo > 0)) | ((fp == hi) & (hi < B))
            if not touch.any() or W >= B:
                return jn  # touching a binding floor also counts as touching: stop widening at 16 steps
            path, W = fp, W * 2

    # ---- taxable account as a second state -------------------------------------------------
    Rn = d[:N] / d[1:N + 1]
    kt_pv = d[:N] * inp["kap_tax_c"] * (1 + (Rn - 1) / 2) / Rn  # PV of a mid-year contribution
    K_t0 = K_t

    def grid(Tmax):
        """Levels of the taxable state on [0, Tmax], with the starting balance on a level."""
        use = taxable and Tmax > 0
        step = Tmax / (K_t0 - 1) if use else 1.0
        if use and inp["T0"] > 0:  # resolution set by the starting balance, at most K_max levels
            step = max(min(step, inp["T0"] / (K_t0 - 1)), Tmax / (K_max - 1))
        K = K_t0
        if use and inp["T0"] > 0:
            step = inp["T0"] / max(1, round(inp["T0"] / step))
            K = int(np.ceil(Tmax / step - 1e-9)) + 1
        return use, step, K

    # top of the grid before spending is known: start balance, contributions, cash windfalls
    # (fixed cash well above the plan's typical year, e.g. a house sale); reset after pass 0
    windfall = np.maximum(0.0, inp["cash"] - np.median(inp["cash"]))
    use_tax, ht, K_t = grid(inp["T0"] + kt_pv.sum() + float(np.sum(d[:N] * windfall)))
    levels = np.arange(K_t)
    cgr = _gain_fraction(inp)

    def dp_2d(wmin, G, Gd, liq=True):
        """Coarse 2-D DP over (PV recognized, PV taxable balance). Returns the taxable path
        (levels at the start of each year and at the end) and the coarse recognition path."""
        ratio = max(1, B // 100)
        Sc = np.arange(0, B + 1, ratio)
        nS = len(Sc)
        t_start = int(round(inp["T0"] / ht))
        F = np.full((nS, K_t), np.inf)
        F[0, t_start] = 0.0
        back = []
        jdiff = np.arange(nS)[None, :] - np.arange(nS)[:, None]   # coarse steps, (prev, next)
        jdc = np.clip(jdiff, 0, nS - 1)
        for n in range(N):
            kt = kt_pv[n] / ht
            Fn = np.full((nS, K_t), np.inf)
            bs = np.zeros((nS, K_t), dtype=np.int64)
            bt = np.zeros((nS, K_t), dtype=np.int64)
            okj0 = (jdiff >= 0) & (jdiff * ratio >= jmin_of(n, Sc, wmin)[:, None]) & (Sc[None, :] <= caps[n])
            xx = (Sc * h) / d[n]
            for t in np.flatnonzero(np.isfinite(F).any(axis=0)):
                draw_pv = (t + kt - levels) * ht                              # net draw; < 0 is a deposit
                tps = levels
                dr = draw_pv / d[n]                                           # nominal
                ta = np.maximum((t * ht) / d[n] - dr + 0.5 * inp["kap_tax_c"][n], 0.0)
                eo, eq = _taxable_extras(inp, ta, dr, cgr[n], n)
                Cn = row_cost(inp, n, xx[:, None], eo[None, :], eq[None, :])  # (nS, ntp)
                cm = d[n] * Cn - nu * (Sc * h)[:, None]
                Ft = F[:, t]
                sp = np.flatnonzero(np.isfinite(Ft))
                ok = okj0[sp]
                T = np.where(ok[:, :, None], Ft[sp][:, None, None] + cm[jdc[sp]], np.inf)  # (sp, nS, ntp)
                # net draw <= cash need - RMD (see draw_ok); a negative need must be deposited
                need = Gd[n] + d[n] * Cn[jdc[sp]] - cash_floor(n, Sc[sp][:, None], jdiff[sp] * ratio * h)[:, :, None]
                # one level of slack both ways (draw limit, Roth >= 0), so rounding to levels
                # cannot accumulate over years of forced deposits
                T = np.where(need >= draw_pv[None, None, :] - ht, T, np.inf)
                if liquidity and liq:
                    lq = liquid_after(n, Sc[None, :, None], T, G)
                    T = np.where(lq >= (tps[None, None, :] - 1) * ht, T, np.inf)   # Roth >= 0, one level of slack
                k = np.argmin(T, axis=0)                                       # (nS, ntp)
                v = np.take_along_axis(T, k[None], axis=0)[0]
                cur = Fn[:, tps]
                better = v < cur
                cur = np.where(better, v, cur)
                Fn[:, tps] = cur
                bsub, btsub = bs[:, tps], bt[:, tps]
                bs[:, tps] = np.where(better, sp[k], bsub)
                bt[:, tps] = np.where(better, t, btsub)
            F = Fn
            back.append((bs, bt))
            if os.environ.get("EM_DEBUG") and not np.isfinite(F).any():
                print("   dp_2d infeasible in year", n, "K_t", K_t, "ht", round(ht), flush=True)
                return None, None
        if not np.isfinite(F).any():
            return None, None
        si, ti = np.unravel_index(int(np.argmin(F)), F.shape)
        tpath = np.zeros(N + 1, dtype=np.int64)
        spath = np.zeros(N, dtype=np.int64)
        tpath[N] = ti
        for n in range(N - 1, -1, -1):
            spath[n] = Sc[si]
            bs, bt = back[n]
            si, ti = bs[si, ti], bt[si, ti]
            tpath[n] = ti
        return tpath, spath


    def dp_t(jn, G, Gd, t_hint):
        """Taxable path on a fine grid for a fixed recognition schedule: a 1-D DP over the
        taxable balance with the same constraints (net draw <= need, balance <= liquid pool),
        within +-2 coarse levels of the hint. Returns the path in PV dollars, or None."""
        y = jn * h
        x = y / d[:N]
        cumy = np.cumsum(y)
        band = None  # all levels: K_f^2 pairs per year is cheap
        t0f = int(round(inp["T0"] / htf))
        F = np.full(K_f, np.inf)
        F[t0f] = 0.0
        back = []
        for n in range(N):
            kt = kt_pv[n] / htf
            cur = np.flatnonzero(np.isfinite(F))
            if len(cur) == 0:
                return None
            nxt = lev_f if band is None else lev_f[np.abs(lev_f * htf - t_hint[n + 1]) <= band]
            draw_pv = (cur[:, None] + kt - nxt[None, :]) * htf
            dr = draw_pv / d[n]
            ta = np.maximum((cur[:, None] * htf) / d[n] - dr + 0.5 * inp["kap_tax_c"][n], 0.0)
            eo_, eq_ = _taxable_extras(inp, ta, dr, cgr[n], n)
            Cn = row_cost(inp, n, np.full(ta.shape, x[n]), eo_, eq_)
            T = F[cur][:, None] + d[n] * Cn
            ok = (Gd[n] + d[n] * Cn - cash_floor(n, np.array([(cumy[n] - y[n]) / h]), y[n])[0]) >= draw_pv - htf
            if liquidity:
                ok &= (L0 + cumy[n] - G[n] - T) >= (nxt[None, :] - 1) * htf
            T = np.where(ok, T, np.inf)
            k = np.argmin(T, axis=0)
            Fn = np.full(K_f, np.inf)
            Fn[nxt] = T[k, np.arange(len(nxt))]
            bk = np.zeros(K_f, dtype=np.int64)
            bk[nxt] = cur[k]
            back.append(bk)
            F = Fn
        if not np.isfinite(F).any():
            return None
        tf = np.zeros(N + 1, dtype=np.int64)
        tf[N] = int(np.argmin(F))
        for n in range(N - 1, -1, -1):
            tf[n] = back[n][tf[n + 1]]
        return tf * htf

    # ---- outer fixed point: spending (maxSpending) and penalized withdrawals --------------
    wmin = np.zeros(N, dtype=np.int64)
    pen = np.zeros(N)
    prof = inp["xi"] * inp["gamma"][:N]
    if inp["objective"] == "maxSpending":
        g = 0.0 * prof
    else:
        g = netSpending / inp["xi"][0] * prof
    eo, eq = np.zeros(N), np.zeros(N)
    draw = np.zeros(N)
    t_before = np.zeros(N)
    t_table = 0.0
    best = None
    tp = None
    hist = []
    stable = False
    for it in range(max_iter):
        Gd = d[:N] * (g - inp["cash"] + pen)       # PV cash need per year, before taxes
        G = np.cumsum(Gd - d[:N] * inp["kap_liq"])  # liquid pool: contributions come from outside
        floor = np.zeros(N)
        spath = None
        if tax_fixed is not None:  # a given taxable path (diagnostics): start balances, draws, eo, eq
            t_before, draw, eo, eq = tax_fixed
            floor = np.append(d[1:N] * t_before[1:], 0.0)
        else:
            # pass 0 leaves the taxable account untaxed (an upper estimate of spending); pass 1
            # runs the coarse 2-D DP; later passes refine the previous taxable path
            spath = None
            if it == 1 and taxable:
                # cash that must be deposited: fixed cash and RMDs beyond spending and taxes,
                # along pass 0's plan
                y0 = d[:N] * x
                rmd0 = np.array([req_pv(n, np.array([(np.cumsum(y0)[n] - y0[n]) / h]))[0] for n in range(N)])
                surplus = np.maximum(0.0, d[:N] * (inp["cash"] - v["g"] - tau) + np.maximum(rmd0, y0 - cap_pv))
                use_tax, ht, K_t = grid(inp["T0"] + kt_pv.sum() + float(surplus.sum()))
                levels = np.arange(K_t)
            K_f = 4 * (K_t - 1) + 1
            htf = ht / 4
            lev_f = np.arange(K_f)
            if use_tax and (it == 1 or (it > 1 and tp is None)):
                tpath, spath = dp_2d(wmin, G, Gd)
                if tpath is None and inp["objective"] == "maxSpending":
                    # spending too high to stay liquid once the taxable account is taxed
                    g = 0.97 * g
                    continue
                if tpath is None:  # coarse grid too tight for the liquidity floor: drop it here
                    tpath, spath = dp_2d(wmin, G, Gd, liq=False)
                tp = (tpath if tpath is not None else np.zeros(N + 1, dtype=np.int64)) * ht
        tax_now = use_tax and tax_fixed is None and tp is not None
        if use_tax and tax_fixed is None and tp is None:
            eo, eq, draw, floor = np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N)
        best_in = None
        for sweep in range(6 if tax_now else 1):
            if tax_now:
                t_before = tp[:N] / d[:N]
                draw = (tp[:N] + kt_pv - tp[1:]) / d[:N]
                eo, eq = _taxable_extras(inp, np.maximum(t_before - draw + 0.5 * inp["kap_tax_c"], 0.0), draw, cgr)
                floor = tp[1:]
            tt0 = time.time()
            C = np.array([row_cost(inp, n, X[n], eo[n], eq[n]) for n in range(N)])
            t_table += time.time() - tt0
            cost = d[:N, None] * C - nu * J[None, :] * h
            # the draw limit is enforced where the taxable path is chosen (dp_2d, dp_t); imposing
            # it again here with the path fixed lets the DP meet it by raising taxes
            dcap = (C, Gd, d[:N] * draw) if tax_fixed is not None else None
            if (it == 0 and inp["objective"] == "maxSpending"):
                # the first pass relaxes the draw limit, so spending is iterated down from an upper
                # estimate: from below, a low spending guess makes the draw limit tight and the
                # iteration stops at the lowest fixed point
                dcap = None
            try:
                jn = dp_1d(cost, wmin, G, floor, dcap, path=spath)
            except RuntimeError:
                try:
                    jn = dp_1d(cost, wmin, G, np.zeros(N), None, path=None)
                except RuntimeError:
                    jn = None
            if jn is None:
                break
            cand = (float(np.sum(cost[np.arange(N), jn])), jn, C[np.arange(N), jn], eo, eq, draw, t_before)
            tf = None
            if tax_now:
                # the taxable path for this schedule on the fine grid, which re-imposes the draw
                # limit and the liquidity floor; the pair (schedule, path) is the candidate
                tf = dp_t(jn, G, Gd, tp)
                if tf is not None:
                    tb2 = tf[:N] / d[:N]
                    dr2 = (tf[:N] + kt_pv - tf[1:]) / d[:N]
                    eo2, eq2 = _taxable_extras(inp, np.maximum(tb2 - dr2 + 0.5 * inp["kap_tax_c"], 0.0), dr2, cgr)
                    x2 = X[np.arange(N), jn]
                    Cx2 = np.array([row_cost(inp, n, np.array([x2[n]]), eo2[n], eq2[n])[0] for n in range(N)])
                    cand = (float(np.sum(d[:N] * Cx2 - nu * jn * h)), jn, Cx2, eo2, eq2, dr2, tb2)
            obj = cand[0]
            if os.environ.get("EM_DEBUG"):
                print("   sweep", sweep, round(obj), "dp_t", tf is not None, flush=True)
            if best_in is not None and obj >= best_in[0] - 1e-6 * abs(best_in[0]) - 1:
                break
            best_in = cand
            if not tax_now or tf is None:
                break
            tp, spath = tf, np.cumsum(jn)
        if best_in is None:
            # spending too high to stay liquid (the upper estimate of pass 0): lower it and retry
            if inp["objective"] != "maxSpending" or it == max_iter - 1:
                raise RuntimeError("EM infeasible")
            g = 0.97 * g
            continue
        _, jn, Cx, eo, eq, draw, t_before = best_in
        x = X[np.arange(N), jn]
        tau = Cx + pen
        v = _value(inp, x, tau, const, budget, netSpending, bequest)
        # cash plan: penalized withdrawals before 59.5, 5-year lock on conversions
        need = d[:N] * (v["g"] + Cx - inp["cash"] - inp["kap_liq"])
        new_pen, new_w = np.zeros(N), np.zeros(N)
        if penalty:
            S, conv = L0, np.zeros(N)
            for n in range(N):
                if n >= 5:
                    S += conv[n - 5]
                y = d[n] * x[n]
                if inp["penalized"][n]:
                    short = need[n] - S
                    if short > 0:
                        new_w[n] = short / 0.9
                        new_pen[n] = 0.1 * new_w[n] / d[n]
                        S = 0.0
                    else:
                        S -= need[n]
                    conv[n] = max(0.0, y - new_w[n])
                else:
                    S += y - need[n]  # recognized dollars are spendable (withdrawal or conversion)
        new_wmin = np.where(new_w > 0, np.ceil(new_w / h - 1e-9), 0).astype(np.int64)
        # the iterate is consistent if the penalties it charged are the ones its cash plan needs
        consistent = bool(np.all(new_pen <= pen + 1.0) and np.all(jn >= new_wmin))
        hist.append(v["value"])
        spend = inp["objective"] == "maxSpending"
        # spending iterates are ranked by how close they are to their own fixed point (a plan
        # solved for spending g that funds spending V is exact only when V = g); bequest
        # iterates (spending given) by value. Pass 0 has no taxable state and is not a candidate.
        gap = abs(v["value"] - g[0] / prof[0]) / abs(v["value"]) if spend else 0.0
        score = -gap if spend else v["value"]
        real = not (taxable and tax_fixed is None and it == 0)
        if consistent and real and (best is None or score > best[0]):
            best = (score, x.copy(), tau.copy(), pen.copy(), draw.copy(), t_before.copy(), (eo + eq).sum(), gap)
        if os.environ.get("EM_DEBUG"):
            print(it, round(v["value"]), "consistent", consistent, "wmin", int(np.abs(new_wmin - wmin).max()),
                  "pen", round(float(np.abs(new_pen - pen).max())), "g", round(float(np.abs(v["g"] - g).max())), flush=True)
        stable = (it >= (1 if taxable and tax_fixed is None else 0) and np.array_equal(new_wmin, wmin) and np.allclose(new_pen, pen, atol=1.0)
                  and np.allclose(v["g"], g, rtol=2e-4, atol=1.0))
        if stable:
            break
        # spending: damped after the first taxable pass, since liquidity and the draw limit pull
        # the value in opposite directions and the plain iteration cycles
        damp = 0.5 if (spend and it >= 2) else 1.0
        wmin, pen, g = new_wmin, new_pen, g + damp * (v["g"] - g)
    fp_gap = 0.0
    if best is not None and not stable:
        _, x, tau, pen, draw, t_before, drag, fp_gap = best
    else:
        drag = (eo + eq).sum()
    out = _value(inp, x, tau, const, budget, netSpending, bequest)
    # how far the final plan's taxable draws exceed the year's cash need net of the RMD (the
    # refinement does not re-impose that limit): the excess would have to stay in the account
    y_ = d[:N] * x
    s_prev = np.concatenate([[0.0], np.cumsum(y_)[:-1]]) / h
    rmd_ = np.array([req_pv(n, np.array([s_prev[n]]))[0] for n in range(N)]) / d[:N]
    rmd_ = np.maximum(rmd_, x - inp["conv_cap"])
    excess = np.maximum(0.0, draw - (out["g"] + tau - inp["cash"] - rmd_)) if use_tax else np.zeros(N)
    out.update(draw_excess=float(np.sum(d[:N] * excess)), draw_excess_max=float(np.max(d[:N] * excess)))  # PV
    out.update(iters=it + 1, converged=bool(stable), t_table=t_table, t_total=time.time() - t0, grid=B + 1, h=h,
               penalty_total=float(pen.sum()), taxable_draw=draw, taxable_before=t_before, drag_income=float(drag),
               history=hist, fp_gap=fp_gap)
    return out


def _value(inp, x, tau, const, budget, netSpending, bequest):
    N, nu, d, gam = inp["N"], inp["nu"], inp["d"], inp["gamma"]
    phi = float(np.sum(d[:N] * tau)) + const  # PV of all taxes and premiums
    W = inp["L0"] + float(np.sum(d[:N] * (inp["cash"] + inp["kap_liq"]))) + budget
    leftover = budget - float(np.sum(d[:N] * x))
    prof = inp["xi"] * gam[:N]
    if inp["objective"] == "maxSpending":
        val = (W - phi - nu * leftover - d[N] * (bequest * gam[N] + inp["debt_end"])) / float(np.sum(d[:N] * prof))
        g = val * prof
    else:
        g = netSpending / inp["xi"][0] * prof
        val = ((W - phi - nu * leftover - float(np.sum(d[:N] * g))) / d[N] - inp["debt_end"]) / gam[N]
    # liquidity check: liquid balance at the start of each year after its flows
    liq = inp["L0"] + np.cumsum(d[:N] * (inp["cash"] + inp["kap_liq"] + x - g - tau))
    return dict(value=val, g=g, x=x, tau=tau, liq_min=float(np.min(liq / d[:N])), leftover=leftover)


def evaluate(inp, r, x, netSpending=None, bequest=0.0, eo=None, eq=None, pen=None):
    """EM accounting of a given recognition schedule x (e.g. the full model's own), optionally
    with given taxable-account income (eo ordinary, eq qualified) and early-withdrawal penalties."""
    d = _set_returns(inp, r)
    N = inp["N"]
    budget = inp["D0_i"].sum() + float(np.sum(d[:N] * inp["kap_def"]))
    x = np.asarray(x, dtype=float)
    eo = np.zeros(N) if eo is None else np.asarray(eo, dtype=float)
    eq = np.zeros(N) if eq is None else np.asarray(eq, dtype=float)
    tau = np.array([row_cost(inp, n, np.array([x[n]]), eo[n], eq[n])[0] for n in range(N)])
    if pen is not None:
        tau = tau + np.asarray(pen, dtype=float)
    return _value(inp, x, tau, medicare_const(inp), budget, netSpending, bequest)


def owl_extras(p):
    """Taxable-account income and penalties exactly as the full model booked them."""
    N = p.N_n
    fak_in = np.sum(np.maximum(0, p.tau_kn[1:, :N]) * p.alpha_ijkn[:, 0, 1:, :N], axis=1)
    base = p.b_ijn[:, 0, :N] - p.w_ijn[:, 0, :] + p.d_in[:, :N] + 0.5 * p.kappa_ijn[:, 0, :N]
    eo = np.sum(fak_in * base, axis=0)
    eq = np.asarray(p.Q_n) - np.asarray(p.fixed_assets_capital_gains_n)
    return eo, eq, np.asarray(p.P_n, dtype=float)
