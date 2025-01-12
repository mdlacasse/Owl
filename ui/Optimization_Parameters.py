import streamlit as st

import sskeys as kz
import owlbridge as owb


profileChoices = ['smile', 'flat']
kz.initKey('spendingProfile', profileChoices[0])
kz.initKey('survivor', 60)
kz.initKey('smileDip', 15)
kz.initKey('smileIncrease', 12)


def initProfile():
    owb.setProfile(profileChoices[0], False)


kz.runOncePerCase(initProfile)

ret = kz.titleBar('opto')
kz.caseHeader("Optimization Parameters")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        choices = ['Net spending', 'Bequest']
        helpmsg = "Value is in today's \\$k."
        kz.initKey('objective', choices[0])
        ret = kz.getRadio("Maximize", choices, 'objective')

    with col2:
        if kz.getKey('objective') == 'Net spending':
            kz.initKey('bequest', 0)
            ret = kz.getNum("Desired bequest (\\$k)", 'bequest', help=helpmsg)

        else:
            kz.initKey('netSpending', 0)
            ret = kz.getNum("Desired annual net spending (\\$k)", 'netSpending', help=helpmsg)

    st.divider()
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        iname0 = kz.getKey('iname0')
        helpmsg = "Value is in nominal \\$k."
        kz.initKey('readRothX', False)
        fromFile = kz.getKey('readRothX')
        kz.initKey('maxRothConversion', 50)
        ret = kz.getNum("Maximum Roth conversion (\\$k)", 'maxRothConversion', disabled=fromFile, help=helpmsg)
        caseHasNoContributions = (kz.getKey('stTimeLists') is None)
        ret = kz.getToggle('Convert as in contributions file', 'readRothX', disabled=caseHasNoContributions)

    with col2:
        if kz.getKey('status') == 'married':
            iname1 = kz.getKey('iname1')
            choices = ['None', iname0, iname1]
            kz.initKey('noRothConversions', choices[0])
            helpmsg = "`None` means no exclusion. Set `Maximum Roth conversion` to 0 to exclude both spouses."
            ret = kz.getRadio("Exclude Roth conversions for...", choices,
                              "noRothConversions", help=helpmsg)

    st.divider()
    kz.initKey('withMedicare', True)
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        helpmsg = "Do or do not perform additional Medicare and IRMAA calculations."
        ret = kz.getToggle('Medicare and IRMAA calculations', 'withMedicare', help=helpmsg)
    with col2:
        if owb.hasMOSEK():
            choices = ['HiGHS', 'MOSEK']
            kz.initKey('solver', choices[0])
            ret = kz.getRadio('Solver', choices, 'solver')

    st.divider()
    col1, col2, col3, col4 = st.columns(4, gap='medium', vertical_alignment='top')
    with col1:
        ret = kz.getRadio("Spending profile", profileChoices, 'spendingProfile', callback=owb.setProfile)
    with col2:
        if kz.getKey('status') == 'married':
            ret = kz.getIntNum("Survivor's spending (%)", 'survivor', max_value=100, callback=owb.setProfile)
    with col3:
        if kz.getKey('spendingProfile') == 'smile':
            ret = kz.getIntNum("Smile dip (%)", 'smileDip', max_value=100, callback=owb.setProfile)
    with col4:
        if kz.getKey('spendingProfile') == 'smile':
            ret = kz.getIntNum("Smile increase (%)", 'smileIncrease', max_value=100, callback=owb.setProfile)

    st.divider()
    col1, col2 = st.columns(2, gap='small')
    with col1:
        st.write('#### Spending Profile')
        owb.showProfile()
