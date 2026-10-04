"""Envelope model (EM): a separable reformulation of Owl under back-of-envelope assumptions.

Assumptions (the "envelope world"):
  - real dollars: inflation 0, so every bracket and threshold is constant in time;
  - one common real return r for every account and asset class (r = 0: no gains, no interest);
  - no dividends or interest taxed inside the taxable account (no tax drag);
  - the taxable, tax-free and HSA accounts are pooled as one liquid balance.

Under these assumptions a dollar is worth the same in every account up to taxes, so the only
decision that matters is x_n, the tax-deferred dollars recognized as ordinary income in year n
(withdrawals plus Roth conversions). Discounting at r, with d_n = (1+r)^-n,

    maxSpending:  basis = (W - sum_n d_n [tau_n(x_n) - nu x_n] - nu D) / sum_n d_n xi_n
    maxBequest:   bequest = (W' - sum_n d_n [tau_n(x_n) - nu x_n] - nu D) / d_N

where tau_n is the year's whole tax-and-premium bill as a function of x_n alone (federal
ordinary and LTCG tax, SS taxability, OBBBA senior deduction, NIIT, state and local tax, IRMAA
two years later, ACA), and W, W', D collect exogenous quantities. Both objectives reduce to

    min  sum_n d_n [tau_n(x_n) - nu x_n]   s.t.  sum_n d_n x_n <= D,   x_n >= rmd_n

a separable resource-allocation problem with ONE coupling constraint. It is solved exactly (up
to a grid) by dynamic programming over the PV budget used so far (solve_dp). Each year's cost is
tabulated over a grid of x, so the non-convex pieces (SS torpedo, IRMAA cliffs, ACA, phase-outs)
are priced exactly, including their marginal effect. RMDs are a constraint on the DP state. Cash
liquidity (the pooled liquid balance never negative) is a floor on the state, iterated because
it depends on spending and taxes.

Exogenous series (SS, pensions, wages, contributions, spending profile, fixed assets, debts,
brackets, state parameters) are read from an Owl Plan after its own setup, so the two models
see the same inputs. The tax tables are evaluated with Owl's own functions where they exist
(mediCosts, acaCosts, taxParams).
"""
import time
import numpy as np
from owlplanner import tax_federal as tx

THISYEAR = 2026


def _bracket_tax(ti, theta, delta):
    """ti: (G,), theta/delta: (T,) -> (G,) tax from filling brackets in order."""
    tops = np.cumsum(delta)
    bots = tops - delta
    fill = np.clip(ti[:, None] - bots[None, :], 0, delta[None, :])
    return fill @ theta


def inputs(p, opts=None):
    opts = opts or {}
    N, Ni = p.N_n, p.N_i
    g = p.gamma_n[:N]
    if not np.allclose(g, 1.0):
        raise ValueError("EM needs an inflation-free plan (gamma_n == 1)")
    inp = dict(N=N, Ni=Ni, n_d=min(p.n_d, N), i_d=p.i_d, nu=p.nu, objective=p.objective)
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
    # federal standard deduction without the senior bonus, and the count of bonus-eligible seniors
    big = np.full(N, 1e12)
    s_inf = tx.taxParams(p.yobs, p.i_d, p.n_d, N, g, big, p.yOBBBA)[0]
    s_zero, theta, Delta = tx.taxParams(p.yobs, p.i_d, p.n_d, N, g, np.zeros(N), p.yOBBBA)
    inp["sigma0"] = s_inf
    inp["seniors"] = np.round((s_zero - s_inf) / 6000.0)
    inp["theta"], inp["Delta"] = theta, Delta
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
    inp["plan"] = p  # for Owl's Medicare/ACA functions
    return inp


def _with_r(inp, r):
    """Contributions in start-of-year equivalents for return r."""
    half = (1 + r / 2) / (1 + r)
    inp["kap_def"] = inp["kap_def_c"] * half - inp["kap_def_out"]
    inp["kap_liq"] = inp["kap_liq_c"] * half
    return inp


