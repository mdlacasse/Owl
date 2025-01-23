import streamlit as st

import sskeys as kz
import owlbridge as owb


def resetTimeLists():
    # kz.resetTimeLists()
    tlists = owb.resetContributions()
    for i, iname in enumerate(tlists):
        kz.setKey('timeList'+str(i), tlists[iname])


kz.runOncePerCase(resetTimeLists)
kz.initKey('stTimeLists', None)

ret = kz.titleBar('wages')
kz.caseHeader("Wages and Contributions")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    n = 2 if kz.getKey('status') == 'married' else 1

    if kz.getKey('stTimeLists') is None:
        original = kz.getKey('timeListsFileName')
        if original is None or original == 'None':
            iname0 = kz.getKey('iname0')
            st.info("Case *'%s'* contains no contributions file.\n\n" % kz.currentCaseName() +
                    "You can build your own contribution file by starting from this "
                    "[template](https://raw.github.com/mdlacasse/Owl/main/examples/template.xlsx). "
                    "Enter your numbers and ensure that the final workbook contains a tab for each "
                    "individual in the plan, "
                    f"i.e., a tab named *{iname0}*, and another one named after the spouse if applicable. "
                    "If no file is uploaded, zero will be used for all values "
                    "(anticipated wages, savings contributions, and big-ticket items)."
                    )
        elif original != 'edited values':
            st.info("Case *'%s'* contains contributions file *'%s'* that has not yet been uploaded." %
                    (kz.currentCaseName(), original))

    for i in range(n):
        st.write('#### ' + kz.getKey('iname'+str(i)) + "'s timetable")
        newdf = st.data_editor(kz.getKey('timeList'+str(i)), hide_index=True)
        st.caption('Values are in $.')
        kz.storeKey('_timeList'+str(i), newdf)

    col1, col2 = st.columns(2, gap='large', vertical_alignment='bottom')
    with col1:
        kz.initKey('_xlsx', 0)
        stTimeLists = st.file_uploader('Upload values from contribution file...',
                                       key='_stTimeLists'+str(kz.getKey('_xlsx')), type=['xlsx'])
        if stTimeLists is not None:
            if owb.readContributions(stTimeLists):
                kz.setKey('stTimeLists', stTimeLists)
                # Change key to reset uploader.
                kz.storeKey('_xlsx', kz.getKey('_xlsx') + 1)
                st.rerun()
    with col2:
        st.button('Reset to zero', help='Reset all values to zero.', on_click=resetTimeLists)
