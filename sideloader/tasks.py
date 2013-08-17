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

    builder = subprocess.Popen([buildpack, giturl, branch], 
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=local)
    builder.wait()

    build.log = builder.stdout.read()

    if builder.returncode != 0:
        build.state = 2
    else:
        build.state = 1
    
    build.save()
