# Adobe_Connect_Participation_Extracter

## Table of Contents
1. [About This Script]
1. [Imported Modules]
1. [My Approach)
1. [Unit Tests]
1. [Instructions]

## About this Script

This Python script extracts participation inform from the .XML files that are included with downloaded recordings of Adobe Connect sessions. The script determines, for each participant, time on camera, time with camera paused, time on microphone, number of chat messages sent, and a summary participatin grade. The script generates a report on all of these features and some related calculations in a summary participation report .csv file. Additionally the script generates a series of bar plots showing each of the participation features and saves them as a .html file. If you'd like to examples of the reports and plots generated by this script they can be found in the main folder of this repo: demo_participation_report.csv and demo_report_plots.html.
## Imported Modules

This script requires the following modules to be imported:
* argv from sys
* save, output_file from bokeh.plotting
* gridplot from bokeh.layouts
* defaultdict from collections
* bs4 from BeautifulSoup
* Counter from collections
* copy from copy
* csv
* datetime from datetime
* glob
* numpy
* pytz
* re
* time


## My approach

Adobe Connect recordings are not simply videos of evertying that appeared on the screen during the session, rather they are a transscript (written in several .xml files) that is read by the Adobe Connect software to reenact the events that occurred during the class. The video and audio are actual recordings, but the start time and end times of these events are triggered by the transcript .xml files. 

This script extracts each participant's activities during the class (when they sent a message, and when they came on camera or microphone) from the .xml transcript and uses this information to determine the total number of messages they sent, the total time they spent on camera, and the total time they spent on microphone. Finally, the script calculates a total participation score from a student's message count, camera time and microphone time.

Message count:
Adobe Connect transcripts message events in ftchat<number>.xml. Every message sent in the class is tagged with the publisher id (pid) of the sender. Each student's total message count is determined by finding the publisher id that AC assigns to each of the students and then counting messages tagged with that pid. 

Camera Time:
Adobe Connect transcripts most camera events in indexstream.xml but pause events are only recorded in ftstage<number>.xml. Every participant is assigned an id (a different number than their pid). Any time someone comes on camera (adds a videostream), stops their camera (removes a videostream, or leaves the class), pauses or unpauses their camera (updateVideoPauseStatus) these events are tagged with the person's id number. To determine total time on camera, the sum of the times the student had their camera paused (each time is calculated by subtracting the time paused status changed to false from the time paused status changed to true) was subtracted from the total time the student spent on camera (time student left class (or removed video stream) -  time student added video stream).

Microphone Time:
Adobe Connect transcripts microphone events in indexstream.xml. While a participant is talking the microphone icon will turn on and off automatically. These icon changes, are tagged with the participants id. To determine the total time a participant spent on microphone the script determines the sum of speaking-event times (one speaking event is the time microphone icon status changed to false, when the student stopped talking, minus the time when the microphone icon changed to true, when the student started talking).

Participation grade:
The participation grade is determined by calculating the average and standard deviation for message count, camera time, and microphone time and adjusts average participation to 100%. Each student's score for each participation factor is the number of standard deviations their adjusted participation factor is added to the adjusted average for the participation score. The participation grade is then calculating by average the participation scores for messages sent, camera time, and microphone time with a maximum time of 105%.

### Unit Tests

This script passed seven end-to-end tests using available recordings.

*Test_1: class session where students change names

*Test_2: class session where students do not come on microphone.

*Test_3: class session where some students do not come on camera.

*Test_4: class session where some students come on microphone but others do not.

### Acknowledgements 

Thanks to Christopher Wolfram for recognizing that this was possible and for his proof of principle script in Mathematica. 
Thanks to Jim Doherty for his help with testing this script. 
