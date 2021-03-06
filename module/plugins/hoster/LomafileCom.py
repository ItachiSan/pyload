# -*- coding: utf-8 -*-

from module.plugins.internal.DeadHoster import DeadHoster, create_getInfo


class LomafileCom(DeadHoster):
    __name__    = "LomafileCom"
    __type__    = "hoster"
    __version__ = "0.52"

    __pattern__ = r'http://lomafile\.com/\w{12}'

    __description__ = """Lomafile.com hoster plugin"""
    __license__     = "GPLv3"
    __authors__     = [("nath_schwarz", "nathan.notwhite@gmail.com"),
                       ("guidobelix", "guidobelix@hotmail.it")]


getInfo = create_getInfo(LomafileCom)
