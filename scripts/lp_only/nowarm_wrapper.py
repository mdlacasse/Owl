import runpy, sys
from owlplanner.plan import Plan
_orig = Plan._run_highs
def _nowarm(self, *a, warm_x=None, **k):
    return _orig(self, *a, warm_x=None, **k)
Plan._run_highs = _nowarm
sys.argv = [sys.argv[1]] + sys.argv[2:]
runpy.run_path(sys.argv[0], run_name="__main__")
