#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 16 11:14:13 2019

@author: JeffHalley
"""

from sys import argv
from bokeh.io import save, output_file
from bokeh.plotting import figure
from bokeh.layouts import gridplot
from collections import defaultdict
from bs4 import BeautifulSoup
from collections import Counter
from copy import copy
import csv
from datetime import datetime
import glob
import numpy as np
import pytz
import re
import time


def get_index_stream(recording_folder_path):
    '''
    indexstream.xml is a file in the adobe connect recordings folder that
    indicates student names and IDs when students enter the session, come on 
    camera, come on microphone, and when they use the status buttons
    '''
    index_stream_xml_path = recording_folder_path + "indexstream.xml"
    with open(index_stream_xml_path) as filepath:
        index_stream = BeautifulSoup(filepath, 'xml')
    return index_stream


def get_student_ids_and_pids(index_stream):
    # this will return a result set that can be used as an index to find
    # the record that contains id and pID for each student
    student_names_index = index_stream.find_all('fullName')
    student_names = []
    id_numbers = []
    pid_numbers = []
    for item in range(len(student_names_index)):
        # use the name index to access the actual name and add it to the list of names
        student_name = student_names_index[item].parent.fullName.text
        
        '''sometimes students have connection issues and they end up with multiple
        logins with their name followed by a number, for this reason the
        following is done to remove any numbers from names'''
        student_name = ''.join([i for i in student_name if not i.isdigit()])
        
        # remove any doubled spaces in the name
        student_name = re.sub(' +', ' ', student_name)
        
        # remove any space before or after the name
        student_name = student_name.strip()
        student_names.append(student_name)
        
        # use the name index to find the student id number for the student
        id_number = student_names_index[item].find_next_sibling("id").text
        id_numbers.append(id_number)
        
        # use the name index to find the the pID for each student and add to list
        pid_number = student_names_index[item].find_next_sibling("pID").text
        pid_numbers.append(pid_number)

        '''
        make dict with student ID or pID and student name. Reverse list is used 
        because sometimes students change names, but the first name is always
        as listed in class roster, also note sometimes students are kicked out
        and log back in and thus given a new ID and pID, this will be dealt
        with when names are subbed in for IDs at the end of each results
        collection function
        '''

    student_ids = defaultdict(str, zip(list(reversed(id_numbers)), list(reversed(student_names))))
    student_pids = defaultdict(str, zip(list(reversed(pid_numbers)), list(reversed(student_names))))
    return student_ids, student_pids
    # future plans: take a second argument a student roster cvs file make a dict
    # with zeroes for all students to act as a placeholder. Then use combined
    # dict from insight project. to give students with no record a zero


def get_instructor_id_and_instructor_name(index_stream, student_ids, student_pids):
    instructor_id = index_stream.find("myID").text
    instructor = student_ids[instructor_id]
    instructor_pid = list(student_pids.keys())[list(student_pids.values()).index(instructor)]
    
    #designate instructor in instructor's name
    instructor_title_and_name = " ~ ~Instructor~ ~ " + instructor
    instructor_name = instructor_title_and_name
    
    #replace instructor name with instructor title name in student IDs dict
    student_ids[instructor_id] = instructor_title_and_name
    student_pids[instructor_pid] = instructor_title_and_name
    
    return instructor_id, instructor_name


def assign_zeroes_for_no_participation(dict_of_student_ids, dict_of_results):
    for k in dict_of_student_ids.keys():
        if type(dict_of_results[k]) == list:
            if len(dict_of_results[k]) == 0:
                dict_of_results[k].append(0)
        if type(dict_of_results[k]) == int:
            if dict_of_results[k] == 0:
                dict_of_results[k] = 0


def get_participant_names(student_ids):
    participant_names = dict(zip(student_ids.values(), student_ids.values()))
    return participant_names


def get_results_by_name_from_results_by_id(dict_of_results_by_id, student_ids):
    ids = list(dict_of_results_by_id.keys())
    names_subbed_for_ids = [student_ids.get(item, 0) for item in ids]
    results = list(dict_of_results_by_id.values())
    if type(results[0]) == list:
        results_with_names_subbed_for_ids = defaultdict(list)
        for names, results in zip(names_subbed_for_ids, results):
            results_with_names_subbed_for_ids[names].append(results)
        return results_with_names_subbed_for_ids
    if type(results[0]) == int or type(results[0]) == float:
        results_with_names_subbed_for_ids = defaultdict(list)
        for names, results in zip(names_subbed_for_ids, results):
            results_with_names_subbed_for_ids[names].append(results)
        return {k: sum(v) for k, v in results_with_names_subbed_for_ids.items()}

    return results_with_names_subbed_for_ids


def get_ftstage(recording_folder_path):
    '''
    ftstage is the xml file describing what happens with the camera streams
    in the video pod, much of this information is in the indexstream xml
    file as well, but not the camera pause info. ftstage is used to find
    times when students pause the camera. ftstage files always start with
    "ftstage" and end with ".xml" but they have different numbers in
    different recordings so a wildcard is used to find the file in the
    recording folder
    '''
    ftstage_wildcard = "ftstage*.xml"

    '''
    glob searches for the wildcard and returns a list of results. index is to
    get the first result from the resulting list
    '''
    ftstage_file_path = glob.glob(recording_folder_path + ftstage_wildcard)[0]
    with open(ftstage_file_path) as filepath:
        ftstage = BeautifulSoup(filepath, "xml")
    return ftstage


def get_camera_contributions(index_stream, ftstage, student_ids, instructor_id):
    # get time when student came on camera from index stream soup
    camera_starts_index = index_stream.find_all(string='streamAdded')
    camera_start_ids = []
    camera_start_times = []
    for item in range(len(camera_starts_index)):
        # get id number of student that started their camera
        camera_start_id = camera_starts_index[item].parent.parent.streamPublisherID.text
        camera_start_ids.append(camera_start_id)
        # get time that student started their camera
        camera_start_time = int(camera_starts_index[item].parent.parent.startTime.text)
        camera_start_times.append(camera_start_time)
    student_camera_start_times = defaultdict(list)
    for student_id, start_time in zip(camera_start_ids, camera_start_times):
        student_camera_start_times[student_id].append(start_time)

        # get time when student turned off camera
    stream_removed_index = index_stream.find_all(string='streamRemoved')
    stream_removed_ids = []
    stream_removed_times = []
    for item in range(len(stream_removed_index)):
        # get id number of student that stopped their camera
        stream_removed_id = stream_removed_index[item].parent.parent.streamPublisherID.text
        stream_removed_ids.append(stream_removed_id)
        # get time that student stopped their camera
        stream_removed_time = int(stream_removed_index[item].parent.parent.time.text)
        stream_removed_times.append(stream_removed_time)

    # get time when student loses connection
    user_deleted_index = index_stream.find_all(string='userDeleted')
    user_deleted_ids = []
    user_deleted_times = []
    for item in range(len(user_deleted_index)):
        # get id number of student that loses connection
        user_deleted_id = user_deleted_index[item].parent.parent.next_sibling.next_sibling.text
        user_deleted_ids.append(user_deleted_id)
        # get time that student that loses connection
        user_deleted_time = int(user_deleted_index[item].parent.parent.parent.time.text)
        user_deleted_times.append(user_deleted_time)

    # merge lists of stream removed and stream ids b/c both are ways camera stops
    camera_stops_ids = stream_removed_ids + user_deleted_ids
    camera_stops_times = stream_removed_times + user_deleted_times

    # initialize a default dict that has the same keys as the student_camera_start_times dict
    student_camera_stop_times = defaultdict(list)
    for k in student_camera_start_times.keys():
        student_camera_stop_times[k]
    for student_id, stop_time in zip(camera_stops_ids, camera_stops_times):
        student_camera_stop_times[student_id].append(stop_time)

    '''
    having students with ids but with no camera time interfere with later calcs
    so I will give all of the students that did not appear on camera a start
    and end time that is is the same as the end of class
    '''
    for k in student_camera_stop_times.keys():
        if len(student_camera_start_times[k]) == 0:
            student_camera_stop_times[k] = [0]
            student_camera_start_times[k].append(0)

    # determine total time student has camera on, not including pauses
    student_minutes_with_camera_on = defaultdict(int)
    for k in student_camera_stop_times.keys():
        times = [a - b for a, b in zip(student_camera_stop_times[k], student_camera_start_times[k])]
        total_time = sum(times) / 1000 / 60
        student_minutes_with_camera_on[k] += total_time

    # get total time student pauses camera from ftstage soup
    pause_change_index = ftstage.find_all(string="updateVideoPauseStatus")
    pause_start_ids = []
    pause_start_times = []
    pause_stop_ids = []
    pause_stop_times = []
    for item in range(len(pause_change_index)):
        if pause_change_index[item].parent.parent.String.find_next_sibling("String").text == 'true':
            pause_start_times.append(int(pause_change_index[item].parent.parent.Object.time.text))
            pause_start_ids.append(pause_change_index[item].parent.next_sibling.next_sibling.text)
        else:
            pause_stop_times.append(int(pause_change_index[item].parent.parent.Object.time.text))
            pause_stop_ids.append(pause_change_index[item].parent.next_sibling.next_sibling.text)
    student_pause_start_times = defaultdict(list)
    for student_id, start_time in zip(pause_start_ids, pause_start_times):
        student_pause_start_times[student_id].append(start_time)
    student_pause_stop_times = defaultdict(list)
    for student_id, stop_time in zip(pause_stop_ids, pause_stop_times):
        student_pause_stop_times[student_id].append(stop_time)
        # the first pause_stop_time is when the student turns on their camera so it will be discarded
        # trimmed_student_pause_stop_times = {k: student_pause_stop_times[k][1:] for k in student_pause_stop_times}

    # find times when student video feed was lost
    video_removed_index = ftstage.find_all(string="removeVideo")
    video_removed_ids = []
    video_removed_times = []
    for item in range(len(video_removed_index)):
        video_removed_ids.append(video_removed_index[item].parent.next_sibling.next_sibling.text)
        video_removed_times.append(int(video_removed_index[item].parent.parent.time.text))
    student_video_removed_times = defaultdict(list)
    for student_id, removed_time in zip(video_removed_ids, video_removed_times):
        student_video_removed_times[student_id].append(removed_time)

    '''sometimes a student loses connection or ends stream. when they reconnect 
    a stop pause is recorded to get rid of these false stops I will use the 
    camera_start_times to identify them (they occur within 100 ms of the camera
    start event). Since I've already trimmed the false stop from 
    the first camera start event. I will trim all of those from the camera starts
    list. Also, I can't just use the within 100 ms method to eliminate the first 
    camera start events because if a student's camera is turned on before the
    recording starts it is recorded as much as 3000 ms before the false stop
    event'''

    # give every student that didn't come on camera  pause stop time
    for k in student_camera_stop_times.keys():
        if len(student_pause_stop_times[k]) == 0:
            student_pause_stop_times[k].append(0)

    # combine pause stop times with video removed times because sometimes a pause is stopped by student leaving
    combined_pause_stop_times = defaultdict(list)
    for k in student_video_removed_times.keys():
        for item in range(len(student_video_removed_times[k])):
            combined_pause_stop_times[k].append(student_video_removed_times[k][item])

    for k in student_pause_stop_times.keys():
        for item in range(len(student_pause_stop_times[k])):
            combined_pause_stop_times[k].append(student_pause_stop_times[k][item])

    # sort the lists of stop times
    for k in combined_pause_stop_times.keys():
        combined_pause_stop_times[k].sort()

    # remove stop times that occur before first pause
    for k in student_pause_start_times.keys():
        if len(student_pause_start_times[k]) != 0:
            for pause_stop_time in reversed(range(len(combined_pause_stop_times[k]))):
                if combined_pause_stop_times[k][pause_stop_time] < student_pause_start_times[k][0]:
                    del (combined_pause_stop_times[k][pause_stop_time])

    # remove stops when students lose connection
    for k in student_camera_start_times.keys():
        for camera_start_time in reversed(range(len(student_camera_start_times[k]))):
            for pause_stop_time in reversed(range(len(combined_pause_stop_times[k]))):
                if (
                        combined_pause_stop_times[k][pause_stop_time] - student_camera_start_times[k][
                    camera_start_time] > 0 and
                        combined_pause_stop_times[k][pause_stop_time] < student_camera_start_times[k][
                    camera_start_time] + 100
                ):
                    del (combined_pause_stop_times[k][pause_stop_time])

    # remove stops that are last student removed from class                    
    for k in combined_pause_stop_times.keys():
        if len(combined_pause_stop_times[k]) > len(student_pause_start_times[k]):
            del (combined_pause_stop_times[k][len(combined_pause_stop_times[k]) - 1])

    # many of the stop times will not correspond to real mic starts, so they should be removed
    clean_stops = []
    clean_stops_ids = []
    for k in student_pause_start_times.keys():
        for start_time in range(len(student_pause_start_times[k])):
            clean_stops_ids.append(k)
            clean_stops.append(
                next((x for x in combined_pause_stop_times[k] if x > student_pause_start_times[k][start_time]),
                     student_pause_start_times[k][start_time]))

    student_clean_stop_times = defaultdict(list)
    for student_id, stop_time in zip(clean_stops_ids, clean_stops):
        student_clean_stop_times[student_id].append(stop_time)

    # determine the total time the student had the camera paused
    student_minutes_with_camera_paused = defaultdict(int)
    for k in combined_pause_stop_times.keys():
        times = [a - b for a, b in zip(student_clean_stop_times[k], student_pause_start_times[k])]
        total_time = sum(times) / 1000 / 60
        student_minutes_with_camera_paused[k] += total_time

    # determine time student was on camera minus time paused
    student_time_on_camera = {k: student_minutes_with_camera_on[k] - student_minutes_with_camera_paused.get(k, 0) for k
                              in student_minutes_with_camera_on.keys()}

    # get fraction of class time student spent on camera based on end of class time
    end_of_class_object = index_stream.find_all(text='__stop__')
    end_of_class_time = int(end_of_class_object[len(end_of_class_object) - 1].parent.parent.Number.text)
    end_of_clas_time_minutes = end_of_class_time / 1000 / 60
    student_fraction_of_class_on_camera = {k: v / end_of_clas_time_minutes for k, v in student_time_on_camera.items()}
    student_fraction_of_class_on_camera = defaultdict(int, student_fraction_of_class_on_camera)

    # determine fraction of time student is on mic compared to instructor
    instructor_time_on_camera = student_time_on_camera[instructor_id]
    
    #sometimes, unclear why at this point, instructor camera time gets recorded as 0, this is a patch for that
    if instructor_time_on_camera == 0:
        instructor_time_on_camera = end_of_clas_time_minutes
        
    student_fraction_of_instructor_time_on_camera = {k: v / instructor_time_on_camera for k, v in
                                                     student_time_on_camera.items()}
    student_fraction_of_instructor_time_on_camera = defaultdict(int, student_fraction_of_instructor_time_on_camera)

    return (
        get_results_by_name_from_results_by_id(student_time_on_camera, student_ids),
        get_results_by_name_from_results_by_id(student_minutes_with_camera_paused, student_ids),
        get_results_by_name_from_results_by_id(student_fraction_of_class_on_camera, student_ids),
        get_results_by_name_from_results_by_id(student_fraction_of_instructor_time_on_camera, student_ids)

    )


def get_microphone_contributions(index_stream, student_ids, instructor_id):
    # get times when student has a microphone change (turns it on OR off)
    mic_change_index = index_stream.find_all(string='userVoipStatusChanged')
    mic_start_ids = []
    mic_start_times = []
    mic_stop_ids = []
    mic_stop_times = []
    for item in range(len(mic_change_index)):
        # look in index of microphone changes to find instances where student turned mic on (started talking)
        if mic_change_index[item].parent.parent.parent.String.find_next_sibling("String").text == 'true':
            mic_start_ids.append(mic_change_index[item].parent.parent.parent.String.text)
            mic_start_times.append(int(mic_change_index[item].parent.find_next_sibling("time").text))

        if mic_change_index[item].parent.parent.parent.String.find_next_sibling("String").text == 'false':
            mic_stop_ids.append(mic_change_index[item].parent.parent.parent.String.text)
            mic_stop_times.append(int(mic_change_index[item].parent.find_next_sibling("time").text))

    student_mic_start_times = defaultdict(list)
    for student_id, start_time in zip(mic_start_ids, mic_start_times):
        student_mic_start_times[student_id].append(start_time)
    dirty_student_mic_stop_times = defaultdict(list)
    # dirty because it contains some stops that do not correspond to starts
    for student_id, stop_time in zip(mic_stop_ids, mic_stop_times):
        dirty_student_mic_stop_times[student_id].append(stop_time)

    # many of the stop times will not correspond to real mic starts, so they should be removed
    clean_stops = []
    clean_stops_ids = []
    for k in student_mic_start_times.keys():
        for start_time in range(len(student_mic_start_times[k])):
            clean_stops_ids.append(k)
            clean_stops.append(
                next((x for x in dirty_student_mic_stop_times[k] if x > student_mic_start_times[k][start_time]),
                     student_mic_start_times[k][start_time]))

    student_mic_stop_times = defaultdict(list)
    for student_id, stop_time in zip(clean_stops_ids, clean_stops):
        student_mic_stop_times[student_id].append(stop_time)

    # give every student that didn't come on mic a zero

    for k in student_ids.keys():
        if len(student_mic_stop_times[k]) == 0:
            student_mic_stop_times[k].append(0)
        if len(student_mic_start_times[k]) == 0:
            student_mic_start_times[k].append(0)

            # get end of class time
    end_of_class_object = index_stream.find_all(text='__stop__')
    end_of_class_time = int(end_of_class_object[len(end_of_class_object) - 1].parent.parent.Number.text)

    # determine total time on microphone
    student_minutes_on_microphone = defaultdict(int)
    student_fraction_of_class_on_microphone = defaultdict(int)

    for k in student_mic_stop_times.keys():
        times = [a - b for a, b in zip(student_mic_stop_times[k], student_mic_start_times[k])]
        total_time = sum(times) / 1000 / 60
        fraction_of_class_time_on_microphone = (sum(times) / end_of_class_time)

        student_minutes_on_microphone[k] += total_time
        student_fraction_of_class_on_microphone[k] += fraction_of_class_time_on_microphone

    # determine fraction of time student is on mic compared to instructor
    instructor_time_on_mic = student_minutes_on_microphone[instructor_id]
    
    if instructor_time_on_mic == 0:
        instructor_time_on_mic = 1.0
    
    student_fraction_of_instructor_mic = {k: v / instructor_time_on_mic for k, v in
                                          student_minutes_on_microphone.items()}
    student_fraction_of_instructor_mic = defaultdict(int, student_fraction_of_instructor_mic)

    return (
        get_results_by_name_from_results_by_id(student_minutes_on_microphone, student_ids),
        get_results_by_name_from_results_by_id(student_fraction_of_class_on_microphone, student_ids),
        get_results_by_name_from_results_by_id(student_fraction_of_instructor_mic, student_ids)
    )


def get_chat_contributions(index_stream, student_pids, recording_folder_file_path):
    '''
    ftchatX logs record time of chat message as unixtime code multiplied by 1000
    in PST. The start date in indexstream is a readable string stating the 
    in Greenwich mean time zone. This code will strip the time from 
    indexstream.xml and convert it into the same format used in the ftchat logs
    '''
    # get get start date from indextream timestamp
    start_date = index_stream.root.Message.Array.String.next_sibling.next_sibling.next_sibling.next_sibling.text

    # convert to format used in ftchats
    start_timestamp = datetime.fromtimestamp(time.mktime(time.strptime(start_date)))

    # remove time information to capture chats after class starts but before recording
    start_day_timestamp = datetime(start_timestamp.year, start_timestamp.month, start_timestamp.day)
    old_timezone = pytz.timezone("Greenwich")
    new_timezone = pytz.timezone("US/Pacific")

    # all of the timestamps used by AC are multiplied by 1000
    corrected_start_timestamp = 1000 * (
        datetime.timestamp(old_timezone.localize(start_day_timestamp).astimezone(new_timezone)))

    # get list of ftchat files
    ftchat_wildcard = "ftchat*.xml"
    ftchat_file_path_list = glob.glob(recording_folder_file_path + ftchat_wildcard)

    # loop through the list finding all messages chat_times, and chat_lengths
    chat_pids = []
    chat_messages = []
    chat_times = []
    chat_lengths = []
    for file_path in ftchat_file_path_list:
        with open(file_path) as filepath:
            ftchat = BeautifulSoup(filepath, "xml")
        chat_index = ftchat.find_all("fromPID")
        for item in range(len(chat_index)):
            if float(chat_index[item].parent.when.text) > corrected_start_timestamp:
                chat_pids.append(chat_index[item].parent.fromPID.text)
                chat_times.append(float(chat_index[item].parent.when.text))
                chat_messages.append(chat_index[item].parent.fromPID.next_sibling.next_sibling.text)
                chat_lengths.append(int(len(chat_index[item].parent.fromPID.next_sibling.next_sibling.text)))

    student_chat_messages = defaultdict(list)
    for student_pid, chat_message in zip(chat_pids, chat_messages):
        student_chat_messages[student_pid].append(chat_message)
    assign_zeroes_for_no_participation(student_pids, student_chat_messages)

    student_chat_times = defaultdict(list)
    for student_pid, chat_time in zip(chat_pids, chat_times):
        student_chat_times[student_pid].append(chat_time)
    assign_zeroes_for_no_participation(student_pids, student_chat_times)

    student_chat_lengths = defaultdict(list)
    for student_pid, chat_length in zip(chat_pids, chat_lengths):
        student_chat_messages[student_pid].append(chat_length)
    assign_zeroes_for_no_participation(student_pids, student_chat_lengths)

    student_message_count = Counter(chat_pids)
    assign_zeroes_for_no_participation(student_pids, student_message_count)

    student_fraction_of_chats = {k: student_message_count[k] / len(chat_messages)
                                 for k in student_message_count}

    assign_zeroes_for_no_participation(student_pids, student_message_count)

    return (
        get_results_by_name_from_results_by_id(student_chat_times, student_pids),
        get_results_by_name_from_results_by_id(student_chat_lengths, student_pids),
        get_results_by_name_from_results_by_id(student_message_count, student_pids),
        get_results_by_name_from_results_by_id(student_fraction_of_chats, student_pids)
    )


def get_participation_grades(student_time_on_camera, student_minutes_on_microphone, student_message_count, instructor_name):
    # get camera grade, decimal at end is made to avoid divide by zero errors
    camera_times = copy(student_time_on_camera)
    del (camera_times[instructor_name])
    camera_time_mean = np.mean(list(camera_times.values()))
    camera_time_stdev = np.std(list(camera_times.values())) + .00000001
    # adjust scores so average participation is 100%
    if camera_time_mean > 0:
        camera_adjustment = 100 / camera_time_mean
    else:
        camera_adjustment = 100
    student_camera_grades = {k: (((camera_times[k] - camera_time_mean) / camera_time_stdev) * camera_adjustment) + 100
                             for k in camera_times}

    # get microphone grade
    mic_times = copy(student_minutes_on_microphone)
    del (mic_times[instructor_name])
    mic_time_mean = np.mean(list(mic_times.values()))
    mic_time_stdev = np.std(list(mic_times.values())) + .00000001
    # adjust scores so average participation is 100%
    if mic_time_mean > 0:
        mic_adjustment = 100 / (mic_time_mean)
    else:
        mic_adjustment = 100
    student_mic_grades = {k: (((mic_times[k] - mic_time_mean) / mic_time_stdev) * mic_adjustment) + 100
                          for k in mic_times}

    # get chat grades
    message_count = copy(student_message_count)
    del (message_count[instructor_name])
    messages_mean = np.mean(list(message_count.values()))
    messages_stdev = np.std(list(message_count.values())) + .00000001
    # adjust scores so average participation is 90%
    if messages_mean > 0:
        messages_adjustment = 100 / messages_mean
    else:
        messages_adjustment = 100
    student_message_grades = {k: (((message_count[k] - messages_mean) / messages_stdev) * messages_adjustment) + 100
                              for k in message_count}

    # get total participation grade (average of cam,mic,and chat grades)
    student_participation_grades = {
        k: (student_message_grades[k] + student_camera_grades[k] + student_mic_grades[k]) / 3
        for k in student_message_grades}

    for k in student_participation_grades.keys():
        if student_participation_grades[k] > 105:
            student_participation_grades[k] = 105

    return student_participation_grades


def save_report_csv(results, report_file_path):
    with open(report_file_path, "w") as outfile:
        writer = csv.writer(outfile)
        writer.writerows(results)

def get_results_summary(recording_folder_file_path, report_folder_file_path):
    index_stream = get_index_stream(recording_folder_file_path)
    student_ids, student_pids = get_student_ids_and_pids(index_stream)
    ftstage = get_ftstage(recording_folder_file_path)
    instructor_id, instructor_name = get_instructor_id_and_instructor_name(index_stream, 
                                                                           student_ids, 
                                                                           student_pids)
    participant_names = get_participant_names(student_ids)
    
    
    (
        student_time_on_camera,
        student_minutes_with_camera_paused,
        student_fraction_of_class_on_camera,
        student_fraction_of_instructor_time_on_camera
    ) = get_camera_contributions(index_stream, ftstage, student_ids, instructor_id)
    
    (
        student_minutes_on_microphone,
        student_fraction_of_class_on_microphone,
        student_fraction_of_instructor_mic
    ) = get_microphone_contributions(index_stream, student_ids, instructor_id)
    
    (
        student_chat_times,
        student_chat_lengths,
        student_message_count,
        student_fraction_of_chats
    ) = get_chat_contributions(index_stream, student_pids, recording_folder_file_path)
    
    student_participation_grades = get_participation_grades(student_time_on_camera,
                                                            student_minutes_on_microphone,
                                                            student_message_count,
                                                            instructor_name)
    
    class_data = [
        participant_names,
        student_participation_grades,
        student_time_on_camera,
        student_minutes_with_camera_paused,
        student_fraction_of_class_on_camera,
        student_fraction_of_instructor_time_on_camera,
        student_minutes_on_microphone,
        student_fraction_of_class_on_microphone,
        student_fraction_of_instructor_mic,
        student_message_count,
        student_fraction_of_chats
    ]
    
    results = defaultdict(list)
    for k in participant_names.keys():
        for item in class_data:
            results[k].append(item.get(k, 0))
    
    # convert results to list for sorting
    results = list(results.values())
    
    # sort orders by student name
    results.sort()
    results.sort(key=lambda n: n[0].split()[1])
    
    # make headers for results.csv file
    headers = [
        "Participant",
        "Participation Grades",
        "Minutes on Camera",
        "Minutes with Camera Paused",
        "Fraction of Class Time on Camera",
        "Fraction of Instructor Time on Camera",
        "Minutes on Microphone",
        "Fraction of Class Time on Microphone",
        "Fraction of Instructor Time on Microphone",
        "Chat Messages Sent",
        "Fraction of Messages Sent"
    ]
    
    # add headers to results list
    results.insert(0, headers)
    
    report_file_path = report_folder_file_path + "participation_report.csv"
    
    save_report_csv(results, report_file_path)
    
    return results, headers

def get_summary_plots(results,headers,report_folder_file_path):
    output_file(report_folder_file_path + "participation_report_plots.html") 
    plots = []
    for result in range(len(results[0])):
        students = list(reversed([item[0] for item in results]))[:-1]
        participation_data = list(reversed([item[result] for item in results]))[:-1]
    
        p = figure(y_range=students, plot_width=400, plot_height=400, title=headers[result])
        p.hbar(y=students, height=0.5, left=0,
               right=participation_data, color="navy")
        plots.append(p)
    
    g = gridplot([plots[1:2], plots[2:4], plots[6:7], plots[9:10]])
    
    save(g)

if __name__ == '__main__':
    recording_folder_file_path, report_folder_file_path = argv[1],argv[2]
    results, headers = get_results_summary(recording_folder_file_path, report_folder_file_path)
    get_summary_plots(results,headers,report_folder_file_path)
    
