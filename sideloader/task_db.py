import time

from twisted.internet import defer, reactor, protocol
from twisted.python import log
from twisted.enterprise import adbapi

class SideloaderDB(object):
    def __init__(self):
        self.p = adbapi.ConnectionPool('psycopg2',
            database='sideloader',
            host='localhost',
            user='postgres',
        )

    def _fetchOneTxn(self, txn, *a, **kw):
        " Transaction callback for self.fetchOne "
        txn.execute(*a)

        r = txn.fetchall()

        if r:
            return r[0]
        else:
            return None

    def fetchOne(self, *a, **kw):
        " Fetch one row only with this query "
        return self.p.runInteraction(self._fetchOneTxn, *a, **kw)

    def runInsert(self, table, keys):
        " Builds a boring INSERT statement and runs it "
        # Unzip the items tupple set into matched order k/v's
        keys, values = zip(*keys.items())

        st = "INSERT INTO %s (%s) VALUES (%s) RETURNING id" % (
            table,
            ','.join(keys),
            ','.join(['%s']*len(keys)) # Witchcraft
        )

        return self.fetchOne(st, values)

    @defer.inlineCallbacks
    def select(self, table, fields, **kw):
        q = []
        args = []
        for k, v in kw.items():
            q.append('%s=%%%%s' % k)
            args.append(v)

        query = "SELECT %s FROM %s" 

        if q:
            query += " WHERE " + ' and '.join(q)

        results = yield self.p.runQuery(query % (
                ','.join(fields),
                table,
            ), tuple(args))

        res = []

        for r in results:
            obj = {}
            for i, col in enumerate(r):
                obj[fields[i]] = col

            res.append(obj)

        defer.returnValue(res)

    # Project queries

    @defer.inlineCallbacks
    def getProject(self, id):
        r = yield self.select('sideloader_project',
            ['id', 'name', 'github_url', 'branch', 'deploy_file', 'idhash',
            'notifications', 'slack_channel', 'created_by_user_id',
            'release_stream_id', 'build_script', 'package_name',
            'postinstall_script', 'package_manager', 'deploy_type'], id=id)
    
        defer.returnValue(r[0])

    def updateBuildLog(self, id, log):
        return self.p.runOperation('UPDATE sideloader_build SET log=%s WHERE id=%s', (log, id))

    @defer.inlineCallbacks
    def getProjectNotificationSettings(self, id):
        
        q = yield self.p.runQuery(
            'SELECT name, notifications, slack_channel FROM sideloader_project'
            ' WHERE id=%s', (id,))

        defer.returnValue(q[0])

    # Build queries

    @defer.inlineCallbacks
    def getBuild(self, id):
        r = yield self.select('sideloader_build', ['id', 'build_time',
            'task_id', 'log', 'project_id', 'state', 'build_file'], id=id)

        defer.returnValue(r[0])

    @defer.inlineCallbacks
    def getBuildNumber(self, repo):
        q = yield self.p.runQuery('SELECT build_num FROM sideloader_buildnumbers WHERE package=%s', (repo,))
        if q:
            defer.returnValue(q[0][0])
        else:
            defer.returnValue(0)

    def setBuildNumber(self, repo, num):
        return self.p.runOperation('UPDATE sideloader_buildnumbers SET build_num=%s WHERE package=%s', (num, repo))

    def setBuildState(self, id, state):
        return self.p.runOperation('UPDATE sideloader_build SET state=%s WHERE id=%s', (state, id))

    def setBuildFile(self, id, f):
        return self.p.runOperation('UPDATE sideloader_build SET build_file=%s WHERE id=%s', (f, id))

    # Release queries

    def createRelease(self, release):
        return self.runInsert('sideloader_release', release)

    def checkReleaseSchedule(self, release):
        if not release['scheduled']:
            return True

        t = int(time.mktime(release['scheduled'].timetuple()))
        if (time.time() - t) > 0:
            return True
        return False

    @defer.inlineCallbacks
    def releaseSignoffCount(self, release_id):
        q = yield self.p.runQuery(
            'SELECT COUNT(*) FROM sideloader_releasesignoff WHERE release_id=%s AND signed=true', (release_id))

        defer.returnValue(q[0][0])

    @defer.inlineCallbacks
    def signoff_remaining(self, release_id, flow):
        q = flow['quorum']

        count = yield self.releaseSignoffCount(release_id)

        email_list = self.getFlowSignoffList(flow)

        if q == 0:
            defer.returnValue(len(email_list) - count)

        defer.returnValue(q - count)

    @defer.inlineCallbacks
    def checkReleaseSignoff(self, release_id, flow):
        if not flow['require_signoff']:
            defer.returnValue(True)

        rem = yield self.signoff_remaining(release_id, flow)
        if rem > 0:
            defer.returnValue(False)

        defer.returnValue(True)

    @defer.inlineCallbacks
    def countReleases(self, id, waiting=False, lock=False):
        q = yield self.p.runQuery('SELECT count(*) FROM sideloader_release'
            ' WHERE flow_id=%s AND waiting=%s AND lock=%s', (id, waiting, lock)
        )

        defer.returnValue(q[0][0])

    def getReleases(self, flowid=None, waiting=None, lock=None):
        q = {}
        if flowid is not None:
            q['flowid'] = flowid
        if waiting is not None:
            q['waiting'] = waiting
        if lock is not None:
            q['lock'] = lock

        return self.select('sideloader_release', 
            ['id', 'release_date', 'scheduled', 'waiting', 'lock', 'build_id', 'flow_id'], **q)

    @defer.inlineCallbacks
    def getRelease(self, id):
        r = yield self.select('sideloader_release', 
            ['id', 'release_date', 'scheduled', 'waiting', 'lock', 'build_id', 'flow_id'], id=id)

        defer.returnValue(r[0])

    @defer.inlineCallbacks
    def getReleaseStream(self, id):
        r = yield self.select('sideloader_releasestream', 
            ['id', 'name', 'push_command'], id=id)

        defer.returnValue(r[0])

    def updateReleaseLocks(self, id, lock):
        return self.p.runOperation('UPDATE sideloader_release SET lock=%s WHERE id=%s', (lock, id))

    def updateReleaseState(self, id, lock=False, waiting=False):
        return self.p.runOperation('UPDATE sideloader_release SET lock=%s, waiting=%s WHERE id=%s', (lock, waiting, id))

    # Flow queries
    @defer.inlineCallbacks
    def getFlow(self, id):
        r = yield self.select('sideloader_releaseflow', [
            'id', 'name', 'stream_mode', 'require_signoff', 'signoff_list',
            'quorum', 'service_restart', 'service_pre_stop', 'puppet_run',
            'auto_release', 'project_id', 'stream_id', 'notify', 'notify_list'
        ], id=id)

        if r:
            defer.returnValue(r[0])
        else:
            defer.returnValue(None)

    def getFlowSignoffList(self, flow):
        return flow['signoff_list'].replace('\r', ' ').replace(
            '\n', ' ').replace(',', ' ').strip().split()

    def getFlowNotifyList(self, flow):
        if flow['notify']:
            return flow['notify_list'].replace('\r', ' ').replace(
                '\n', ' ').replace(',', ' ').strip().split()
        else:
            return []

    def getAutoFlows(self, project):
        return self.select('sideloader_releaseflow', [
            'id', 'name', 'stream_mode', 'require_signoff', 'signoff_list',
            'quorum', 'service_restart', 'service_pre_stop', 'puppet_run',
            'auto_release', 'project_id', 'stream_id', 'notify', 'notify_list'
        ], project_id=project, auto_release=True)

    @defer.inlineCallbacks
    def getNextFlowRelease(self, flow_id):
        q = yield self.p.runQuery('SELECT id FROM sideloader_release'
            ' WHERE flow_id=%s AND waiting=true ORDER BY release_date DESC LIMIT 1', (flow_id,)
        )

        if q:
            release = yield self.getRelease(q[0][0])
        else:
            release = None

        defer.returnValue(release)

    @defer.inlineCallbacks
    def getLastFlowRelease(self, flow_id):
        q = yield self.p.runQuery('SELECT id FROM sideloader_release'
            ' WHERE flow_id=%s AND waiting=false ORDER BY release_date DESC LIMIT 1', (flow_id,)
        )

        if q:
            release = yield self.getRelease(q[0][0])
        else:
            release = None

        defer.returnValue(release)

    # Targets

    def getFlowTargets(self, flow_id):
        return self.select('sideloader_target', ['id', 'deploy_state', 
            'log', 'current_build_id', 'release_id', 'server_id'],
            release_id = flow_id)

    @defer.inlineCallbacks
    def getServer(self, id):
        s = yield self.select('sideloader_server', ['id', 'name',
            'last_checkin', 'last_puppet_run', 'status', 'change',
            'specter_status'], id=id)

        if s:
            defer.returnValue(s[0])
        else:
            defer.returnValue(None)

    def updateTargetState(self, id, state):
        return self.p.runOperation('UPDATE sideloader_target SET deploy_state=%s WHERE id=%s', (state, id))

    def updateTargetLog(self, id, log):
        return self.p.runOperation('UPDATE sideloader_target SET log=%s WHERE id=%s', (log, id))

    def updateTargetBuild(self, id, build):
        return self.p.runOperation('UPDATE sideloader_target SET current_build_id=%s WHERE id=%s', (build, id))

    def updateServerStatus(self, id, status):
        return self.p.runOperation('UPDATE sideloader_server SET status=%s WHERE id=%s', (status, id))
