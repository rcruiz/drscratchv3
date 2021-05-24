#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# -*- coding: utf-8 -*-

from django.http import HttpResponseRedirect, HttpResponse
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.contrib.auth import logout, login, authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.db.models import Avg
from app.models import File, CSVs
from app.models import Organization, OrganizationHash, Coder
from app.models import Discuss, Stats
from app.forms import UploadFileForm, UserForm, NewUserForm, UrlForm
from app.forms import OrganizationForm, OrganizationHashForm
from app.forms import TeacherForm, LoginOrganizationForm
from app.forms import CoderForm, LoginCoderForm
from app.forms import DiscussForm
from django.contrib.auth.models import User
from django.utils.encoding import smart_str
from django.shortcuts import render

import os
import ast
import json
import urllib2
import shutil
import unicodedata
import csv
import zipfile
import uuid
from datetime import datetime, timedelta, date
import traceback

from app import pyploma
from app import org

import mastery
import spriteNaming
import backdropNaming
import duplicateScripts
import deadCode

from exception import DrScratchException

import logging

logger = logging.getLogger(__name__)

PATH_DRSCRATCH_PROJECT = os.path.dirname(os.path.dirname(__file__))

TYPE_DRSCRATCH_USER = {
    'coder': 'coder',
    'organization': 'organization',
    'non-authenticated-user': 'non-authenticated-user'
}


def main(request):
    """
    Shows the main page of Dr Scratch, personalized if the user is
    authenticated.

    :param request: HTTP Request.
    """
    if request.user.is_authenticated():
        username = request.user.username
        user_type, user_type_str = get_type_user(request)
        img = user_type.img
    else:
        username = None
        user_type_str = 'main'
        img = ''
    dict_params_template = {'username': username, 'img': str(img)}
    return render(request, user_type_str + '/main.html', dict_params_template)


def contest(request):
    """
    Render the contest Scratch 2019 page.

    :param request: Http Request.
    """
    return render(request, 'contest.html', {})


def collaborators(request):
    """
    Render the page with the collaborators of Dr. Scratch.

    :param request: HTTP Request
    """
    return render(request, 'main/collaborators.html')


def date_range(start, end):
    """Initialization of ranges.

    :param start: minimum date of the considered range.
    :param end: maximum date of the considered range.
    :return: list with the dates considered that are inside the range.
    """
    r = (end + timedelta(days=1) - start).days
    return [start + timedelta(days=i) for i in range(r)]


def statistics(request):
    """Initializing variables
    Take the data in an orderly way so that the statistics of Dr.
    Scratch can be represented. For this, the date on which these
    statistics are collected is taken into account. Statistical
    analysis are displayed according to a template.

    :param request: Http Request.
    """

    start = date(2015, 8, 1)
    end = datetime.today()
    y = end.year
    m = end.month
    d = end.day
    end = date(y, m, d)
    date_list = date_range(start, end)
    my_dates = []
    for n in date_list:
        my_dates.append(n.strftime("%d/%m"))  # used for x axis in. Convert object to a string according to a given format

    # This final section stores all data for the template
    obj = Stats.objects.order_by("-id")[0]
    data = {"date": my_dates,
            "dailyRate": obj.daily_score,
            "levels": {"basic": obj.basic,
                       "development": obj.development,
                       "master": obj.master},
            "totalProjects": obj.daily_projects,
            "skillRate": {"parallelism": obj.parallelism,
                          "abstraction": obj.abstraction,
                          "logic": obj.logic,
                          "synchronization": obj.synchronization,
                          "flowControl": obj.flowControl,
                          "userInteractivity": obj.userInteractivity,
                          "dataRepresentation": obj.dataRepresentation},
            "codeSmellRate": {"deadCode": obj.deadCode,
                              "duplicateScript": obj.duplicateScript,
                              "spriteNaming": obj.spriteNaming,
                              "initialization": obj.initialization}}

    # Show general statistics page of Dr. Scratch: www.drscratch.org/statistics
    # return render_to_response("main/statistics.html",
    #                                data, context_instance=RC(request))

    return render(request, 'main/statistics.html', data)


def show_dashboard(request):
    """Shows the different dashboards.

    This method display the dashboards of the analysis. Show the achieved
    score and levels once the project analysis has been carried out. It
    includes measures of bad habits if the score is higher than 7.
    If any error occurs, the key 'Error' stores the failure type as
    value, inside the dictionary.

    :param request: HTTP request.
    """

    if request.method == 'POST':

        dict_metrics_ct = build_dictionary_with_ct_automatic_analysis(request)
        user_type, user_type_str = get_type_user(request)

        if dict_metrics_ct['Error'] == 'analyzing':
            return render(request, 'error/analyzing.html')
        elif dict_metrics_ct['Error'] == 'MultiValueDict': ###
            return render(request, user_type_str + '/main.html', {'error': True})
        elif dict_metrics_ct['Error'] == 'id_error':
            return render(request, user_type_str + '/main.html', {'id_error': True})
        elif dict_metrics_ct['Error'] == 'no_exists':
            return render(request, user_type_str + '/main.html', {'no_exists': True})
        else:
            if dict_metrics_ct["mastery"]["points"] >= 15:
                return render(request, user_type_str + '/dashboard-master.html', dict_metrics_ct)
            elif dict_metrics_ct["mastery"]["points"] > 7:
                return render(request, user_type_str + '/dashboard-developing.html', dict_metrics_ct)
            else:
                return render(request, user_type_str + '/dashboard-basic.html', dict_metrics_ct)
    else:
        return HttpResponseRedirect('/')


def build_dictionary_with_ct_automatic_analysis(request):
    """
    Search the value of field in Http Request that indicates if the
    analysis will be make by upload or by url. Build the dictionary
    with metrics associated with CT skills by analyzing a Scratch
    project.

    :param request: HTTP request.
    :return dict_metrics_ct: Dictionary with all metrics of CT for a
        Scratch project.
    """
    dict_metrics_ct = {}
    url = ""

    if "_upload" in request.POST:
        dict_metrics_ct = _make_analysis_by_upload(request)
        if dict_metrics_ct['Error'] != 'None':
            return dict_metrics_ct
        filename = request.FILES['zipFile'].name.encode('utf-8')
        print(filename + "upload")

    elif '_url' in request.POST:
        dict_metrics_ct = _make_analysis_by_url(request)
        url = request.POST['urlProject']
        filename = url

    dict_aux = {'url': url, 'filename': filename}
    dict_metrics_ct.update(dict_aux)

    return dict_metrics_ct


def get_type_user(request):
    """
    Check whether the user is authenticated or not, returning the user
    type of Dr. Scratch. The types of user are organization, coder or none.

    :param request: HttpRequest.
    :returns: Name and type of Scratch user.
    """
    if request.user.is_authenticated():
        username = request.user.username
        if Organization.objects.filter(username=username.encode('utf-8')):
            return Organization.objects.get(username=username), 'organization'
        elif Coder.objects.filter(username=username.encode('utf-8')):
            return Coder.objects.get(username=username), 'coder'
    else:
        return None, 'main'


def save_entry_file_in_db(sb3_filename_from_form, username, method, datetime_now):
    """
    Save information of Scratch project as a File Object in a table in DB.

    :param sb3_filename_from_form: name of Scratch Project post in form
        by HTTP Request.
    :param username: string of user of Dr. Scratch to store in DB.
    :param method: string with analysis mode by project or by url.
    :param datetime_now: date when the project is registered.
    :return filename: File Object in DB with all fields fill in.
    """
    if Organization.objects.filter(username=username):
        filename = File(filename=sb3_filename_from_form,
                        organization=username,
                        method=method,
                        time=datetime_now,
                        score=0, abstraction=0, parallelization=0,
                        logic=0, synchronization=0, flowControl=0,
                        userInteractivity=0, dataRepresentation=0,
                        spriteNaming=0, initialization=0,
                        deadCode=0, duplicateScript=0)
    elif Coder.objects.filter(username=username):
        filename = File(filename=sb3_filename_from_form,
                        coder=username,
                        method=method,
                        time=datetime_now,
                        score=0, abstraction=0, parallelization=0,
                        logic=0, synchronization=0, flowControl=0,
                        userInteractivity=0, dataRepresentation=0,
                        spriteNaming=0, initialization=0,
                        deadCode=0, duplicateScript=0)
    else:
        filename = File(filename=sb3_filename_from_form,
                        method=method,
                        time=datetime_now,
                        score=0, abstraction=0, parallelization=0,
                        logic=0, synchronization=0, flowControl=0,
                        userInteractivity=0, dataRepresentation=0,
                        spriteNaming=0, initialization=0,
                        deadCode=0, duplicateScript=0)

    filename.save()

    return filename


def generate_uniqueid_for_saving_sb3(id_project):
    """
    Create an identifier to save the Scratch project. This id includes
    the date.

    :param id_project: Identifier of Scratch project.
    :return project_name_sb3: String with the name of Scratch project to save.
    """
    date_now = datetime.now()
    date_now_string = date_now.strftime("%Y_%m_%d_%H_%M_%S_%f")
    project_name_sb3 = id_project + "_" + date_now_string
    # Check that project_name_sb3 does not exist in the DB

    return project_name_sb3


def generate_unique_name_for_saving_project(sb3_filename_from_form):
    """
    Generate an unique identifier for a Scratch project.

    :param sb3_filename_from_form: Name of Scratch Project uploaded.
    :return unique_id: String with name and date of Scratch project.
    """

    now = datetime.now()
    date = now.strftime("%Y_%m_%d_%H_%M_%S_")
    ms = now.microsecond

    project_name = str(sb3_filename_from_form).split(".sb")[0]
    project_name = project_name.replace(" ", "_")
    unique_id = project_name + "_" + date + str(ms)

    return unique_id


