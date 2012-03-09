# -*- coding: utf-8 -*-

from __future__ import print_function

import optparse
import re
import socket
import sys
import urllib2
import xml.dom.minidom

import mechanize

import lj
from utils import console

class LjrssException(Exception): pass

XML_INDENT = 2 * ' '

MODE_MUTUAL = 'mutual'
MODE_ALL = 'all'
MODES = (MODE_MUTUAL, MODE_ALL)

FMF_RE = re.compile(r'\<p id="viewrss"\>\<a href="(.*)" onclick.*\<\/p\>')

def getfriends(lj_username, lj_password):
    try:
        livejournal = lj.LJServer('lj.py; kemayo@gmail.com', 'Python-PyLJ/0.0.1')
        livejournal.login(lj_username, lj_password)

        def getusernames(response):
            return set(item['username'] for item in response)

        friendof = getusernames(livejournal.friendof()['friendofs'])
        friends = getusernames(livejournal.getfriends()['friends'])
        mutual = sorted(str(friend) for friend in friends & friendof)
        nonmutual = sorted(str(friend) for friend in friends - friendof)
    except lj.LJException, ex:
        raise LjrssException(ex)
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

    fmfurl = 'http://freemyfeed.com/'
    browser = mechanize.Browser()
    try:
        browser.open(fmfurl)
    except urllib2.URLError, ex:
        error = ex.args[0]
        if isinstance(error, socket.gaierror):
            error = 'Error {0}: {1}'.format(*error.args)
        raise LjrssException(error)

    browser.select_form(nr=0)
    browser['url'] = url
    browser['user'] = options.lj_username
    browser['pass'] = options.lj_password
    response = browser.submit()

    match = FMF_RE.search(response.read())
    if match:
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


def main(argv):
    global options, args

    oparser = optparse.OptionParser()
    oparser.add_option('-m', '--mode', dest='mode', default=MODE_MUTUAL,
        help='friends selection method ({0})'.format('|'.join(MODES)))
    oparser.add_option('-u', '--lj-username', default='', metavar='USERNAME',
        help='LiveJournal username')
    oparser.add_option('-p', '--lj-password', default='', metavar='PASSWORD',
        help='LiveJournal password')
    oparser.add_option('', '--filename', default='lj.opml',
        help='OPML filename')
    oparser.add_option('', '--folder', default='livejournal',
        help='LJ folder name in OPML')

    options, args = oparser.parse_args()
    if options.mode not in MODES:
        raise LjrssException('Unknown mode "{0}"'.format(options.mode))

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

    console.writeline('Generating feeds...')
    progressbar = console.ProgressBar(maxval=len(friends))
    for friend in friends:
        feed = ljusername2url(friend)
        if options.mode == MODE_ALL and friend in mutual:
            feed = freefeed(digest(feed))
            if not feed:
                console.writeline(
                    'Warning: Couldn\'t free feed for {0}'.format(friend))
                continue
        folder.appendChild(opmlentry(document, friend, feed))
        progressbar.update(1)
    progressbar.finish()

    console.writeline('Creating OPML file...')
    open(options.filename, 'w').write(document.toprettyxml(indent=XML_INDENT))

    return 0

if __name__ == '__main__':
    try:
        options, args = None, None
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        console.writeline('Interrupted by user')
    except LjrssException, ex:
        console.writeline(ex.args[0])
    sys.exit(1)
