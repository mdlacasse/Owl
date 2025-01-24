import streamlit as st

import sskeys as kz
import owlbridge as owb


def resetTimeLists():
    # kz.resetTimeLists()
    tlists = owb.resetContributions()
    for i, iname in enumerate(tlists):
        kz.setKey('timeList'+str(i), tlists[iname])


ret = kz.titleBar('wages')
kz.caseHeader("Wages and Contributions")

if ret is None or kz.caseHasNoPlan():
    st.info('Case(s) must be first created before running this page.')
else:
    print('ret is:', ret)
    kz.runOncePerCase(resetTimeLists)
    kz.initKey('stTimeLists', None)
    n = 2 if kz.getKey('status') == 'married' else 1

    if kz.getKey('stTimeLists') is None:
        original = kz.getKey('timeListsFileName')
        if original is None or original == 'None':
            st.info("Case *'%s'* makes no reference to a wages and contributions file.\n\n" % kz.currentCaseName() +
                    "You can build your own file by directly filling the table(s) below."
                    "Once a case has been successfully run, values can be saved on the `Case Results` page."
                    "Alternatively, you can start from an Excel "
                    "[template](https://raw.github.com/mdlacasse/Owl/main/examples/template.xlsx) "
                    "and upload the file using the widget below."
                    )
        elif original != 'edited values':
            st.info("Case *'%s'* refers to wages and contributions file *'%s'* that has not yet been uploaded." %
                    (kz.currentCaseName(), original))

    kz.initKey('_xlsx', 0)
    stTimeLists = st.file_uploader('Upload values from a wages and contributions file...',
                                   key='_stTimeLists'+str(kz.getKey('_xlsx')), type=['xlsx'])
    if stTimeLists is not None:
        if owb.readContributions(stTimeLists):
            kz.setKey('stTimeLists', stTimeLists)
            # Change key to reset uploader.
            kz.storeKey('_xlsx', kz.getKey('_xlsx') + 1)
            st.rerun()

    for i in range(n):
        st.write('#### ' + kz.getKey('iname'+str(i)) + "'s timetable")
        colfor = {'year': st.column_config.NumberColumn(None, format='%d')}
        newdf = st.data_editor(kz.getKey('timeList'+str(i)), column_config=colfor, hide_index=True)
        st.caption('Values are in $.')
        kz.storeKey('_timeList'+str(i), newdf)

    st.button('Reset to zero', help='Reset all values to zero.', on_click=resetTimeLists)