def _make_analysis_by_upload(request):
    """Upload file from form POST for unregistered users.

    Search in form POST the value to field zipFile. This is the uploaded
    file object. This is how file data gets bound into a form. Save the
    project in the database and register it in logFile in the correct
    version. Write its content in folder upload, looping over file to
    ensures that large files don’t overwhelm the system’s memory.
    If any error occurs when analyzing the project, it is marked and
    goes to the folder error_analyzing.

    :param request: HTTP request.
    :return dict_metrics_ct: Dictionary with all metrics associated
        with Computational Thinking.
    :raise Exception: The project is empty or is not saved in the uploads folder.
    :ToDo refactor --This method is too long.
    """

    if request.method == 'POST':
        try:
            file_sb3_uploaded = request.FILES['zipFile']

        except:
            dict_metrics_ct = {'Error': 'MultiValueDict'}
            return dict_metrics_ct

        if request.user.is_authenticated():
            username = request.user.username
        else:
            username = None

        datetime_now = datetime.now()
        method = "project"

        sb3_filename_from_form = file_sb3_uploaded.name.encode('utf-8')
        file_object= save_entry_file_in_db(sb3_filename_from_form, username, method, datetime_now)
        write_entry_activity_in_logfile(file_object)

        sb3_unique_name = generate_unique_name_for_saving_project(sb3_filename_from_form)
        path_sb3_file_saved, version = check_version(sb3_filename_from_form, sb3_unique_name)

        with open(path_sb3_file_saved, 'wb+') as destination:
            for chunk in file_sb3_uploaded.chunks():
                destination.write(chunk)

        try:
            dict_metrics_ct = analyze_project(request, path_sb3_file_saved, file_object, ext_type_project=None)
        except Exception:
            traceback.print_exc()
            file_object.method = 'project/error'
            file_object.save()
            old_path_project = path_sb3_file_saved
            new_path_project = path_sb3_file_saved.split("/uploads/")[0] + "/error_analyzing/" + path_sb3_file_saved.split("/uploads/")[1]
            shutil.copy(old_path_project, new_path_project)
            dict_metrics_ct = {'Error': 'analyzing'}
            return dict_metrics_ct

        dict_metrics_ct['Error'] = 'None'

        return dict_metrics_ct

    else:
        return HttpResponseRedirect('/')


def _make_analysis_by_url(request):
    """
    Analyze Scratch project by URL. It takes the values, that have been
    sent with POST, in a object of class UrlForm. The validated form
    data will be in the url with the id_project. With that, you get a
    dictionary to this project.

    :param request: HttpRequest object.
    :return dict_metrics_ct: Dictionary with metrics associated with CT skills.
    """

    if request.method == "POST":
        form = UrlForm(request.POST)
        if form.is_valid():
            dict_metrics_ct = {}
            url = form.cleaned_data['urlProject']
            id_project = extract_scratch_idproject_from_url(url)
            if id_project == "error":
                dict_metrics_ct = {'Error': 'id_error'}
            else:
                dict_metrics_ct = generator_dic(request, id_project)
            return dict_metrics_ct
        else:
            dict_metrics_ct = {'Error': 'MultiValueDict'}
            return dict_metrics_ct
    else:
        return HttpResponseRedirect('/')


def extract_scratch_idproject_from_url(url):
    """Process String from URL Form.

    This method extracts a valid project identifier from the url.
    Verify that the id has an associated integer.

    :param url: string with url where id is searched.
    :return id_project: string contains the identifier of the project.
    :raises ValueError: id value is not integer when we make a casting.
    """
    id_project = ''
    aux_string = url.split("/")[-1]
    if aux_string == '':
        possible_id = url.split("/")[-2]
        if possible_id == "editor":
            id_project = url.split("/")[-3]
        else:
            id_project = possible_id
    else:
        if aux_string == "editor":
            id_project = url.split("/")[-2]
        else:
            id_project = aux_string

    try:
        check_int = int(id_project)
    except ValueError:
        logger.error('Project id is not an integer')
        id_project = "error"
    return id_project


def generator_dic(request, id_project):
    """
    Returns dictionary with analysis and errors.
    If any error occurs when analyzing the project, his method will be
    url/error. The path will change from uploads folder to error_analyzing
    folder.

    :param request: Http Request.
    :param id_project: Identifier of Scratch project.
    :return dict_metrics_ct: dictionary with metrics associated with CT skills
    :raise DrScratchException: Fail in logger. The dictionary does not exist.
    :raise Exception: The Scratch project does not exist in the Scratch server.
    """

    try:
        if request.user.is_authenticated():
            username = request.user.username
        else:
            username = None
        path_project, file, ext_type_project = send_request_getsb3(id_project, username, method="url")
    except DrScratchException:
        logger.error('DrScratchException')
        dict_metrics_ct = {'Error': 'no_exists'}
        return dict_metrics_ct
    except Exception:
        logger.error('File not found into Scratch server')
        traceback.print_exc()
        dict_metrics_ct = {'Error': 'no_exists'}
        return dict_metrics_ct

    try:
        dict_metrics_ct = analyze_project(request, path_project, file, ext_type_project)
    except Exception:
        logger.error('Impossible analyze project')
        traceback.print_exc()

        file.method = 'url/error'
        file.save()
        old_path_project = path_project
        new_path_project = path_project.split("/uploads/")[0] + "/error_analyzing/" + path_project.split("/uploads/")[1]
        shutil.copy(old_path_project, new_path_project)
        dict_metrics_ct = {'Error': 'analyzing'}
        return dict_metrics_ct

    dict_metrics_ct['Error'] = 'None'
    return dict_metrics_ct


def save_projectsb3(path_file_temporary, id_project):
    """
    Save Scratch project in sb3 format into uploads folder. The project goes from
    temporary folder utemp to upload folder.

    :param path_file_temporary: Path to temporary file associated with Scratch project.
    :param id_project: ID of Scratch project.
    :return unique_file_name_for_saving: Given name to identify the project sb3.
    :return ext_project: string with new or old project.json.
    """
    path_dir_zips = PATH_DRSCRATCH_PROJECT + "/uploads/"

    unique_id = generate_uniqueid_for_saving_sb3(id_project)
    unique_file_name_for_saving = path_dir_zips + unique_id + ".sb3"
    dir_utemp = path_file_temporary.split(id_project)[0].encode('utf-8')

    if '_new_project.json' in path_file_temporary:
        ext_project = '_new_project.json'
    else:
        ext_project = '_old_project.json'

    temporary_file_name = id_project + ext_project

    os.chdir(dir_utemp)  # Change the current working directory to dir_utemp #

    with zipfile.ZipFile(unique_file_name_for_saving, 'w') as myzip:
        os.rename(temporary_file_name, 'project.json')
        myzip.write('project.json')

    try:
        os.remove('project.json')
        os.chdir(PATH_DRSCRATCH_PROJECT)
    except:
        logger.error('Error removing temporary project.json')

    return unique_file_name_for_saving, ext_project


def send_request_getstudio(id_studio):
    api_get_projects_by_studio = "https://api.scratch.mit.edu/studios/" + id_studio + "/projects"


def write_entry_activity_in_logfile(file_object):
    """
    Add a new ent  in logFile of folder log with fileName, ID, method of
    analysis(url or project) and time. Write Scratch project in the
    log_file.

    :param file_object: File object with data of Scratch project.
    :raise OSError: Exception when the file log_file is not found.
    :raise Exception: Print other exception information and stack
        trace entries from traceback.
    """

    path_log = PATH_DRSCRATCH_PROJECT + "/log/"

    try:
        log_file = open(path_log + "logFile.txt", "a")
        log_file.write("FileName: " + str(file_object.filename) + "\t\t\t" + "ID: " + str(file_object.id) + "\t\t\t" +
                       "Method: " + str(file_object.method) + "\t\t\t" + "Time: " + str(file_object.time) + "\n")
    except OSError:
        logger.error('FileNotFoundError')
    except Exception:
        traceback.print_exc()
    finally:
        log_file.close()


def download_save_project_json_from_servers(id_project):
    """
    Download and save JSON file associated with Scratch project from Scratch
    servers. It'll be fetching onto servers MIT, the specified project.
    Open and write the json obtained as a response from the server
    in a file whose path goes to a utemp folder.

    :param id_project: unicode ID associated with the Scratch project.
    :return path_json_file: Path of JSON file of the project in utemp
        folder.
    :raise HTTPError: the Scratch project is hosted by another server
    or its id does not exist. Therefore, this server could not fulfill
    the request.
    :raise URLError: there is no route to the specified server or this server
        doesn’t exist. Server unreachable.
    :raise except: Print other exception information and stack
    trace entries from traceback.
    """
    random_string = uuid.uuid4().hex
    url_json_scratch = "https://projects.scratch.mit.edu/{}/get?foo={}".format(id_project, random_string)
    path_utemp = PATH_DRSCRATCH_PROJECT + '/utemp/' + str(id_project)
    path_json_file = path_utemp + '_new_project.json'

    try:
        response_from_scratch = urllib2.urlopen(url_json_scratch)
    except urllib2.HTTPError as e:
        print('The server could not fulfill the request.')
        # Two ways, id does not exist in servers or id is in other server
        logger.error('HTTPError %s', e.message)
        url_json_scratch = "http://127.0.0.1:3030/api/{}".format(id_project)
        response_from_scratch = urllib2.urlopen(url_json_scratch)
        path_json_file = path_utemp + '_old_project.json'
    except urllib2.URLError as e:
        print('We failed to reach a server.')
        logger.error('URLError: %s', e.message)
        traceback.print_exc()
    except:
        traceback.print_exc()

    try:
        json_string_format = response_from_scratch.read()
        json_data = json.loads(json_string_format)  #
        resulting_file = open(path_json_file, 'wb')
        resulting_file.write(json_string_format)
        resulting_file.close()
    except ValueError as e:
        logger.error('ValueError: %s', e.message)
        raise DrScratchException
    except IOError as e:
        logger.error('IOError %s' % e.message)
        raise IOError

    return path_json_file


