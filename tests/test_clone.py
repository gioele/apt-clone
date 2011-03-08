#!/usr/bin/python

import apt
import apt_pkg
import mock
import os
import shutil
import sys
import tempfile
import unittest

from StringIO import StringIO

sys.path.insert(0, "..")
import apt_clone
from apt_clone import AptClone

class MockAptCache(apt.Cache):
    def commit(self, fetchp, installp):
        pass
    def update(self, fetchp):
        pass

class TestClone(unittest.TestCase):

    def setUp(self):
        apt_pkg.init_config()
        apt_pkg.config.set("Debug::pkgDPkgPM","1")
        apt_pkg.config.clear("DPkg::Post-Invoke")
        self.tempdir = tempfile.mkdtemp("apt-clone-tests-")
        os.makedirs(os.path.join(self.tempdir, "var/lib/dpkg/"))
        # ensure we are the right arch
        os.makedirs(os.path.join(self.tempdir, "etc/apt"))
        open(os.path.join(self.tempdir, "etc/apt/apt.conf"), "w").write('''
APT::Architecture "i386";
#clear Dpkg::Post-Invoke;
#clear Dpkg::Pre-Invoke;
''')

    @mock.patch("apt_clone.LowLevelCommands")
    def test_save_state(self, mock_lowlevel):
        self._save_state(False)

    @mock.patch("apt_clone.LowLevelCommands")
    def test_save_state_with_dpkg_repack(self, mock_lowlevel):
        self._save_state(True)

    def _save_state(self, with_dpkg_repack):
        # setup mock
        targetdir = self.tempdir
        # test
        clone = AptClone(cache_cls=MockAptCache)
        sourcedir = "/"
        clone.save_state(sourcedir, targetdir, with_dpkg_repack)
        self.assertTrue(
            os.path.exists(os.path.join(targetdir, "sources.list")))
        self.assertTrue(
            os.path.exists(os.path.join(targetdir, "installed.pkgs")))
        self.assertTrue(
            os.path.exists(os.path.join(targetdir, "extended_states")))
        self.assertTrue(
            os.path.exists(os.path.join(targetdir, "sources.list.d")))
        self.assertTrue(
            os.path.exists(os.path.join(targetdir, "apt-state.tar.gz")))
        if clone.not_downloadable:
            self.assertEqual(clone.commands.repack_deb.called, with_dpkg_repack)

    @mock.patch("apt_clone.LowLevelCommands")
    def test_restore_state(self, mock_lowlevel):
        # setup mock
        mock_lowlevel.install_debs.return_value = True
        targetdir = self.tempdir
        # test
        clone = AptClone(cache_cls=MockAptCache)
        clone.restore_state("./tests/data/apt-state.tar.gz", targetdir)
        self.assertTrue(
            os.path.exists(os.path.join(targetdir, "etc","apt","sources.list")))

    @mock.patch("apt_clone.LowLevelCommands")
    def test_restore_state_on_new_distro_release_livecd(self, mock_lowlevel):
        """ 
        test lucid -> maverick apt-clone-ugprade as if it will be used
        from a live cd based upgrader
        """
        # setup mock for dpkg -i
        mock_lowlevel.install_debs.return_value = True
        # create target dir
        targetdir = self.tempdir
        # status file from maverick (to simulate running on a maverick live-cd)
        shutil.copy("./tests/data/dpkg-status/dpkg-status-ubuntu-maverick",
                    os.path.join(targetdir, "var/lib/dpkg", "status"))
        # test upgrade clone from lucid system to maverick
        clone = AptClone(cache_cls=MockAptCache)
        clone.restore_state(
            "./tests/data/apt-state-ubuntu-lucid.tar.gz", 
            targetdir,
            "maverick")
        sources_list = os.path.join(targetdir, "etc","apt","sources.list")
        self.assertTrue(os.path.exists(sources_list))
        self.assertTrue("maverick" in open(sources_list).read())
        self.assertFalse("lucid" in open(sources_list).read())
        

    def test_save_pkgselection_only(self):
        clone = AptClone(cache_cls=MockAptCache)
        targetdir = os.path.join(self.tempdir, "pkgstates.only")
        os.makedirs(targetdir)
        # clone
        sourcedir="/"
        clone._write_state_installed_pkgs(sourcedir, targetdir)
        self.assertTrue(
            os.path.exists(os.path.join(targetdir, "installed.pkgs")))

    def test_restore_pkgselection_only(self):
        clone = AptClone(cache_cls=MockAptCache)
        targetdir = self.tempdir
        open(os.path.join(targetdir, "installed.pkgs"), "w").write("""
4g8 1.0-3 0
libnet1 1.1.2-1 1
""")
        cache = apt.Cache()
        clone._restore_package_selection_in_cache(targetdir, cache)
        self.assertEqual(len(cache.get_changes()), 2)

    def test_restore_state_simulate(self):
        clone = AptClone()
        missing = clone.simulate_restore_state("./tests/data/apt-state.tar.gz")
        # missing, because clone does not have universe enabled
        self.assertEqual(list(missing), ["accerciser"])

    def test_restore_state_simulate_with_new_release(self):
        #apt_pkg.config.set("Debug::PkgProblemResolver", "1")
        clone = AptClone()
        missing = clone.simulate_restore_state(
            "./tests/data/apt-state-ubuntu-lucid.tar.gz", "maverick") 
        # FIXME: check that the stuff in missing is ok
        #print missing

if __name__ == "__main__":
    unittest.main()
