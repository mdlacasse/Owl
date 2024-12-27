"""

Owl/config

This file contains utility functions to save configuration parameters.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.
"""

import configparser
import numpy as np
from io import StringIO, BytesIO

from owlplanner import plan
from owlplanner import logging


def saveConfig(plan, file, mylog):
    """
    Save plan configuration parameters to a file named *basename*.ini.
    Argument file can be a 'filename', or a 'stringio' object.
    """
    accountTypes = ['taxable', 'tax-deferred', 'tax-free']

    config = configparser.ConfigParser()

    config['Who'] = {
        'Count': str(plan.N_i),
        'Names': ','.join(str(k) for k in plan.inames),
    }

    # Parameters getting one value for each spouse.
    config['YOB'] = {}
    config['Life expectancy'] = {}
    config['Pension amounts'] = {}
    config['Pension ages'] = {}
    config['Social security amounts'] = {}
    config['Social security ages'] = {}
    config['Asset balances'] = {}
    config['Solver'] = {}

    for i in range(plan.N_i):
        config['YOB'][plan.inames[i]] = str(plan.yobs[i])
        config['Life expectancy'][plan.inames[i]] = str(plan.expectancy[i])
        config['Pension amounts'][plan.inames[i]] = str(plan.pensionAmounts[i])
        config['Pension ages'][plan.inames[i]] = str(plan.pensionAges[i])
        config['Social security amounts'][plan.inames[i]] = str(plan.ssecAmounts[i])
        config['Social security ages'][plan.inames[i]] = str(plan.ssecAges[i])
        for j in range(len(accountTypes)):
            config['Asset balances'][accountTypes[j] + ' ' + plan.inames[i]] = str(plan.beta_ij[i][j])

    # Joint parameters.
    config['Parameters'] = {
        'Plan name': plan._name,
        'Starting date': plan.startDate,
        'Spending profile': str(plan.spendingProfile),
        'Surviving spouse spending percent': str(100 * plan.chi),
        'Interpolation method': str(plan.interpMethod),
        'Interpolation center': str(plan.interpCenter),
        'Interpolation width': str(plan.interpWidth),
        'Default plots': str(plan.defaultPlots),
        'Heirs rate on tax-deferred estate': str(100 * plan.nu),
        'Spousal surplus deposit fraction': str(plan.eta),
        'Long-term capital gain tax rate': str(100 * plan.psi),
        'Dividend tax rate': str(100 * plan.mu),
        'Beneficiary fractions': str(plan.phi_j.tolist()),
        'Contributions file name': str(plan.timeListsFileName),
    }

    # Asset allocations
    config['Asset allocations'] = {}
    config['Asset allocations']['type'] = str(plan.ARCoord)
    if plan.ARCoord == 'account':
        for aType in accountTypes:
            config['Asset allocations'][aType] = str(plan.boundsAR[aType])
    else:
        config['Asset allocations']['generic'] = str(plan.boundsAR['generic'])

        # ', '.join(str(100 * k) for i,k in plan.boundsAR[aType][:][:])

    config['Rates'] = {
        'Method': str(plan.rateMethod),
        'From': str(plan.rateFrm),
        'To': str(plan.rateTo),
    }
    if plan.rateMethod in ['user', 'stochastic']:
        config['Rates']['values'] = ', '.join(str(100 * k) for k in plan.rateValues)
    if plan.rateMethod in ['stochastic']:
        config['Rates']['standard deviations'] = ', '.join(str(100 * k) for k in plan.rateStdev)
        flat_corr = plan.rateCorr.flatten()
        config['Rates']['correlations'] = ', '.join(str(k) for k in flat_corr)

    config['Solver']['Options'] = str(plan.solverOptions)
    config['Solver']['Objective'] = plan.objective

    if isinstance(file, str):
        if '.ini' in file:
            filename = file
        else:
            filename = file + '.ini'
        mylog.vprint("Saving plan configuration to '%s'." % filename)

        with open(filename, 'w') as configfile:
            config.write(configfile)
    elif isinstance(file, StringIO):
        try:
            config.write(file)
        except Exception as e:
            raise RuntimeError('Failed to save config to stringio: %s', e)
    else:
        raise ValueError('Argument %s has unknown type' % type(file))

    return