def send_request_getsb3(id_project, username, method):
    """
    Get and save the selected Scratch project. Add an entry in logFile.

    :param id_project: ID associated with the Scratch project.
    :param username: User of Dr. Scratch to store in DB.
    :param method: project or url.
    :return path_scratch_project_sb3: locate the path to the project in uploads folder.
    :return ext_type_project: indicate if project.json has a new or old extension.
    :return file_name: object of class File saved.
    """

    file_url = id_project + ".sb3"

    path_json_file_temporary = download_save_project_json_from_servers(id_project)

    now = datetime.now()

    if Organization.objects.filter(username=username):
        file_name = File(filename=file_url,
                        organization=username,
                        method=method, time=now,
                        score=0, abstraction=0, parallelization=0,
                        logic=0, synchronization=0, flowControl=0,
                        userInteractivity=0, dataRepresentation=0,
                        spriteNaming=0, initialization=0,
                        deadCode=0, duplicateScript=0)
    elif Coder.objects.filter(username=username):
        file_name = File(filename=file_url,
                        coder=username,
                        method=method, time=now,
                        score=0, abstraction=0, parallelization=0,
                        logic=0, synchronization=0, flowControl=0,
                        userInteractivity=0, dataRepresentation=0,
                        spriteNaming=0, initialization=0,
                        deadCode=0, duplicateScript=0)
    else:
        file_name = File(filename=file_url,
                        method=method, time=now,
                        score=0, abstraction=0, parallelization=0,
                        logic=0, synchronization=0, flowControl=0,
                        userInteractivity=0, dataRepresentation=0,
                        spriteNaming=0, initialization=0,
                        deadCode=0, duplicateScript=0)

    file_name.save()

    write_entry_activity_in_logfile(file_name)

    path_scratch_project_sb3, ext_type_project = save_projectsb3(path_json_file_temporary, id_project)

    return path_scratch_project_sb3, file_name, ext_type_project


def handler_upload(file_saved, counter, sb3_unique_name):

    if os.path.exists(file_saved):
        counter = counter + 1
        version, file_saved_aux = check_version(file_saved, sb3_unique_name)

        if version == "3.0":
            if counter == 1:
                file_saved = file_saved.split(".")[0] + "(1).sb3"
            else:
                file_saved = file_saved.split('(')[0] + "(" + str(counter) + ").sb3"
        elif version == "2.0":
            if counter == 1:
                file_saved = file_saved.split(".")[0] + "(1).sb2"
            else:
                file_saved = file_saved.split('(')[0] + "(" + str(counter) + ").sb2"
        else:
            if counter == 1:
                file_saved = file_saved.split(".")[0] + "(1).sb"
            else:
                file_saved = file_saved.split('(')[0] + "(" + str(counter) + ").sb"

        file_name = handler_upload(file_saved, counter, sb3_unique_name)

        return file_name

    else:
        file_name = file_saved

        return file_name


def check_version(filename_scratch_project, sb3_unique_name):
    """Check the version of the project and return it with his path.

    :param sb3_unique_name: String with path, name of project and date.
    :param filename_scratch_project: Name of the Scratch project.
    :return version: The version of Dr Scratch (1.4, 2.0 or 3.0).
    :return path_sb3_file_saved: Name of project with extension and
        the correct path where the Scratch project is hosted.
    """

    dir_zips = PATH_DRSCRATCH_PROJECT + '/uploads/'
    extension = filename_scratch_project.split('.')[-1]
    path_sb3_file_saved = ""
    if extension == 'sb2':
        version = '2.0'
        path_sb3_file_saved = dir_zips + sb3_unique_name + ".sb2"
    elif extension == 'sb3':
        version = '3.0'
        path_sb3_file_saved = dir_zips + sb3_unique_name + ".sb3"
    else:
        version = '1.4'
        path_sb3_file_saved = dir_zips + sb3_unique_name + ".sb"

    return path_sb3_file_saved, version


def analyze_project(request, path_projectsb3, file_object, ext_type_project):
    """
    Open a ZIP file, where file is the path to a file object, load zip_file
    in format json to a dict Python object.
    Obtains the evaluation of the characteristics considered to measure
    the computational thinking: logic, flow_control, synchronization,
    abstraction, data representation, user interactivity and parallelization.
    Moreover, it collect the result of applying bad habits when programming,
    such as duplicated scripts, dead code, sprite or backdrop default names.
    All these results are stored and returned in a updated dictionary.

    :param request: HTTP request.
    :param path_projectsb3: locate the path to the project in uploads folder.
    :param file_object: Object of class File that collects information of bad smell related to Scratch project.
    :param ext_type_project: project in format JSON has a new or old extension.
    :return dict_metrics_ct: Dictionary with metrics associated with CT skills and bad smell code.
    :raise Exception: If Scratch project does not exist in uploads folder.
    """
    dict_metrics_ct = {}

    if os.path.exists(path_projectsb3):
        zip_file = zipfile.ZipFile(path_projectsb3, "r")
        json_project = json.loads(zip_file.open("project.json").read()) # Load data of zip as a JSON data
        result_mastery = mastery.main(json_project, path_projectsb3)
        #print("RESULT MASTERY", result_mastery, "RESULT MASTERY")
        result_sprite_naming = spriteNaming.main(json_project)
        result_backdrop_naming = backdropNaming.main(json_project)
        result_duplicate_script = duplicateScripts.main(json_project)
        print(result_duplicate_script)
        result_dead_code = deadCode.main(json_project, path_projectsb3)

        #print(result_dead_code)
        dict_metrics_ct.update(proc_mastery(request, result_mastery, file_object))
        dict_metrics_ct.update(proc_sprite_naming(result_sprite_naming, file_object))
        dict_metrics_ct.update(proc_backdrop_naming(result_backdrop_naming, file_object))
        dict_metrics_ct.update(proc_duplicate_script(result_duplicate_script, file_object))
        dict_metrics_ct.update(proc_dead_code(result_dead_code, file_object))
        # dictionary.update(proc_initialization(resultInitialization, filename))
        code = {'dupCode': duplicate_script_scratch_block(result_duplicate_script)}
        dict_metrics_ct.update(code)
        return dict_metrics_ct
    else:
        raise Exception


# _______________________________ PROCESSORS _________________________________#

def proc_mastery(request, result_mastery_analysis, file_object):
    """
    This method process the string result_mastery_analysis to save
    the total and partial points of CT in DB, for a given Scratch
    project. File object updates the score for each of the seven CT
    dimensions studied. The output is a dictionary that include
    the the total and partial punctuation of CT skills.

    :param request: HTTP request.
    :param result_mastery_analysis: string from which the mastery data
        is obtained.
    :param file_object: File object of Scratch project. Saved into DB.
    :return dict_mastery: Dictionary with parameters of Mastery plugin
        analysis.
    """
    dict_mastery = {}
    lLines = result_mastery_analysis.split('\n')

    dict_ct_skills = ast.literal_eval(lLines[1]) # Convierte un string con forma de dict a un objeto dict
    lLines = lLines[2].split(':')[1]
    points = int(lLines.split('/')[0])
    maxi = int(lLines.split('/')[1])

    file_object.score = points
    file_object.abstraction = dict_ct_skills["Abstraction"]
    file_object.parallelization = dict_ct_skills["Parallelization"]
    file_object.logic = dict_ct_skills["Logic"]
    file_object.synchronization = dict_ct_skills["Synchronization"]
    file_object.flowControl = dict_ct_skills["FlowControl"]
    file_object.userInteractivity = dict_ct_skills["UserInteractivity"]
    file_object.dataRepresentation = dict_ct_skills["DataRepresentation"]
    file_object.save()

    d_ct_skills_translated = _translate(request, dict_ct_skills, file_object)
    dict_mastery["mastery"] = d_ct_skills_translated
    dict_mastery["mastery"]["points"] = points
    dict_mastery["mastery"]["maxi"] = maxi

    return dict_mastery


def proc_duplicate_script(lines, filename):
    """
    Search the duplicated scripts contained in string lines, as well as
    their number. These values are stored inside the dictionary that is
    returned by the method.

    :param lines: String with information about duplicate scripts.
    :param filename: File object of Scratch project. Saved in DB.
    :return dict_duplicate_script: Dictionary with number and duplicate
        script found.
    """
    dict_duplicate_script = {}
    number = 0
    lLines = lines.split('\n')
    number = lLines[0].split(" ")[0]
    dict_duplicate_script["duplicateScript"] = dict_duplicate_script
    dict_duplicate_script["duplicateScript"]["number"] = number
    # if number != "0":
    #     dic["duplicateScript"]["duplicated"] = lLines[1:-1]

    filename.duplicateScript = number
    filename.save()

    return dict_duplicate_script


