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
import time
from datetime import date
import numpy as np
from owlplanner import tax_federal as tx

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
        inp["re_pooled"] = np.asarray(p.st_pe_pooled, dtype=bool) & np.ones(N, dtype=bool)
        inp["st_credit"] = p.st_credit_n
        inp["surch"] = p.lt_surcharge_n
        inp["N_lt"] = getattr(p, "N_lt", 0)
        if inp["N_lt"]:
            inp["lt_theta"], inp["lt_Delta"] = p.lt_theta_tn, p.lt_DeltaBar_tn
    inp["medicare"] = opts.get("withMedicare", "loop") != "none"
    inp["aca"] = opts.get("withACA", "loop") != "none" and p.slcsp_annual > 0
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


def _medicare(inp, magi_prev):
    """Vectorized tx.mediCosts: magi_prev[n] is the MAGI that sets year n's IRMAA (row = year)."""
    N, gam = inp["N"], inp["gamma"]
    yobs, hor = inp["yobs"], inp["horizons"]
    Ni = len(yobs)
    fees_b = tx.partB_irmaa_fees
    fees_d = tx.partD_irmaa_fees if inp["part_d"] else np.zeros_like(fees_b)
    out = np.zeros_like(magi_prev)
    for n in range(N):
        status = 0 if Ni == 1 else 1 if n < hor[0] and n < hor[1] else 0
        k = sum(1 for i in range(Ni) if THISYEAR + n - yobs[i] >= 65 and n < hor[i])
        if k == 0:
            continue
        base = gam[n] * fees_b[0] + (gam[n] * inp["part_d_base"] if inp["part_d"] else 0.0)
        tiers = np.zeros_like(magi_prev[n])
        for q in range(1, 6):
            tiers += (magi_prev[n] > gam[n] * tx.irmaaBrackets[status][q]) * gam[n] * (fees_b[q] + fees_d[q])
        out[n] = k * (base + tiers)
    return out


def _aca(inp, magi):
    """Vectorized tx.acaCosts (2026+ rules), rows = years."""
    N, gam = inp["N"], inp["gamma"]
    yobs, hor = inp["yobs"], inp["horizons"]
    Ni = len(yobs)
    out = np.zeros_like(magi)
    fpl_max = max(tx._ACA_FPL.keys())
    for n in range(inp["n_aca"], N):
        elig = [i for i in range(Ni) if THISYEAR + n - yobs[i] < 65 and n < hor[i]]
        if not elig:
            continue
        cy = THISYEAR + n
        if cy < 2026:
            raise NotImplementedError("2025 ACA rules")
        hh = min(len(elig), 2)
        fpl = tx._ACA_FPL[cy if cy in tx._ACA_FPL else fpl_max][hh - 1] * gam[n]
        scale = tx.couple_to_individual_fraction(THISYEAR + n - yobs[elig[0]]) if (Ni == 2 and hh == 1) else 1.0
        slcsp = inp["slcsp"] * scale * gam[n]
        m = magi[n]
        ratio = m / fpl
        bp, cp, ip = tx._ACA_BREAKPOINTS_2026, tx._ACA_CONTRIB_PCT_2026, tx._ACA_CONTRIB_INITIAL_2026
        idx = np.clip(np.searchsorted(bp, ratio, side="right") - 1, 0, len(bp) - 2)
        t = (ratio - bp[idx]) / (bp[idx + 1] - bp[idx])
        pct = ip[idx] + t * (cp[idx + 1] - ip[idx])
        pct = np.where(ratio < bp[0], cp[0], pct)
        cost = np.minimum(slcsp, pct * m)
        cost = np.where(ratio >= bp[-1], slcsp, cost)
        out[n] = np.where(m < 1.38 * fpl, slcsp, cost)
    return out