def readConfig(file, *, logstreams=None):
    """
    Read plan configuration parameters from file *basename*.ini.
    A new plan is created and returned.
    file can be a 'filename', a 'file', or 'stringIO'.
    """
    import configparser
    import ast

    mylog = logging.Logger(logstreams=logstreams)

    accountTypes = ['taxable', 'tax-deferred', 'tax-free']

    config = configparser.ConfigParser()

    if isinstance(file, str):
        if '.ini' in file:
            filename = file
        else:
            filename = file + '.ini'
        mylog.vprint("Reading plan configuration from '%s'." % filename)

        ret = config.read(filename)
        if ret == []:
            raise FileNotFoundError('File %s not found.' % (filename))
    elif isinstance(file, BytesIO):
        filename = 'fp'
        ret = config.read_file(file)
        if ret == []:
            raise RuntimeError('Cannot read from file.')
    elif isinstance(file, StringIO):
        ret = config.read_string(file.getvalue())
        if ret == []:
            raise RuntimeError('Cannot read from string.')
    else:
        raise ValueError('%s not a valid type' % type(file))

    icount = int(config['Who']['Count'])
    inames = config['Who']['Names'].split(',')
    name = config['Parameters']['Plan name']
    startDate = config['Parameters']['Starting date']
    mylog.vprint('Plan for %d individual%s: %s.' % (icount, ['', 's'][icount - 1], inames))

    # Parameters getting one value for each spouse.
    yobs = []
    expectancy = []
    pensionAmounts = []
    pensionAges = []
    ssecAmounts = []
    ssecAges = []
    boundsAR = {}
    balances = {}

    for aType in accountTypes:
        balances[aType] = []

    for i in range(icount):
        yobs.append(int(config['YOB'][inames[i]]))
        expectancy.append(int(config['Life expectancy'][inames[i]]))
        pensionAmounts.append(float(config['Pension amounts'][inames[i]]))
        pensionAges.append(int(config['Pension ages'][inames[i]]))
        ssecAmounts.append(float(config['Social security amounts'][inames[i]]))
        ssecAges.append(int(config['Social security ages'][inames[i]]))
        for aType in accountTypes:
            balances[aType].append(float(config['Asset balances'][aType + ' ' + inames[i]]))

    p = plan.Plan(inames, yobs, expectancy, name, startDate=startDate, logstreams=logstreams)

    p.setSpousalDepositFraction(float(config['Parameters']['Spousal surplus deposit fraction']))
    p.setDefaultPlots(config['Parameters']['Default plots'])
    p.setDividendRate(float(config['Parameters']['Dividend tax rate']))
    p.setLongTermCapitalTaxRate(float(config['Parameters']['Long-term capital gain tax rate']))
    beneficiaryFractions = ast.literal_eval(config['Parameters']['Beneficiary fractions'])
    p.setBeneficiaryFractions(beneficiaryFractions)
    p.setHeirsTaxRate(float(config['Parameters']['Heirs rate on tax-deferred estate']))

    p.setPension(pensionAmounts, pensionAges, units=1)
    p.setSocialSecurity(ssecAmounts, ssecAges, units=1)

    p.setSpendingProfile(
        config['Parameters']['Spending profile'],
        float(config['Parameters']['Surviving spouse spending percent']),
    )

    rateMethod = config['Rates']['Method']
    frm = None
    to = None
    values = None
    stdev = None
    corr = None
    if rateMethod in ['user', 'stochastic']:
        values = config['Rates']['values'].split(',')
        values = np.array([float(k) for k in values])
        if rateMethod in ['stochastic']:
            stdev = config['Rates']['standard deviations'].split(',')
            stdev = np.array([float(k) for k in stdev])
            flat_corr = config['Rates']['correlations'].split(',')
            flat_corr = np.array([float(k) for k in flat_corr])
            corr = flat_corr.reshape((p.N_k, p.N_k))
    if rateMethod in ['historical', 'means', 'average', 'histochastic']:
        frm = int(config['Rates']['From'])
        to = int(config['Rates']['To'])

    p.setRates(rateMethod, frm, to, values, stdev, corr)

    p.setAccountBalances(
        taxable=balances['taxable'], taxDeferred=balances['tax-deferred'], taxFree=balances['tax-free'], units=1
    )

    p.setInterpolationMethod(
        config['Parameters']['Interpolation method'],
        float(config['Parameters']['Interpolation center']),
        float(config['Parameters']['Interpolation width']),
    )

    allocType = config['Asset allocations']['Type']
    if allocType == 'account':
        for aType in accountTypes:
            boundsAR[aType] = ast.literal_eval(config['Asset allocations'][aType])

        p.setAllocationRatios(
            allocType,
            taxable=boundsAR['taxable'],
            taxDeferred=boundsAR['tax-deferred'],
            taxFree=boundsAR['tax-free'],
        )
    elif allocType == 'individual' or allocType == 'spouses':
        boundsAR['generic'] = ast.literal_eval(config['Asset allocations']['generic'])
        p.setAllocationRatios(
            allocType,
            generic=boundsAR['generic'],
        )

    p.solverOptions = ast.literal_eval(config['Solver']['Options'])
    p.objective = str(config['Solver']['Objective'])

    timeListsFileName = config['Parameters']['Contributions file name']
    if timeListsFileName != 'None':
        p.readContributions(timeListsFileName)

    return p
