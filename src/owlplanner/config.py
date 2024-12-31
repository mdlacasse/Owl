"""

Owl/conftoml

This file contains utility functions to save configuration parameters.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.
"""

import toml as toml
from io import StringIO, BytesIO
import numpy as np
import os
from datetime import date

from owlplanner import plan
from owlplanner import logging


def saveConfig(plan, file, mylog):
    """
    Save config and return a dictionary containing configuration parameters.
    """
    accountTypes = ['taxable', 'tax-deferred', 'tax-free']

    diconf = {}
    diconf['Plan Name'] = plan._name

    # Basic Info.
    diconf['Basic Info'] = {'Status': ['unknown', 'single', 'married'][plan.N_i],
                            'Names': plan.inames,
                            'Birth year': plan.yobs.tolist(),
                            'Life expectancy': plan.expectancy.tolist(),
                            'Start date': plan.startDate,
                            }

    # Assets.
    diconf['Assets'] = {}
    for j in range(plan.N_j):
        amounts = plan.beta_ij[:, j] / 1000
        diconf['Assets']['%s savings balances' % accountTypes[j]] = amounts.tolist()
    if plan.N_i == 2:
        diconf['Assets']['Beneficiary fractions'] = plan.phi_j.tolist()
        diconf['Assets']['Spousal surplus deposit fraction'] = plan.eta

    # Wages and Contributions.
    diconf['Wages and Contributions'] = {'Contributions file name': plan.timeListsFileName}

    # Fixed Income.
    diconf['Fixed Income'] = {'Pension amounts': (plan.pensionAmounts/1000).tolist(),
                              'Pension ages': plan.pensionAges.tolist(),
                              'Social security amounts': (plan.ssecAmounts/1000).tolist(),
                              'Social security ages': plan.ssecAges.tolist(),
                              }

    # Rate Selection.
    diconf['Rate Selection'] = {'Heirs rate on tax-deferred estate': float(100 * plan.nu),
                                'Long-term capital gain tax rate': float(100 * plan.psi),
                                'Dividend tax rate': float(100 * plan.mu),
                                'Method': plan.rateMethod,
                                }
    if plan.rateMethod in ['user', 'stochastic']:
        diconf['Rate Selection']['Values'] = [100 * k for k in plan.rateValues]
    if plan.rateMethod in ['stochastic']:
        diconf['Rate Selection']['Standard deviations'] = [100 * k for k in plan.rateStdev]
        diconf['Rate Selection']['Correlations'] = plan.rateCorr
    if plan.rateMethod in ['historical average', 'historical', 'histochastic']:
        diconf['Rate Selection']['From'] = int(plan.rateFrm)
        diconf['Rate Selection']['To'] = int(plan.rateTo)
    else:
        diconf['Rate Selection']['From'] = int(1928)
        diconf['Rate Selection']['To'] = int(date.today().year - 1)

    # Asset Allocations.
    diconf['Asset Allocations'] = {'Interpolation method': plan.interpMethod,
                                   'Interpolation center': plan.interpCenter,
                                   'Interpolation width': plan.interpWidth,
                                   'Type': plan.ARCoord,
                                   }
    if plan.ARCoord == 'account':
        for accType in accountTypes:
            diconf['Asset Allocations'][accType] = plan.boundsAR[accType]
    else:
        diconf['Asset Allocations']['generic'] = plan.boundsAR['generic']

    # Optimization Parameters.
    diconf['Optimization Parameters'] = {
                                         'Spending profile': plan.spendingProfile,
                                         'Surviving spouse spending percent': float(100 * plan.chi),
                                         'Objective': plan.objective,
                                        }

    diconf['Solver Options'] = plan.solverOptions

    # Results.
    diconf['Results'] = {'Default plots': plan.defaultPlots}

    if isinstance(file, str):
        if '.toml' not in file:
            filename = file + '.toml'
        mylog.vprint("Saving plan configuration to '%s'." % filename)

        try:
            with open(filename, 'w') as configfile:
                toml.dump(diconf, configfile)
        except Exception as e:
            raise RuntimeError('Failed to save config file %s: %s' % (filename, e))
    elif isinstance(file, StringIO):
        try:
            string = toml.dumps(diconf)
            file.write(string)
        except Exception as e:
            raise RuntimeError('Failed to save config to stringio: %s', e)
    elif file is None:
        pass
    else:
        raise ValueError('Argument %s has unknown type' % type(file))

    return diconf


