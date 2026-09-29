# Draft upstream issue (mdlacasse/Owl): married case without `pension_indexed` crashes

**Title:** Config: a married case that omits `pension_indexed` fails with IndexError in `compute_piBar_in`

---

For a couple, leaving `pension_indexed` out of `[fixed_income]` makes every solve fail:

```
  File "src/owlplanner/plan.py", in _adjustParameters
    self.piBar_in = pension.compute_piBar_in(
  File "src/owlplanner/pension.py", line 121, in compute_piBar_in
    if indexed[i]:
IndexError: list index out of range
```

`_apply_fixed_income_to_plan` defaults the key to `[True]`, one entry whatever the household size, and
`setPension` checks the length of `amounts` and `ages` but not `indexed`. A case with no pensions is
where this is most likely to bite: there is nothing to index, so the key looks optional.

**Repro** (on `dev`, `0aabf00`): remove the `pension_indexed` line from `examples/Case_john+sally.toml`
and run `owlcli run` on it.

**Suggested fix:**

```python
# config/plan_bridge.py, _apply_fixed_income_to_plan
pension_indexed = known["fixed_income"].get("pension_indexed", [True] * icount)

# plan.py, setPension, after the None default
u.require_list(indexed, "indexed", self.N_i)
```

The second line turns any other wrong length into the same clear `ValueError` the other lists give.
We have this with two tests in our fork (a couple case without the key solves; a one-entry list for
a couple is rejected) and can open a PR against `dev`.
