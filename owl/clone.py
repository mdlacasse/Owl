'''

Owl/clone
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

Copyright -- Martin-D. Lacasse (2024)

Disclaimer: This program comes with no guarantee. Use at your own risk.

'''

from owl import plan


def clone(plan, name=None):
    '''
    Return an almost identical copy of plan.
    Only the name wiil be modified and appended '(copy)',
    unless a new name is provided as an argument.
    '''
    import copy

    newplan = copy.deepcopy(plan)
    if name is None:
        newplan.rename(plan._name + ' (copy)')
    else:
        newplan.rename(name)

    return newplan
