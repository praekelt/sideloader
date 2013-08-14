#!/usr/bin/python

import yaml
import os
import sys
import shutil


sideloader_config = yaml.load(
    open('config.yaml')
)

install_location = sideloader_config['install_location']
org = sideloader_config['git_org']

repo=sys.argv[1]

try:
    branch=sys.argv[2]
except:
    branch=sideloader_config.get('default_branch', 'develop')


# Path variables
workspace = os.path.join('/workspace', repo)
build = os.path.join(workspace, 'build')
venv = os.path.join(install_location, 'python')
easy_install = os.path.join(venv, 'bin/easy_install')
pip = os.path.join(venv, 'bin/pip')
python = os.path.join(venv, 'bin/python')

def createWorkspace():
    if os.path.exists(workspace):
        shutil.rmtree(workspace)

    os.makedirs(workspace)
    os.makedirs(build)

    os.chdir(workspace)
    # Clone project
    os.system('git clone git@github.com:%s/%s.git' % (org, repo))

    # Checkout the desired branch
    os.chdir(os.path.join(workspace, repo))
    os.system('git checkout %s' % branch)

    # Create clean virtualenv
    if os.path.exists(venv):
        shutil.rmtree(venv)
    os.system('virtualenv --no-site-packages %s' % venv)

    deploy_yam = yaml.load(
        open(os.path.join(workspace,repo,'.deploy.yaml'))
    )

    # Install things
    for dep in deploy_yam.get('pip', []):
        os.system('%s install %s' % (pip, dep))

    os.chdir(workspace)
    return deploy_yam

def createPackage(deploy_yam):
    package = os.path.join(workspace,'package')
    dest = os.path.join(package, install_location.lstrip('/'))
    supervisor = os.path.join(package, 'etc/supervisor/conf.d')
    nginx = os.path.join(package, 'etc/nginx/sites-enabled')

    print build, '->', dest

    try:
        os.makedirs(package)
        os.makedirs(dest)
        os.makedirs(supervisor)
        os.makedirs(nginx)
    except:
        pass

    # Clone build contents to install location
    for d in os.listdir(build):
        shutil.copytree(os.path.join(build, d), os.path.join(dest, d))

    # Create nginx configs
    for conf in deploy_yam.get('nginx', []):
        shutil.copy(os.path.join(build, conf), nginx)

    # Create supervisor configs
    for conf in deploy_yam.get('supervisor', []):
        shutil.copy(os.path.join(build, conf), supervisor)

    # Mirror the virtualenv
    #shutil.copytree(venv, os.path.join(dest, 'python'))
    os.system('%s freeze > %s/%s-requirements.pip' % (pip, dest, repo))

    postinstall = os.path.join(workspace, 'postinstall.sh')
    postscript = open(postinstall, 'wt')
    postscript.write("#!/bin/bash\n")
    postscript.write("/usr/bin/virtualenv --no-site-packages %s\n" % venv)
    # re-install pip requirements
    postscript.write(
        "%s install -r %s\n" % (
            pip, os.path.join(install_location, '%s-requirements.pip' % repo)
        )
    )

    if deploy_yam.get('postinstall'):
        mypost = open(os.path.join(workspace, repo, deploy_yam.get('postinstall')))
        for ln in mypost:
            postscript.write(ln)

    os.chdir(package)
    os.system(
        'fpm -s dir -t deb -n %s -v 0.4 --after-install %s --prefix / -d "nginx" -d "supervisor" -d "python-virtualenv" *' % (
            repo,
            postinstall
        )
    )

deploy_yam = createWorkspace()
print "Config:", deploy_yam
os.system(deploy_yam['buildscript'])
createPackage(deploy_yam)

