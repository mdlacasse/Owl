import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
from functools import wraps
from datetime import datetime, date
import importlib

import owlplanner as owl
from owlplanner.rates import FROM, TO

import sskeys as kz
import progress


def hasMOSEK():
    spec = importlib.util.find_spec('mosek')
    return spec is not None


def createPlan():
    name = kz.currentCaseName()
    inames = [kz.getKey('iname0')]
    yobs = [kz.getKey('yob0')]
    life = [kz.getKey('life0')]
    startDate = kz.getKey('startDate')
    if kz.getKey('status') == 'married':
        inames.append(kz.getKey('iname1'))
        yobs.append(kz.getKey('yob1'))
        life.append(kz.getKey('life1'))

    try:
        strio = StringIO()
        kz.storeKey('logs', strio)
        # print(inames, yobs, life, name, startDate)
        plan = owl.Plan(inames, yobs, life, name, startDate=startDate,
                        verbose=True, logstreams=[strio, strio])
    except Exception as e:
        st.error("Failed creation of plan '%s': %s" % (name, e))
        return

    kz.setKey('plan', plan)

    val = kz.getKey('plots')
    if val is not None:
        plan.setDefaultPlots(val)
    st.toast("Created new case *'%s'*. You can now move to next page." % name)


def _checkPlan(func):
    """
    Decorator to check if plan was created properly.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        plan = kz.getKey('plan')
        if plan is None:
            st.error('Plan not yet created. Preventing to execute method %s().' % (func.__name__))
            return None
        return func(plan, *args, **kwargs)

    return wrapper


def getFixedIncome(ni, what):
    amounts = []
    ages = []
    for i in range(ni):
        amounts.append(kz.getKey(what+'Amt'+str(i)))
        ages.append(kz.getKey(what+'Age'+str(i)))

    return amounts, ages


def getAccountBalances(ni):
    bal = [[], [], []]
    accounts = ['txbl', 'txDef', 'txFree']
    for j, acc in enumerate(accounts):
        for i in range(ni):
            bal[j].append(kz.getKey(acc+str(i)))

    return bal


def getSolveParameters():
    maximize = kz.getKey('objective')
    if maximize is None:
        return None
    if 'spending' in maximize:
        objective = 'maxSpending'
    else:
        objective = 'maxBequest'

    options = {}
    optList = ['netSpending', 'maxRothConversion', 'noRothConversions',
               'withMedicare', 'bequest', 'solver']
    for opt in optList:
        val = kz.getKey(opt)
        if val is not None:
            options[opt] = val

    if kz.getKey('readRothX'):
        options['maxRothConversion'] = 'file'

    return objective, options


def prepareRun(plan):
    ni = 2 if kz.getKey('status') == 'married' else 1

    bal = getAccountBalances(ni)
    try:
        plan.setAccountBalances(taxable=bal[0], taxDeferred=bal[1], taxFree=bal[2])
    except Exception as e:
        st.error('Setting account balances failed: %s' % e)
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
        benfrac = [kz.getKey('benf0'), kz.getKey('benf1'), kz.getKey('benf2')]
        try:
            plan.setBeneficiaryFractions(benfrac)
        except Exception as e:
            st.error('Failed setting beneficiary fractions: %s' % e)
            return

        surplusFrac = kz.getKey('surplusFraction')
        try:
            plan.setSpousalDepositFraction(surplusFrac)
        except Exception as e:
            st.error('Failed setting beneficiary fractions: %s' % e)
            return

    setRates()


def isCaseUnsolved():
    if kz.getKey('plan') is None:
        return True
    return kz.getKey('caseStatus') != 'solved'


@_checkPlan
def caseStatus(plan):
    return plan.caseStatus


@_checkPlan
def runPlan(plan):
    prepareRun(plan)

    objective, options = getSolveParameters()
    try:
        plan.solve(objective, options=options)
    except Exception as e:
        st.error('Solution failed: %s' % e)
        kz.storeKey('caseStatus', 'exception')
        kz.storeKey('summary', '')
        return

    kz.storeKey('caseStatus', plan.caseStatus)
    if plan.caseStatus == 'solved':
        kz.storeKey('summary', plan.summaryString())
    else:
        kz.storeKey('summary', '')


@_checkPlan
def runHistorical(plan):
    prepareRun(plan)

    hyfrm = kz.getKey('hyfrm')
    hyto = kz.getKey('hyto')

    objective, options = getSolveParameters()
    try:
        mybar = progress.Progress(None)
        fig, summary = plan.runHistoricalRange(objective, options, hyfrm, hyto, figure=True, progcall=mybar)
        kz.storeKey('histoPlot', fig)
        kz.storeKey('histoSummary', summary)
    except Exception as e:
        kz.storeKey('histoPlot', None)
        kz.storeKey('histoSummary', None)
        kz.storeKey('caseStatus', 'exception')
        st.error('Solution failed: %s' % e)
        setRates()
        return

    kz.storeKey('caseStatus', 'ran Historical Range')
    setRates()


@_checkPlan
def runMC(plan):
    prepareRun(plan)

    N = kz.getKey('MC_cases')

    objective, options = getSolveParameters()
    try:
        mybar = progress.Progress(None)
        fig, summary = plan.runMC(objective, options, N, figure=True, progcall=mybar)
        kz.storeKey('monteCarloPlot', fig)
        kz.storeKey('monteCarloSummary', summary)
    except Exception as e:
        kz.storeKey('monteCarloPlot', None)
        kz.storeKey('monteCarloSummary', None)
        kz.storeKey('caseStatus', 'exception')
        st.error('Solution failed: %s' % e)
        return

    kz.storeKey('caseStatus', 'ran Monte Carlo')


@_checkPlan
def setRates(plan):
    yfrm = kz.getKey('yfrm')
    yto = kz.getKey('yto')

    if kz.getKey('rateType') == 'fixed':
        if kz.getKey('fixedType') == 'historical average':
            plan.setRates('historical average', yfrm, yto)
            # Set fxRates back to computed values.
            for j in range(4):
                kz.storeKey('fxRate'+str(j), 100*plan.tau_kn[j, -1])
        else:
            plan.setRates('user', values=[float(kz.getKey('fxRate0')),
                                          float(kz.getKey('fxRate1')),
                                          float(kz.getKey('fxRate2')),
                                          float(kz.getKey('fxRate3')), ])
    else:
        varyingType = kz.getKey('varyingType')
        if varyingType.startswith('histo'):
            if varyingType == 'historical':
                yfrm2 = min(yfrm, TO-plan.N_n+1)
                kz.storeKey('yfrm', yfrm2)
                if yfrm != yfrm2:
                    yfrm = yfrm2
                    st.warning('Using %d as Starting year.' % yfrm)
                yto = min(TO, yfrm+plan.N_n-1)
                kz.storeKey('yto', yto)
            plan.setRates(varyingType, yfrm, yto)
            mean, stdev, corr, covar = owl.getRatesDistributions(yfrm, yto, plan.mylog)
            for j in range(4):
                kz.storeKey('mean'+str(j), 100*mean[j])
                kz.storeKey('stdev'+str(j), 100*stdev[j])
            q = 1
            for k1 in range(plan.N_k):
                for k2 in range(k1+1, plan.N_k):
                    kz.storeKey('corr'+str(q), corr[k1, k2])
                    q += 1

        elif varyingType == 'stochastic':
            means = []
            stdev = []
            corr = []
            for kk in range(plan.N_k):
                means.append(kz.getKey('mean'+str(kk)))
                stdev.append(kz.getKey('stdev'+str(kk)))
            for q in range(1, 7):
                corr.append(kz.getKey('corr'+str(q)))
            plan.setRates(varyingType, values=means, stdev=stdev, corr=corr)
        else:
            raise RuntimeError('Logic error in setRates()')

    return True


@_checkPlan
def showAllocations(plan):
    figures = plan.showAllocations(figure=True)
    st.divider()
    st.markdown('#### Asset Allocation')
    n = 3 if kz.getKey('allocType') == 'account' else 2
    c = 0
    cols = st.columns(n, gap='small')
    for fig in figures:
        cols[c].pyplot(fig)
        c = (c + 1) % n


@_checkPlan
def showProfile(plan):
    fig = plan.showProfile(figure=True)
    if fig:
        st.pyplot(fig)


@_checkPlan
def showRates(plan, col):
    fig = plan.showRates(figure=True)
    if fig:
        col.write('#### Selected rates over time horizon')
        col.pyplot(fig)


@_checkPlan
def showRatesCorrelations(plan, col):
    fig = plan.showRatesCorrelations(figure=True)
    if fig:
        col.write('#### Correlations between return rates')
        col.pyplot(fig)


@_checkPlan
def showIncome(plan):
    fig = plan.showIncome(figure=True)
    if fig:
        st.pyplot(fig)


@_checkPlan
def showSources(plan):
    fig = plan.showSources(figure=True)
    if fig:
        st.pyplot(fig)


@_checkPlan
def setInterpolationMethod(plan):
    plan.setInterpolationMethod(kz.getKey('interpMethod'), kz.getKey('interpCenter'), kz.getKey('interpWidth'))


@_checkPlan
def readContributions(plan, stFile):
    if stFile is None:
        return False

    try:
        plan.readContributions(stFile)
        kz.setKey('timeListsFileName', stFile.name)
        plan.timeListsFileName = stFile.name
    except Exception as e:
        st.error("Failed to parse contribution file '%s': %s" % (stFile.name, e))
        return False

    return True


@_checkPlan
def resetContributions(plan):
    return plan.resetContributions()


@_checkPlan
def setAllocationRatios(plan):
    if kz.getKey('allocType') == 'individual':
        try:
            generic = getIndividualAllocationRatios()
            plan.setAllocationRatios('individual', generic=generic)
        except Exception as e:
            st.error('Setting asset allocations failed: %s' % e)
            return
    elif kz.getKey('allocType') == 'account':
        try:
            acc = getAccountAllocationRatios()
            plan.setAllocationRatios('account', taxable=acc[0], taxDeferred=acc[1], taxFree=acc[2])
        except Exception as e:
            st.error('Setting asset allocations failed: %s' % e)
            return


def getIndividualAllocationRatios():
    generic = []
    initial = []
    final = []
    for k1 in range(4):
        initial.append(int(kz.getKey('j3_init%'+str(k1)+'_0')))
        final.append(int(kz.getKey('j3_fin%'+str(k1)+'_0')))
    gen0 = [initial, final]
    generic = [gen0]

    if kz.getKey('status') == 'married':
        initial = []
        final = []
        for k1 in range(4):
            initial.append(int(kz.getKey('j3_init%'+str(k1)+'_1')))
            final.append(int(kz.getKey('j3_fin%'+str(k1)+'_1')))
        gen1 = [initial, final]
        generic.append(gen1)

    return generic


def getAccountAllocationRatios():
    accounts = [[], [], []]
    for j1 in range(3):
        initial = []
        final = []
        for k1 in range(4):
            initial.append(int(kz.getKey(f'j{j1}_init%'+str(k1)+'_0')))
            final.append(int(kz.getKey(f'j{j1}_fin%'+str(k1)+'_0')))
        tmp = [initial, final]
        accounts[j1].append(tmp)

    if kz.getKey('status') == 'married':
        for j1 in range(3):
            initial = []
            final = []
            for k1 in range(4):
                initial.append(int(kz.getKey(f'j{j1}_init%'+str(k1)+'_1')))
                final.append(int(kz.getKey(f'j{j1}_fin%'+str(k1)+'_1')))
            tmp = [initial, final]
            accounts[j1].append(tmp)

    return accounts


@_checkPlan
def plotSingleResults(plan):
    c = 0
    n = 3
    cols = st.columns(n, gap='medium')
    fig = plan.showRates(figure=True)
    if fig:
        cols[c].write('#### Annual Rates')
        cols[c].pyplot(fig)
        c = (c + 1) % n

    fig = plan.showNetSpending(figure=True)
    if fig:
        cols[c].write('#### Net Available Spending')
        cols[c].pyplot(fig)
        c = (c + 1) % n

    fig = plan.showGrossIncome(figure=True)
    if fig:
        cols[c].write('#### Taxable Ordinary Income')
        cols[c].pyplot(fig)
        c = (c + 1) % n

    cols = st.columns(n, gap='medium')
    fig = plan.showSources(figure=True)
    if fig:
        cols[c].write('#### Raw Income Sources')
        cols[c].pyplot(fig)
        c = (c + 1) % n

    fig = plan.showAccounts(figure=True)
    if fig:
        cols[c].write('#### Savings Balance')
        cols[c].pyplot(fig)
        c = (c + 1) % n

    fig = plan.showTaxes(figure=True)
    if fig:
        cols[c].write('#### Taxes and Medicare (incl. IRMAA)')
        cols[c].pyplot(fig)
        c = (c + 1) % n

    c = 0
    figs = plan.showAssetDistribution(figure=True)
    if figs:
        st.write('#### Assets Distribution')
        morecols = st.columns(3, gap='small')
        for fig in figs:
            morecols[c].pyplot(fig)
            c = (c + 1) % 3


@_checkPlan
def setProfile(plan, key, pull=True):
    if pull:
        kz.setpull(key)
    profile = kz.getKey('spendingProfile')
    survivor = kz.getKey('survivor')
    smileDip = kz.getKey('smileDip')
    smileIncrease = kz.getKey('smileIncrease')
    plan.setSpendingProfile(profile, survivor, smileDip, smileIncrease)


@_checkPlan
def setHeirsTaxRate(plan, key):
    val = kz.setpull(key)
    plan.setHeirsTaxRate(val)


@_checkPlan
def setLongTermCapitalTaxRate(plan, key):
    val = kz.setpull(key)
    plan.setLongTermCapitalTaxRate(val)


@_checkPlan
def setDividendRate(plan, key):
    val = kz.setpull(key)
    plan.setDividendRate(val)


@_checkPlan
def setDefaultPlots(plan, key):
    val = kz.storepull(key)
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
def saveCaseFile(plan):
    stringBuffer = StringIO()
    # prepareRun(plan)
    if getSolveParameters() is None:
        return ''
    plan.saveConfig(stringBuffer)
    encoded_data = stringBuffer.getvalue().encode('utf-8')
    bytesBuffer = BytesIO(encoded_data)

    return bytesBuffer


def createCaseFromFile(file):
    strio = StringIO()
    try:
        mystringio = StringIO(file.read().decode('utf-8'))
        plan = owl.readConfig(mystringio, logstreams=[strio], readContributions=False)
    except Exception as e:
        st.error('Failed to parse case file: %s' % (e))
        return '', {}

    name, mydic = genDic(plan)
    mydic['logs'] = strio

    return name, mydic

    # keynames = ['name', 'status', 'plan', 'summary', 'logs', 'startDate',
    #            'timeList', 'plots', 'interpMethod', 'interpCenter', 'interpWidth',
    #            'objective', 'withMedicare', 'bequest', 'netSpending',
    #            'noRothConversions', 'maxRothConversion',
    #            'rateType', 'fixedType', 'varyingType', 'yfrm', 'yto',
    #            'divRate', 'heirsTx', 'gainTx', 'spendingProfile', 'survivor',
    #            'surplusFraction', ]
    # keynamesJ = ['benf', ]
    # keynamesK = ['fxRate', 'mean', 'stdev']
    # keynamesI = ['iname', 'yob', 'life', 'txbl', 'txDef', 'txFree',
    #             'ssAge', 'ssAmt', 'pAge', 'pAmt', 'df',
    #             'jX_init%0_', 'jX_init%1_', 'jX_init%2_', 'jX_init%3_',
    #             'jX_fin%0_', 'jX_fin%1_', 'jX_fin%2_', 'jX_fin%3_']
    # keynames6 = ['corr']


# @_checkPlan
def genDic(plan):
    accName = ['txbl', 'txDef', 'txFree']
    dic = {}
    dic['plan'] = plan
    dic['name'] = plan._name
    dic['summary'] = ''
    dic['caseStatus'] = 'new'
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
    dic['interpMethod'] = plan.interpMethod
    dic['interpCenter'] = plan.interpCenter
    dic['interpWidth'] = plan.interpWidth
    dic['spendingProfile'] = plan.spendingProfile
    dic['survivor'] = 100*plan.chi
    dic['gainTx'] = 100*plan.psi
    dic['divRate'] = 100*plan.mu
    dic['heirsTx'] = 100*plan.nu
    dic['surplusFraction'] = plan.eta
    dic['plots'] = plan.defaultPlots
    dic['allocType'] = plan.ARCoord
    dic['timeListsFileName'] = plan.timeListsFileName
    for j1 in range(plan.N_j):
        dic['benf'+str(j1)] = plan.phi_j[j1]

    for i in range(plan.N_i):
        dic['iname'+str(i)] = plan.inames[i]
        dic['yob'+str(i)] = plan.yobs[i]
        dic['life'+str(i)] = plan.expectancy[i]
        dic['ssAge'+str(i)] = plan.ssecAges[i]
        dic['ssAmt'+str(i)] = plan.ssecAmounts[i]/1000
        dic['pAge'+str(i)] = plan.pensionAges[i]
        dic['pAmt'+str(i)] = plan.pensionAmounts[i]/1000
        for j1 in range(plan.N_j):
            dic[accName[j1]+str(i)] = plan.beta_ij[i, j1]/1000

        if plan.ARCoord == 'individual':
            for k1 in range(plan.N_k):
                dic['j3_init%'+str(k1)+'_'+str(i)] = int(plan.boundsAR['generic'][i][0][k1])
                dic['j3_fin%'+str(k1)+'_'+str(i)] = int(plan.boundsAR['generic'][i][1][k1])
        elif plan.ARCoord == 'account':
            longAccName = ['taxable', 'tax-deferred', 'tax-free']
            for j2 in range(3):
                for k2 in range(plan.N_k):
                    dic[f'j{j2}%d_init%'+str(k2)+'_'+str(i)] = int(plan.boundsAR[longAccName[j2]][i][0][k2])
                    dic[f'j{j2}_fin%'+str(k2)+'_'+str(i)] = int(plan.boundsAR[longAccName[j2]][i][1][k2])
        else:
            st.error("Only 'individual' and 'account' asset allocations are currently supported")
            return None

    optionKeys = list(plan.solverOptions)
    for key in ['maxRothConversion', 'noRothConversions', 'withMedicare', 'netSpending', 'bequest']:
        if key in optionKeys:
            dic[key] = plan.solverOptions[key]

    if plan.objective == 'maxSpending':
        dic['objective'] = 'Net spending'
    else:
        dic['objective'] = 'Bequest'

    if plan.rateMethod in ['default', 'conservative', 'optimistic', 'historical average', 'user']:
        dic['rateType'] = 'fixed'
        dic['fixedType'] = plan.rateMethod
    elif plan.rateMethod in ['histochastic', 'historical', 'stochastic']:
        dic['rateType'] = 'varying'
        dic['varyingType'] = plan.rateMethod

    # Initialize in both cases.
    for k1 in range(plan.N_k):
        dic['fxRate'+str(k1)] = 100*plan.rateValues[k1]

    if plan.rateMethod in ['historical average', 'histochastic', 'historical']:
        dic['yfrm'] = plan.rateFrm
        dic['yto'] = plan.rateTo
    else:
        dic['yfrm'] = FROM
        # Rates avalability are trailing by 1 or 2 years.
        dic['yto'] = date.today().year - 2

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
