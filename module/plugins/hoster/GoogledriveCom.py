# -*- coding: utf-8 -*
#
# Test links:
#   https://drive.google.com/file/d/0B6RNTe4ygItBQm15RnJiTmMyckU/view?pli=1

import re

from module.plugins.internal.SimpleHoster import SimpleHoster, create_getInfo
from module.utils import html_unescape


class GoogledriveCom(SimpleHoster):
    __name__    = "GoogledriveCom"
    __type__    = "hoster"
    __version__ = "0.02"

    __pattern__ = r'https?://(?:www\.)?drive\.google\.com/file/.+'

    __description__ = """Drive.google.com hoster plugin"""
    __license__     = "GPLv3"
    __authors__     = [("zapp-brannigan", "fuerst.reinje@web.de")]


    NAME_PATTERN    = r'"og:title" content="(?P<N>.*?)">'
    OFFLINE_PATTERN = r'align="center"><p class="errorMessage"'


    def setup(self):
        self.multiDL        = True
        self.resumeDownload = True
        self.chunkLimit     = 1


    def handleFree(self, pyfile):
        try:
            link1 = re.search(r'"(https://docs.google.com/uc\?id.*?export=download)",',
                              self.html.decode('unicode-escape')).group(1)

        except AttributeError:
            self.error(_("Hop #1 not found"))

        else:
            self.logDebug("Next hop: %s" % link1)

        self.html = self.load(link1).decode('unicode-escape')

        try:
            link2 = html_unescape(re.search(r'href="(/uc\?export=download.*?)">',
                                  self.html).group(1))

        except AttributeError:
            self.error(_("Hop #2 not found"))

        else:
            self.logDebug("Next hop: %s" % link2)

        link3 = self.load("https://docs.google.com" + link2, just_header=True)
        self.logDebug("DL-Link: %s" % link3['location'])

        self.link = link3['location']  #@NOTE: I don't use disposition=True because it breaks the filename.


getInfo = create_getInfo(GoogledriveCom)
