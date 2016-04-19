from copy import deepcopy
from functools import wraps

from twisted.internet import task


def async(f):
    """
    Make the wrapped function async by calling it a millisecond in the future.
    """
    @wraps(f)
    def wrapper(self, *args, **kw):
        return task.deferLater(self.clock, 0.001, f, self, *args, **kw)
    return wrapper


class FakeDB(object):
    """
    A test double for sideloader.task_db.
    """

    def __init__(self, clock):
        self.clock = clock
        self._releasestream = {}
        self._project = {}
        self._build = {}
        self._buildnumbers = {}
        self._releaseflow = {}
        self._release = {}
        self._webhook = {}

    def _set_id(self, table, row):
        if 'id' not in row:
            row['id'] = max(list(table.keys()) + [0]) + 1
        return row['id']

    @async
    def runInsert(self, table, keys):
        tbl = getattr(self, table.replace('sideloader_', '_'))
        row = deepcopy(keys)
        id = self._set_id(tbl, row)
        assert id not in tbl
        tbl[id] = row
        return (id,)

    # Project queries

    @async
    def getProject(self, id):
        return deepcopy(self._project[id])

    @async
    def updateBuildLog(self, id, data):
        if id in self._build:
            self._build[id]['log'] = data

    @async
    def getProjectNotificationSettings(self, id):
        prj = self._project[id]
        return (prj['name'], prj['notifications'], prj['slack_channel'])

    # Build queries

    @async
    def getBuild(self, id):
        return deepcopy(self._build[id])

    @async
    def getBuildNumber(self, repo):
        return self._buildnumbers.get(repo, 0)

    @async
    def setBuildNumber(self, repo, num, create=False):
        assert type(num) is int
        if create:
            assert repo not in self._buildnumbers
        elif repo not in self._buildnumbers:
            return
        self._buildnumbers[repo] = num

    @async
    def setBuildState(self, id, state):
        if id in self._build:
            self._build[id]['state'] = int(state)

    @async
    def setBuildFile(self, id, file):
        if id in self._build:
            self._build[id]['build_file'] = file

    # Release queries

    def createRelease(self, release):
        return self.runInsert('sideloader_release', release)

    # NOTE: Not async.
    def checkReleaseSchedule(self, release):
        if not release['scheduled']:
            return True
        raise NotImplementedError("TODO")

    def releaseSignoffCount(self, release_id):
        raise NotImplementedError("TODO")

    def signoff_remaining(self, release_id, flow):
        raise NotImplementedError("TODO")

    @async
    def checkReleaseSignoff(self, release_id, flow):
        if not flow['require_signoff']:
            return True
        raise NotImplementedError("TODO")

    def countReleases(self, id, waiting=False, lock=False):
        raise NotImplementedError("TODO")

    def getReleases(self, flowid=None, waiting=None, lock=None):
        raise NotImplementedError("TODO")

    @async
    def getRelease(self, id):
        return deepcopy(self._release[id])

    @async
    def getReleaseStream(self, id):
        return deepcopy(self._releasestream[id])

    @async
    def updateReleaseLocks(self, id, lock):
        assert isinstance(lock, bool)
        self._release[id]['lock'] = lock

    @async
    def updateReleaseState(self, id, lock=False, waiting=False):
        assert isinstance(lock, bool)
        assert isinstance(waiting, bool)
        self._release[id]['lock'] = lock
        self._release[id]['waiting'] = waiting

    # Flow queries

    @async
    def getFlow(self, id):
        return deepcopy(self._releaseflow[id])

    def getFlowSignoffList(self, flow):
        raise NotImplementedError("TODO")

    # NOTE: Not async.
    def getFlowNotifyList(self, flow):
        if flow['notify']:
            return flow['notify_list'].replace('\r', ' ').replace(
                '\n', ' ').replace(',', ' ').strip().split()
        else:
            return []

    @async
    def getAutoFlows(self, id):
        return [flow for flow in self._releaseflow.values()
                if flow['auto_release'] and flow['project_id'] == id]

    def getNextFlowRelease(self, flow_id):
        raise NotImplementedError("TODO")

    def getLastFlowRelease(self, flow_id):
        raise NotImplementedError("TODO")

    # Targets

    def getFlowTargets(self, flow_id):
        raise NotImplementedError("TODO")

    def getServer(self, id):
        raise NotImplementedError("TODO")

    def updateTargetState(self, id, state):
        raise NotImplementedError("TODO")

    def updateTargetLog(self, id, log):
        raise NotImplementedError("TODO")

    def updateTargetBuild(self, id, build):
        raise NotImplementedError("TODO")

    def updateServerStatus(self, id, status):
        raise NotImplementedError("TODO")

    # Webhooks

    @async
    def getWebhooks(self, flow_id):
        return [deepcopy(webhook) for webhook in self._webhook.values()
                if webhook['flow_id'] == flow_id]

    @async
    def setWebhookResponse(self, id, response):
        self._webhook[id]['last_response'] = response
