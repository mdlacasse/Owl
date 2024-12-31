import streamlit as st
from io import StringIO, BytesIO
from functools import wraps
import pandas as pd
from datetime import datetime, date
import importlib

import owlplanner as owl
import sskeys as k
import progress


def hasMOSEK():
    spec = importlib.util.find_spec('mosek')
    return spec is not None


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
        plan = owl.Plan(inames, yobs, life, name, startDate=startDate,
                        verbose=True, logstreams=[strio, strio])
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
    optList = ['netSpending', 'maxRothConversion', 'noRothConversions',
               'withMedicare', 'bequest', 'solver']
    for opt in optList:
        val = k.getKey(opt)
        if val is not None:
            options[opt] = val

    if k.getKey('readRothX'):
        options['maxRothConversion'] = 'file'

    return objective, options


def prepareRun(plan):
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

    if ni == 2:
        benfrac = [k.getKey('benf0'), k.getKey('benf1'), k.getKey('benf2')]
        try:
            plan.setBeneficiaryFractions(benfrac)
        except Exception as e:
            st.error('Failed setting beneficiary fractions: %s' % e)
            return

        surplusFrac = k.getKey('surplusFraction')
        try:
            plan.setSpousalDepositFraction(surplusFrac)
        except Exception as e:
            st.error('Failed setting beneficiary fractions: %s' % e)
            return

    setRates()


@_checkPlan
def runPlan(plan):
    prepareRun(plan)

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


def isCaseUnsolved():
    if k.getKey('plan') is None:
        return True
    return k.getKey('caseStatus') != 'solved'


def caseIsNotMCReady():
    return (caseIsNotRunReady() or
            k.getKey('rateType') != 'varying' or
            'tochastic' not in k.getKey('varyingType'))


def caseIsNotRunReady():
    return (k.getKey('plan') is None or
            k.getKey('objective') is None or
            k.getKey('rateType') is None or
            k.getKey('interp') is None or
            k.getKey('profile') is None)


@_checkPlan
def runHistorical(plan):
    prepareRun(plan)

    hyfrm = k.getKey('hyfrm')
    hyto = k.getKey('hyto')

    objective, options = getSolveParameters()
    try:
        mybar = progress.Progress(None)
        fig = plan.runHistoricalRange(objective, options, hyfrm, hyto, figure=True, barcall=mybar)
        k.setKey('histoPlot', fig)
    except Exception as e:
        k.setKey('histoPlot', None)
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
def runMC(plan):
    prepareRun(plan)

    N = k.getKey('MC_cases')

    objective, options = getSolveParameters()
    try:
        mybar = progress.Progress(None)
        fig = plan.runMC(objective, options, N, figure=True, barcall=mybar)
        k.setKey('monteCarloPlot', fig)
    except Exception as e:
        k.setKey('monteCarloPlot', None)
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
            # Set fxRates back to computed values.
            for j in range(4):
                k.setKey('fxRate'+str(j), 100*plan.tau_kn[j, -1])
        else:
            plan.setRates('user', values=[float(k.getKey('fxRate0')),
                                          float(k.getKey('fxRate1')),
                                          float(k.getKey('fxRate2')),
                                          float(k.getKey('fxRate3')), ])
    else:
        varyingType = k.getKey('varyingType')
        if 'histo' in varyingType:
            if varyingType == 'historical':
                yto = min(2023, yfrm+plan.N_n-1)
                k.setKey('yto', yto)
            plan.setRates(varyingType, yfrm, yto)
            mean, stdev, corr, covar = owl.getRatesDistributions(yfrm, yto, plan.mylog)
            for j in range(4):
                k.setKey('mean'+str(j), 100*mean[j])
                k.setKey('stdev'+str(j), 100*stdev[j])
            q = 1
            for k1 in range(plan.N_k):
                for k2 in range(k1+1, plan.N_k):
                    # k.setKey('corr'+str(q), plan.rateCorr[k1, k2])
                    k.setKey('corr'+str(q), corr[k1, k2])
                    q += 1

        elif varyingType == 'stochastic':
            means = []
            stdev = []
            corr = []
            for kk in range(plan.N_k):
                means.append(k.getKey('mean'+str(kk)))
                stdev.append(k.getKey('stdev'+str(kk)))
            for q in range(1, 7):
                corr.append(k.getKey('corr'+str(q)))
            plan.setRates(varyingType, values=means, stdev=stdev, corr=corr)
        else:
            raise RuntimeError('Logic error in setRates()')

    return True


