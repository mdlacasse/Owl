from datetime import date
import streamlit as st

import key as k
import owlplanner as owl


def isIncomplete():
    return (k.currentCaseName() == '' or k.getKey('iname0') == ''
            or (k.getKey('status') == 'married' and k.getKey('iname1') == ''))


def genPlan():
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
        print(inames, yobs, life, name, startDate)
        plan = owl.Plan(inames, yobs, life, name, startDate)
    except Exception as e:
        st.info('Failed plan creation %s.' % e)
        return
    k.store('plan', plan)


choices = k.allCaseNames()
nkey = 'case'
ret = st.selectbox('Select case', choices,
                    index=k.getIndex(k.currentCaseName(), choices), key='_'+nkey,
                    on_change=k.switchToCase, args=[nkey])

# ret = k.titleBar('case')
st.divider()
st.write('## Case Setup')

if ret == 'New case':
    st.info('A name for the scenario must be provided.')
    st.text_input("Enter case name", value='', key='_newcase', on_change=k.createCase)
    # k.switchToCase(ret)
else:
    diz = len(k.allCaseNames()) > 2
    choices = ['single', 'married']
    k.init('status', choices[0])
    st.radio('Marital status', choices, disabled=diz,
             index=choices.index(k.getKey('status')), key='_status',
             on_change=k.pull, args=['status'], horizontal=True)

    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        k.init('iname0', '')
        if k.getKey('iname0') == '':
            st.info('First name must be provided.')

        iname0 = k.getText('Your first name', 'iname0', disabled=diz)

        k.init('yob0', 1965)
        ret = k.getNum("%s's birth year" % iname0, 'yob0', disabled=diz)

        k.init('life0', 80)
        ret = k.getNum("%s's expected longevity" % iname0, 'life0')

        today = date.today()
        thisyear = today.year
        k.init('startDate', today)
        ret = st.date_input("Plan's starting date on first year",
                            min_value=date(thisyear, 1, 1), max_value=date(thisyear, 12, 31),
                            value=k.getKey('startDate'), key='_startDate', args=['startDate'],
                            on_change=k.pull)

    cantdel = (k.currentCaseName() == 'New case')
    st.button('Delete case', on_click=k.deleteCurrentCase, disabled=cantdel)

    with col2:
        if k.getKey('status') == 'married':
            k.init('iname1', '')
            if k.getKey('iname1') == '':
                st.info('First name must be provided.')

            iname1 = k.getText("Your spouse's first name", 'iname1', disabled=diz)

            k.init('yob1', 1965)
            ret = k.getNum("%s's birth year" % iname1, 'yob1', disabled=diz)

            k.init('life1', 80)
            ret = k.getNum("%s's expected longevity" % iname1, 'life1')

    st.button('Initialize plan', on_click=genPlan, disabled=isIncomplete())

