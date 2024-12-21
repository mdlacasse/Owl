import streamlit as st
from io import StringIO
from functools import wraps

import owlplanner as owl
import sskeys as k


def isIncomplete():
    return (k.currentCaseName() == '' or k.getKey('iname0') == ''
            or (k.getKey('status') == 'married' and k.getKey('iname1') == ''))


def createPlan():
    name = k.currentCaseName()
    inames = [k.getKey('iname0')]
    yobs = [k.getKey('yob0')]
    life = [k.getKey('life0')]
    startDate = k.getKey('startDate')
    if k.getKey('status') == 'married':
        inames.append(k.getKey('iname1'))
        yobs.append(k.getKey('yob1'))
        life.append(k.getKey('life1'))

    try:
        strio = StringIO()
        k.store('logs', strio)
        # print(inames, yobs, life, name, startDate)
        plan = owl.Plan(inames, yobs, life, name, startDate=startDate, verbose=True, logstreams=[strio, strio])
    except Exception as e:
        st.error('Failed plan creation: %s' % e)
        return
    k.store('plan', plan)


def _checkPlan(func):
    """
    Decorator to check if plan was created properly.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        plan = k.getKey('plan')
        if plan is None:
            st.error('Preventing to execute method %s().' % (func.__name__))
            return None
        return func(plan, *args, **kwargs)

    return wrapper


@_checkPlan
def runPlan(plan):
    maximize = k.getKey('objective')
    if 'spending' in maximize:
        objective = 'maxSpending'
    else:
        objective = 'maxBequest'

    ni = 1
    if k.getKey('status') == 'married':
        ni += 1

    bal = [[], [], []]
    accounts = ['txbl', 'txDef', 'txFree']
    for j, acc in enumerate(accounts):
        for i in range(ni):
            bal[j].append(k.getKey(acc+str(i)))

    try:
        plan.setAccountBalances(taxable=bal[0], taxDeferred=bal[1], taxFree=bal[2])
    except Exception as e:
        st.error('Account balance failed: %s' % e)
        return

    options = {}
    optList = ['netSpending', 'maxRothConversion', 'noRothConversions', 'withMedicare', 'bequest', 'solver']
    for opt in optList:
        val = k.getKey(opt)
        if val:
            options[opt] = val

    try:
        plan.solve(objective, options=options)
    except Exception as e:
        st.error('Solution failed: %s' % e)
        k.store('summary', '')
        return

    k.init('caseStatus', 'unknown')
    k.store('caseStatus', plan.caseStatus)
    k.store('summary', plan.summaryString())


@_checkPlan
def setRates(plan):
    if k.getKey('rateType') == 'fixed':
        plan.setRates('fixed', values=[float(k.getKey('fxRate0')),
                                       float(k.getKey('fxRate1')),
                                       float(k.getKey('fxRate2')),
                                       float(k.getKey('fxRate3')), ])
    elif k.getKey('varyingType') == 'historical':
        yfrm = k.getKey('yfrm')
        yto = k.getKey('yto')
        plan.setRates('historical', yfrm, yto)

    return True


@_checkPlan
def showAllocations(plan):
    figures = plan.showAllocations(figure=True)
    # print('figures', figures)
    for fig in figures:
        st.pyplot(fig)


@_checkPlan
def showProfile(plan):
    profile = k.getKey('profile')
    survivor = k.getKey('survivor')
    plan.setSpendingProfile(profile, survivor)
    fig = plan.showProfile(figure=True)
    st.pyplot(fig)


@_checkPlan
def showRates(plan):
    fig = plan.showRates(figure=True)
    st.pyplot(fig)


@_checkPlan
def showIncome(plan):
    fig = plan.showIncome(figure=True)
    st.pyplot(fig)


@_checkPlan
def showSources(plan):
    fig = plan.showSources(figure=True)
    st.pyplot(fig)


@_checkPlan
def setInterpolationMethod(plan):
    plan.setInterpolationMethod(k.getKey('interp'))


@_checkPlan
def readContributions(plan, file):
    if file is None:
        return None

    return plan.readContributions(file)


@_checkPlan
def setAllocationRatios(plan):
    tags = ['S&P500', 'Baa', 'T-Notes', 'Cash']

    generic = []
    initial = []
    final = []
    for tg in tags:
        initial.append(float(k.getKey('init%'+tg+'0')))
        final.append(float(k.getKey('fin%'+tg+'0')))
    gen0 = [initial, final]
    generic = [gen0]

    if k.getKey('status') == 'married':
        initial = []
        final = []
        for tg in tags:
            initial.append(float(k.getKey('init%'+tg+'1')))
            final.append(float(k.getKey('fin%'+tg+'1')))
        gen1 = [initial, final]
        generic.append(gen1)

    return plan.setAllocationRatios('individual', generic=generic)


@_checkPlan
def plotSingleResults(plan):
    fig = plan.showNetSpending(figure=True)
    if fig:
        st.write('## Net Spending')
        st.pyplot(fig)

    fig = plan.showSources(figure=True)
    if fig:
        st.write('## Sources')
        st.pyplot(fig)

    fig = plan.showAccounts(figure=True)
    if fig:
        st.write('## Account Balances')
        st.pyplot(fig)

    fig = plan.showGrossIncome(figure=True)
    if fig:
        st.write('## Gross Income')
        st.pyplot(fig)

    fig = plan.showTaxes(figure=True)
    if fig:
        st.write('## Income Taxes & Medicare')
        st.pyplot(fig)
