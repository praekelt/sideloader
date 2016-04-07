"""
Tests for sideloader.task_db.
"""

from twisted.internet import defer, reactor
from twisted.trial import unittest

from sideloader import task_db
from sideloader.tests import fake_db
from sideloader.tests.fake_data import (
    RELEASESTREAM_QA, RELEASESTREAM_PROD, PROJECT_SIDELOADER, BUILD_1,
    RELEASEFLOW_QA, RELEASEFLOW_PROD)


class BothDBsProxy(object):
    """
    A database object wrapper that makes proxies any call to both a real
    database and a fake database. It asserts that both return the same result,
    or that both raise an exception.
    """

    def __init__(self, real_db, fake_db):
        self._real_db = real_db
        self._fake_db = fake_db

    def __getattr__(self, name):
        realattr = getattr(self._real_db, name)
        fakeattr = getattr(self._fake_db, name)

        @defer.inlineCallbacks
        def callboth(self, *args, **kw):
            df = fakeattr(self, *args, **kw)
            dr = realattr(self, *args, **kw)
            [(rs, rr), (fs, fr)] = yield defer.DeferredList([dr, df])
            if not rs:
                assert not fs, (
                    "Real operation failed, fake succeeded: %r" % (rr,))
                raise rr.value
            assert fs, (
                "Real operation succeeded, fake failed: %r" % (fr,))

            assert rr == fr, (
                "Real operation returned %r, fake returned %r" % (rr, fr))
            defer.returnValue(rr)

        return callboth


class TestDB(unittest.TestCase):
    """
    Tests for both task_db and fake_db.
    """

    def setUp(self):
        self.real_db = task_db.SideloaderDB()
        self.addCleanup(self.real_db.p.close)
        self.addCleanup(self.clear_db)
        self.fake_db = fake_db.FakeDB(reactor)
        self.db = BothDBsProxy(self.real_db, self.fake_db)
        return self.clear_db()

    def clear_db(self):
        return defer.DeferredList([self.clear_table(tbl) for tbl in [
            'sideloader_build',
            'sideloader_buildnumbers',
            'sideloader_releaseflow',
            'sideloader_project',
            'sideloader_releasestream',
        ]])

    def clear_table(self, table):
        return self.real_db.p.runOperation('DELETE FROM %s' % (table,))

    @defer.inlineCallbacks
    def test_real_select(self):
        yield self.real_db.select('sideloader_project', [
            'id', 'name', 'github_url', 'branch', 'deploy_file', 'idhash',
            'notifications', 'slack_channel', 'created_by_user_id',
            'release_stream_id', 'build_script', 'package_name',
            'postinstall_script', 'package_manager', 'deploy_type'])

    @defer.inlineCallbacks
    def test_getProject(self):
        """
        We can get information about a project.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        proj = yield self.db.getProject(1)
        assert proj == PROJECT_SIDELOADER

    @defer.inlineCallbacks
    def test_getProject_missing(self):
        """
        We can't get information about a project that doesn't exist.
        """
        yield self.assertFailure(self.db.getProject(42), Exception)

    @defer.inlineCallbacks
    def test_updateBuildLog(self):
        """
        We can update a build's log.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.updateBuildLog(1, "Stardate 19564.3: Building a thing.")
        build = yield self.db.getBuild(1)
        assert build['log'] == "Stardate 19564.3: Building a thing."

    @defer.inlineCallbacks
    def test_updateBuildLog_missing(self):
        """
        Updates to missing builds go to /dev/null.
        """
        yield self.db.updateBuildLog(42, "Stardate 19564.3: Building a thing.")

    @defer.inlineCallbacks
    def test_getProjectNotificationSettings(self):
        """
        We can get notification settings for a project.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        pns = yield self.db.getProjectNotificationSettings(1)
        assert pns == (
            PROJECT_SIDELOADER['name'],
            PROJECT_SIDELOADER['notifications'],
            PROJECT_SIDELOADER['slack_channel'],
        )

    @defer.inlineCallbacks
    def test_getProjectNotificationSettings_missing(self):
        """
        We can't get notification settings for a project  that doesn't exist.
        """
        yield self.assertFailure(
            self.db.getProjectNotificationSettings(1), Exception)

    @defer.inlineCallbacks
    def test_getBuild(self):
        """
        We can get information about a build.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        build = yield self.db.getBuild(1)
        assert build == BUILD_1

    @defer.inlineCallbacks
    def test_getBuild_missing(self):
        """
        We can't get information about a build that doesn't exist.
        """
        yield self.assertFailure(self.db.getBuild(42), Exception)

    @defer.inlineCallbacks
    def test_getBuildNumber_missing(self):
        """
        If we ask for a missing build number, we get zero.
        """
        r = yield self.db.getBuildNumber('myproj')
        assert r == 0

    @defer.inlineCallbacks
    def test_setBuildNumber_create(self):
        """
        If we set a new build number and then get it, we get the one we set.
        """
        yield self.db.setBuildNumber('myproj', 7, create=True)
        r = yield self.db.getBuildNumber('myproj')
        assert r == 7

    @defer.inlineCallbacks
    def test_setBuildNumber_create_exists(self):
        """
        We can't set a new build number if the project already has one.
        """
        yield self.db.setBuildNumber('myproj', 7, create=True)
        d = self.db.setBuildNumber('myproj', 12, create=True)
        yield self.assertFailure(d, Exception)
        r = yield self.db.getBuildNumber('myproj')
        assert r == 7

    @defer.inlineCallbacks
    def test_setBuildNumber_getBuildNumber(self):
        """
        If we set a build number and then get it, we get the one we set.
        """
        yield self.db.setBuildNumber('myproj', 7, create=True)
        yield self.db.setBuildNumber('myproj', 12)
        r = yield self.db.getBuildNumber('myproj')
        assert r == 12

    @defer.inlineCallbacks
    def test_setBuildState(self):
        """
        We can update a build's state.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.setBuildState(1, 2)
        build = yield self.db.getBuild(1)
        assert build['state'] == 2

    @defer.inlineCallbacks
    def test_setBuildState_missing(self):
        """
        Updates to missing builds go to /dev/null.
        """
        yield self.db.setBuildState(42, 2)

    @defer.inlineCallbacks
    def test_setBuildFile(self):
        """
        We can update a build's file.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.setBuildFile(1, 'foo.deb')
        build = yield self.db.getBuild(1)
        assert build['build_file'] == 'foo.deb'

    @defer.inlineCallbacks
    def test_setBuildFile_missing(self):
        """
        Updates to missing builds go to /dev/null.
        """
        yield self.db.setBuildFile(42, 'foo.deb')

    @defer.inlineCallbacks
    def test_getAutoFlows(self):
        """
        We can get all the autorelease flows for a project.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_PROD)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_PROD)
        flows = yield self.db.getAutoFlows(1)
        assert flows == [RELEASEFLOW_QA]

    @defer.inlineCallbacks
    def test_getAutoFlows_no_flows(self):
        """
        We can get all the autorelease flows for a project.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        flows = yield self.db.getAutoFlows(1)
        assert flows == []