@_checkPlan
def showAllocations(plan):
    figures = plan.showAllocations(figure=True)
    # print('figures', figures)
    for fig in figures:
        st.markdown('###')
        st.pyplot(fig)


@_checkPlan
def showProfile(plan):
    fig = plan.showProfile(figure=True)
    st.pyplot(fig)


@_checkPlan
def showRates(plan):
    fig = plan.showRates(figure=True)
    if fig:
        st.markdown('###')
        st.pyplot(fig)


@_checkPlan
def showRatesCorrelations(plan):
    fig = plan.showRatesCorrelations(figure=True)
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
    plan.setInterpolationMethod(k.getKey('interp'), k.getKey('center'), k.getKey('width'))


@_checkPlan
def readContributions(plan, file):
    if file is None:
        return None

    return plan.readContributions(file)


@_checkPlan
def resetContributions(plan):
    return plan.resetContributions()


@_checkPlan
def setAllocationRatios(plan):
    generic = []
    initial = []
    final = []
    for j in range(4):
        initial.append(int(k.getKey('init%'+str(j)+'_0')))
        final.append(int(k.getKey('fin%'+str(j)+'_0')))
    gen0 = [initial, final]
    generic = [gen0]

    if k.getKey('status') == 'married':
        initial = []
        final = []
        for j in range(4):
            initial.append(int(k.getKey('init%'+str(j)+'_1')))
            final.append(int(k.getKey('fin%'+str(j)+'_1')))
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
def setProfile(plan, key, pull=True):
    if pull:
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


@_checkPlan
def showWorkbook(plan):
    wb = plan.saveWorkbook(saveToFile=False)
    if wb is None:
        return
    for name in wb.sheetnames:
        if name == 'Summary':
            continue
        ws = wb[name]
        df = pd.DataFrame(ws.values)
        st.write('#### '+name)
        st.dataframe(df.astype(str), use_container_width=True)


@_checkPlan
def saveWorkbook(plan):
    wb = plan.saveWorkbook(saveToFile=False)
    buffer = BytesIO()
    if wb is None:
        return buffer
    try:
        wb.save(buffer)
    except Exception as e:
        raise Exception('Unanticipated exception %r.' % e)

    return buffer


@_checkPlan
def saveConfig(plan):
    prepareRun(plan)
    getSolveParameters()
    stringBuffer = StringIO()
    plan.saveConfig(stringBuffer)
    encoded_data = stringBuffer.getvalue().encode('utf-8')
    bytesBuffer = BytesIO(encoded_data)

    return bytesBuffer


def createCaseFromConfig(file):
    strio = StringIO()
    try:
        mystringio = StringIO(file.read().decode('utf-8'))
        plan = owl.readConfig(mystringio, logstreams=[strio], readContributions=False)
    except Exception as e:
        raise RuntimeError('Failed to parse config file: %s' % (e))

    name, mydic = genDic(plan)
    mydic['logs'] = strio

    return name, mydic

    # keynames = ['name', 'status', 'plan', 'summary', 'logs', 'startDate',
    #            'timeList', 'plots', 'interp',
    #            'objective', 'withMedicare', 'bequest', 'netSpending',
    #            'noRothConversions', 'maxRothConversion',
    #            'rateType', 'fixedType', 'varyingType', 'yfrm', 'yto',
    #            'divRate', 'heirsTx', 'gainTx', 'profile', 'survivor',
    #            'surplusFraction', ]
    # keynamesJ = ['benf', ]
    # keynamesK = ['fxRate', 'mean', 'stdev']
    # keynamesI = ['iname', 'yob', 'life', 'txbl', 'txDef', 'txFree',
    #             'ssAge', 'ssAmt', 'pAge', 'pAmt', 'df',
    #             'init%0_', 'init%1_', 'init%2_', 'init%3_',
    #             'fin%0_', 'fin%1_', 'fin%2_', 'fin%3_']
    # keynames6 = ['corr']