def readConfig(file, *, verbose=True, logstreams=None, readContributions=True):
    """
    Read plan configuration parameters from file *basename*.toml.
    A new plan is created and returned.
    Argument file can be a filename, a file, or a stringIO.
    """
    mylog = logging.Logger(verbose, logstreams)

    accountTypes = ['taxable', 'tax-deferred', 'tax-free']

    dirname = ''
    if isinstance(file, str):
        dirname = os.path.dirname(file)
        if '.toml' not in file:
            filename = file + '.toml'

        mylog.vprint("Reading plan configuration from '%s'." % filename)

        try:
            with open(filename, 'r') as f:
                diconf = toml.load(f)
        except Exception as e:
            raise FileNotFoundError('File %s not found: %s' % (filename, e))
    elif isinstance(file, BytesIO):
        try:
            string = file.getvalue().decode('utf-8')
            diconf = toml.loads(string)
        except Exception as e:
            raise RuntimeError('Cannot read from BytesIO: %s' % e)
    elif isinstance(file, StringIO):
        try:
            string = file.getvalue()
            diconf = toml.loads(string)
        except Exception as e:
            raise RuntimeError('Cannot read from StringIO: %s' % e)
    else:
        raise ValueError('%s not a valid type' % type(file))

    # Basic Info.
    name = diconf['Plan Name']
    inames = diconf['Basic Info']['Names']
    # status = diconf['Basic Info']['Status']
    yobs = diconf['Basic Info']['Birth year']
    expectancy = diconf['Basic Info']['Life expectancy']
    startDate = diconf['Basic Info']['Start date']
    icount = len(yobs)

    mylog.vprint('Plan for %d individual%s: %s.' % (icount, ['', 's'][icount - 1], inames))
    p = plan.Plan(inames, yobs, expectancy, name, startDate=startDate, verbose=True, logstreams=logstreams)

    # Assets.
    balances = {}
    for acc in accountTypes:
        balances[acc] = diconf['Assets']['%s savings balances' % acc]
    p.setAccountBalances(taxable=balances['taxable'], taxDeferred=balances['tax-deferred'],
                         taxFree=balances['tax-free'])
    if icount == 2:
        phi_j = diconf['Assets']['Beneficiary fractions']
        p.setBeneficiaryFractions(phi_j)
        eta = diconf['Assets']['Spousal surplus deposit fraction']
        p.setSpousalDepositFraction(eta)

    # Wages and Contributions.
    timeListsFileName = diconf['Wages and Contributions']['Contributions file name']
    if timeListsFileName != 'None':
        if readContributions:
            if os.path.exists(timeListsFileName):
                myfile = timeListsFileName
            elif dirname != '' and os.path.exists(dirname + '/' + timeListsFileName):
                myfile = dirname + '/' + timeListsFileName
            else:
                raise FileNotFoundError("File '%s' not found." % timeListsFileName)
            p.readContributions(myfile)
        else:
            mylog.vprint('Ignoring to read contributions file %s.' % timeListsFileName)

    # Fixed Income.
    ssecAmounts = np.array(diconf['Fixed Income']['Social security amounts'])
    # values = diconf['Fixed Income']['Social security ages']
    ssecAges = np.array(diconf['Fixed Income']['Social security ages'], dtype=np.int32)
    p.setSocialSecurity(ssecAmounts, ssecAges)
    pensionAmounts = np.array(diconf['Fixed Income']['Pension amounts'])
    pensionAges = np.array(diconf['Fixed Income']['Pension ages'], dtype=np.int32)
    p.setPension(pensionAmounts, pensionAges)

    # Rate Selection.
    p.setDividendRate(diconf['Rate Selection']['Dividend tax rate'])
    p.setLongTermCapitalTaxRate(diconf['Rate Selection']['Long-term capital gain tax rate'])
    p.setHeirsTaxRate(diconf['Rate Selection']['Heirs rate on tax-deferred estate'])

    frm = None
    to = None
    rateValues = None
    stdev = None
    rateCorr = None
    rateMethod = diconf['Rate Selection']['Method']
    if rateMethod in ['historical average', 'historical', 'histochastic']:
        frm = diconf['Rate Selection']['From']
        if not isinstance(frm, int):
            frm = int(frm)
        to = int(diconf['Rate Selection']['To'])
        if not isinstance(to, int):
            to = int(to)
    if rateMethod in ['user', 'stochastic']:
        rateValues = np.array(diconf['Rate Selection']['Values'])
    if rateMethod in ['stochastic']:
        stdev = np.array(diconf['Rate Selection']['Standard deviations'], dtype='float64')
        rateCorr = np.array(diconf['Rate Selection']['Correlations'], dtype='float64')
    p.setRates(rateMethod, frm, to, rateValues, stdev, rateCorr)

    # Asset Allocation.
    boundsAR = {}
    p.setInterpolationMethod(
        diconf['Asset Allocations']['Interpolation method'],
        float(diconf['Asset Allocations']['Interpolation center']),
        float(diconf['Asset Allocations']['Interpolation width']),
    )
    allocType = diconf['Asset Allocations']['Type']
    if allocType == 'account':
        for aType in accountTypes:
            boundsAR[aType] = np.array(diconf['Asset Allocations'][aType])

        p.setAllocationRatios(
            allocType,
            taxable=boundsAR['taxable'],
            taxDeferred=boundsAR['tax-deferred'],
            taxFree=boundsAR['tax-free'],
        )
    elif allocType == 'individual' or allocType == 'spouses':
        boundsAR['generic'] = np.array(diconf['Asset Allocations']['generic'])
        p.setAllocationRatios(
            allocType,
            generic=boundsAR['generic'],
        )
    else:
        raise ValueError('Unknown asset allocation type %s.' % allocType)

    # Optimization Parameters.
    p.objective = diconf['Optimization Parameters']['Objective']
    p.setSpendingProfile(
        diconf['Optimization Parameters']['Spending profile'],
        float(diconf['Optimization Parameters']['Surviving spouse spending percent'])
    )

    # Solver Options.
    p.solverOptions = diconf['Solver Options']

    # Results.
    p.setDefaultPlots(diconf['Results']['Default plots'])

    return p