def cost_table(inp, xg, parts=None):
    """C[n, k] = cost, in year-n dollars, of recognizing X[n, k] in year n: that year's taxes
    and ACA plus the IRMAA two years later (discounted to year n). Also returns the constant
    Medicare cost of years 0 and 1 (set by prevMAGI), in PV."""
    N = inp["N"]
    d = inp["d"]
    gam = inp["gamma"]
    X = np.broadcast_to(np.asarray(xg, dtype=float), (N, np.shape(xg)[-1]))
    G = X.shape[1]
    C = np.zeros((N, G))
    AGI = np.zeros((N, G))
    MAGI_aca = np.zeros((N, G))
    for n in range(N):
        st = inp["status"][n]
        O, ss, Q = inp["ord"][n], inp["ss"][n], inp["Q"][n]
        xg = X[n]
        lo, hi = tx.ssTaxabilityLo[st], tx.ssTaxabilityHi[st]  # not indexed
        pi = O + xg + Q + 0.5 * ss
        a50 = 0.5 * np.minimum(ss, np.minimum(hi - lo, np.maximum(0, pi - lo)))
        tss = np.where(pi < lo, 0, np.where(pi < hi, a50, np.minimum(a50 + 0.85 * np.maximum(0, pi - hi), 0.85 * ss)))
        if inp["fixed_psi"] is not None:
            tss = np.full_like(xg, inp["fixed_psi"] * ss)
        agi = O + xg + tss + Q
        AGI[n], MAGI_aca[n] = agi, agi + (ss - tss)
        sigma = inp["sigma0"][n]
        if THISYEAR + n <= tx.OBBBA_BONUS_EXPIRATION_YEAR and inp["seniors"][n] > 0:
            sigma = sigma + inp["seniors"][n] * np.maximum(0, 6000 - 0.06 * np.maximum(0, agi - tx.bonusThreshold[st]))
        Gt = np.maximum(0, O + xg + tss - sigma)
        fed = _bracket_tax(Gt, inp["theta"][:, n], inp["Delta"][:, n])
        T15, T20 = gam[n] * tx.capGainRates[st][0], gam[n] * tx.capGainRates[st][1]
        q0 = np.minimum(Q, np.maximum(0, T15 - Gt))
        q1 = np.minimum(Q - q0, np.maximum(0, T20 - Gt) - q0)
        ltcg = 0.15 * q1 + 0.20 * (Q - q0 - q1)
        thr = tx.niitThreshold[st]  # not indexed
        niit = np.where(agi > thr, tx.niitRate * np.minimum(agi - thr, inp["I"][n] + Q), 0)
        state = 0
        if inp["N_st"]:
            st_agi = agi - (0 if inp["st_tax_ss"][n] else tss) - inp["pe_adj"][n]
            re = np.minimum(inp["re_cap"][n], xg + (inp["pension"][n] if inp["re_pooled"][n] else 0))
            st_ti = np.maximum(0, st_agi - inp["st_sigma"][n] - re)
            stt = _bracket_tax(st_ti, inp["st_theta"][:, n], inp["st_Delta"][:, n])
            stt = (stt - np.minimum(inp["st_credit"][n], stt)) * (1 + inp["surch"][n])
            if inp.get("N_lt") and np.any(inp["lt_Delta"][:, n] > 0):
                stt = stt + _bracket_tax(st_ti, inp["lt_theta"][:, n], inp["lt_Delta"][:, n])
            state = stt
        C[n] = fed + ltcg + niit + state
        if parts is not None:
            for key, val in (("fed", fed), ("ltcg", ltcg), ("niit", niit), ("state", state), ("agi", agi), ("tss", tss)):
                parts.setdefault(key, np.zeros((N, G)))[n] = val
    const = 0.0
    if inp["medicare"]:
        # year n's MAGI sets the IRMAA of year n+2
        lagged = np.zeros((N, G))
        lagged[2:] = AGI[: N - 2]
        M = _medicare(inp, lagged)
        C[: N - 2] += M[2:] * (d[2:N] / d[: N - 2])[:, None]
        pm = np.zeros((N, 1))
        pm[0, 0], pm[1 % N, 0] = inp["prevMAGI"][0], inp["prevMAGI"][1]
        M0 = _medicare(inp, pm)
        const = float(M0[0, 0] + (M0[1, 0] * d[1] if N > 1 else 0.0))
    if inp["aca"]:
        C += _aca(inp, MAGI_aca)
    return C, const