def proc_sprite_naming(lines, filename):
    """
    Get a list of the default sprites contained in lines, as well as
    their number. these values are stored inside the dictionary that is
    returned by the function.

    :param lines: String to extract information about sprite names.
    :param filename: File object of Scratch project. Saved in DB
    :return dict_sprite_naming: Mapping number and sprite names by
        default that appear in lines.
    """
    dict_sprite_naming = {}
    lLines = lines.split('\n')
    number = lLines[0].split(' ')[0]
    lObjects = lLines[1:]
    lfinal = lObjects[:-1]
    dict_sprite_naming['spriteNaming'] = dict_sprite_naming
    dict_sprite_naming['spriteNaming']['number'] = int(number)
    dict_sprite_naming['spriteNaming']['sprite'] = lfinal

    filename.spriteNaming = number
    filename.save()

    return dict_sprite_naming


def proc_backdrop_naming(result_backdrop_naming_analysis, filename):
    """
    Extract the number and default backdrop naming from given string
    as parameter. The number and the list of retrieved backdrop naming
    are stored into a dictionary. The number of default backdrop naming
    is saved in DB.

    :param result_backdrop_naming_analysis: String with information
        of backdrop naming.
    :param filename: File object of Scratch project. Saved in DB.
    :return dict_backdrop_naming: Dictionary with number and backdrop names.
    """
    dict_backdrop_naming = {}
    lLines = result_backdrop_naming_analysis.split('\n') # %d default backdrop names found:\n" % self.total_default
    number = lLines[0].split(' ')[0]
    lObjects = lLines[1:]
    lfinal = lObjects[:-1]
    dict_backdrop_naming['backdropNaming'] = dict_backdrop_naming
    dict_backdrop_naming['backdropNaming']['number'] = int(number)
    dict_backdrop_naming['backdropNaming']['backdrop'] = lfinal

    filename.backdropNaming = number
    filename.save()

    return dict_backdrop_naming


def proc_dead_code(result_dead_coded_analysis, filename):
    """
    Gets a dictionary containing the blocks of dead code. Save in
    the dictionary the number of items of dead code. Save this number
    in DB.

    :param result_dead_coded_analysis: String separated by break line by
        summarizing the result from DeadCode plugin.
    :param filename: File object used for saving information related
        to project analyzed.
    :return dict_dead_code: Dictionary with parameters of DeadCode analysis.
    """
    dead_code = result_dead_coded_analysis.split("\n")[1:]
    iterator = 0
    lcharacter = []
    lblocks = []

    if dead_code:
        d = ast.literal_eval(dead_code[0])
        for keys, values in d.items():
            lcharacter.append(keys)
            lblocks.append(values)
            iterator += len(values)

    dict_dead_code = {}
    dict_dead_code["deadCode"] = dict_dead_code
    dict_dead_code["deadCode"]["number"] = iterator

    number = len(lcharacter)

    for i in range(number):
        dict_dead_code["deadCode"][lcharacter[i].encode('utf-8')] = lblocks[i]

    filename.deadCode = iterator
    filename.save()
    return dict_dead_code


"""
def proc_initialization(lines, filename):


    dic = {}
    lLines = lines.split('.sb2')
    d = ast.literal_eval(lLines[1])
    keys = d.keys()
    values = d.values()
    items = d.items()
    number = 0

    for keys, values in items:
        list = []
        attribute = ""
        internalkeys = values.keys()
        internalvalues = values.values()
        internalitems = values.items()
        flag = False
        counterFlag = False
        i = 0
        for internalkeys, internalvalues in internalitems:
            if internalvalues == 1:
                counterFlag = True
                for value in list:
                    if internalvalues == value:
                        flag = True
                if not flag:
                    list.append(internalkeys)
                    if len(list) < 2:
                        attribute = str(internalkeys)
                    else:
                        attribute = attribute + ", " + str(internalkeys)
        if counterFlag:
            number = number + 1
        d[keys] = attribute
    dic["initialization"] = d
    dic["initialization"]["number"] = number

    #Save in DB
    filename.initialization = number
    filename.save()

    return dic

"""


# ____________________  INFORMATION TO SCRATCH BLOCKS  ________________________#

def duplicate_script_scratch_block(code):
    """
    Get the duplicated script from given code as parameter.

    :param code: string in which repeating code is searched.
    :return code: string with output of duplicated code.
    """
    try:
        code = code.split("\n")[1:][0]
        if code == "":  # No duplicated scripts found
            code = ""
        else:
            code = code[1:-1].split(",")
    except:
        code = ""

    return code

# ______________________________ TRANSLATE MASTERY ___________________________#

def _translate(request, d, filename):
    """Translate the output of Scratch project.

    Assign the seven computational thinking skills to a dictionary
    in the chosen language. Save this language in DB.

    :param request: HTTP Request.
    :param d: dictionary with CT skills in english.
    :param filename: File Object saves the chosen language.
    :return d_translate_any: dictionary with CT skills in selected language.
    """

    if request.LANGUAGE_CODE == "es":
        d_translate_es = {}
        d_translate_es['Abstracción'] = d['Abstraction']
        d_translate_es['Paralelismo'] = d['Parallelization']
        d_translate_es['Pensamiento lógico'] = d['Logic']
        d_translate_es['Sincronización'] = d['Synchronization']
        d_translate_es['Control de flujo'] = d['FlowControl']
        d_translate_es['Interactividad con el usuario'] = d['UserInteractivity']
        d_translate_es['Representación de la información'] = d['DataRepresentation']
        filename.language = "es"
        filename.save()
        return d_translate_es
    elif request.LANGUAGE_CODE == "en":
        d_translate_en = {}
        d_translate_en['Abstraction'] = d['Abstraction']
        d_translate_en['Parallelism'] = d['Parallelization']
        d_translate_en['Logic'] = d['Logic']
        d_translate_en['Synchronization'] = d['Synchronization']
        d_translate_en['Flow control'] = d['FlowControl']
        d_translate_en['User interactivity'] = d['UserInteractivity']
        d_translate_en['Data representation'] = d['DataRepresentation']
        filename.language = "en"
        filename.save()
        return d_translate_en
    elif request.LANGUAGE_CODE == "ca":
        d_translate_ca = {}
        d_translate_ca['Abstracció'] = d['Abstraction']
        d_translate_ca['Paral·lelisme'] = d['Parallelization']
        d_translate_ca['Lògica'] = d['Logic']
        d_translate_ca['Sincronització'] = d['Synchronization']
        d_translate_ca['Controls de flux'] = d['FlowControl']
        d_translate_ca["Interactivitat de l'usuari"] = d['UserInteractivity']
        d_translate_ca['Representació de dades'] = d['DataRepresentation']
        filename.language = "ca"
        filename.save()
        return d_translate_ca
    elif request.LANGUAGE_CODE == "gl":
        d_translate_gl = {}
        d_translate_gl['Abstracción'] = d['Abstraction']
        d_translate_gl['Paralelismo'] = d['Parallelization']
        d_translate_gl['Lóxica'] = d['Logic']
        d_translate_gl['Sincronización'] = d['Synchronization']
        d_translate_gl['Control de fluxo'] = d['FlowControl']
        d_translate_gl["Interactividade do susario"] = d['UserInteractivity']
        d_translate_gl['Representación dos datos'] = d['DataRepresentation']
        filename.language = "gl"
        filename.save()
        return d_translate_gl

    elif request.LANGUAGE_CODE == "pt":
        d_translate_pt = {}
        d_translate_pt['Abstração'] = d['Abstraction']
        d_translate_pt['Paralelismo'] = d['Parallelization']
        d_translate_pt['Lógica'] = d['Logic']
        d_translate_pt['Sincronização'] = d['Synchronization']
        d_translate_pt['Controle de fluxo'] = d['FlowControl']
        d_translate_pt["Interatividade com o usuário"] = d['UserInteractivity']
        d_translate_pt['Representação de dados'] = d['DataRepresentation']
        filename.language = "pt"
        filename.save()
        return d_translate_pt

    elif request.LANGUAGE_CODE == "el":
        d_translate_el = {}
        d_translate_el['Αφαίρεση'] = d['Abstraction']
        d_translate_el['Παραλληλισμός'] = d['Parallelization']
        d_translate_el['Λογική'] = d['Logic']
        d_translate_el['Συγχρονισμός'] = d['Synchronization']
        d_translate_el['Έλεγχος ροής'] = d['FlowControl']
        d_translate_el['Αλληλεπίδραση χρήστη'] = d['UserInteractivity']
        d_translate_el['Αναπαράσταση δεδομένων'] = d['DataRepresentation']
        filename.language = "el"
        filename.save()
        return d_translate_el

    elif request.LANGUAGE_CODE == "eu":
        d_translate_eu = {}
        d_translate_eu['Abstrakzioa'] = d['Abstraction']
        d_translate_eu['Paralelismoa'] = d['Parallelization']
        d_translate_eu['Logika'] = d['Logic']
        d_translate_eu['Sinkronizatzea'] = d['Synchronization']
        d_translate_eu['Kontrol fluxua'] = d['FlowControl']
        d_translate_eu['Erabiltzailearen elkarreragiletasuna'] = d['UserInteractivity']
        d_translate_eu['Datu adierazlea'] = d['DataRepresentation']
        filename.language = "eu"
        filename.save()
        return d_translate_eu

    elif request.LANGUAGE_CODE == "it":
        d_translate_it = {}
        d_translate_it['Astrazione'] = d['Abstraction']
        d_translate_it['Parallelismo'] = d['Parallelization']
        d_translate_it['Logica'] = d['Logic']
        d_translate_it['Sincronizzazione'] = d['Synchronization']
        d_translate_it['Controllo di flusso'] = d['FlowControl']
        d_translate_it['Interattività utente'] = d['UserInteractivity']
        d_translate_it['Rappresentazione dei dati'] = d['DataRepresentation']
        filename.language = "it"
        filename.save()
        return d_translate_it

    elif request.LANGUAGE_CODE == "ru":
        d_translate_ru = {}
        d_translate_ru['Абстракция'] = d['Abstraction']
        d_translate_ru['Параллельность действий'] = d['Parallelization']
        d_translate_ru['Логика'] = d['Logic']
        d_translate_ru['cинхронизация'] = d['Synchronization']
        d_translate_ru['Управление потоком'] = d['FlowControl']
        d_translate_ru['Интерактивность'] = d['UserInteractivity']
        d_translate_ru['Представление данных'] = d['DataRepresentation']
        filename.language = "ru"
        filename.save()
        return d_translate_ru


    else:
        d_translate_en = {}
        d_translate_en['Abstraction'] = d['Abstraction']
        d_translate_en['Parallelism'] = d['Parallelization']
        d_translate_en['Logic'] = d['Logic']
        d_translate_en['Synchronization'] = d['Synchronization']
        d_translate_en['Flow control'] = d['FlowControl']
        d_translate_en['User interactivity'] = d['UserInteractivity']
        d_translate_en['Data representation'] = d['DataRepresentation']
        filename.language = "any"
        filename.save()
        return d_translate_any


