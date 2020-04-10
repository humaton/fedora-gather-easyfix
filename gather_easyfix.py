#!/usr/bin/python -tt
# -*- coding: utf-8 -*-

#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
The idea of this program is to gather tickets from different project
which are marked as 'easyfix' (or any other keyword for that matter).

This version is a simple proof of concept, eventually it should be
converted to an html page and this script run by a cron job of some sort.

The different project to suscribe by email or a git repo or a page on
the wiki. To be sorted out...
"""

import argparse
import datetime
import json
import logging
import os
import re

try:
    from urllib2 import urlopen
except:
    from urllib.request import urlopen
from bugzilla.rhbugzilla import RHBugzilla

# Let's import template stuff
from jinja2 import Template
import mwclient

__version__ = "0.2.1"
bzclient = RHBugzilla(
    url="https://bugzilla.redhat.com/xmlrpc.cgi", cookiefile=None
)
# So the bugzilla module has some way to complain
logging.basicConfig()
logger = logging.getLogger("bugzilla")
# logger.setLevel(logging.DEBUG)

RETRIES = 2


class Project(object):
    """ Simple object representation of a project. """

    def __init__(self):
        self.name = ""
        self.url = ""
        self.site = ""
        self.owner = ""
        self.tag = ""
        self.tickets = []


class Ticket(object):
    """ Simple object representation of a ticket. """

    def __init__(self):
        self.id = ""
        self.url = ""
        self.title = ""
        self.status = ""
        self.type = ""
        self.component = ""

def gather_bz_projects():
    """ Retrieve all Bugzilla projects from cpe list.
    """
    projects_path = "./projects.txt"
    if not os.path.exists(projects_path):
        print("No projects file is found")
        return 1
    projects_file = open(projects_path,'r')
    page = projects_file.read()
    projects = []
    for row in page.split("\n"):
        regex = re.search("\* (bugzilla:)([^ ]*) ?$", row)
        if regex:
            project = Project()
            project.name = regex.group(2)
            projects.append(project)
    projects_file.close()
    return projects


def gather_bugzilla_issues():
    """ From the Red Hat bugzilla, retrieve all new tickets with keyword
    easyfix or whiteboard trivial.
    """
    bz_projects = gather_bz_projects()
    for bz_project in bz_projects:
        bz_issues = bzclient.query(
            {
                "query_format": "advanced",
                "bug_status": ["NEW", "ASSIGNED"],
                "classification": "Fedora",
                "product": "Fedora",
                "component": bz_project.name
            }
        )
        bz_issues += bz_issues
    # print(" {0} trivial bugs retrieved from BZ".format(len(bugbz)))
    return bz_issues


def gather_projects():
    """ Retrieve all the projects which have subscribed to this idea.
    """
    projects_path = "./projects.txt"
    if not os.path.exists(projects_path):
        print("No projects file is found")
        return 1
    projects_file = open(projects_path,'r')
    page = projects_file.read()
    projects = []
    for row in page.split("\n"):
        regex = re.search("\* (?!bugzilla)([^ ]*) ?$", row)
        if regex:
            project = Project()
            project.name = regex.group(1)
            projects.append(project)
    projects_file.close()
    return projects


def parse_arguments():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--fedmenu-url", help="URL of the fedmenu resources (optional)"
    )
    parser.add_argument(
        "--fedmenu-data-url", help="URL of the fedmenu data source (optional)"
    )
    args = parser.parse_args()
    result = {}
    for key in ["fedmenu_url", "fedmenu_data_url"]:
        if getattr(args, key):
            result[key] = getattr(args, key)
    return result


def main():
    """ For each projects which have suscribed in the correct place
    (fedoraproject wiki page), gather all the tickets containing the
    provided keyword.
    """

    extra_kwargs = parse_arguments()

    template = "/etc/fedora-gather-easyfix/template.html"
    if not os.path.exists(template):
        template = "./template.html"
    if not os.path.exists(template):
        print("No template found")
        return 1

    projects = gather_projects()

    labels = ['groomed', 'assigned']
    ticket_num = 0
    for project in projects:
        # print('Project: %s' % project.name)
        tickets = []
        full_project_name = project.name
        if full_project_name.startswith("github:"):
            for label in labels:
                project.tag = label
                project.name = full_project_name.split("github:")[1]
                project.url = "https://github.com/%s/" % (project.name)
                project.site = "github"
                url = (
                    "https://api.github.com/repos/%s/issues"
                    "?labels=%s&state=open" % (project.name, project.tag)
                )
                stream = urlopen(url)
                output = stream.read()
                jsonobj = json.loads(output)
                if jsonobj:
                    for ticket in jsonobj:
                        ticket_num = ticket_num + 1
                        ticketobj = Ticket()
                        ticketobj.id = ticket["number"]
                        ticketobj.title = ticket["title"]
                        ticketobj.url = ticket["html_url"]
                        ticketobj.status = ticket["state"]
                        tickets.append(ticketobj)
        elif full_project_name.startswith("pagure.io:"):
            for label in labels:
                project.tag = label
                project.name = full_project_name.split("pagure.io:")[1]
                project.url = "https://pagure.io/%s/" % (project.name)
                project.site = "pagure.io"
                url = (
                    "https://pagure.io/api/0/%s/issues"
                    "?status=Open&tags=%s" % (project.name, project.tag)
                )
                stream = urlopen(url)
                output = stream.read()
                jsonobj = json.loads(output)
                if jsonobj:
                    for ticket in jsonobj["issues"]:
                        ticket_num = ticket_num + 1
                        ticketobj = Ticket()
                        ticketobj.id = ticket["id"]
                        ticketobj.title = ticket["title"]
                        ticketobj.url = "https://pagure.io/%s/issue/%s" % (
                            project.name,
                            ticket["id"],
                        )
                        ticketobj.status = ticket["status"]
                        tickets.append(ticketobj)
        elif full_project_name.startswith("gitlab.com:"):
            for label in labels:
                project.tag = label
                # https://docs.gitlab.com/ee/api/issues.html#list-project-issues
                project.name = full_project_name.split("gitlab.com:")[1]
                project.url = "https://gitlab.com/%s/" % (project.name)
                project.site = "gitlab.com"
                url = (
                    "https://gitlab.com/api/v4/projects/%s/issues"
                    "?state=opened&labels=%s"
                    % (urllib2.quote(project.name, safe=""), project.tag)
                )
                stream = urlopen(url)
                output = stream.read()
                jsonobj = json.loads(output)
                if jsonobj:
                    for ticket in jsonobj:
                        ticket_num = ticket_num + 1
                        ticketobj = Ticket()
                        ticketobj.id = ticket["id"]
                        ticketobj.title = ticket["title"]
                        ticketobj.url = ticket["web_url"]
                        ticketobj.status = ticket["state"]
                        tickets.append(ticketobj)
        project.tickets = tickets

    bzbugs = gather_bugzilla_issues()
    bzbugs.sort(key=lambda x: x.id)

    try:
        # Read in template
        stream = open(template, "r")
        tplfile = stream.read()
        stream.close()
        # Fill the template
        mytemplate = Template(tplfile)
        html = mytemplate.render(
            projects=projects,
            bzbugs=bzbugs,
            ticket_num=ticket_num,
            bzbugs_num=len(bzbugs),
            date=datetime.datetime.now().strftime("%a %b %d %Y %H:%M"),
            **extra_kwargs
        )
        # Write down the page
        stream = open("index.html", "w")
        stream.write(html)
        stream.close()
    except IOError as err:
        print("ERROR: %s" % err)


if __name__ == "__main__":
    main()