def cost_table(inp, xg, r, parts=None):
    """C[n, k] = PV-at-n cost of recognizing xg[k] in year n (all taxes and premiums it drives)."""
    p = inp["plan"]
    N = inp["N"]
    X = np.broadcast_to(np.asarray(xg, dtype=float), (N, np.shape(xg)[-1]))
    G = X.shape[1]
    d = (1 + r) ** -np.arange(N + 2)
    C = np.zeros((N, G))
    AGI = np.zeros((N, G))
    MAGI_aca = np.zeros((N, G))
    for n in range(N):
        st = inp["status"][n]
        O, ss, Q = inp["ord"][n], inp["ss"][n], inp["Q"][n]
        xg = X[n]
        lo, hi = tx.ssTaxabilityLo[st], tx.ssTaxabilityHi[st]
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
        T15, T20 = tx.capGainRates[st][0], tx.capGainRates[st][1]
        q0 = np.minimum(Q, np.maximum(0, T15 - Gt))
        q1 = np.minimum(Q - q0, np.maximum(0, T20 - Gt) - q0)
        ltcg = 0.15 * q1 + 0.20 * (Q - q0 - q1)
        thr = tx.niitThreshold[st]
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
    # Medicare (IRMAA lags two years) and ACA, with Owl's own functions, one grid value at a time.
    inc_d = getattr(p, "_include_medicare_part_d", True)
    pd_base = getattr(p, "_medicare_part_d_base_annual_per_person", 0.0)
    ones = np.ones(N)
    n_aca = max(0, p.aca_start_year - int(p.year_n[0])) if p.aca_start_year > 0 else 0
    for k in range(G if (inp["medicare"] or inp["aca"]) else 0):
        if not inp["medicare"]:
            C[:, k] += tx.acaCosts(p.yobs, p.horizons, MAGI_aca[:, k], ones, p.slcsp_annual, N, n_aca_start=n_aca)
            continue
        M = tx.mediCosts(p.yobs, p.horizons, AGI[:, k], p.prevMAGI, ones, N, include_part_d=inc_d,
                         part_d_base_annual_per_person=pd_base)
        # cost driven by year n's MAGI lands in year n+2
        C[: N - 2, k] += M[2:] * d[2:N] / d[: N - 2]
        if inp["aca"]:
            C[:, k] += tx.acaCosts(p.yobs, p.horizons, MAGI_aca[:, k], ones, p.slcsp_annual, N, n_aca_start=n_aca)
    # Medicare in years 0 and 1 depends only on prevMAGI: a constant
    M0 = tx.mediCosts(p.yobs, p.horizons, np.zeros(N), p.prevMAGI, ones, N, include_part_d=inc_d,
                      part_d_base_annual_per_person=pd_base)
    const = (M0[0] + M0[1] * d[1]) if inp["medicare"] else 0.0
    return C, const


