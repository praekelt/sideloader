import os
import uuid
import shutil
import sys
import time
import datetime
import traceback

from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart

from sideloader import specter, slack, task_db
from skeleton import settings

from twisted.mail.smtp import sendmail
from twisted.internet import defer, reactor, protocol
from twisted.python import log
from twisted.enterprise import adbapi

from rhumba.plugin import RhumbaPlugin, fork
from rhumba import cron


class BuildProcess(protocol.ProcessProtocol):
    def __init__(self, id, prjid, idhash, db, callback):
        self.id = id
        self.project_id = prjid
        self.idhash = idhash
        self.db = db
        self.data = ""
        self.callback = callback

    def log(self, msg):
        log.msg('[%s] %s' % (self.id, msg))

    @defer.inlineCallbacks
    def outReceived(self, data):
        self.log(data)
        self.data = self.data + data

        yield self.db.updateBuildLog(self.id, self.data)

    @defer.inlineCallbacks
    def errReceived(self, data):
        self.log(data)
        self.data = self.data + data
        
        yield self.db.updateBuildLog(self.id, self.data)

    def processEnded(self, reason):
        reactor.callLater(0, self.callback, reason.value.exitCode,
            self.project_id, self.id, self.idhash)

class Plugin(RhumbaPlugin):
    def __init__(self, *a):
        RhumbaPlugin.__init__(self, *a)

        self.db = task_db.SideloaderDB()

        self.build_locks = {}

    @defer.inlineCallbacks
    def sendEmail(self, to, content, subject):
        start = '<html><head></head><body style="font-family:arial,sans-serif;">'
        end = '</body></html>'

        cont = MIMEText(start+content+end, 'html')

        msg = MIMEMultipart('related')

        msg['Subject'] = subject
        msg['From'] = settings.SIDELOADER_FROM
        msg['To'] = to
        msg.attach(cont)

        fr = settings.SIDELOADER_FROM.split('<')[-1].strip('>')

        yield sendmail('localhost', fr, msg['To'], msg.as_string())

    @defer.inlineCallbacks
    def sendNotification(self, message, project_id):
        (name, notify, slack_channel
            ) = yield self.db.getProjectNotificationSettings(project_id)
        
        if notify:
            self.log("Sending notification %s" % repr(message))
            if settings.SLACK_TOKEN:
                if slack_channel:
                    channel = slack_channel
                else:
                    channel=settings.SLACK_CHANNEL

                sc = slack.SlackClient(settings.SLACK_HOST,
                        settings.SLACK_TOKEN, channel)

                yield sc.message(name + ": " + message)


    def sendSignEmail(self, to, name, release, h):
        cont = 'A build release has been requested for "%s" to release stream "%s".<br/><br/>' % (name, release)
        cont += "You are listed as a contact to approve this release. "
        cont += "If you would like to do so please click the link below,"
        cont += " if you do not agree then simply ignore this mail.<br/><br/>"

        cont += "http://%s/api/rap/%s" % (settings.SIDELOADER_DOMAIN, h)

        return self.sendEmail(to, cont, '%s release approval - action required' % name)

    def sendScheduleNotification(self, to, release, flow, project):
        cont = 'A %s release for %s has been scheduled for %s UTC' % (
            flow['name'],
            project['name'],
            str(release['scheduled'])
        )

        return self.sendEmail(to, cont, '%s %s release scheduled - %s UTC' % (
            project['name'],
            flow['name'],
            release['scheduled']
        ))

    @defer.inlineCallbacks
    def sendBuildEmail(self, to, flow, release):
        build = yield self.db.getBuild(release['build_id'])
        cont = 'Release %s deployed to %s' % (
            build['build_file'], flow['name']
        )

        yield self.sendEmail(to, cont, cont)

    def call_release(self, params):
        return self.doRelease(
            params['build_id'],
            params['flow_id'],
            scheduled=params.get('schedule', None)
        )

    @defer.inlineCallbacks
    def doRelease(self, build_id, flow_id, scheduled=None):
        build = yield self.db.getBuild(build_id)
        flow = yield self.db.getFlow(flow_id)

        release_id = yield self.db.createRelease({
            'flow_id': flow_id,
            'build_id': build_id,
            'waiting': True,
            'scheduled': scheduled,
            'release_date': datetime.datetime.now(),
            'lock': False
        })

        if scheduled:
            release = yield self.db.getRelease(release_id)
            reactor.callLater(0, self.sendNotification,
                'Deployment scheduled for build %s at %s UTC to %s' % (
                    build['build_file'],
                    release['scheduled'],
                    flow['name']
                ), flow['project_id'])

            project = yield self.db.getProject(flow['project_id'])

            for name, email in settings.ADMINS:
                reactor.callLater(
                    0, self.sendScheduleNotification, email, release, flow, project)

        if flow['require_signoff']:
            # Create a signoff release
            # Turn whatever junk is in the email text into a list
            users = self.db.getFlowSignoffList(flow)

            project = yield self.db.getProject(flow['project_id'])

            for email in users:
                h = uuid.uuid1().get_hex()
                so_id = yield self.db.createReleaseSignoff({
                    'release_id': release_id,
                    'signature': email,
                    'idhash': h,
                    'signed': False
                })
                reactor.callLater(0, self.sendSignEmail,
                    email, project['name'], flow['name'], h)

    @defer.inlineCallbacks
    def pushTargets(self, release, flow):
        """
        Pushes a release using Specter
        """
        targets = yield self.db.getFlowTargets(flow['id'])
        project = yield self.db.getProject(flow['project_id'])

        for target in targets:
            server = yield self.db.getServer(target['server_id'])

            self.log("Deploing release %s to target %s" % (repr(release), server['name']))

            build = yield self.db.getBuild(release['build_id'])

            yield self.sendNotification('Deployment started for build %s -> %s' % (
                build['build_file'],
                server['name']
            ), project['id'])

            yield self.db.updateTargetState(target['id'], 1)

            sc = specter.SpecterClient(server['name'],
                    settings.SPECTER_AUTHCODE, settings.SPECTER_SECRET)

            if project['package_name']:
                package = project['package_name']
            else:
                url = project['github_url']
                package = url.split(':')[1].split('/')[-1][:-4]
            
            url = "%s/%s" % (
                settings.SIDELOADER_PACKAGEURL, 
                build['build_file']
            )

            stop, start, restart, puppet = "", "", "", ""

            try:
                if flow['service_pre_stop']:
                    stop = yield sc.get_all_stop()
                    stop = stop['stdout']

                result = yield sc.post_install({
                    'package': package,
                    'url': url
                })

                if ('error' in result) or (result.get('code',2) > 0) or (
                    result.get('stderr') and not result.get('stdout')):
                    # Errors during deployment
                    yield self.db.updateTargetState(target['id'], 3)

                    if 'error' in result:
                        yield self.db.updateTargetLog(target['id'], 
                            '\n'.join([stop, result['error']])
                        )
                    else:
                        yield self.db.updateTargetLog(target['id'], 
                            '\n'.join([
                                stop, result['stdout'], result['stderr']
                            ])
                        )

                    yield self.sendNotification('Deployment of build %s to %s failed!' % (
                        build['build_file'], server['name']
                    ), project['id'])

                    # Start services back up even on failure
                    if flow['service_pre_stop']:
                        start = yield sc.get_all_start()
                        start = start['stdout']
                else:
                    if flow['puppet_run']:
                        puppet = yield sc.get_puppet_run()
                        puppet = puppet['stdout']

                    if flow['service_pre_stop']:
                        start = yield sc.get_all_start()
                        start = start['stdout']
                    elif flow['service_restart']:
                        r1 = yield sc.get_all_stop()
                        r2 = yield sc.get_all_start()

                        restart = r1['stdout'] + r2['stdout']

                    yield self.db.updateTargetState(target['id'], 2)

                    yield self.db.updateTargetLog(target['id'],
                        '\n'.join([
                            stop, result['stdout'], result['stderr'], puppet, start, restart
                        ])
                    )

                    yield self.db.updateTargetBuild(target['id'], build['id'])

                    yield self.sendNotification('Deployment of build %s to %s complete' % (
                        build['build_file'],
                        server['name']
                    ), project['id'])

                yield self.db.updateServerStatus(server['id'], "Reachable")

            except Exception, e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                lines = traceback.format_exception(exc_type, exc_value, exc_traceback)

                yield self.db.updateTargetLog(target['id'], ''.join(lines))
                yield self.db.updateTargetState(target['id'], 3)

                yield self.db.updateServerStatus(server['id'], ''.join(lines))
               
                yield self.sendNotification('Deployment of build %s to %s failed!' % (
                    build['build_file'],
                    server['name']
                ), project['id'])


        yield self.db.updateReleaseState(release['id'])

    @defer.inlineCallbacks
    def streamRelease(self, release):
        build = yield self.db.getBuild(release['build_id'])
        flow = yield self.db.getFlow(release['flow_id'])
        stream = yield self.db.getReleaseStream(flow['stream_id'])

        yield self.sendNotification('Pushing build %s to %s stream' % (
            build['build_file'],
            stream['name']
        ), flow['project_id'])
        # Stream release

        push_cmd = stream['push_command']
        result = yield fork('/bin/sh', ('-c', push_cmd % os.path.join(
            '/workspace/packages/', build['build_file'])))

        yield self.db.updateReleaseState(release['id'])

    @defer.inlineCallbacks
    def cleanRelease(self, release):
        if release['waiting']:
            flow = yield self.db.getFlow(release['flow_id'])
            next_release = yield self.db.getNextFlowRelease(release['flow_id'])
            last_release = yield self.db.getLastFlowRelease(release['flow_id'])

            # Cleanup stale releases, deprecated by request date
            if next_release:
                if release['release_date'] < next_release['release_date']:
                    yield self.db.updateReleaseState(release['id'])

            if last_release:
                if release['release_date'] < last_release['release_date']:
                    yield self.db.updateReleaseState(release['id'])

    @defer.inlineCallbacks
    def call_runrelease(self, params):
        release = yield self.db.getRelease(params['release_id'])
        if release['waiting']:
            flow = yield self.db.getFlow(release['flow_id'])

            signoff = yield self.db.checkReleaseSignoff(release['id'], flow)

            if self.db.checkReleaseSchedule(release) and signoff:
                yield self.db.updateReleaseLocks(release['id'], True)

                addrs = self.db.getFlowNotifyList(flow)

                for to in addrs:
                    reactor.callLater(
                        0, self.sendBuildEmail, to, flow, release)

                # Release the build
                if flow['stream_mode'] == 0:
                    # Stream only
                    yield self.streamRelease(release)
                elif flow['stream_mode'] == 2:
                    # Stream and targets
                    yield self.streamRelease(release)
                    yield self.pushTargets(release, flow)
                else:
                    # Target only
                    yield self.pushTargets(release, flow)

                yield self.db.updateReleaseLocks(release['id'], False)

    @cron(secs="*/10")
    @defer.inlineCallbacks
    def call_checkreleases(self, params):
        releases = yield self.db.getReleases(waiting=True, lock=False)
        #self.log("Release queue is at %s" % len(releases))

        skip = []

        # Clean old releases
        for release in releases:
            yield self.cleanRelease(release)

            current = yield self.db.countReleases(
                release['flow_id'], waiting=True, lock=True)

            if current > 0:
                self.log("Skipping release %s on this run - %s in queue" % (
                    repr(release), current))
                skip.append(release['id'])

        # Lock all the release objects we now see
        r = yield self.db.getReleases(waiting=True, lock=False)
        releases = [i for i in r if i['id'] not in skip]

        #for release in releases:
        #    yield self.db.updateReleaseLocks(release['id'], True)

        for release in releases:
            self.log("Running release %s" % repr(release))
            # XXX Use client queue
            reactor.callLater(0, self.call_runrelease, 
                {'release_id': release['id']})

    @defer.inlineCallbacks
    def endBuild(self, code, project_id, build_id, idhash):
        workspace = os.path.join('/workspace', idhash)
        package = os.path.join(workspace, 'package')
        packages = '/workspace/packages'

        del self.build_locks[project_id]

        if code != 0:
            yield self.db.setBuildState(build_id, 2)

            reactor.callLater(0, self.sendNotification,
                'Build <http://%s/projects/build/view/%s|#%s> failed' % (
                    settings.SIDELOADER_DOMAIN, build_id, build_id
                ), project_id)

        else:
            if not os.path.exists(packages):
                os.makedirs(packages)

            debs = [i for i in os.listdir(package) if ((i[-4:]=='.deb') or (i[-4:]=='.rpm'))]

            if not debs:
                # We must have failed actually
                yield self.db.setBuildState(build_id, 2)

                reactor.callLater(0, self.sendNotification,
                    'Build <http://%s/projects/build/view/%s|#%s> failed' % (
                        settings.SIDELOADER_DOMAIN, build_id, build_id
                    ), project_id)

            else:
                deb = debs[0]

                yield self.db.setBuildState(build_id, 1)
                yield self.db.setBuildFile(build_id, deb)

                reactor.callLater(0, self.sendNotification,
                    'Build <http://%s/projects/build/view/%s|#%s> successful' % (
                        settings.SIDELOADER_DOMAIN, build_id, build_id
                    ),
                    project_id)

                # Relocate the package to our archive
                shutil.move(os.path.join(package, deb), os.path.join(packages, deb))

                # Find any auto-release streams
                # XXX Implement auto flow XXX
                flows = yield self.db.getAutoFlows(project_id)
                if flows:
                    for flow in flows:
                        reactor.callLater(0, self.doRelease, build_id, flow['id'])

    @defer.inlineCallbacks
    def call_build(self, params):
        """
        Use subprocess to execute a build, update the db with results along the way
        """
        
        build_id = params['build_id']

        build = yield self.db.getBuild(build_id)

        project_id = build['project_id']

        if project_id in self.build_locks:
            if (time.time() - self.build_locks[project_id]) < 1800:
                # Don't build
                defer.returnValue(None)

        self.build_locks[project_id] = time.time()

        project = yield self.db.getProject(project_id)
        
        chunks = project['github_url'].split(':')[1].split('/')
        repo = chunks[-1][:-4]

        # Get a build number
        build_num = yield self.db.getBuildNumber(repo)
        build_num += 1

        # Increment the project build number
        yield self.db.setBuildNumber(repo, build_num)

        local = self.config.get('localdir', 
            os.path.join(os.path.dirname(sys.argv[0]), '../..'))
        buildpack = os.path.join(local, 'bin/build_package')

        # Figure out some directory paths

        if settings.DEBUG:
            print "Executing build %s %s" % (project['github_url'], project['branch'])

        reactor.callLater(0, self.sendNotification, 
            'Build <http://%s/projects/build/view/%s|#%s> started for branch %s' % (
                settings.SIDELOADER_DOMAIN, build_id, build_id, project['branch']
            ), project_id)

        args = ['build_package', '--branch', project['branch'], '--build', str(build_num), '--id', project['idhash']]

        if project['deploy_file']:
            args.extend(['--deploy-file', project['deploy_file']])

        if project['package_name']:
            args.extend(['--name', project['package_name']])

        if project['build_script']:
            args.extend(['--build-script', project['build_script']])

        if project['postinstall_script']:
            args.extend(['--postinst-script', project['postinstall_script']])

        if project['package_manager']:
            args.extend(['--packman', project['package_manager']])

        if project['deploy_type']:
            args.extend(['--dtype', project['deploy_type']])

        args.append(project['github_url'])

        self.log('Spawning build %s: %s :: %s %s' % (build_id, local, buildpack, repr(args)))

        buildProcess = BuildProcess(build_id, project_id, project['idhash'], self.db, self.endBuild)

        proc = reactor.spawnProcess(buildProcess, buildpack, args=args, path=local, env=os.environ)