def solve_dp(inp, r=None, h=None, netSpending=None, bequest=0.0, liquidity=True, fast=True):
    """Exact (up to the grid) solution by dynamic programming over the PV recognized so far.

    The choice in year n is y_n = d_n x_n on a grid of step h (PV dollars), so the budget
    accounting is exact; each year's cost is the tax and premium bill at x_n = y_n / d_n.
    F_{n+1}(s + j) = min_j F_n(s) + d_n tau_n(j h / d_n) - nu j h, a min-plus convolution.
    r=None uses the plan's own per-year returns.
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
    C, const = cost_table(inp, X)
    t_table = time.time() - t0
    cost = d[:N, None] * C - nu * J[None, :] * h
    # RMDs are a state constraint: the PV balance before year n is avail_n - s h, where avail_n
    # is the initial balance plus the PV of contributions before n.
    avail = inp["D0_i"].sum() + np.concatenate([[0.0], np.cumsum(d[:N] * inp["kap_def"])])
    share = inp["D0_i"] / max(inp["D0_i"].sum(), 1e-9)
    rho_n = np.zeros(N)
    for n in range(N):
        rho = inp["rho_in"][:, n]
        if inp["Ni"] == 2 and n >= inp["n_d"]:
            rho_n[n] = rho[1 - inp["i_d"]] if rho[1 - inp["i_d"]] > 0 else rho.max()
        else:
            rho_n[n] = float(np.dot(share, rho))
    S = np.arange(B + 1)

    def jmin_of(n, states):
        # a QCD counts toward the RMD
        req = rho_n[n] * np.maximum(0.0, avail[n] - states * h) - d[n] * inp["qcd"][n]
        return np.where(req > 0, np.ceil(req / h - 1e-9), 0).astype(np.int64)

    caps = np.array([min(B, int(np.floor(avail[n + 1] / h + 1e-9))) for n in range(N)])

    def dp_full(smin):
        """Exact DP over all states, a Python loop over reachable states (the reference)."""
        F = np.full(B + 1, np.inf)
        F[0] = 0.0
        arg = np.zeros((N, B + 1), dtype=np.int64)
        for n in range(N):
            jmin = jmin_of(n, S)
            Fn = np.full(B + 1, np.inf)
            an = np.zeros(B + 1, dtype=np.int64)
            for s0 in np.flatnonzero(np.isfinite(F)):
                jmax = caps[n] - s0
                if jmax < jmin[s0]:
                    continue
                tot = F[s0] + cost[n, jmin[s0]: jmax + 1]
                tgt = Fn[s0 + jmin[s0]: s0 + jmax + 1]
                better = tot < tgt
                tgt[better] = tot[better]
                an[s0 + jmin[s0]: s0 + jmax + 1][better] = jmin[s0] + np.flatnonzero(better)
            Fn[: smin[n]] = np.inf
            F, arg[n] = Fn, an
        if not np.isfinite(F).any():
            raise RuntimeError("EM infeasible: liquidity floor cannot be met")
        s_cur = int(np.argmin(F))
        jn = np.zeros(N, dtype=np.int64)
        for n in range(N - 1, -1, -1):
            jn[n] = arg[n][s_cur]
            s_cur -= jn[n]
        return jn

    def dp_window(smin, lo, hi):
        """Same DP with the state after year n restricted to [lo[n], hi[n]] (vectorized)."""
        prev_lo, F = 0, np.zeros(1)
        args = []
        for n in range(N):
            a, b = lo[n], hi[n]
            sp = prev_lo + np.arange(len(F))          # previous states
            tt = np.arange(a, b + 1)                  # next states
            j = tt[None, :] - sp[:, None]
            ok = (j >= jmin_of(n, sp)[:, None]) & (j >= 0) & (tt[None, :] <= caps[n]) & (tt[None, :] >= smin[n])
            T = np.where(ok, F[:, None] + cost[n, np.clip(j, 0, B)], np.inf)
            k = np.argmin(T, axis=0)
            F = T[k, np.arange(len(tt))]
            args.append(sp[k])
            prev_lo = a
        if not np.isfinite(F).any():
            return None
        t_cur = lo[N - 1] + int(np.argmin(F))
        jn = np.zeros(N, dtype=np.int64)
        for n in range(N - 1, -1, -1):
            s_prev = args[n][t_cur - lo[n]]
            jn[n] = t_cur - s_prev
            t_cur = s_prev
        return jn

    def dp(smin):
        if not fast:
            jn = dp_full(smin)
            return jn, X[np.arange(N), jn]
        # coarse pass on every state of a grid `ratio` times coarser, then the exact DP in a
        # band of +-W fine steps around the coarse path; widen the band if the optimum
        # touches its edge
        ratio = max(1, B // 200)
        Sc = np.arange(0, B + 1, ratio)
        # coarse: states and steps on the multiples of ratio
        F = np.zeros(1)
        prev_states = np.array([0])
        args = []
        for n in range(N):
            tt = Sc
            j = tt[None, :] - prev_states[:, None]
            ok = (j >= jmin_of(n, prev_states)[:, None]) & (j >= 0) & (tt[None, :] <= caps[n]) & (tt[None, :] >= smin[n])
            T = np.where(ok, F[:, None] + cost[n, np.clip(j, 0, B)], np.inf)
            k = np.argmin(T, axis=0)
            F = T[k, np.arange(len(tt))]
            args.append(prev_states[k])
            prev_states = tt
        t_cur = int(Sc[np.argmin(F)])
        path = np.zeros(N, dtype=np.int64)
        for n in range(N - 1, -1, -1):
            path[n] = t_cur
            t_cur = int(args[n][np.searchsorted(Sc, t_cur)])
        W = 4 * ratio
        while True:
            lo = np.maximum(0, path - W)
            hi = np.minimum(B, path + W)
            jn = dp_window(smin, lo, hi)
            if jn is None:
                W *= 2
                continue
            fine_path = np.cumsum(jn)
            touch = ((fine_path == lo) & (lo > 0)) | ((fine_path == hi) & (hi < B))
            if not touch.any() or W >= B:
                return jn, X[np.arange(N), jn]
            path, W = fine_path, W * 2

    # Liquidity: the liquid balance after year n's flows must stay >= 0. It depends on spending
    # and taxes, so it is imposed as a floor on the PV recognized through year n, recomputed
    # from the previous solution until it stops moving.
    smin = np.zeros(N, dtype=np.int64)
    for it in range(20):
        jn, x = dp(smin)
        tau = C[np.arange(N), jn]
        v = _value(inp, x, tau, const, budget, netSpending, bequest)
        need = np.cumsum(d[:N] * (v["g"] + tau - inp["cash"] - inp["kap_liq"])) - inp["L0"]
        new = np.maximum(smin, np.minimum(B, np.ceil(np.maximum(0, need) / h - 1e-9).astype(np.int64)))
        if not liquidity or np.array_equal(new, smin):
            break
        smin = new
    out = _value(inp, x, tau, const, budget, netSpending, bequest)
    out.update(iters=it + 1, t_table=t_table, t_total=time.time() - t0, grid=B + 1, h=h, liquidity=liquidity)
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


def evaluate(inp, r, x, netSpending=None, bequest=0.0):
    """EM accounting of a given recognition schedule x (e.g. the full model's own)."""
    d = _set_returns(inp, r)
    N = inp["N"]
    budget = inp["D0_i"].sum() + float(np.sum(d[:N] * inp["kap_def"]))
    x = np.asarray(x, dtype=float)
    C, const = cost_table(inp, x[:, None])
    return _value(inp, x, C[:, 0], const, budget, netSpending, bequest)
