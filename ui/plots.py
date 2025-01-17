import matplotlib.style as style
import matplotlib.pyplot as plt

import sskeys as kz


def changeStyle(key):
    val = kz.getGlobalKey('_'+key)
    kz.storeGlobalKey(key, val)
    plt.style.use(val)


styles = ['default']
otherChoices = [x for x in style.available if not x.startswith('_')]
otherChoices = sorted(otherChoices, key=str.casefold)
styles.extend(otherChoices)
