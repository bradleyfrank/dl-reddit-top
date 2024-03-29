#!/usr/bin/env python3

__author__ = "Bradley Frank"

import argparse
import configparser
import datetime
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import smtplib
import sys
import urllib.request
import uuid
from urllib.error import HTTPError
from urllib.error import URLError

POSTS = {}
REDDIT_URL = "https://www.reddit.com"


def is_url_image(url):
    mimetype, _ = mimetypes.guess_type(url)
    return mimetype and mimetype.startswith("image")


def calculate_hash(image):
    sha1 = hashlib.sha1(image).hexdigest()
    dlrlog.log("debug", "Calculated sha1: " + sha1)
    return sha1


def is_duplicate_hash(image_hash):
    for _, metadata in POSTS.items():
        if metadata["hash"] == image_hash:
            dlrlog.log("warn", "Found duplicate hash: " + metadata["title"])
            return True
    else:
        return False


def is_duplicate_file(filename):
    if os.path.isfile(filename):
        dlrlog.log("warn", "Found duplicate file: " + filename)
        return True
    else:
        return False


def make_filename(url, name, subreddit, out_dir):
    #
    # Make the date prefix in the format "DDMMYY".
    #
    day = datetime.datetime.now().strftime("%d")
    month = datetime.datetime.now().strftime("%m")
    year = datetime.datetime.now().strftime("%y")
    date = day + month + year

    #
    # Remove spaces, special characters, etc. Then truncate filename to 50
    # characters if too long. If the name ends up being blank, create a
    # random string instead (can happen with emoji-only titles).
    #
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", "-", name)
    name = name[:50] if len(name) > 50 else name
    if name == "":
        name = str(uuid.uuid4().hex)
    dlrlog.log("debug", "Sanitized name: " + name)

    #
    # Get the file extension of the image (e.g. png, jpg).
    #
    _, ext = os.path.splitext(url)

    #
    # Concatenate parts to make a filename.
    #
    filename = date + "_" + subreddit + "_" + name + ext
    dlrlog.log("debug", "Filename: " + filename)

    #
    # Return full path to file.
    #
    return os.path.join(out_dir, filename)


def download_image(url):
    try:
        response = urllib.request.urlopen(url)
    except HTTPError as e:
        dlrlog.log("error", "Could not download image: " + e.code)
        return False
    except URLError as e:
        dlrlog.log("error", "Could not download image: " + e.reason)
        return False

    return response.read()


def save_image(filename, data):
    try:
        with open(filename, "wb") as f:
            f.write(data)
    except IOError as e:
        dlrlog.log("error", e)
        return False

    return True


def get_top_posts(subreddit, timeframe):
    #
    # Dictionary structure of subreddit posts:
    # subreddit_posts = {
    #   postID: {
    #       url:
    #       title:
    #       subreddit:
    #       hash:
    #   }
    # }
    #
    subreddit_posts = {}

    #
    # Create the full URL to the subreddit json feed.
    #
    url = REDDIT_URL + "/r/" + subreddit + "/top/.json?t=" + timeframe

    #
    # Attempt to download the json feed.
    #
    try:
        req = urllib.request.Request(url)
        req.add_header(
            "User-Agent", "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)"
        )
        response = urllib.request.urlopen(req)
    except HTTPError as e:
        dlrlog.log("error", "Could not get " + subreddit + " data: " + e.code)
        return False
    except URLError as e:
        dlrlog.log(
            "error", "Could not get " + subreddit + " data: " + e.reason
        )
        return False

    #
    # Convert the downloaded data into a readable json feed.
    #
    data = response.readline().decode("utf-8")
    feed = json.loads(data)

    #
    # A proper subreddit json feed has a section named 'data'; look for that.
    #
    if "data" not in feed:
        dlrlog.log("error", "Error finding data in " + subreddit + " feed.")
        return False
    else:
        dlrlog.log("info", "Downloaded " + subreddit + " feed.")

    #
    # Each child of the 'data' section is a post; loop through them to get
    # the metadata. The post's unique ID will become the dictionary's key.
    #
    for asset in feed["data"]["children"]:
        pid = asset["data"]["id"]
        url = asset["data"]["url"]
        title = asset["data"]["title"]

        #
        # Confirm the post is an image since that's the whole point of this.
        #
        if is_url_image(url):
            dlrlog.log("info", "Found image: " + title)
            subreddit_posts[pid] = {}
            subreddit_posts[pid]["url"] = url
            subreddit_posts[pid]["title"] = title
            subreddit_posts[pid]["subreddit"] = subreddit
            subreddit_posts[pid]["hash"] = ""
        else:
            dlrlog.log("debug", "Skipping non-image: " + title)
            break

    return subreddit_posts


def send_email(sender, recipient, subject, body, password):
    s = smtplib.SMTP("smtp.gmail.com", 587)
    message = "Subject: {}\n\n{}".format(subject, body)
    s.starttls()
    s.login(sender, password)
    s.sendmail(sender, recipient, message)
    s.quit()


