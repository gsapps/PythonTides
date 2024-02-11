# # Tides

# In[64]:

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from datetime import date
from datetime import time
from datetime import datetime
from datetime import timedelta
import requests as web
import xml.etree.ElementTree as xml

# print("numpy Version: ", np.__version__)
# print("pandas Version: ", pd.__version__)
# print("matplotlib Version: ", matplotlib.__version__)
# print("requests Version: ", web.__version__)

# ## constants

# In[24]:

strNoaaUrl = "https://tidesandcurrents.noaa.gov/api/datagetter?begin_date=<date>&range=<range>&station=9410230&product=predictions&datum=mllw&units=english&time_zone=lst_ldt&application=grandview&format=xml"

dateStartDate = date.today()
datetimeToday = datetime(dateStartDate.year, dateStartDate.month, dateStartDate.day)
intRangeDays = 4

# useful timedelta's
tdRange = timedelta(days=intRangeDays)
tdQuarterDay = timedelta(hours=6)
tdHalfDay = timedelta(hours=12)
tdFullDay = timedelta(days=1)

# ## functions

# In[61]:


def total_minutes(tdTimeDelta) :  # this is an obviously-missing method in timedelta
    return tdTimeDelta.total_seconds() / 60

def formatMinutesToConciseHourLabel(minute) :  # e.g. 06:00 => 6a
    timeZero = datetime(1900,1,1)
    tdDelta = timedelta(minutes=minute)
    strHour = datetime.strftime(timeZero + tdDelta, "%I%p")  # just zero-padded hour and AM/PM ('-I' doesn't work)
    if (strHour.startswith('0')):
        strHour = strHour.replace("0", "")
    return strHour.replace("AM", "a").replace("PM","p")


# ## get xml tide data from NOAA

# In[26]:

__strToday = dateStartDate.isoformat().replace("-", "")
__url = strNoaaUrl.replace("<date>", __strToday).replace("<range>", str(intRangeDays * 24))

strXml = web.get(__url)  # this is the web response from NOAA
# print(strXml.text[:130], "...", strXml.text[-50:], sep='\n')

#output
# strXml


# ## process the XML for the water-level curve, times and levels

# In[27]:


# extract the times and levels from the xml (strXml)

# get the 't' (time) and 'v' (level) attributes from the 'predictions' node of the xml text
__xmlroot = xml.fromstring(strXml.text)
__strTimes = [wl.attrib['t'] for wl in __xmlroot.iter('pr')]  # times in string format for now
fltLevels = [float(wl.attrib['v']) for wl in __xmlroot.iter('pr')]

# convert times (string format) to datetime format
__dtTimes = [datetime.strptime(t, "%Y-%m-%d %H:%M") for t in __strTimes]
# convert times (datetime format) to "minutes since StartDate" (usually midnight of the current day)
fltTimes = [(t - datetimeToday).total_seconds() / 60 for t in __dtTimes]

# print(len(fltTimes), fltTimes[:4])
# print(len(fltLevels), fltLevels[:4])

#output
# fltTimes
# fltLevels


# ## create night and day line segments for shading the background from 6p to 6a

# In[34]:


def createNightAndDaySegment(tdStartOfNight, lstX, lstY) :  # a new "high" segment and a "low" segment is added to LstX/lstY
    tdRelativeStart = tdStartOfNight
    lstY.extend([7, 7, -2, -2])
    lstX.append(total_minutes(tdRelativeStart))
    tdRelativeStart += tdHalfDay
    lstX.append(total_minutes(tdRelativeStart))
    lstX.append(total_minutes(tdRelativeStart))
    tdRelativeStart += tdHalfDay
    lstX.append(total_minutes(tdRelativeStart))

# loop for each day from 6p yesterday until the end of the graph
lstNightSegsX = list()
lstNightSegsY = list()
__tdStartOfSegment = -tdQuarterDay
while __tdStartOfSegment < tdRange :
    createNightAndDaySegment(__tdStartOfSegment, lstNightSegsX, lstNightSegsY)
    __tdStartOfSegment += tdFullDay
    
# print(lstNightSegsX)

#output
# lstNightSegsX
# lstNightSegsY


# ## create time axis labels

# In[59]:


# set up some durations (in minutes)
__nMinutesInGraph = fltTimes[-1]
__nMinutesPerTick = int(2 * 60)  # number of minutes between each tick mark -- 3hrs

lstLabelLocs = np.arange(0, __nMinutesInGraph + 1, __nMinutesPerTick)  # the "minutes-location" of each tick mark, including one at the very end
lstLabels = list([formatMinutesToConciseHourLabel(60*24)])  # start it off with a "12a" at the zero-minute
for minute in lstLabelLocs[1:] :
    lstLabels.append(formatMinutesToConciseHourLabel(int(minute)))
    
# print(lstLabelLocs)
# print(lstLabels)

#output
# lstLabelLocs
# lstLabels


# ## plot the graph

# In[63]:


fig, ax = plt.subplots(figsize=(20,6))

ax.set_xlim(0,1)  # remove the left/right padding around the plot area
ax.set_ylim(0,)  # remove the top/bottom padding around the plot area
ax.set_title(datetime.strftime(dateStartDate, "%A %B %d"), loc = 'left')
ax.set_ylabel("water level")

# tick marks a time-axis labels
plt.xticks(lstLabelLocs, (lstLabels))
plt.yticks(np.arange(-2, 8))

# gridlines at each hour
plt.grid(axis='x')

# plot the data
ax.fill_between([0, fltTimes[-1]], 0, [1,1], color='lightblue', zorder=0)  # show a line at 1 foot (during daytime)
ax.fill_between(lstNightSegsX, -2, lstNightSegsY, color='lightgray')  # shade the background for night time (6a to 6p)
ax.plot(fltTimes, fltLevels)  # plot the water level curve
ax.fill_between(fltTimes, 0, fltLevels)  # fill in the area under the curve

plt.show()
None
