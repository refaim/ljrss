# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import re
import xml.dom.minidom
import mechanize

import lj
from utils import console

class Config(object):
    def __init__(self):
        self.user = None
        self.password = None

def error(message):
    message = 'Error: {0!s}'.format(message)
    console.writeline(message)
    return 1

config = Config()

def main(argv):
    if len(argv) > 3:
        return error('ljrss.py <lj-username> <password> [filename]')
    config.user, config.password = argv[0], argv[1]
    config.filename = argv[2] if len(argv) == 3 else 'lj_mutual.xml'

    console.writeline('Getting the list of mutual friends...')
    try:
        livejournal = lj.LJServer('lj.py; kemayo@gmail.com', 'Python-PyLJ/0.0.1')
        livejournal.login(config.user, config.password)

        def getusernames(response):
            return (item['username'] for item in response)

        friendof = getusernames(livejournal.friendof()['friendofs'])
        friends = getusernames(livejournal.getfriends()['friends'])
        mutualfriends = [str(friend) for friend in set(friendof) & set(friends)]
    except lj.LJException as e:
        return error(e)
    console.writeline('User {0} has {1} mutual friends'.format(
        config.user, len(mutualfriends)))

    browser = mechanize.Browser()

    def getrssurl(url):
        browser.open('http://freemyfeed.com/')
        browser.select_form(nr=0)
        browser['url'] = url
        browser['user'] = config.user
        browser['pass'] = config.password
        response = browser.submit()

        url_re = r'\<p id="viewrss"\>\<a href="(.*)" onclick.*\<\/p\>'
        match = re.search(url_re, response.read())
        if match:
            return match.group(1)

    def username2url(ljuser):
        if ljuser.startswith('_') or ljuser.endswith('_'):
            template = 'http://users.livejournal.com/{0}'
        else:
            ljuser = ljuser.replace('_', '-')
            template = 'http://{0}.livejournal.com'
        return template.format(ljuser) + '/data/rss?auth=digest'

    data = ((username, getrssurl(username2url(username))) for username in mutualfriends)

    document = xml.dom.minidom.Document()
    opml = document.createElement('opml')
    opml.setAttribute('version', '1.1')
    document.appendChild(opml)
    body = document.createElement('body')
    opml.appendChild(body)
    folder = document.createElement('outline')
    folder.setAttribute('text', 'lj_mutual')
    body.appendChild(folder)

    console.writeline('Working with FreeMyFeed...')
    progressbar = console.ProgressBar(maxval=len(mutualfriends))
    for username, url in data:
        if not url:
            console.writeline(
                'Warning: Couldn\'t get URL for {0]'.format(username))
            continue
        entry = document.createElement('outline')
        entry.setAttribute('title', username)
        entry.setAttribute('text', username)
        entry.setAttribute('xmlUrl', url)
        folder.appendChild(entry)
        progressbar.update(1)
    progressbar.finish()

    console.writeline('Creating OPML file...')
    with open(config.filename, 'w') as opmlfile:
        opmlfile.write(document.toprettyxml(indent=' ' * 2))

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
