from datetime import date
import streamlit as st

import sskeys as k
import owlbridge as owb


caseChoices = k.allCaseNames()
ret = k.titleBar('setup', caseChoices)
st.write("## Basic Info\n:orange[*%s*]" % k.currentCaseName())

if ret == k.newCase:
    st.info('Starting a new case from scratch.\n\nA name for the scenario must first be provided.')
    st.text_input("Case name", value='', key='_newcase',
                  on_change=k.createNewCase, args=['newcase'], placeholder='Enter a name...')
elif ret == k.loadCaseFile:
    st.info('Starting a case from a *case* file.\n\nLook at the :material/help: Documentation for where to find examples.')
    confile = st.file_uploader('Upload *case* file...', key='_confile', type=['toml'])
    if confile is not None:
        if k.createCaseFromFile(confile):
            st.rerun()
else:
    helpmsg = "Case name can be changed by editing it directly"
    name = st.text_input('Case name',
                         value=k.currentCaseName(),
                         on_change=k.renameCase, args=['caseNewName'], key='_caseNewName',
                         placeholder='Enter a name', help=helpmsg)

    diz1 = (k.getKey('plan') is not None)
    diz2 = diz1
    # diz2 = (diz1 or len(k.allCaseNames()) > 3)
    statusChoices = ['single', 'married']
    k.initKey('status', statusChoices[0])
    st.radio('Marital status', statusChoices, disabled=diz2,
             index=statusChoices.index(k.getKey('status')), key='_status',
             on_change=k.setpull, args=['status'], horizontal=True)

    col1, col2 = st.columns(2, gap='large', vertical_alignment='top')
    with col1:
        k.initKey('iname0', '')
        if k.getKey('iname0') == '':
            st.info('First name must be provided.')

        iname0 = k.getText('Your first name', 'iname0', disabled=diz2, placeholder='Enter name...')

        k.initKey('yob0', 1965)
        ret = k.getIntNum("%s's birth year" % iname0, 'yob0', disabled=diz2)

        k.initKey('life0', 80)
        ret = k.getIntNum("%s's expected longevity" % iname0, 'life0', disabled=diz1)

        today = date.today()
        thisyear = today.year
        k.initKey('startDate', today)
        ret = st.date_input("Plan's starting date on first year",
                            min_value=date(thisyear, 1, 1), max_value=date(thisyear, 12, 31),
                            value=k.getKey('startDate'), key='_startDate', args=['startDate'],
                            on_change=k.setpull, disabled=diz2)

    with col2:
        if k.getKey('status') == 'married':
            k.initKey('iname1', '')
            if k.getKey('iname1') == '':
                st.info('First name must be provided.')

            iname1 = k.getText("Your spouse's first name", 'iname1', disabled=diz2, placeholder='Enter a name...')

            k.initKey('yob1', 1965)
            ret = k.getIntNum("%s's birth year" % iname1, 'yob1', disabled=diz2)

            k.initKey('life1', 80)
            ret = k.getIntNum("%s's expected longevity" % iname1, 'life1', disabled=diz1)

    st.divider()
    cantcreate = k.isIncomplete() or diz1
    if not cantcreate and k.getKey('plan') is None:
        st.info('Plan needs to be created once all the information needed has been entered.')

    cantmodify = (k.currentCaseName() == k.newCase or k.currentCaseName() == k.loadCaseFile)
    cantcopy = cantmodify or k.caseHasNoPlan()
    col1, col2, col3 = st.columns(3, gap='small', vertical_alignment='top')
    with col1:
        st.button('Create case :material/add:', on_click=owb.createPlan, disabled=cantcreate)
    with col2:
        st.button('Duplicate case :material/content_copy:', on_click=k.duplicateCase, disabled=cantcopy)
    with col3:
        st.button('Delete case :material/delete:', on_click=k.deleteCurrentCase, disabled=cantmodify)
        # st.error("Do you really, really, wanna do this?")
        # if st.button("Yes"):
        # run_expensive_function()