class myLogger:
    def __init__(self, debug=False):
        # Logging settings
        self.logger = logging.getLogger("dl-reddit-top")
        if not debug:
            log_level = 100
        else:
            log_level = 10
        self.logger.setLevel(log_level)

        # Logging formats
        _log_format = "[%(asctime)s] [%(levelname)8s] %(message)s"
        log_format = logging.Formatter(_log_format, "%H:%M:%S")

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
    description="Downloads top monthly posts from Reddit subreddits."
)
parser.add_argument(
    "-d", "--debug", action="store_true", help="enables debug messages"
)
parser.add_argument(
    "-c", "--config", help="Which config to use.", required=True
)
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
    os.path.join(os.getcwd(), os.path.dirname(__file__))
)

#
# Ensure the user config file exists.
#
config_file = os.path.join(__location__, "dl-reddit-top.conf")

if not os.path.exists(config_file):
    dlrlog.log("error", "No config file found at " + config_file + ".")
    print("No config file found; please create " + config_file + ".")
    sys.exit()

#
# Setup ConfigParser to read the user's config file. Begin with setting some
# default values in case they aren't defined in the config.
#
config_defaults = {
    "send_email": "False",
    "output_directory": os.path.join(__location__, "images"),
    "subreddits": "pics",
    "timeframe": "month",
}
conf = configparser.ConfigParser(defaults=config_defaults)
conf.read(config_file)

user_config = args.config

#
# Ensure the specified config section exists. If not, exit the program.
#
if not conf.has_section(user_config):
    dlrlog.log("error", 'No config section "' + user_config + '" was found.')
    print('No config section "' + user_config + '" was found.')
    sys.exit()

#
# Save the various settings, but skip checking that the options exist because
# they were previously defined in the default settings above.
#
output_directory = conf[user_config]["output_directory"]
subreddits = conf[user_config]["subreddits"].split(",")
timeframe = conf[user_config]["timeframe"]

if conf[user_config]["send_email"] == "True":
    email_user = True
    email_headers = {
        "email_address": "",
        "email_subject": "",
        "email_body": "",
    }
    for header in email_headers:
        if not conf.has_option(user_config, header):
            dlrlog.log(
                "critical", 'No setting for "' + option + '" was found.'
            )
            print('No config section "' + user_config + '" was found.')
            sys.exit()
        else:
            email_headers[header] = conf[user_config][header]
else:
    email_user = False

#
# Read in Gmail credentials for sending emails. Only do this if the option
# to send email notifications was enabled.
#
if email_user:
    creds = configparser.ConfigParser()
    creds_config = os.path.join(__location__, ".credentials")

    # Ensure the config file exists.
    if not os.path.exists(creds_config):
        dlrlog.log("critical", "No credentials found at " + creds_config + ".")
        print("No credentails file found; please create " + creds_config + ".")
        sys.exit()

    # Read the configuration file.
    creds.read(creds_config)

    # Ensure the "credentials" section exists.
    if not creds.has_section("credentials"):
        dlrlog.log("critical", 'No config section "credentials" was found.')
        print('Credentials conf file missing "credentials" section.')
        sys.exit()

    # Ensure the address and password exist.
    if not creds.has_option('credentials', "address") or \
       not creds.has_option('credentials', "password"):
        dlrlog.log(
            "critical", "No address or password credentials were found."
        )
        print("No address or password credentials were found.")
        sys.exit()

    # Save the credentials.
    email_sender = creds["credentials"]["address"]
    email_passwd = creds["credentials"]["password"]

#
# Create output directory if it does not exist.
#
if not os.path.isdir(output_directory):
    os.makedirs(output_directory, exist_ok=True)

#
# Loop through subreddits and download metadata of the top posts.
#
for subreddit in subreddits:
    top_posts = get_top_posts(subreddit, timeframe)
    if top_posts is False:
        dlrlog.log("debug", "No posts were found.")
    else:
        POSTS.update(top_posts)

#
# Iterate over all discovered top posts and perform the following operations:
#   (1) Create a filename that includes the full path on disk
#   (2) Check for that filename exists already
#   (3) Get the sha1 hash of the image
#   (4) Compare the hash to previous images to find duplicates
#   (5) Save the image to disk
#
for _, metadata in POSTS.items():
    dlrlog.log("info", "Processing: " + metadata["title"])

    # Use the post metadata to construct a filename.
    filename = make_filename(
        metadata["url"],
        metadata["title"],
        metadata["subreddit"],
        output_directory,
    )

    # Skip this image if the file exists already.
    if is_duplicate_file(filename):
        continue

    # Get the sha1 hash of the image.
    image = download_image(metadata["url"])
    image_hash = calculate_hash(image)

    # Skip this image if it matches the hash of a previous image.
    if is_duplicate_hash(image_hash):
        continue

    # Save the hash to the dictionary for comparison to subsequent posts.
    metadata["hash"] = image_hash

    # Save the image to disk.
    save_image(filename, image)

#
# If set to True, email the user that downloads are complete.
#
if email_user:
    send_email(
        email_sender,
        email_headers['email_address'],
        email_headers['email_subject'],
        email_headers['email_body'],
        email_passwd
    )
