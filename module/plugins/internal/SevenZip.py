# -*- coding: utf-8 -*-

import os
import re

from subprocess import Popen, PIPE

from module.plugins.internal.UnRar import ArchiveError, CRCError, PasswordError, UnRar, renice
from module.utils import fs_encode, save_join


class SevenZip(UnRar):
    __name__    = "SevenZip"
    __version__ = "0.07"

    __description__ = """7-Zip extractor plugin"""
    __license__     = "GPLv3"
    __authors__     = [("Michael Nowak", ""),
                       ("Walter Purcaro", "vuolter@gmail.com")]


    CMD = "7z"

    EXTENSIONS = [".7z", ".xz", ".zip", ".gz", ".gzip", ".tgz", ".bz2", ".bzip2",
                  ".tbz2", ".tbz", ".tar", ".wim", ".swm", ".lzma", ".rar", ".cab",
                  ".arj", ".z", ".taz", ".cpio", ".rpm", ".deb", ".lzh", ".lha",
                  ".chm", ".chw", ".hxs", ".iso", ".msi", ".doc", ".xls", ".ppt",
                  ".dmg", ".xar", ".hfs", ".exe", ".ntfs", ".fat", ".vhd", ".mbr",
                  ".squashfs", ".cramfs", ".scap"]


    #@NOTE: there are some more uncovered 7z formats
    re_filelist = re.compile(r'([\d\:]+)\s+([\d\:]+)\s+([\w\.]+)\s+(\d+)\s+(\d+)\s+(.+)')
    re_wrongpwd = re.compile(r'(Can not open encrypted archive|Wrong password)', re.I)
    re_wrongcrc = re.compile(r'Encrypted\s+\=\s+\+', re.I)


    @classmethod
    def isUsable(cls):
        if os.name == "nt":
            cls.CMD = os.path.join(pypath, "7z.exe")
            p = Popen([cls.CMD], stdout=PIPE, stderr=PIPE)
            p.communicate()
        else:
            p = Popen([cls.CMD], stdout=PIPE, stderr=PIPE)
            p.communicate()

        return True


    def check(self):
        file = fs_encode(self.filename)

        p = self.call_cmd("t", file)
        out, err = p.communicate()

        if p.returncode > 1:
            raise CRCError(err)

        p = self.call_cmd("l", "-slt", file)
        out, err = p.communicate()

        if p.returncode > 1:
            raise ArchiveError(_("Process return code: %d") % p.returncode)

        # check if output or error macthes the 'wrong password'-Regexp
        if self.re_wrongpwd.search(out):
            raise PasswordError

        # check if output matches 'Encrypted = +'
        if self.re_wrongcrc.search(out):
            raise CRCError(_("Header protected"))


    def isPassword(self, password):
        p = self.call_cmd("l", fs_encode(self.filename), password=password)
        p.communicate()
        return p.returncode == 0


    def repair(self):
        return False


    def extract(self, password=None):
        command = "x" if self.fullpath else "e"

        p = self.call_cmd(command, '-o' + self.out, fs_encode(self.filename), password=password)

        renice(p.pid, self.renice)

        # communicate and retrieve stderr
        self._progress(p)
        err = p.stderr.read().strip()

        if err:
            if self.re_wrongpwd.search(err):
                raise PasswordError

            elif self.re_wrongcrc.search(err):
                raise CRCError(err)

            else:  #: raise error if anything is on stderr
                raise ArchiveError(err)

        if p.returncode > 1:
            raise ArchiveError(_("Process return code: %d") % p.returncode)

        self.files = self.list(password)


    def list(self, password=None):
        command = "l" if self.fullpath else "l"

        p = self.call_cmd(command, fs_encode(self.filename), password=password)
        out, err = p.communicate()

        if "Can not open" in err:
            raise ArchiveError(_("Cannot open file"))

        if p.returncode > 1:
            raise ArchiveError(_("Process return code: %d") % p.returncode)

        result = set()
        for groups in self.re_filelist.findall(out):
            f = groups[-1].strip()
            result.add(save_join(self.out, f))

        return list(result)


    def call_cmd(self, command, *xargs, **kwargs):
        args = []

        #overwrite flag
        if self.overwrite:
            args.append("-y")

        #set a password
        if "password" in kwargs and kwargs["password"]:
            args.append("-p'%s'" % kwargs["password"])
        else:
            args.append("-p-")

        #@NOTE: return codes are not reliable, some kind of threading, cleanup whatever issue
        call = [self.cmd, command] + args + list(xargs)

        self.manager.logDebug(" ".join(map(decode, call)))

        p = Popen(call, stdout=PIPE, stderr=PIPE)
        return p
