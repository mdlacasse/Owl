from datetime import date
import streamlit as st

import sskeys as k
import owlbridge as owb


caseChoices = k.allCaseNames()
ret = k.titleBar('setup', caseChoices)

# ret = k.titleBar('case')
st.divider()
st.write('## Case Setup')

if ret == k.newCase:
    st.info('A name for the scenario must be provided.')
    st.text_input("Case name", value='', key='_newcase',
                  on_change=k.createCase, placeholder='Enter a name...')
elif ret == k.loadConfig:
    st.info('A config file must be uploaded.')
    config = st.file_uploader('Upload configuration file...')
else:
    diz1 = (k.getKey('plan') is not None)
    diz2 = (diz1 or len(k.allCaseNames()) > 3)
    statusChoices = ['single', 'married']
    k.init('status', statusChoices[0])
    st.radio('Marital status', statusChoices, disabled=diz2,
             index=statusChoices.index(k.getKey('status')), key='_status',
             on_change=k.pull, args=['status'], horizontal=True)

    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        k.init('iname0', '')
        if k.getKey('iname0') == '':
            st.info('First name must be provided.')

        iname0 = k.getText('Your first name', 'iname0', disabled=diz2, placeholder='Enter name...')

        k.init('yob0', 1965)
        ret = k.getIntNum("%s's birth year" % iname0, 'yob0', disabled=diz2)

        k.init('life0', 80)
        ret = k.getIntNum("%s's expected longevity" % iname0, 'life0', disabled=diz1)

        today = date.today()
        thisyear = today.year
        k.init('startDate', today)
        ret = st.date_input("Plan's starting date on first year",
                            min_value=date(thisyear, 1, 1), max_value=date(thisyear, 12, 31),
                            value=k.getKey('startDate'), key='_startDate', args=['startDate'],
                            on_change=k.pull, disabled=diz2)

    with col2:
        if k.getKey('status') == 'married':
            k.init('iname1', '')
            if k.getKey('iname1') == '':
                st.info('First name must be provided.')

            iname1 = k.getText("Your spouse's first name", 'iname1', disabled=diz2, placeholder='Enter a name...')

            k.init('yob1', 1965)
            ret = k.getIntNum("%s's birth year" % iname1, 'yob1', disabled=diz2)

            k.init('life1', 80)
            ret = k.getIntNum("%s's expected longevity" % iname1, 'life1', disabled=diz1)

    st.divider()
    cantcreate = owb.isIncomplete() or diz1
    if not cantcreate and k.getKey('plan') is None:
        st.info('Plan needs to be created when all information has been entered.')

    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        st.button('Create case', on_click=owb.createPlan, disabled=cantcreate)
    with col2:
        cantdel = (k.currentCaseName() == k.newCase)
        st.button('Delete case', on_click=k.deleteCurrentCase, disabled=cantdel)
        # st.error("Do you really, really, wanna do this?")
        # if st.button("Yes"):
        # run_expensive_function()
