from celery import task
import os
import sys
import subprocess


@task()
def build(build, giturl, branch):
    # Use subprocess to execute a build, update the db with results
    local = os.path.dirname(sys.argv[0])
    buildpack = os.path.join(local, 'bin/build_package')

    print "Executing build %s %s" % (giturl, branch)

    args = [buildpack, '--branch', branch]

    if build.project.deploy_file:
        args.extend(['--deploy-file', build.project.deploy_file])

    if build.project.release_stream:
        args.extend(['--push', build.project.release_stream.push_command])

    args.append(giturl)

    builder = subprocess.Popen(args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, cwd=local)

    while builder.poll() is None:
        output = builder.stdout.readline()
        build.log += output
        build.save()

    stdoutdata, stderrdata = builder.communicate()
    build.log += stdoutdata

    if builder.returncode != 0:
        build.state = 2
    else:
        build.state = 1

    build.save()
