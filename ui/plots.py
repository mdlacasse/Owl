import matplotlib.style as style
import matplotlib.pyplot as plt

import sskeys as kz


def changeStyle(key):
    val = kz.getGlobalKey('_'+key)
    kz.setGlobalKey(key, val)
    plt.style.use(val)
    print('SET', key, 'TO', val)


styles = ['default']
otherChoices = [x for x in style.available if not x.startswith('_')]
otherChoices = sorted(otherChoices, key=str.casefold)
styles.extend(otherChoices)