def solve_dp(inp, r=0.0, h=None, netSpending=None, bequest=0.0, liquidity=True):
    """Exact (up to the grid) solution by dynamic programming over the PV budget used.

    The choice in year n is y_n = d_n x_n on a grid of step h (PV dollars), so the budget
    accounting is exact; each year's cost is Owl's tax and premium bill at x_n = y_n / d_n.
    F_{n+1}(s + j) = min_j F_n(s) + d_n tau_n(j h / d_n) - nu j h, a min-plus convolution.
    """
    t0 = time.time()
    _with_r(inp, r)
    N, nu = inp["N"], inp["nu"]
    d = (1 + r) ** -np.arange(N + 1)
    budget = inp["D0_i"].sum() + float(np.sum(d[:N] * inp["kap_def"]))
    if h is None:
        h = max(250.0, 500.0 * np.ceil(budget / 2000 / 500.0)) if budget > 0 else 500.0
    B = int(np.floor(budget / h + 1e-9))
    J = np.arange(B + 1)
    X = (J[None, :] * h) / d[:N, None]  # year-n dollars for each PV step
    C, const = cost_table(inp, X, r)
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
    def dp(smin):
        F = np.full(B + 1, np.inf)
        F[0] = 0.0
        arg = np.zeros((N, B + 1), dtype=np.int32)
        for n in range(N):
            cap = min(B, int(np.floor(avail[n + 1] / h + 1e-9)))
            Fn = np.full(B + 1, np.inf)
            an = np.zeros(B + 1, dtype=np.int32)
            for s0 in np.flatnonzero(np.isfinite(F)):
                # a QCD counts toward the RMD
                req = rho_n[n] * max(0.0, avail[n] - s0 * h) - d[n] * inp["qcd"][n]
                jmin = int(np.ceil(req / h - 1e-9)) if req > 0 else 0
                jmax = cap - s0
                if jmax < jmin:
                    continue
                tot = F[s0] + cost[n, jmin: jmax + 1]
                tgt = Fn[s0 + jmin: s0 + jmax + 1]
                better = tot < tgt
                tgt[better] = tot[better]
                an[s0 + jmin: s0 + jmax + 1][better] = jmin + np.flatnonzero(better)
            Fn[: smin[n]] = np.inf
            F, arg[n] = Fn, an
        if not np.isfinite(F).any():
            raise RuntimeError("EM infeasible: liquidity floor cannot be met")
        s_end = int(np.argmin(F))
        jn = np.zeros(N, dtype=int)
        s_cur = s_end
        for n in range(N - 1, -1, -1):
            jn[n] = arg[n][s_cur]
            s_cur -= jn[n]
        x = X[np.arange(N), jn]
        return jn, x

    # Liquidity: the liquid balance after year n's flows must stay >= 0. It depends on spending
    # and taxes, so it is imposed as a floor on the PV recognized through year n, recomputed
    # from the previous solution until it stops moving.
    smin = np.zeros(N, dtype=int)
    for it in range(20):
        jn, x = dp(smin)
        tau = C[np.arange(N), jn]
        v = _value(inp, r, x, tau, const, budget, netSpending, bequest)
        g = v["g"]
        need = np.cumsum(d[:N] * (g + tau - inp["cash"] - inp["kap_liq"])) - inp["L0"]
        new = np.maximum(smin, np.minimum(B, np.ceil(np.maximum(0, need) / h - 1e-9).astype(int)))
        if not liquidity or np.array_equal(new, smin):
            break
        smin = new
    tau = C[np.arange(N), jn]
    out = _value(inp, r, x, tau, const, budget, netSpending, bequest)
    out.update(iters=it + 1, t_table=t_table, t_total=time.time() - t0, grid=B + 1, h=h, liquidity=liquidity)
    return out


def _value(inp, r, x, tau, const, budget, netSpending, bequest):
    N, nu = inp["N"], inp["nu"]
    d = (1 + r) ** -np.arange(N + 1)
    phi = float(np.sum(d[:N] * tau)) + const  # PV of all taxes and premiums
    W = inp["L0"] + float(np.sum(d[:N] * (inp["cash"] + inp["kap_liq"]))) + budget
    leftover = budget - float(np.sum(d[:N] * x))
    if inp["objective"] == "maxSpending":
        val = (W - phi - nu * leftover - d[N] * (bequest + inp["debt_end"])) / float(np.sum(d[:N] * inp["xi"]))
        g = val * inp["xi"]
    else:
        g = netSpending / inp["xi"][0] * inp["xi"]
        val = (W - phi - nu * leftover - float(np.sum(d[:N] * g))) / d[N] - inp["debt_end"]
    # liquidity check: liquid balance at the start of each year after its flows
    liq = inp["L0"] + np.cumsum(d[:N] * (inp["cash"] + inp["kap_liq"] + x - g - tau))
    return dict(value=val, g=g, x=x, tau=tau, liq_min=float(np.min(liq / d[:N])), leftover=leftover)


def evaluate(inp, r, x, netSpending=None, bequest=0.0):
    """EM accounting of a given recognition schedule x (e.g. the full model's own)."""
    _with_r(inp, r)
    N = inp["N"]
    d = (1 + r) ** -np.arange(N + 1)
    budget = inp["D0_i"].sum() + float(np.sum(d[:N] * inp["kap_def"]))
    C, const = cost_table(inp, np.asarray(x, dtype=float), r)
    tau = C[np.arange(N), np.arange(N)]
    return _value(inp, r, np.asarray(x, dtype=float), tau, const, budget, netSpending, bequest)
