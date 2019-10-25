# Download Top Subreddit Images

## Table of Contents
+ [About](#about)
+ [Getting Started](#getting_started)
+ [Usage](#usage)
+ [Contributing](../CONTRIBUTING.md)

## About <a name = "about"></a>
Downloads top image posts for defined subreddits to a directory of your choice, and optionally sends an email notification upon completion.

For emailing notifications, it's tested with Gmail credentials.

## Getting Started <a name = "getting_started"></a>

Add two configuration files to the cloned repository.

The `dl-reddit-top.conf` file looks like this:
```
[FunnyAnimals]
;send_email = [True|False]
send_email = True
email_address = myemail@domain.tld
email_subject = New pictures downloaded!
email_body = New top pictures have been downloaded, check them out!
output_directory = /path/to/downloads/folder
subreddits = AnimalsBeingBros,rarepuppers,AnimalsBeingDerps,dogswithjobs
;timeframe = [year|month|week|day]
timeframe = month
```

*The config header is passed to the program as a parameter. See below.*

The `.credentials` file should look like this:
```
[credentials]
address = <my email address>
password = <my password>
```

### Prerequisites

* Python3 (Tested on 3.7.4)

### Installing

1. Clone the repository
2. Write config files
3. Setup Google app password for email (optional)

## Usage <a name = "usage"></a>

* Help: `dl-reddit-top.py -h`
* Debug: `dl-reddit-top.py -d`
* Execute: `dl-reddit-top.py -c FunnyAnimals`