###############################################################################

###############################################################################

# _______________________________ LEARN MORE __________________________________#

def learn(request, page):
    """
    Shows pages to learn more about every CT in the chosen language.
    The user receives advice on how to improve each skill.

    :param request: HTTP request.
    :param page: requested resource to learn more about a specific skill CT.
    """
    flagUser = 0

    if request.user.is_authenticated():
        user = request.user.username
        flagUser = 1

    if request.LANGUAGE_CODE == "en":
        dic = {u'Logic': 'Logic',
               u'Parallelism': 'Parallelism',
               u'Data': 'Data',
               u'Synchronization': 'Synchronization',
               u'User': 'User',
               u'Flow': 'Flow',
               u'Abstraction': 'Abstraction'}
    elif request.LANGUAGE_CODE == "es":
        page = unicodedata.normalize('NFKD', page).encode('ascii', 'ignore')
        dic = {'Pensamiento': 'Logic',
               'Paralelismo': 'Parallelism',
               'Representacion': 'Data',
               'Sincronizacion': 'Synchronization',
               'Interactividad': 'User',
               'Control': 'Flow',
               'Abstraccion': 'Abstraction'}
    elif request.LANGUAGE_CODE == "ca":
        page = unicodedata.normalize('NFKD', page).encode('ascii', 'ignore')
        dic = {u'Logica': 'Logic',
               u'Paral': 'Parallelism',
               u'Representacio': 'Data',
               u'Sincronitzacio': 'Synchronization',
               u'Interactivitat': 'User',
               u'Controls': 'Flow',
               u'Abstraccio': 'Abstraction'}
    elif request.LANGUAGE_CODE == "gl":
        page = unicodedata.normalize('NFKD', page).encode('ascii', 'ignore')
        dic = {'Loxica': 'Logic',
               'Paralelismo': 'Parallelism',
               'Representacion': 'Data',
               'Sincronizacion': 'Synchronization',
               'Interactividade': 'User',
               'Control': 'Flow',
               'Abstraccion': 'Abstraction'}
    elif request.LANGUAGE_CODE == "pt":
        page = unicodedata.normalize('NFKD', page).encode('ascii', 'ignore')
        dic = {'Logica': 'Logic',
               'Paralelismo': 'Parallelism',
               'Representacao': 'Data',
               'Sincronizacao': 'Synchronization',
               'Interatividade': 'User',
               'Controle': 'Flow',
               'Abstracao': 'Abstraction'}
    elif request.LANGUAGE_CODE == "el":
        dic = {u'Λογική': 'Logic',
               u'Παραλληλισμός': 'Parallelism',
               u'Αναπαράσταση': 'Data',
               u'Συγχρονισμός': 'Synchronization',
               u'Αλληλεπίδραση': 'User',
               u'Έλεγχος': 'Flow',
               u'Αφαίρεση': 'Abstraction'}
    elif request.LANGUAGE_CODE == "eu":
        page = unicodedata.normalize('NFKD', page).encode('ascii', 'ignore')
        dic = {u'Logika': 'Logic',
               u'Paralelismoa': 'Parallelism',
               u'Datu': 'Data',
               u'Sinkronizatzea': 'Synchronization',
               u'Erabiltzailearen': 'User',
               u'Kontrol': 'Flow',
               u'Abstrakzioa': 'Abstraction'}
    elif request.LANGUAGE_CODE == "it":
        page = unicodedata.normalize('NFKD', page).encode('ascii', 'ignore')
        dic = {u'Logica': 'Logic',
               u'Parallelismo': 'Parallelism',
               u'Rappresentazione': 'Data',
               u'Sincronizzazione': 'Synchronization',
               u'Interattivita': 'User',
               u'Controllo': 'Flow',
               u'Astrazione': 'Abstraction'}
    elif request.LANGUAGE_CODE == "ru":
        dic = {u'Логика': 'Logic',
               u'Параллельность': 'Parallelism',
               u'Представление': 'Data',
               u'cинхронизация': 'Synchronization',
               u'Интерактивность': 'User',
               u'Управление': 'Flow',
               u'Абстракция': 'Abstraction'}
    else:
        dic = {u'Logica': 'Logic',
               u'Paralelismo': 'Parallelism',
               u'Representacao': 'Data',
               u'Sincronizacao': 'Synchronization',
               u'Interatividade': 'User',
               u'Controle': 'Flow',
               u'Abstracao': 'Abstraction'}

    if page in dic:
        page = dic[page]

    page = "learn/" + page + ".html"

    if request.user.is_authenticated():
        user = get_type_user(request)
        username = request.user.username
        return render(request, page, {'flagUser': flagUser, 'user': user, 'username': username})
    else:
        return render(request, page)


def download_certificate(request):
    """Function to download your project's certificate.

    This method process the POST request to get the filename, the score
    and the language of the sb3 project. The certificate is generated
    with these parameters. The programmer can see his obtained level
    on pdf format as response.

    :param request: HTTP Request with data for certificate.
    :returns response: HTTP Response with the PDF file.
    """

    if request.method == "POST":
        data = request.POST["certificate"]
        data = unicodedata.normalize('NFKD', data).encode('ascii', 'ignore')
        filename = data.split(",")[0]
        level = data.split(",")[1]

        if request.LANGUAGE_CODE == 'es' or request.LANGUAGE_CODE == 'ca' or request.LANGUAGE_CODE == 'gl' or request.LANGUAGE_CODE == 'pt':
            language = request.LANGUAGE_CODE
        else:
            language = 'en'

        pyploma.generate(filename, level, language)
        path_to_file = PATH_DRSCRATCH_PROJECT + "/app/certificate/output.pdf"

        pdf_data = open(path_to_file, 'r')
        response = HttpResponse(pdf_data, content_type='application/pdf')

        try:
            file_pdf = filename.split("/")[-2] + ".pdf"
        except:
            file_pdf = filename.split(".")[0] + ".pdf"

        response['Content-Disposition'] = 'attachment; filename=%s' % file_pdf
        return response
    else:
        return HttpResponseRedirect('/')


# ___________________________ ASYNCHRONOUS FORMS ______________________________#

def search_email(request):
    """Confirm email"""

    if request.is_ajax():
        user = Organization.objects.filter(email=request.GET['email'])
        if user:
            return HttpResponse(json.dumps({"exist": "yes"}),
                                content_type='application/json')


def search_username(request):
    """Confirm username"""

    if request.is_ajax():
        user = Organization.objects.filter(username=request.GET['username'])
        if user:
            return HttpResponse(json.dumps({"exist": "yes"}),
                                content_type='application/json')


def search_hashkey(request):
    """Confirm hashkey"""

    if request.is_ajax():
        user = OrganizationHash.objects.filter(hashkey=request.GET['hashkey'])
        if not user:
            return HttpResponse(json.dumps({"exist": "yes"}),
                                content_type='application/json')


# ____________________________ PLUG-INS _______________________________________#

def plugin(request, urlProject):
    """Analysis by plugin"""

    user = None
    idProject = extract_scratch_idproject_from_url(urlProject)
    d = generator_dic(request, idProject)
    # Find if any error has occurred
    if d['Error'] == 'analyzing':
        return render(request, user + '/error_analyzing.html')

    elif d['Error'] == 'MultiValueDict':
        error = True
        return render(request, user + '/main.html', {'error': error})

    elif d['Error'] == 'id_error':
        id_error = True
        return render(request, user + '/main.html', {'id_error': id_error})

    elif d['Error'] == 'no_exists':
        no_exists = True
        return render(request, user + '/main.html', {'no_exists': no_exists})

    # Show the dashboard according the CT level
    else:
        user = "main"
        base_dir = os.getcwd()
        if d["mastery"]["points"] >= 15:
            return render(request, user + '/dashboard-master.html', d)

        elif d["mastery"]["points"] > 7:
            return render(request, user + '/dashboard-developing.html', d)

        else:
            return render(request, user + '/dashboard-basic.html', d)

        # _____________________ TRANSLATION SCRATCHBLOCKS______________________________#


def blocks(request):
    """Translate blocks of Scratch shown in learn pages"""

    callback = request.GET.get('callback')
    headers = {}
    headers['Accept-Language'] = str(request.LANGUAGE_CODE)

    headers = json.dumps(headers)  #vuelca las cabeceras
    if callback:
        headers = '%s(%s)' % (callback, headers)
        return HttpResponse(headers, content_type="application/json")


