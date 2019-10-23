#!/usr/bin/env python3

__author__ = 'Bradley Frank'

import argparse
import configparser
import datetime
import json
import logging
import mimetypes
import os
import re
import shutil
import smtplib
import sys
import urllib.request
from urllib.error import HTTPError
from urllib.error import URLError

REDDIT_URL = 'https://www.reddit.com'


def is_url_image(url):
    mimetype, _ = mimetypes.guess_type(url)
    return (mimetype and mimetype.startswith('image'))


def make_filename(url, name, out_dir):
    # get the short month name (e.g. Jan, Feb) and year (e.g. 2019, 2020)
    month = datetime.datetime.now().strftime('%b')
    year = datetime.datetime.now().strftime('%y')
    date = month + year
    # get the file extension of the image (e.g. png, jpg)
    _, ext = os.path.splitext(url)
    # remove spaces, special characters, etc.
    name = re.sub(r"[^\w\s]", '', name)
    name = re.sub(r"\s+", '-', name)
    # shorten filename if too long
    name = name[:75] if len(name) > 75 else name
    # return completed filename
    return out_dir + '/' + date + '-' + name + ext


def download_image(url, title, download_dir):
    filename = make_filename(url, title, download_dir)

    if os.path.isfile(filename):
        dlrlog.log('warn', 'Duplicate image: ' + title)
        return True

    try:
        response = urllib.request.urlopen(url)
    except HTTPError as e:
        print('Could not download image ' + title)
        dlrlog.log('error', e.code)
        return False
    except URLError as e:
        print('Could not download image ' + title)
        dlrlog.log('error', e.reason)
        return False

    try:
        with open(filename, 'wb') as f:
            shutil.copyfileobj(response, f)
    except IOError as e:
        print('Could not save image: ' + title)
        dlrlog.log('error', e)
        return False

    return True


def get_top_posts(subreddit, timeframe, download_dir):
    url = REDDIT_URL + '/r/' + subreddit + '/top/.json?t=' + timeframe

    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/4.0 (compatible; MSIE 7.0; \
            Windows NT 6.0)')
        response = urllib.request.urlopen(req)
    except HTTPError as e:
        print(subreddit + ': could not download subreddit data.')
        dlrlog.log('error', e.code)
        return False
    except URLError as e:
        print(subreddit + ': could not download subreddit data.')
        dlrlog.log('error', e.reason)
        return False

    data = response.readline().decode('utf-8')
    feed = json.loads(data)

    if 'data' not in feed:
        print(subreddit + ': could not find subreddit information.')
        return False
    else:
        dlrlog.log('info', subreddit + ': downloaded subreddit information.')

    for asset in feed['data']['children']:
        content = asset['data']['url']
        title = asset['data']['title']
        if is_url_image(content):
            dlrlog.log('info', 'Found post: ' + title)
            download_image(content, title, download_dir)

    return True


def send_email(sender, recipient, subject, body, password):
    s = smtplib.SMTP('smtp.gmail.com', 587)
    message = 'Subject: {}\n\n{}'.format(subject, body)
    s.starttls()
    s.login(sender, password)
    s.sendmail(sender, recipient, message)
    s.quit()


class myLogger:

    def __init__(self, debug=False):
        # Logging settings
        self.logger = logging.getLogger('reposyncer')
        if not debug:
            log_level = 0
        else:
            log_level = 10
        self.logger.setLevel(log_level)

        # Logging formats
        _log_format = '[%(asctime)s] [%(levelname)8s] %(message)s'
        log_format = logging.Formatter(_log_format, '%H:%M:%S')

        # Adds a console handler to the logger
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(log_level)
        ch.setFormatter(log_format)
        self.logger.addHandler(ch)

    def log(self, lvl, msg):
        level = logging.getLevelName(lvl.upper())
        self.logger.log(level, msg)


#
# Setup argparser to accept two command line parameters:
#   (1) -d or --debug to enable debugging
#   (2) -c or --config to specify which configuration to use (required)
#
parser = argparse.ArgumentParser(
    description='Downloads top monthly posts from Reddit subreddits.')
parser.add_argument('-d', '--debug', action='store_true',
                    help='enables debug messages')
parser.add_argument('-c', '--config', help='Which config to use.',
                    required=True)
args = parser.parse_args()

#
# Check if debugging is enabled and configure the Logger.
#
if args.debug:
    dlrlog = myLogger(True)
else:
    dlrlog = myLogger(False)

#
# Get the current working directory of this script.
#
__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

#
# Create a config parser instance and read in the config file, located
# in the same directory as this script.
#
conf = configparser.ConfigParser()
conf.read(os.path.join(__location__, 'dl-reddit-top.conf'))

#
# Read and apply settings from the config file.
#
CONFIG = args.config

if conf[CONFIG]['send_email'] == 'True':
    email_user = True
    email_receiver = conf[CONFIG]['email_address']
    email_subject = conf[CONFIG]['email_subject']
    email_body = conf[CONFIG]['email_body']
else:
    email_user = False

if conf.has_option(CONFIG, 'output_directory'):
    output_directory = conf[CONFIG]['output_directory']
else:
    output_directory = __location__

subreddits = conf[CONFIG]['subreddits'].split(',')

if conf.has_option(CONFIG, 'timeframe'):
    timeframe = conf[CONFIG]['timeframe']
else:
    timeframe = 'month'

#
# Read in Gmail address and password for sending emails.
#
creds = configparser.ConfigParser()
creds.read(os.path.join(__location__, '.credentials'))
email_sender = creds['credentials']['address']
email_passwd = creds['credentials']['password']

#
# Loop through subreddits and download images.
#
for subreddit in subreddits:
    download_dir = os.path.join(output_directory, subreddit)
    if not os.path.isdir(download_dir):
        os.makedirs(download_dir, exist_ok=True)
    get_top_posts(subreddit, 'month', download_dir)

#
# If set to True, email the user that downloads are complete.
#
if email_user:
    send_email(email_sender, email_receiver, email_subject, email_body,
               email_passwd)
