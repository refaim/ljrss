# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import re
import xml.dom.minidom
import mechanize

import lj
from pbar import ProgressBar

FMF_URL = 'http://freemyfeed.com/'
FMF_FORM_ID = 0
LJ_RSS_URL = 'http://{0}.livejournal.com/data/rss?auth=digest'

class Config(object):
    def __init__(self):
        self.user = None
        self.password = None

def error(message):
    message = 'Error: {0!s}'.format(message)
    print(message)
    return 1

config = Config()

def main(argv):
    if len(argv) > 3:
        return error('ljrss.py <lj-username> <password> [filename]')
    config.user, config.password = argv[0], argv[1]
    config.filename = argv[2] if len(argv) == 3 else 'lj_mutual.xml'

    print('Getting the list of mutual friends...')
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
    print('User {0} has {1} mutual friends'.format(config.user, len(mutualfriends)))

    browser = mechanize.Browser()
    
    def getrssurl(url):
        browser.open(FMF_URL)
        browser.select_form(nr=FMF_FORM_ID)
        browser['url'] = url
        browser['user'] = config.user
        browser['pass'] = config.password
        response = browser.submit()
    
        url_re = r'\<p id="viewrss"\>\<a href="(.*)" onclick.*\<\/p\>'
        match = re.search(url_re, response.read())
        if match:
            return match.group(1)

    data = ((username, getrssurl(LJ_RSS_URL.format(username.replace('_', '-')))) for username in mutualfriends)

    document = xml.dom.minidom.Document()
    opml = document.createElement('opml')
    opml.setAttribute('version', '1.1')
    document.appendChild(opml)
    body = document.createElement('body')
    opml.appendChild(body)
    folder = document.createElement('outline')
    folder.setAttribute('text', 'lj_mutual')
    body.appendChild(folder)

    print('Working with FreeMyFeed...')
    progressbar = ProgressBar(maxval=len(mutualfriends))
    for username, url in data:
        if not url:
            print("Warning!  Couldn't get URL for", username)
            continue
        entry = document.createElement('outline')
        entry.setAttribute('title', username)
        entry.setAttribute('text', username)
        entry.setAttribute('xmlUrl', url)
        folder.appendChild(entry)
        progressbar.update(1)
    progressbar.finish()

    print('Creating OPML-file...')
    with open(config.filename, 'w') as opmlfile:
        opmlfile.write(document.toprettyxml(indent=' ' * 2))
    
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