def blocks_v3(request):
    return render(request, 'learn/blocks_v3.html')


# _____________________________ TO REGISTER ORGANIZATION ______________________#

def organization_hash(request):
    """Method for to sign up in the platform"""

    if request.method == "POST":
        form = OrganizationHashForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('/organization_hash')
    elif request.method == 'GET':
        return render(request, 'organization/organization-hash.html')

    else:
        return HttpResponseRedirect('/')


def sign_up_organization(request):
    """Method which allow to sign up organizations"""

    flagOrganization = 1
    flagHash = 0
    flagName = 0
    flagEmail = 0
    flagForm = 0
    if request.method == 'POST':
        form = OrganizationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            hashkey = form.cleaned_data['hashkey']

            # Checking the validity into the dbdata contents.
            # They will be refused if they already exist.
            # If they exist an error message will be shown.
            if User.objects.filter(username=username):
                # This name already exists
                flagName = 1
                return render(request, 'error/sign-up.html',
                              {'flagName': flagName,
                               'flagEmail': flagEmail,
                               'flagHash': flagHash,
                               'flagForm': flagForm,
                               'flagOrganization': flagOrganization})

            elif User.objects.filter(email=email):
                # This email already exists
                flagEmail = 1
                return render(request, 'error/sign-up.html',
                              {'flagName': flagName,
                               'flagEmail': flagEmail,
                               'flagHash': flagHash,
                               'flagForm': flagForm,
                               'flagOrganization': flagOrganization})

            if OrganizationHash.objects.filter(hashkey=hashkey):
                organizationHashkey = OrganizationHash.objects.get(hashkey=hashkey)
                organization = Organization.objects.create_user(username=username,
                                                                email=email,
                                                                password=password,
                                                                hashkey=hashkey)
                organizationHashkey.delete()
                organization = authenticate(username=username, password=password)
                user = Organization.objects.get(email=email)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                c = {
                    'email': email,
                    'uid': uid,
                    'token': token}

                body = render_to_string("organization/email-sign-up.html", c)
                subject = "Welcome to Dr. Scratch for organizations"
                sender = "no-reply@drscratch.org"
                to = [email]
                email = EmailMessage(subject, body, sender, to)
                # email.attach_file("static/app/images/logo_main.png")
                email.send()
                login(request, organization)
                return HttpResponseRedirect('/organization/' + organization.username)

            else:
                # Doesn't exist this hash
                flagHash = 1

                return render(request, 'error/sign-up.html',
                              {'flagName': flagName,
                               'flagEmail': flagEmail,
                               'flagHash': flagHash,
                               'flagForm': flagForm,
                               'flagOrganization': flagOrganization})


        else:
            flagForm = 1
            return render(request, 'error/sign-up.html',
                          {'flagName': flagName,
                           'flagEmail': flagEmail,
                           'flagHash': flagHash,
                           'flagForm': flagForm,
                           'flagOrganization': flagOrganization})

    elif request.method == 'GET':
        if request.user.is_authenticated():
            return HttpResponseRedirect('/organization/' + request.user.username)
        else:
            return render(request, 'organization/organization.html')


# _________________________ TO SHOW ORGANIZATION'S DASHBOARD ___________#

def login_organization(request):
    """Log in app to user"""

    if request.method == 'POST':
        flag = False
        flagOrganization = 0
        form = LoginOrganizationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            organization = authenticate(username=username, password=password)
            if organization is not None:
                if organization.is_active:
                    login(request, organization)
                    return HttpResponseRedirect('/organization/' + organization.username)

            else:
                flag = True
                flagOrganization = 1
                return render(request, 'sign-password/user-doesnt-exist.html',
                              {'flag': flag,
                               'flagOrganization': flagOrganization})

    else:
        return HttpResponseRedirect("/")


def logout_organization(request):
    """Method for logging out"""
    logout(request)
    return HttpResponseRedirect('/')


def organization(request, name):
    """Show page of Organizations to sign up"""

    if request.method == 'GET':
        if request.user.is_authenticated():
            username = request.user.username
            if username == name:
                if Organization.objects.filter(username=username):
                    user = Organization.objects.get(username=username)
                    img = user.img
                    dic = {'username': username,
                           "img": str(img)}

                    return render(request, 'organization/main.html', dic)

                else:
                    logout(request)
                    return HttpResponseRedirect("/organization")

            else:
                # logout(request)
                return render(request, 'organization/organization.html')

        return render(request, 'organization/organization.html')

    else:
        return HttpResponseRedirect("/")


def stats(request, username):
    """Generator of the stats from Coders and Organizations"""

    flagOrganization = 0
    flagCoder = 0
    if Organization.objects.filter(username=username):
        flagOrganization = 1
        page = 'organization'
        user = Organization.objects.get(username=username)
    elif Coder.objects.filter(username=username):
        flagCoder = 1
        page = 'coder'
        user = Coder.objects.get(username=username)

    date_joined = user.date_joined
    end = datetime.today()
    end = date(end.year, end.month, end.day)
    start = date(date_joined.year, date_joined.month, date_joined.day)
    dateList = date_range(start, end)
    daily_score = []
    mydates = []
    for n in dateList:
        mydates.append(n.strftime("%d/%m"))
        if flagOrganization:
            points = File.objects.filter(organization=username).filter(time=n)
        elif flagCoder:
            points = File.objects.filter(coder=username).filter(time=n)
        points = points.aggregate(Avg("score"))["score__avg"]
        daily_score.append(points)

    for n in daily_score:
        if n == None:
            daily_score[daily_score.index(n)] = 0

    if flagOrganization:
        f = File.objects.filter(organization=username)
    elif flagCoder:
        f = File.objects.filter(coder=username)
    if f:

        # If the org has analyzed projects
        parallelism = f.aggregate(Avg("parallelization"))
        parallelism = int(parallelism["parallelization__avg"])
        abstraction = f.aggregate(Avg("abstraction"))
        abstraction = int(abstraction["abstraction__avg"])
        logic = f.aggregate(Avg("logic"))
        logic = int(logic["logic__avg"])
        synchronization = f.aggregate(Avg("synchronization"))
        synchronization = int(synchronization["synchronization__avg"])
        flowControl = f.aggregate(Avg("flowControl"))
        flowControl = int(flowControl["flowControl__avg"])
        userInteractivity = f.aggregate(Avg("userInteractivity"))
        userInteractivity = int(userInteractivity["userInteractivity__avg"])
        dataRepresentation = f.aggregate(Avg("dataRepresentation"))
        dataRepresentation = int(dataRepresentation["dataRepresentation__avg"])

        deadCode = File.objects.all().aggregate(Avg("deadCode"))
        deadCode = int(deadCode["deadCode__avg"])
        duplicateScript = File.objects.all().aggregate(Avg("duplicateScript"))
        duplicateScript = int(duplicateScript["duplicateScript__avg"])
        spriteNaming = File.objects.all().aggregate(Avg("spriteNaming"))
        spriteNaming = int(spriteNaming["spriteNaming__avg"])
        initialization = File.objects.all().aggregate(Avg("initialization"))
        initialization = int(initialization["initialization__avg"])
    else:

        # If the org hasn't analyzed projects yet
        parallelism, abstraction, logic = [0], [0], [0]
        synchronization, flowControl, userInteractivity = [0], [0], [0]
        dataRepresentation, deadCode, duplicateScript = [0], [0], [0]
        spriteNaming, initialization = [0], [0]

    # Saving data in the dictionary
    dic = {
        "date": mydates,
        "username": username,
        "img": user.img,
        "daily_score": daily_score,
        "skillRate": {"parallelism": parallelism,
                      "abstraction": abstraction,
                      "logic": logic,
                      "synchronization": synchronization,
                      "flowControl": flowControl,
                      "userInteractivity": userInteractivity,
                      "dataRepresentation": dataRepresentation},
        "codeSmellRate": {"deadCode": deadCode,
                          "duplicateScript": duplicateScript,
                          "spriteNaming": spriteNaming,
                          "initialization": initialization}}

    return render(request, page + '/stats.html', dic)


def settings(request, username):
    """Allow to Coders and Organizations change the image and password"""

    base_dir = os.getcwd()
    if base_dir == "/":
        base_dir = "/var/www/drscratchv3"
    flagOrganization = 0
    flagCoder = 0
    if Organization.objects.filter(username=username):
        page = 'organization'
        user = Organization.objects.get(username=username)
    elif Coder.objects.filter(username=username):
        page = 'coder'
        user = Coder.objects.get(username=username)

    if request.method == "POST":

        # Saving image in DB
        user.img = request.FILES["img"]
        os.chdir(base_dir + "/static/img")
        user.img.name = str(user.img)

        if os.path.exists(user.img.name):
            os.remove(user.img.name)

        os.chdir(base_dir)
        user.save()

    dic = {
        "username": username,
        "img": user.img
    }

    return render(request, page + '/settings.html', dic)


