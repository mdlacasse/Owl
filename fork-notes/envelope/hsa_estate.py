"""HSA left at the end of Owl's plan and the heirs' tax on it (Owl taxes the HSA estate at nu),
which the one-state EM, pooling the HSA with the liquid accounts, does not charge."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa  (chdir to examples)

for c in sys.argv[1:]:
    p = compare.load("Case_%s.toml" % c)
    if compare.PHI1:
        p.setBeneficiaryFractions([1, 1, 1, 1])
    p.solve(p.objective, dict(p.solverOptions))
    N = p.N_n
    end = float(p.b_ijn[:, 3, N].sum())
    print(json.dumps({"case": c, "phi1": compare.PHI1, "hsa_start": float(p.beta_ij[:, 3].sum()),
                      "hsa_end_nominal": round(end), "heirs_tax_today": round(p.nu * end / p.gamma_n[N]),
                      "objective": round(p.basis if p.objective == "maxSpending" else p.bequest)}))