# @_checkPlan
def genDic(plan):
    accName = ['txbl', 'txDef', 'txFree']
    dic = {}
    dic['plan'] = plan
    dic['name'] = plan._name
    dic['summary'] = ''
    dic['status'] = ['unknown', 'single', 'married'][plan.N_i]
    # Prepend year if not there.
    tdate = plan.startDate.split('-')
    if len(tdate) == 2:
        mystartDate = str(date.today().year)+'-'+plan.startDate
    elif len(tdate) == 3:
        mystartDate = str(date.today().year)+'-'+tdate[-2]+'-'+tdate[-1]
    else:
        raise ValueError('Wrong date format %s.' % (plan.startDate))
    try:
        startDate = datetime.strptime(mystartDate, '%Y-%m-%d').date()
    except Exception as e:
        raise ValueError('Wrong date format %s: %s' % (plan.startDate, e))
    dic['startDate'] = startDate
    dic['interp'] = plan.interpMethod
    dic['center'] = plan.interpCenter
    dic['width'] = plan.interpWidth
    dic['profile'] = plan.spendingProfile
    dic['survivor'] = 100*plan.chi
    dic['gainTx'] = 100*plan.psi
    dic['divRate'] = 100*plan.mu
    dic['heirsTx'] = 100*plan.nu
    dic['surplusFraction'] = plan.eta
    dic['plots'] = plan.defaultPlots
    # self.eta = (self.N_i - 1) / 2  # Spousal deposit ratio (0 or .5)
    for j in range(plan.N_j):
        dic['benf'+str(j)] = plan.phi_j[j]

    for i in range(plan.N_i):
        dic['iname'+str(i)] = plan.inames[i]
        dic['yob'+str(i)] = plan.yobs[i]
        dic['life'+str(i)] = plan.expectancy[i]
        dic['ssAge'+str(i)] = plan.ssecAges[i]
        dic['ssAmt'+str(i)] = plan.ssecAmounts[i]/1000
        dic['pAge'+str(i)] = plan.pensionAges[i]
        dic['pAmt'+str(i)] = plan.pensionAmounts[i]/1000
        for j in range(plan.N_j):
            dic[accName[j]+str(i)] = plan.beta_ij[i, j]/1000
        if plan.ARCoord == 'individual':
            for k1 in range(plan.N_k):
                dic['init%'+str(k1)+'_'+str(i)] = int(plan.boundsAR['generic'][i][0][k1])
                dic['fin%'+str(k1)+'_'+str(i)] = int(plan.boundsAR['generic'][i][1][k1])
        else:
            raise ValueError("Only 'individual' asset allocation currently supported")

    optionKeys = list(plan.solverOptions)
    for key in ['maxRothConversion', 'noRothConversions', 'withMedicare', 'netSpending', 'bequest']:
        if key in optionKeys:
            dic[key] = plan.solverOptions[key]

    if plan.objective == 'maxSpending':
        dic['objective'] = 'Net spending'
    else:
        dic['objective'] = 'Bequest'

    if plan.rateMethod in ['default', 'conservative', 'optimistic', 'average', 'user']:
        dic['rateType'] = 'fixed'
        dic['fixedType'] = plan.rateMethod
    elif plan.rateMethod in ['histochastic', 'historical', 'stochastic']:
        dic['rateType'] = 'varying'
        dic['varyingType'] = plan.rateMethod

    # Initialize in both cases.
    for kk in range(plan.N_k):
        dic['fxRate'+str(kk)] = 100*plan.rateValues[kk]

    if plan.rateMethod in ['average', 'histochastic', 'historical']:
        dic['yfrm'] = plan.rateFrm
        dic['yto'] = plan.rateTo
    else:
        dic['yfrm'] = 1928
        dic['yto'] = date.today().year - 1

    if plan.rateMethod in ['stochastic', 'histochastic']:
        qq = 1
        for k1 in range(plan.N_k):
            dic['mean'+str(k1)] = 100*plan.rateValues[k1]
            dic['stdev'+str(k1)] = 100*plan.rateStdev[k1]
            for k2 in range(k1+1, plan.N_k):
                dic['corr'+str(qq)] = plan.rateCorr[k1, k2]
                qq += 1

    # print('Name:', plan._name)
    # print('Dic:', dic)
    return plan._name, dic


def clone(plan, newname, logstreams=None):
    return owl.clone(plan, newname, logstreams=logstreams)
