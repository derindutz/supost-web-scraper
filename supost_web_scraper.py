#!/usr/bin/env python3
"""Web scraper application for supost.com.

This program searches supost.com for posts that contain certain given keywords.
The program then sends an email to the given address containing titles and
links for the appropriate posts. The program also keeps track of which matches
have already been found and only sends an email if there are new matches on the
website. I run this program every morning in the background and am thus able to
automatically find great deals on items I'm interested in purchasing.

Example:
    $ python3 supost_web_scraper.py

Attributes:
    OFFSET_INCREASE (int): number of pages to search per iteration in the
        program loop.
    FROM_ADDRESS (string): email address from which to send the emails (if not
        using gmail, the server settings will need to be changed).
    FROM_ADDRESS_PASSWORD (string): password for FROM_ADDRESS
    TO_ADDRESS (str): email address to which to send the emails (can be the
        same as FROM_ADDRESS if you want to send emails to yourself).
"""

import os                             # for checking if file exists
import datetime                       # for date and time
import smtplib                        # import for email sending function
from email.mime.text import MIMEText  # import needed email modules
import httplib2                       # for receiving web pages
from bs4 import BeautifulSoup         # for getting information from web pages

__author__ = "Derin Dutz"
__copyright__ = "Copyright 2014, Derin Dutz. All rights reserved."
__credits__ = ["Derin Dutz"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Derin Dutz"
__email__ = "dddutz@cs.stanford.edu"
__status__ = "Development"

OFFSET_INCREASE = 99  # amount to increase page offset
FROM_ADDRESS = "example@gmail.com"
FROM_ADDRESS_PASSWORD = "example_password"
TO_ADDRESS = "example2@gmail.com"


class Prepender:
    """Implements functionality to prepend to a file.

    Attributes:
        write_queue (list of str): queue of strings to write to the file.
        file (file): file to prepend to.`
    """

    def __init__(self, filename, mode="w", encoding="utf-8"):
        """Initializes the prepender.

        Args:
            filename (str): file name
            mode (str, optional): file opening mode
            encoding (str, optional): file encoding to use
        """
        if os.path.isfile(filename):
            with open(filename, mode="r", encoding="utf-8") as readfile:
                # splits by newline and keeps the newline characters
                self.write_queue = readfile.read().splitlines(True)
        else:
            self.write_queue = []
        self.file = open(filename, mode=mode, encoding=encoding)

    def write(self, string):
        """Inserts to the beginning of the file.

        Args:
            string (str): string to write
        """
        self.write_queue.insert(0, string)

    def close(self):
        """Closes the prepender."""
        self.__exit__(None, None, None)

    def __enter__(self):
        """Returns the prepender."""
        return self

    def __exit__(self, type, value, traceback):
        """Exits the prepender and writes the lines to the file."""
        if self.write_queue:
            self.file.writelines(self.write_queue)
        self.file.close()


def main():
    """Runs the program."""
    keywords = ["monitor"]
    days_to_check = 5
    logfile_name = "supost_scraper-" + "-".join(keywords) + ".log"
    logfile_path = os.path.join(os.path.expanduser("~"), "Documents",
                                "Web_Scraper_Log", logfile_name)
    previous_logfile_contents = read_file_to_string(logfile_path)
    new_matches, offset = scrape_supost(keywords, days_to_check, logfile_path,
                                        previous_logfile_contents)
    output_new_matches(new_matches, keywords, logfile_path, offset,
                       previous_logfile_contents)


def read_file_to_string(path):
    """Reads a file into a string and returns an empty string if the file does
    not exist.

    Args:
        path (str): file path
    """
    if os.path.isfile(path):
        with open(path, mode="r", encoding="utf-8") as f:
            return f.read()
    else:
        return ""


def scrape_supost(keywords, days_to_check, logfile_path,
                  previous_logfile_contents):
    """Scrapes supost.com to find all posts which contains the given keywords.

    Args:
        keywords (list of str): keywords to search for
        days_to_check (int): number of days back to search
        logfile_path (str): path of log file
        previous_logfile_contents (str): contents of the old log file

    Returns:
        list of str, int: list of new matches, posts searched
    """
    oldest_date = (datetime.date.today() -
                   datetime.timedelta(days=days_to_check))
    oldest_date_str = oldest_date.strftime("%a, %b %d")

    offset = 0
    new_matches = []
    h = httplib2.Http(".cache")
    link = "http://supost.com/search/index/5"

    is_scraping = True
    while is_scraping:
        response, content = h.request(link)
        link_page = BeautifulSoup(content)
        for link in link_page.find_all("a"):
            if ("post/index" in str(link.get("href"))):
                response, content = h.request("http://supost.com" +
                                              str(link.get("href")))
                post_page = BeautifulSoup(content)
                for keyword in keywords:
                    if keyword in str(post_page.get_text()).lower():
                        post_title = post_page.find("h2",
                                                    {"id": "posttitle"}).text
                        output_string = (post_title + ": supost.com" +
                                         link.get("href"))
                        if output_string in previous_logfile_contents:
                            return new_matches, offset
                        else:
                            new_matches.append(output_string)

        # stops scraper when oldest date is found
        if (oldest_date_str in str(link_page.get_text())):
            return new_matches, offset

        # makes sure scraper doesn't go too far
        if (offset + OFFSET_INCREASE > (OFFSET_INCREASE*2*days_to_check)):
            return new_matches, offset

        offset = offset + OFFSET_INCREASE

        # updates the link with the new offset
        link = "http://supost.com/search/index/5?offset=" + str(offset)

    return new_matches, offset


def output_new_matches(new_matches, keywords, logfile_path, offset,
                       previous_logfile_contents):
    """Outpus the new matches to a file containing the old matches and sends an
    email summarizing the findings.

    Args:
        new_matches (list of str): list of found matches
        keywords (list of str): keywords to search for
        days_to_check (int): number of days back to search
        logfile_path (str): path of log file
        offset (int): posts searched
        previous_logfile_contents (str): contents of the old log file
    """
    if new_matches:
        # add new matches to the start of the file
        with Prepender(logfile_path, encoding="utf-8") as logfile:
            new_matches_string = "\n".join(new_matches) + "\n"
            logfile.write(new_matches_string)

        mail_message = create_mail_message(new_matches, keywords, offset,
                                           previous_logfile_contents)
        send_email(mail_message)
        print("New matches found. Email sent.")
    else:
        print("No new matches found.")


def create_mail_message(new_matches, keywords, offset,
                        previous_logfile_contents):
    """Creates a new mail message.

    Args:
        new_matches (list of str): list of found matches
        keywords (list of str): keywords to search for
        offset (int): posts searched
        previous_logfile_contents (str): contents of the old log file

    Returns:
        str: mail message
    """
    # add message header
    mail_message = ("Keywords used: " + str(keywords) + "\n\n")
    mail_message += ("We checked through " + str(offset) +
                     " posts, and found " + str(len(new_matches)) +
                     " new matches:\n")

    # add new matches
    for found_link in new_matches:
        mail_message += found_link + "\n"

    # add old matches
    mail_message += "\nHere are your old matches:\n"
    mail_message += previous_logfile_contents

    return mail_message


def send_email(message):
    """Sends an email.

    Args:
        message (str): email body
    """
    from_address = FROM_ADDRESS
    to_address = TO_ADDRESS
    today_date = datetime.datetime.today()
    today_date_str = today_date.strftime("%m/%d/%y %H:%M:%S")

    msg = MIMEText(str(message))
    msg["Subject"] = "SUPOST SCRAPER [" + str(today_date_str) + "]"
    msg["From"] = from_address
    msg["To"] = to_address

    server = smtplib.SMTP("smtp.gmail.com:587")
    server.starttls()
    server.login(from_address, FROM_ADDRESS_PASSWORD)
    server.sendmail(from_address, to_address, str(msg))
    server.quit()


if __name__ == "__main__":
    main()
