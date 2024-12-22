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
        k.setKey('logs', strio)
        # print(inames, yobs, life, name, startDate)
        plan = owl.Plan(inames, yobs, life, name, startDate=startDate, verbose=True, logstreams=[strio, strio])
    except Exception as e:
        st.error('Failed plan creation: %s' % e)
        return
    k.setKey('plan', plan)


def _checkPlan(func):
    """
    Decorator to check if plan was created properly.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        plan = k.getKey('plan')
        if plan is None:
            st.error('Plan not yet created. Preventing to execute method %s().' % (func.__name__))
            return None
        return func(plan, *args, **kwargs)

    return wrapper


def getFixedIncome(ni, what):
    amounts = []
    ages = []
    for i in range(ni):
        amounts.append(k.getKey(what+'Amt'+str(i)))
        ages.append(k.getKey(what+'Age'+str(i)))

    return amounts, ages


def getAccountBalances(ni):
    bal = [[], [], []]
    accounts = ['txbl', 'txDef', 'txFree']
    for j, acc in enumerate(accounts):
        for i in range(ni):
            bal[j].append(k.getKey(acc+str(i)))

    return bal


def getSolveParameters():
    maximize = k.getKey('objective')
    if 'spending' in maximize:
        objective = 'maxSpending'
    else:
        objective = 'maxBequest'

    options = {}
    optList = ['netSpending', 'maxRothConversion', 'noRothConversions', 'withMedicare', 'bequest', 'solver']
    for opt in optList:
        val = k.getKey(opt)
        if val:
            options[opt] = val

    return objective, options


@_checkPlan
def runPlan(plan):
    ni = 2 if k.getKey('status') == 'married' else 1

    bal = getAccountBalances(ni)
    try:
        plan.setAccountBalances(taxable=bal[0], taxDeferred=bal[1], taxFree=bal[2])
    except Exception as e:
        st.error('Account balance failed: %s' % e)
        return

    amounts, ages = getFixedIncome(ni, 'p')
    try:
        plan.setPension(amounts, ages)
    except Exception as e:
        st.error('Failed setting pensions: %s' % e)
        return

    amounts, ages = getFixedIncome(ni, 'ss')
    try:
        plan.setSocialSecurity(amounts, ages)
    except Exception as e:
        st.error('Failed setting social security: %s' % e)
        return

    objective, options = getSolveParameters()
    try:
        plan.solve(objective, options=options)
    except Exception as e:
        st.error('Solution failed: %s' % e)
        k.setKey('summary', '')
        return

    k.init('caseStatus', 'unknown')
    k.setKey('caseStatus', plan.caseStatus)
    if plan.caseStatus == 'solved':
        k.setKey('summary', plan.summaryString())
    else:
        k.setKey('summary', '')


@_checkPlan
def setRates(plan):
    yfrm = k.getKey('yfrm')
    yto = k.getKey('yto')

    if k.getKey('rateType') == 'fixed':
        if k.getKey('fixedType') == 'historical average':
            plan.setRates('average', yfrm, yto)
            # Need to set fxRates to computed values.
            k.setKey('fxRate0', 100*plan.tau_kn[0, -1])
            k.setKey('fxRate1', 100*plan.tau_kn[1, -1])
            k.setKey('fxRate2', 100*plan.tau_kn[2, -1])
            k.setKey('fxRate3', 100*plan.tau_kn[3, -1])
        else:
            plan.setRates('fixed', values=[float(k.getKey('fxRate0')),
                                           float(k.getKey('fxRate1')),
                                           float(k.getKey('fxRate2')),
                                           float(k.getKey('fxRate3')), ])
    else:
        varyingType = k.getKey('varyingType')
        if 'histo' in varyingType:
            plan.setRates(varyingType, yfrm, yto)
        elif varyingType == 'stochastic':
            pass
        else:
            raise RuntimeError('Logic error in setRates()')

    return True


@_checkPlan
def showAllocations(plan):
    figures = plan.showAllocations(figure=True)
    # print('figures', figures)
    for fig in figures:
        st.pyplot(fig)


@_checkPlan
def showProfile(plan):
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
        st.write('#### Net Available Spending')
        st.pyplot(fig)

    fig = plan.showSources(figure=True)
    if fig:
        st.write('#### Raw Income Sources')
        st.pyplot(fig)

    fig = plan.showAccounts(figure=True)
    if fig:
        st.write('#### Account Balances')
        st.pyplot(fig)

    fig = plan.showGrossIncome(figure=True)
    if fig:
        st.write('#### Taxable Ordinary Income')
        st.pyplot(fig)

    fig = plan.showTaxes(figure=True)
    if fig:
        st.write('#### Income Taxes and Medicare (including IRMAA)')
        st.pyplot(fig)


@_checkPlan
def setProfile(plan, key):
    k.pull(key)
    profile = k.getKey('profile')
    survivor = k.getKey('survivor')
    plan.setSpendingProfile(profile, survivor)


@_checkPlan
def setHeirsTaxRate(plan, key):
    val = k.pull(key)
    plan.setHeirsTaxRate(val)


@_checkPlan
def setLongTermCapitalTaxRate(plan, key):
    val = k.pull(key)
    plan.setLongTermCapitalTaxRate(val)


@_checkPlan
def setDividendRate(plan, key):
    val = k.pull(key)
    plan.setDividendRate(val)


@_checkPlan
def setDefaultPlots(plan, key):
    val = k.pull(key)
    plan.setDefaultPlots(val)
