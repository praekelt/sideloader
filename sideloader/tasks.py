import os
import uuid
import shutil
import sys
import subprocess

import smtplib

from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.MIMEImage import MIMEImage

from django.conf import settings
from celery import task
from sideloader import models

@task()
def sendEmail(to, content, subject):
    start = '<html><head></head><body style="font-family:arial,sans-serif;">'
    end = '</body></html>'

    cont = MIMEText(start+content+end, 'html')

    msg = MIMEMultipart('related')

    msg['Subject'] = subject
    msg['From'] = settings.SIDELOADER_FROM
    msg['To'] = to
    msg.attach(cont)

    s = smtplib.SMTP()
    s.connect()
    s.sendmail(msg['From'], msg['To'], msg.as_string())
    s.close()

@task()
def sendSignEmail(to, name, release, h):
    cont = 'A build release has been requested for "%s" to release stream "%s".<br/><br/>' % (name, release)
    cont += "You are listed as a contact to approve this release. "
    cont += "If you would like to do so please click the link below,"
    cont += " if you do not agree then simply ignore this mail.<br/><br/>"

    cont += "http://%s/api/rap/%s" % (settings.SIDELOADER_DOMAIN, h)

    sendEmail(to, cont, '%s release approval - action required' % name)

@task()
def sendScheduleNotification(to, release):
    cont = 'A %s release for %s has been scheduled for %s UTC' % (
        release.flow.name,
        release.flow.project.name,
        release.scheduled
    )

    sendEmail(to, cont, '%s %s release scheduled - %s UTC' % (
        release.flow.project.name,
        release.flow.name,
        release.scheduled
    ))

@task()
def doRelease(build, flow, scheduled=None):
    release = models.Release.objects.create(
        flow=flow,
        build=build,
        waiting=True,
        scheduled=scheduled
    )

    release.save()

    if scheduled:
        for name, email in settings.ADMINS:
            sendScheduleNotification.delay(email, release)

    if flow.require_signoff:
        # Create a signoff release
        # Turn whatever junk is in the email text into a list
        users = flow.email_list()

        for email in users:
            so = models.ReleaseSignoff.objects.create(
                release=release,
                signature=email,
                idhash=uuid.uuid1().get_hex(),
                signed=False
            )
            so.save()
            sendSignEmail.delay(email, build.project.name, flow.name, so.idhash)

@task()
def runRelease(release):
    if release.waiting:
        flow = release.flow
        next_release = flow.next_release()
        last_release = flow.last_release()
        if next_release:
            if release.release_date < next_release.release_date:
                #print "Stale %s" % repr(release)
                release.delete()

        if last_release:
            if release.release_date < last_release.release_date:
                #print "Stale %s" % repr(release)
                release.delete()

        if release.check_schedule() and release.check_signoff():
            #print "Released %s" % repr(release)
            release.waiting = False
            release.save()
            push_cmd = release.flow.stream.push_command
            os.system(push_cmd % os.path.join(
                '/workspace/packages/', release.build.build_file))

@task()
def checkReleases():
    releases = models.Release.objects.filter(waiting=True)
    for release in releases:
        # Check releases synchronously 
        runRelease(release)

@task()
def build(build, giturl, branch):
    # Use subprocess to execute a build, update the db with results
    local = os.path.dirname(sys.argv[0])
    buildpack = os.path.join(local, 'bin/build_package')

    # Figure out some directory paths
    chunks = giturl.split(':')[1].split('/')
    repo = chunks[-1][:-4]
    workspace = os.path.join('/workspace', repo)
    package = os.path.join(workspace, 'package')
    packages = '/workspace/packages'

    #print "Executing build %s %s" % (giturl, branch)

    args = [buildpack, '--branch', branch]

    if build.project.deploy_file:
        args.extend(['--deploy-file', build.project.deploy_file])

    if build.project.release_stream:
        args.extend(['--push', build.project.release_stream.push_command])

    args.append(giturl)

    builder = subprocess.Popen(args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, cwd=local, bufsize=1)

    for line in iter(builder.stdout.readline, b''):
        build.log += line
        build.save()

    builder.communicate()


    if builder.returncode != 0:
        build.state = 2
    else:
        build.state = 1
        if not os.path.exists(packages):
            os.makedirs(packages)

        debs = [i for i in os.listdir(package) if i[-4:]=='.deb']
        deb = debs[0]
        build.build_file = deb

        # Relocate the package to our archive
        shutil.move(os.path.join(package, deb), os.path.join(packages, deb))

        # Find any auto-release streams
        flows = build.project.releaseflow_set.filter(auto_release=True)
        if flows:
            build.save()
            for flow in flows:
                doRelease.delay(build, flow)

    build.save()