def downloads(request, username, filename=""):
    """Allow to Coders and Organizations download the files.CSV already analyzed"""

    flagOrganization = 0
    flagCoder = 0
    # segmentation
    if Organization.objects.filter(username=username):
        flagOrganization = 1
        user = Organization.objects.get(username=username)
    elif Coder.objects.filter(username=username):
        flagCoder = 1
        user = Coder.objects.get(username=username)

    if flagOrganization:
        csv = CSVs.objects.all().filter(organization=username)
        page = 'organization'
    elif flagCoder:
        csv = CSVs.objects.all().filter(coder=username)
        page = 'coder'
    # LIFO to show the files.CSV

    csv_len = len(csv)
    lower = 0
    upper = 10
    list_csv = {}

    if csv_len > 10:
        for n in range((csv_len / 10) + 1):
            list_csv[str(n)] = csv[lower:upper - 1]
            lower = upper
            upper = upper + 10

        dic = {
            "username": username,
            "img": user.img,
            "csv": list_csv,
            "flag": 1
        }
    else:
        dic = {
            "username": username,
            "img": user.img,
            "csv": csv,
            "flag": 0
        }

    if request.method == "POST":
        filename = request.POST["csv"]
        path_to_file = PATH_DRSCRATCH_PROJECT + "/csvs/Dr.Scratch/" + filename
        csv_data = open(path_to_file, 'r')
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s' % smart_str(filename)
        return response

    return render(request, page + '/downloads.html', dic)


# ________________________ ANALYZE CSV FOR ORGANIZATIONS ____________#

