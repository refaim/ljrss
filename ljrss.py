# -*- coding: utf-8 -*-

from __future__ import print_function

import getpass
import optparse
import re
import socket
import sys
import urllib2
import xmlrpclib
import xml.dom.minidom

import mechanize

from lj import lj
from utils import console

class LjrssException(Exception): pass
class FreeMyFeedException(LjrssException): pass

XML_INDENT = 2 * ' '

MODE_MUTUAL = 'mutual'
MODE_ALL = 'all'
MODES = (MODE_MUTUAL, MODE_ALL)

FMF_RE = re.compile(r'<p id="viewrss"><a href="([^"]+)"')


class LjFriend(object):
    def __init__(self, name, is_identity, is_deleted):
        self.name = name
        self.is_identity = is_identity
        self.is_deleted = is_deleted

    def __eq__(self, other):
        return (self.name, self.is_identity, self.is_deleted ==
            other.name, other.is_identity, other.is_deleted)

    def __hash__(self):
        return hash((self.name, self.is_identity, self.is_deleted))

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


def getfriends(lj_username, lj_password):
    try:
        livejournal = lj.LJServer('lj.py; kemayo@gmail.com', 'Python-PyLJ/0.0.1')
        livejournal.login(lj_username, lj_password)

        def process(response):
            return {
                LjFriend(
                    item['username'],
                    item.get('type', '') == 'identity',
                    item.get('status', '') == 'purged'
                )
                for item in response}

        response = livejournal.getfriends(friendof=True)
        friendofs = process(response['friendofs'])
        friends = process(response['friends'])
        mutual = sorted(friends & friendofs, key=str)
        nonmutual = sorted(friends - friendofs, key=str)
    except lj.LJException, ex:
        error = ex
        if isinstance(ex.args[0], xmlrpclib.Fault):
            error = 'Error: %s' % ex.args[0].faultString
        raise LjrssException(error)
    return mutual, nonmutual


def ljusername2url(ljuser):
    if ljuser.startswith('_') or ljuser.endswith('_'):
        template = 'http://users.livejournal.com/{0}'
    else:
        ljuser = ljuser.replace('_', '-')
        template = 'http://{0}.livejournal.com'
    return template.format(ljuser) + '/data/rss'


def digest(feed):
    return feed + '?auth=digest'


def freefeed(url):
    global options

    browser = mechanize.Browser()
    try:
        browser.open('http://freemyfeed.com/')
    except urllib2.URLError, ex:
        error = ex.args[0]
        if isinstance(error, socket.gaierror):
            error = '{0}: {1}'.format(*error.args)
        raise FreeMyFeedException(error)

    try:
        browser.select_form(nr=0)
    except mechanize._mechanize.FormNotFoundError, ex:
        raise FreeMyFeedException(ex)

    try:
        browser['url'] = url
        browser['user'] = options.lj_username
        browser['pass'] = options.lj_password
    except mechanize._form.LocateError, ex:
        raise FreeMyFeedException(ex)

    try:
        response = browser.submit()
    except urllib2.HTTPError, ex:
        raise FreeMyFeedException(ex)

    match = FMF_RE.search(response.read())
    if not match:
        raise FreeMyFeedException('Unable to free feed {0}'.format(url))
    return match.group(1)


def opml(document, foldername):
    opml = document.createElement('opml')
    opml.setAttribute('version', '1.1')
    document.appendChild(opml)
    body = document.createElement('body')
    opml.appendChild(body)
    folder = document.createElement('outline')
    folder.setAttribute('text', foldername)
    body.appendChild(folder)
    return document, folder


def opmlentry(document, title, url):
    entry = document.createElement('outline')
    entry.setAttribute('title', title)
    entry.setAttribute('text', title)
    entry.setAttribute('xmlUrl', url)
    return entry


def main():
    global options, args

    oparser = optparse.OptionParser()
    oparser.add_option('-m', '--mode', dest='mode', default=MODE_ALL,
        help='friends selection method ({0})'.format('|'.join(MODES)))
    oparser.add_option('-u', '--lj-username', default='', metavar='USERNAME',
        help='LiveJournal username')
    oparser.add_option('', '--filename', default='lj.opml',
        help='OPML filename')
    oparser.add_option('', '--folder', default='livejournal',
        help='LJ folder name in OPML')

    options, args = oparser.parse_args()
    if not options.lj_username:
        raise LjrssException('No username specified')
    if options.mode not in MODES:
        raise LjrssException('Unknown mode "{0}"'.format(options.mode))

    options.lj_password = getpass.getpass()

    console.writeline('Getting friends list...')
    mutual, nonmutual = getfriends(options.lj_username, options.lj_password)
    console.writeline('User {0} has {1} friends (including {2} mutual)'.format(
        options.lj_username, len(mutual) + len(nonmutual), len(mutual)))

    document, folder = opml(xml.dom.minidom.Document(), options.folder)

    if options.mode == MODE_MUTUAL:
        friends = mutual
    elif options.mode == MODE_ALL:
        friends = sorted(mutual + nonmutual)
        mutual = set(mutual)

    friends = [user for user in friends
        if not (user.is_identity or user.is_deleted)]

    console.writeline('Generating feeds...')
    progressbar = console.ProgressBar(maxval=len(friends))
    for friend in friends:
        feed = ljusername2url(friend.name)
        if options.mode == MODE_ALL and friend in mutual:
            feed = freefeed(digest(feed))
        folder.appendChild(opmlentry(document, friend.name, feed))
        progressbar.update(1)
    progressbar.finish()

    console.writeline('Creating OPML file...')
    open(options.filename, 'w').write(document.toprettyxml(indent=XML_INDENT))

    return 0

if __name__ == '__main__':
    try:
        options, args = None, None
        sys.exit(main())
    except KeyboardInterrupt:
        console.writeline('Interrupted by user')
    except FreeMyFeedException, ex:
        console.writeline('FreeMyFeed error: {0}'.format(ex.args[0]))
    except LjrssException, ex:
        console.writeline(ex.args[0])
    sys.exit(1)
