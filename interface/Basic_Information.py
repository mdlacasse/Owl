from datetime import date
import streamlit as st

import key as k
import owlplanner as owl


def checkStartDate(key):
    mydate = st.session_state['_'+key]
    mydatelist = mydate.split('/')
    if (len(mydatelist) != 2 or mydatelist[0] > 12 or mydatelist[1] > 31):
        st.info('Invalid date.')
        return False
    k.push(key)
    return True

    
def checkAllOK():
    ss = st.session_state
    return (ss.name == '' or ss.iname0 == '' 
            or (ss.status == 'married' and ss.iname1 == ''))


def genPlan():
    ss = st.session_state
    inames = [ss.iname0]
    yobs = [ss.yob0]
    life = [ss.life0]
    if ss.status == 'married':
        inames.append(ss.iname1)
        yobs.append(ss.yob1)
        life.append(ss.life1)

    try: 
        print(inames, yobs, life, ss.name, ss.startDate)
        plan = owl.Plan(inames, yobs, life, ss.name, ss.startDate)
    except:
        st.info('Failed plan creation.')
        return
    ss.plan = plan

st.write('## Basic Information')

choices = ['single', 'married']
k.init('status', choices[0])
st.radio('Marital status', choices,
          index=choices.index(st.session_state['status']), key='_status',
          on_change=k.push, args=['status'], horizontal=True)

col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
with col1:
    k.init('iname0', '')
    if st.session_state.iname0 == '':
        st.info('Fist name must be provided.')

    iname0 = k.getText('Your first name', 'iname0')

    k.init('yob0', 1965)
    ret = k.getNum("%s's birth year"%iname0, 'yob0')

    k.init('life0', 80)
    ret = k.getNum("%s's expected longevity"%iname0, 'life0')

    today = date.today()
    todaysDate = '%d/%d' % (today.month, today.day)
    k.init('startDate', todaysDate)
    ret = k.getText("Plan's starting date on first year (MM/DD)", 'startDate',
                    callback=checkStartDate)

    k.init('name', '')
    if st.session_state.name == '':
        st.info('A name for the plan must be provided.')
    k.getText("Plan's name", 'name')

with col2:
    if st.session_state['status'] == 'married':
        k.init('iname1', '')
        if st.session_state.iname1 == '':
            st.info('Fist name must be provided.')

        iname1 = k.getText("Your spouse's first name", 'iname1')

        k.init('yob1', 1965)
        ret = k.getNum("%s's birth year"%iname1, 'yob1')

        k.init('life1', 80)
        ret = k.getNum("%s's expected longevity"%iname1, 'life1')

st.button('Initialize plan', on_click=genPlan, disabled=checkAllOK())

