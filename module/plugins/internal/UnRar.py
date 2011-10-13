# -*- coding: utf-8 -*-

"""
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License,
    or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <http://www.gnu.org/licenses/>.
    
    @author: mkaay
"""
from __future__ import with_statement

import sys
import os
from os.path import exists, join, isabs, isdir
from os import remove, makedirs, rmdir, listdir, chmod
from traceback import print_exc

from module.plugins.Hook import Hook
from module.lib.pyunrar import Unrar, WrongPasswordError, CommandError, UnknownError, LowRamError

from module.utils import save_join

if os.name != "nt":
    from pwd import getpwnam
    from os import chown

import re

class UnRar(Hook):
    __name__ = "UnRar"
    __version__ = "0.1"
    __description__ = """Unrar plugin for archive extractor"""
    __config__ = [("activated", "bool", "Activated", False),
        ("fullpath", "bool", "extract full path", True),
        ("overwrite", "bool", "overwrite files", True),
        ("passwordfile", "str", "unrar password file", "unrar_passwords.txt"),
        ("deletearchive", "bool", "delete archives when done", False),
        ("ramwarning", "bool", "warn about low ram", True),
        ("renice", "int", "Cpu Priority", 10),
        ("unrar_destination", "str", "Unpack files to", "")]
    __threaded__ = ["packageFinished"]
    __author_name__ = ("mkaay")
    __author_mail__ = ("mkaay@mkaay.de")

    def setup(self):
        self.comments = ["# one password each line"]
        self.passwords = []
        if exists(self.getConfig("passwordfile")):
            with open(self.getConfig("passwordfile"), "r") as f:
                for l in f.readlines():
                    l = l.strip("\n\r")
                    if l and not l.startswith("#"):
                        self.passwords.append(l)
        else:
            with open(self.getConfig("passwordfile"), "w") as f:
                f.writelines(self.comments)
        self.re_splitfile = re.compile("(.*)\.part(\d+)\.rar$")

        self.ram = 0  #ram in kb for unix osses
        try:
            f = open("/proc/meminfo")
            line = True
            while line:
                line = f.readline()
                if line.startswith("MemTotal:"):
                    self.ram = int(re.search(r"([0-9]+)", line).group(1))
        except:
            self.ram = 0

        self.ram /= 1024

    def setOwner(self, d, uid, gid, mode):
        if not exists(d):
            self.core.log.debug(_("Directory %s does not exist!") % d)
            return

        for fileEntry in listdir(d):
            fullEntryName = join(d, fileEntry)
            if isdir(fullEntryName):
                self.setOwner(fullEntryName, uid, gid, mode)
            try:
                chown(fullEntryName, uid, gid)
                chmod(fullEntryName, mode)
            except:
                self.core.log.debug(_("Chown/Chmod for %s failed") % fullEntryName)
                self.core.log.debug(_("Exception: %s") % sys.exc_info()[0])
                continue
        try:
            chown(d, uid, gid)
            chmod(d, mode)
        except:
            self.core.log.debug(_("Chown/Chmod for %s failed") % d)
            self.core.log.debug(_("Exception: %s") % sys.exc_info()[0])
            return

    def addPassword(self, pws):
        if not type(pws) == list: pws = [pws]
        pws.reverse()
        for pw in pws:
            pw = pw.strip()
            if not pw or pw == "None" or pw in self.passwords: continue
            self.passwords.insert(0, pw)

        with open(self.getConfig("passwordfile"), "w") as f:
            f.writelines([c + "\n" for c in self.comments])
            f.writelines([p + "\n" for p in self.passwords])

    def removeFiles(self, pack, fname):
        if not self.getConfig("deletearchive"):
            return
        m = self.re_splitfile.search(fname)

        download_folder = self.core.config['general']['download_folder']
        if self.core.config['general']['folder_per_package']:
            folder = join(download_folder, pack.folder.decode(sys.getfilesystemencoding()))
        else:
            folder = download_folder
        if m:
            nre = re.compile("%s\.part\d+\.rar" % m.group(1))
            for fid, data in pack.getChildren().iteritems():
                if nre.match(data["name"]):
                    remove(join(folder, data["name"]))
        elif not m and fname.endswith(".rar"):
            nre = re.compile("^%s\.r..$" % fname.replace(".rar", ""))
            for fid, data in pack.getChildren().iteritems():
                if nre.match(data["name"]):
                    remove(join(folder, data["name"]))

    def packageFinished(self, pack):
        if pack.password and pack.password.strip() and pack.password.strip() != "None":
            self.addPassword(pack.password.splitlines())
        files = []

        for fid, data in pack.getChildren().iteritems():
            m = self.re_splitfile.search(data["name"])
            if m and int(m.group(2)) == 1:
                files.append((fid, m.group(0)))
            elif not m and data["name"].endswith(".rar"):
                files.append((fid, data["name"]))

        for fid, fname in files:
            self.core.log.info(_("starting Unrar of %s") % fname)
            pyfile = self.core.files.getFile(fid)
            pyfile.setStatus("processing")

            def s(p):
                pyfile.setProgress(p)

            download_folder = self.core.config['general']['download_folder']
            self.core.log.debug(_("download folder %s") % download_folder)

            folder = save_join(download_folder, pack.folder, "")


            destination = folder
            if self.getConfig("unrar_destination") and not self.getConfig("unrar_destination").lower() == "none":
                destination = self.getConfig("unrar_destination")
                sub = "."
                if self.core.config['general']['folder_per_package']:
                    sub = pack.folder.decode(sys.getfilesystemencoding())
                if isabs(destination):
                    destination = join(destination, sub, "")
                else:
                    destination = join(folder, destination, sub, "")

            self.core.log.debug(_("Destination folder %s") % destination)
            if not exists(destination):
                self.core.log.info(_("Creating destination folder %s") % destination)
                makedirs(destination)

            u = Unrar(join(folder, fname), tmpdir=join(folder, "tmp"),
                      ramSize=(self.ram if self.getConfig("ramwarning") else 0), cpu=self.getConfig("renice"))
            try:
                success = u.crackPassword(passwords=self.passwords, statusFunction=s, overwrite=True,
                                          destination=destination, fullPath=self.getConfig("fullpath"))
            except WrongPasswordError:
                self.core.log.info(_("Unrar of %s failed (wrong password)") % fname)
                continue
            except CommandError, e:
                if self.core.debug:
                    print_exc()
                if re.search("Cannot find volume", e.stderr):
                    self.core.log.info(_("Unrar of %s failed (missing volume)") % fname)
                    continue
                try:
                    if e.getExitCode() == 1 and len(u.listContent(u.getPassword())) == 1:
                        self.core.log.info(_("Unrar of %s ok") % fname)
                        self.removeFiles(pack, fname)
                except:
                    if self.core.debug:
                        print_exc()
                    self.core.log.info(_("Unrar of %s failed") % fname)
                    continue
            except LowRamError:
                self.log.warning(_(
                    "Your ram amount of %s MB seems not sufficient to unrar this file. You can deactivate this warning and risk instability") % self.ram)
                continue
            except UnknownError:
                if self.core.debug:
                    print_exc()
                self.core.log.info(_("Unrar of %s failed") % fname)
                continue
            else:
                if success:
                    self.core.log.info(_("Unrar of %s ok") % fname)
                    self.removeFiles(pack, fname)

                    if os.name != "nt" and self.core.config['permission']['change_dl'] and\
                       self.core.config['permission']['change_file']:
                        ownerUser = self.core.config['permission']['user']
                        fileMode = int(self.core.config['permission']['file'], 8)

                        self.core.log.debug("Setting destination file/directory owner / mode to %s / %s"
                        % (ownerUser, fileMode))

                        uinfo = getpwnam(ownerUser)
                        self.core.log.debug("Uid/Gid is %s/%s." % (uinfo.pw_uid, uinfo.pw_gid))
                        self.setOwner(destination, uinfo.pw_uid, uinfo.pw_gid, fileMode)
                        self.core.log.debug("The owner/rights have been successfully changed.")

                    self.core.hookManager.unrarFinished(folder, fname)
                else:
                    self.core.log.info(_("Unrar of %s failed (wrong password or bad parts)") % fname)
            finally:
                pyfile.setProgress(100)
                pyfile.setStatus("finished")
                pyfile.release()