def analyze_CSV(request):
    """Analyze files.CSV with a list of projects to analyze them at a time"""

    if request.method == 'POST':
        if "_upload" in request.POST:
            # Analize CSV file
            csv_data = 0
            flag_csv = False
            file = request.FILES['csvFile']
            file_name = request.user.username + "_" + str(datetime.now()) + \
                        ".csv"  # file.name.encode('utf-8')
            dir_csvs = PATH_DRSCRATCH_PROJECT + "/csvs/" + file_name
            # Save file .csv
            with open(dir_csvs, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            dictionary = {}
            for line in open(dir_csvs, 'r'):
                row = len(line.split(","))
                type_csv = ""
                username = request.user.username

                # Check doesn't exist any old project.json
                try:
                    os.remove(dir_zips + "project.json")
                except:
                    print("No existe")

                if row == 2:
                    type_csv = "2_row"
                    code = line.split(",")[0]
                    url = line.split(",")[1]
                    url = url.split("\n")[0]
                    method = "csv"
                    if url.isdigit():
                        idProject = url
                    else:
                        slashNum = url.count('/')
                        if slashNum == 4:
                            idProject = url.split("/")[-1]
                        elif slashNum == 5:
                            idProject = url.split('/')[-2]
                    try:
                        pathProject, file = send_request_getsb3(idProject, username, method)
                        d = analyze_project(request, pathProject, file)
                    except:
                        d = ["Error analyzing project", url]

                    try:
                        os.remove(dir_zips + "project.json")
                    except:
                        print("No existe")

                    dic = {}
                    dic[line] = d
                    dictionary.update(dic)
                elif row == 1:
                    type_csv = "1_row"
                    url = line.split("\n")[0]
                    method = "csv"
                    if url.isdigit():
                        idProject = url
                    else:
                        slashNum = url.count('/')
                        if slashNum == 4:
                            idProject = url.split("/")[-1]
                        elif slashNum == 5:
                            idProject = url.split('/')[-2]
                    try:
                        pathProject, file = send_request_getsb3(idProject, username, method)
                        d = analyze_project(request, pathProject, file)
                    except:
                        d = ["Error analyzing project", url]

                    try:
                        os.remove(dir_zips + "project.json")
                    except:
                        print("No existe")

                    dic = {}
                    dic[url] = d
                    dictionary.update(dic)

            csv_data = generator_CSV(request, dictionary, file_name, type_csv)

            # segmentation
            if Organization.objects.filter(username=username):
                csv_save = CSVs(filename=file_name,
                                directory=csv_data,
                                organization=username)

                page = 'organization'
            elif Coder.objects.filter(username=username):
                csv_save = CSVs(filename=file_name,
                                directory=csv_data,
                                coder=username)
                page = 'coder'
            csv_save.save()

            return HttpResponseRedirect('/' + page + "/downloads/" + username)

        elif "_download" in request.POST:
            # Export a CSV File

            if request.user.is_authenticated():
                username = request.user.username
            csv = CSVs.objects.latest('date')

            path_to_file = PATH_DRSCRATCH_PROJECT + "/csvs/Dr.Scratch/" + csv.filename
            csv_data = open(path_to_file, 'r')
            response = HttpResponse(csv_data, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=%s' % smart_str(csv.filename)
            return response

    else:
        return HttpResponseRedirect("/organization")


# _________________________GENERATOR CSV FOR ORGANIZATION____________________________#

def generator_CSV(request, dictionary, filename, type_csv):
    """Generator of a csv file"""

    csv_directory = os.path.dirname(os.path.dirname(__file__)) + \
                    "/csvs/Dr.Scratch/"
    csv_data = csv_directory + filename
    writer = csv.writer(open(csv_data, "wb"))
    dic = org.translate_CT(request.LANGUAGE_CODE)

    if type_csv == "2_row":
        writer.writerow([dic["code"], dic["url"], dic["mastery"],
                         dic["abstraction"], dic["parallelism"],
                         dic["logic"], dic["sync"],
                         dic["flow_control"], dic["user_inter"], dic["data_rep"],
                         dic["dup_scripts"], dic["sprite_naming"],
                         dic["dead_code"], dic["attr_init"]])

    elif type_csv == "1_row":
        writer.writerow([dic["url"], dic["mastery"],
                         dic["abstraction"], dic["parallelism"],
                         dic["logic"], dic["sync"],
                         dic["flow_control"], dic["user_inter"], dic["data_rep"],
                         dic["dup_scripts"], dic["sprite_naming"],
                         dic["dead_code"], dic["attr_init"]])

    for key, value in dictionary.items():
        total = 0
        flag = False
        try:
            if value[0] == "Error analyzing project":
                if type_csv == "2_row":
                    row1 = key.split(",")[0]
                    row2 = key.split(",")[1]
                    row2 = row2.split("\n")[0]
                    writer.writerow([row1, row2, dic["error"]])
                elif type_csv == "1_row":
                    row1 = key.split(",")[0]
                    writer.writerow([row1, dic["error"]])
        except:
            total = 0
            row1 = key.split(",")[0]
            if type_csv == "2_row":
                row2 = key.split(",")[1]
                row2 = row2.split("\n")[0]

            for key, subvalue in value.items():
                if key == "duplicateScript":
                    for key, sub2value in subvalue.items():
                        if key == "number":
                            row11 = sub2value
                if key == "spriteNaming":
                    for key, sub2value in subvalue.items():
                        if key == "number":
                            row12 = sub2value
                if key == "deadCode":
                    for key, sub2value in subvalue.items():
                        if key == "number":
                            row13 = sub2value
                if key == "initialization":
                    for key, sub2value in subvalue.items():
                        if key == "number":
                            row14 = sub2value

            for key, value in value.items():
                if key == "mastery":
                    for key, subvalue in value.items():
                        if key != "maxi" and key != "points":
                            if key == dic["parallelism"]:
                                row5 = subvalue
                            elif key == dic["abstraction"]:
                                row4 = subvalue
                            elif key == dic["logic"]:
                                row6 = subvalue
                            elif key == dic["sync"]:
                                row7 = subvalue
                            elif key == dic["flow_control"]:
                                row8 = subvalue
                            elif key == dic["user_inter"]:
                                row9 = subvalue
                            elif key == dic["data_rep"]:
                                row10 = subvalue
                            total = total + subvalue
                    row3 = total
            if type_csv == "2_row":
                writer.writerow([row1, row2, row3, row4, row5, row6, row7, row8,
                                 row9, row10, row11, row12, row13, row14])
            elif type_csv == "1_row":
                writer.writerow([row1, row3, row4, row5, row6, row7, row8,
                                 row9, row10, row11, row12, row13, row14])
    return csv_data


# __________________________ TO REGISTER USER _________________________________#

def coder_hash(request):
    """Method for to sign up users in the platform"""

    if request.method == "POST":
        form = CoderHashForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('/coder_hash')
    elif request.method == 'GET':
        return render(request, 'coder/coder-hash.html')


def sign_up_coder(request):
    """Method which allow to sign up coders"""

    flagCoder = 1
    flagHash = 0
    flagName = 0
    flagEmail = 0
    flagForm = 0
    flagWrongEmail = 0
    flagWrongPassword = 0
    if request.method == 'POST':
        form = CoderForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            password_confirm = form.cleaned_data['password_confirm']
            email = form.cleaned_data['email']
            email_confirm = form.cleaned_data['email_confirm']
            birthmonth = form.cleaned_data['birthmonth']
            birthyear = form.cleaned_data['birthyear']
            gender = form.cleaned_data['gender']
            # gender_other = form.cleaned_data['gender_other']
            country = form.cleaned_data['country']

            # Checking the validity into the dbdata contents.
            # They will be refused if they already exist.
            # If they exist an error message will be shown.
            if User.objects.filter(username=username):
                # This name already exists
                flagName = 1
                # return render_to_response("error/sign-up.html",
                #                          {'flagName':flagName,
                #                           'flagEmail':flagEmail,
                #                           'flagHash':flagHash,
                #                           'flagForm':flagForm,
                #                           'flagCoder':flagCoder},
                #                          context_instance = RC(request))
                return render(request, 'error/sign-up.html', {'flagName': flagName,
                                                              'flagEmail': flagEmail,
                                                              'flagHash': flagHash,
                                                              'flagForm': flagForm,
                                                              'flagCoder': flagCoder})

            elif User.objects.filter(email=email):
                # This email already exists
                flagEmail = 1
                # return render_to_response("error/sign-up.html",
                #                        {'flagName':flagName,
                #                        'flagEmail':flagEmail,
                #                        'flagHash':flagHash,
                #                        'flagForm':flagForm,
                #                        'flagCoder':flagCoder},
                #                        context_instance = RC(request))
                return render(request, 'error/sign-up.html', {'flagName': flagName,
                                                              'flagEmail': flagEmail,
                                                              'flagHash': flagHash,
                                                              'flagForm': flagForm,
                                                              'flagCoder': flagCoder})
            elif (email != email_confirm):
                flagWrongEmail = 1
                # return render_to_response("error/sign-up.html",
                #        {'flagName':flagName,
                #        'flagEmail':flagEmail,
                #        'flagHash':flagHash,
                #        'flagForm':flagForm,
                #        'flagCoder':flagCoder,
                #        'flagWrongEmail': flagWrongEmail},
                #        context_instance = RC(request))
                return render(request, 'error/sign-up.html', {'flagName': flagName,
                                                              'flagEmail': flagEmail,
                                                              'flagHash': flagHash,
                                                              'flagForm': flagForm,
                                                              'flagCoder': flagCoder,
                                                              'flagWrongEmail': flagWrongEmail})

            elif (password != password_confirm):
                flagWrongPassword = 1
                # return render_to_response("error/sign-up.html",
                #        {'flagName':flagName,
                #        'flagEmail':flagEmail,
                #        'flagHash':flagHash,
                #        'flagForm':flagForm,
                #        'flagCoder':flagCoder,
                #        'flagWrongPassword':flagWrongPassword},
                #        context_instance = RC(request))
                return render(request, 'error/sign-up.html', {'flagName': flagName,
                                                              'flagEmail': flagEmail,
                                                              'flagHash': flagHash,
                                                              'flagForm': flagForm,
                                                              'flagCoder': flagCoder,
                                                              'flagWrongPassword': flagWrongPassword})

            else:
                coder = Coder.objects.create_user(username=username,
                                                  email=email, password=password,
                                                  birthmonth=birthmonth,
                                                  birthyear=birthyear,
                                                  gender=gender,
                                                  # gender_other = gender_other,
                                                  country=country)

                coder = authenticate(username=username, password=password)
                user = Coder.objects.get(email=email)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                c = {
                    'email': email,
                    'uid': uid,
                    'token': token}

                body = render_to_string("coder/email-sign-up.html", c)
                subject = "Welcome to Dr. Scratch!"
                sender = "no-reply@drscratch.org"
                to = [email]
                email = EmailMessage(subject, body, sender, to)
                email.send()
                login(request, coder)
                return HttpResponseRedirect('/coder/' + coder.username)

        else:
            flagForm = 1
            # return render_to_response("error/sign-up.html",
            #      {'flagName':flagName,
            #       'flagEmail':flagEmail,
            #       'flagHash':flagHash,
            #       'flagForm':flagForm},
            #      context_instance = RC(request))
            return render(request, 'error/sign-up.html', {'flagName': flagName,
                                                          'flagEmail': flagEmail,
                                                          'flagHash': flagHash,
                                                          'flagForm': flagForm})

    elif request.method == 'GET':
        if request.user.is_authenticated():
            return HttpResponseRedirect('/coder/' + request.user.username)
        else:
            # return render_to_response("main/main.html",
            #        context_instance = RC(request))
            return render(request, 'main/main.html')


# _________________________ TO SHOW USER'S DASHBOARD ___________#

def coder(request, name):
    """Shows the main page of coders"""

    if (request.method == 'GET') or (request.method == 'POST'):
        if request.user.is_authenticated():
            username = request.user.username
            if username == name:
                if Coder.objects.filter(username=username):
                    user = Coder.objects.get(username=username)
                    img = user.img
                    dic = {'username': username,
                           "img": str(img)}

                    # return render_to_response("coder/main.html",
                    #                            dic,
                    #                            context_instance = RC(request))
                    return render(request, 'coder/main.html', dic)
                else:
                    logout(request)
                    return HttpResponseRedirect("/")

    else:
        return HttpResponseRedirect("/")


def login_coder(request):
    """Log in app to user"""

    if request.method == 'POST':
        flagCoder = 0
        flag = False
        form = LoginOrganizationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            coder = authenticate(username=username, password=password)
            if coder is not None:
                if coder.is_active:
                    login(request, coder)
                    return HttpResponseRedirect('/coder/' + coder.username)

            else:
                flag = True
                flagCoder = 1
                # return render_to_response("sign-password/user-doesnt-exist.html",
                #                            {'flag': flag,
                #                             'flagCoder': flagCoder},
                #                            context_instance=RC(request))
                return render(request, 'sign-password/user-doesnt-exist.html', {'flag': flag, 'flagCoder': flagCoder})
    else:
        return HttpResponseRedirect("/")


def logout_coder(request):
    """Method for logging out"""

    logout(request)
    return HttpResponseRedirect('/')


# _________________________ CHANGE PASSWORD __________________________________#


def change_pwd(request):
    """Change user's password

    This method is used to try to recover the account when the registered
    user forgot their password. Takes the email sent in POST. Look for
    whether the user belongs to an organization or is a coder in the DB.
    With an uid (that encodes a bytestring in base 64) and a token that
    can be used once to do a password reset for the given user, render
    the context of the template. Send an email message to the person who
    requested the change to confirm it.

    :param request: HTTP Request.
    """

    if request.method == 'POST':
        recipient = request.POST['email']

        # segmentation
        user_type, user_type_str = get_type_user(request)
        try:
            if Organization.objects.filter(email=recipient):
                user = Organization.objects.get(email=recipient)
            elif Coder.objects.filter(email=recipient):
                user = Coder.objects.get(email=recipient)
        except:
            # return render_to_response("sign-password/user-doesnt-exist.html",
            #                               context_instance=RC(request))
            return render(request, 'sign-password/user-doesnt-exist.html')

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        c = {
            'email': recipient,
            'uid': uid,
            'token': token,
            'id': user.username}

        body = render_to_string("sign-password/email-reset-pwd.html", c)
        subject = "Dr. Scratch: Did you forget your password?"
        sender = "no-reply@drscratch.org"
        to = [recipient]
        email = EmailMessage(subject, body, sender, to)
        email.send()
        # return render_to_response("sign-password/email-sended.html",
        #                        context_instance=RC(request))
        return render(request, 'sign-password/email-sended.html')

    else:

        page = get_type_user(request)
        # return render_to_response("sign-password/password.html",
        #                        context_instance=RC(request))
        return render(request, 'sign-password/password.html')


def reset_password_confirm(request, uidb64=None, token=None, *arg, **kwargs):
    """Confirm change password

    It tries to retrieve from its uid, the active user model. Check
    that a password reset token is correct for a given user. Save the
    new password after confirming it. After an authentication process
    it is redirected at the user page.


    :param request: HTTP Request.
    :param uidb64:  base64 encoded string with de user id.
    :param token: string to check user account activation.
    :param *args: varying number of positional arguments.
    :param **kwargs: Dictionary with varying number of items.
    :raise TypeError: Raised because uid has inappropriate type.
    :raise ValueError: Raised when uid has an inappropriate value
    :raise OverflowError: Raisen if uid is outside a required range.
    :raise UserModel.DoesNotExist: The user is not in DB.
    """

    UserModel = get_user_model()
    try:
        uid = urlsafe_base64_decode(uidb64)
        if Organization.objects.filter(pk=uid):
            user = Organization._default_manager.get(pk=uid)
            page = 'organization'
        elif Coder.objects.filter(pk=uid):
            user = Coder._default_manager.get(pk=uid)
            page = 'coder'
    except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist):
        user = None

    if request.method == "POST":
        flag_error = False
        if user is not None and default_token_generator.check_token(user, token):
            new_password = request.POST['password']
            new_confirm = request.POST['confirm']
            if new_password == "":
                return render(request, 'sign-password/new-password.html')

            elif new_password == new_confirm:
                user.set_password(new_password)
                user.save()
                logout(request)
                user = authenticate(username=user.username,
                                    password=new_password)
                login(request, user)
                return HttpResponseRedirect('/' + page + '/' + user.username)
                return render(request, page + '/main.html')

            else:
                flag_error = True
                return render(request, 'sign-password/new-password.html',
                              {'flag_error': flag_error})

    else:
        if user is not None and default_token_generator.check_token(user, token):
            return render(request, 'sign-password/new-password.html')
        else:
            return render(request, page + '/main.html')


# _________________________________ DISCUSS ___________________________________#
def discuss(request):
    """Forum to get feedback

    With objects of type DiscussForm or Discuss it saves the values
    of the corresponding keys sent by POST. The form must be validated.
    Show all comments sorted by date.

    :param request: HTTP Request.
    """

    comments = dict()
    form = DiscussForm()
    if request.user.is_authenticated():
        user = request.user.username
    else:
        user = ""
    if request.method == "POST":

        form = DiscussForm(request.POST)
        if form.is_valid():
            nick = user
            date = timezone.now()
            comment = form.cleaned_data["comment"]
            new_comment = Discuss(nick=nick,
                                  date=date,
                                  comment=comment)
            new_comment.save()
        else:
            comments["form"] = form

    data = Discuss.objects.all().order_by("-date")
    lower = 0
    upper = 10
    list_comments = {}

    if len(data) > 10:
        for n in range((len(data) / 10) + 1):
            list_comments[str(n)] = data[lower:upper - 1]
            lower = upper
            upper = upper + 10
    else:
        list_comments[0] = data

    comments["comments"] = list_comments

    return render(request, 'discuss.html', comments)


########################## UNDERDEVELOPMENT ###################################

# _________________________________ ERROR _____________________________________#

def error404(request):
    """Return own 404 page"""

    response = render(request, '404.html', {})
    response.status_code = 404
    return response


def error500(request):
    """Return own 500 page"""

    response = render(request, '500.html', {})
    return response
