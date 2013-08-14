#!/usr/bin/python

import yaml
import os
import sys
import shutil
import json

class Sideloader:

    def __init__(self):
        self.sideloader_config = yaml.load(
            open('config.yaml')
        )

        self.install_location = self.sideloader_config['install_location']
        self.org = self.sideloader_config['git_org']

        # Handle args better, but confparse is a pain in the ass
        try:
            self.repo=sys.argv[1]
        except:
            print "Usage: build_package repo_name [branch]"
            sys.exit(1)

        try:
            self.branch=sys.argv[2]
        except:
            self.branch=self.sideloader_config.get('default_branch', 'develop')


        # It's all about the paths
        self.workspace = os.path.join('/workspace', self.repo)
        self.build = os.path.join(self.workspace, 'build')
        self.venv = os.path.join(self.install_location, 'python')
        self.easy_install = os.path.join(self.venv, 'bin/easy_install')
        self.pip = os.path.join(self.venv, 'bin/pip')
        self.python = os.path.join(self.venv, 'bin/python')

        self.deploy_yam = {}

        self.cachefile = os.path.join(os.getcwd(), 'build_cache')

        if os.path.exists(self.cachefile):
            self.build_cache = json.loads(open(self.cachefile).read())
        else:
            self.build_cache = {}

        print self.build_cache

    def saveCache(self):
        f = open(self.cachefile, 'wt')
        f.write(
            json.dumps(self.build_cache)
        )
        f.close()

    def getBuildNumber(self):
        if self.repo in self.build_cache:
            build = int(self.build_cache[self.repo]) + 1
        else:
            build = 1

        self.build_cache[self.repo] = build
        return build


    def createWorkspace(self):
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)

        os.makedirs(self.workspace)
        os.makedirs(self.build)

        os.chdir(self.workspace)
        # Clone project
        os.system('git clone git@github.com:%s/%s.git' % (self.org, self.repo))

        # Checkout the desired branch
        os.chdir(os.path.join(self.workspace, self.repo))
        os.system('git checkout %s' % self.branch)

        # Create clean virtualenv
        if os.path.exists(self.venv):
            shutil.rmtree(self.venv)
        os.system('virtualenv --no-site-packages %s' % self.venv)

        self.deploy_yam = yaml.load(
            open(os.path.join(self.workspace, self.repo, '.deploy.yaml'))
        )

        # Install things
        for dep in self.deploy_yam.get('pip', []):
            print "Installing", dep
            os.system('PIP_DOWNLOAD_CACHE=~/.pip_cache %s install %s' % (self.pip, dep))

        os.chdir(self.workspace)

    def createPackage(self):
        package = os.path.join(self.workspace,'package')
        dest = os.path.join(package, self.install_location.lstrip('/'))
        supervisor = os.path.join(package, 'etc/supervisor/conf.d')
        nginx = os.path.join(package, 'etc/nginx/sites-enabled')

        print self.build, '->', dest

        try:
            os.makedirs(package)
            os.makedirs(dest)
            os.makedirs(supervisor)
            os.makedirs(nginx)
        except:
            pass

        # Clone build contents to install location
        for d in os.listdir(self.build):
            try:
                shutil.copytree(os.path.join(self.build, d), os.path.join(dest, d))
            except:
                print "Warning: Could not copy %s to package" % d

        # Create nginx configs
        for conf in self.deploy_yam.get('nginx', []):
            shutil.copy(os.path.join(self.build, conf), nginx)

        # Create supervisor configs
        for conf in self.deploy_yam.get('supervisor', []):
            shutil.copy(os.path.join(self.build, conf), supervisor)

        # Construct a post-install that also creates our virtualenv
        os.system('%s freeze > %s/%s-requirements.pip' % (self.pip, dest, self.repo))

        postinstall = os.path.join(self.workspace, 'postinstall.sh')
        postscript = open(postinstall, 'wt')
        postscript.write("#!/bin/bash\n")
        postscript.write("/usr/bin/virtualenv --no-site-packages %s\n" % self.venv)

        # Upgrade pip so we can use the package cache
        postscript.write("mkdir ~/.pip_cache\n")

        # re-install pip requirements
        postscript.write(
            "PIP_DOWNLOAD_CACHE=~/.pip_cache %s install -r %s\n" % (
                self.pip,
                os.path.join(self.install_location,
                    '%s-requirements.pip' % self.repo)
            )
        )

        # Merge the custom postinstall
        if self.deploy_yam.get('postinstall'):
            mypost = open(os.path.join(self.workspace, self.repo,
                self.deploy_yam.get('postinstall')))
            for ln in mypost:
                postscript.write(ln)

        postscript.close()
        os.chmod(postinstall, 0777)

        os.chdir(package)

        # Figure out a build version or use the one in .deploy.yaml
        build_num = self.getBuildNumber()
        version = self.deploy_yam.get('version', "0.%s" % build_num)

        # Build a dependency list
        depends = ""
        deplist = self.deploy_yam.get('dependencies',
            ['nginx', 'supervisor', 'python-virtualenv'])
        for dep in deplist:
            depends += ' -d "%s"' % dep

        os.system(
            'fpm -s dir -t deb -a amd64 -n %s -v %s --after-install %s --prefix / %s *' % (
                self.repo,
                version,
                postinstall,
                depends
            )
        )

        # Sign the package, if we care
        key = self.sideloader_config.get('gpg_key')
        if key:
            os.system('dpkg-sig -k %s --sign builder *.deb' % key)

        os.system(
            self.sideloader_config['drop_command'] % "*.deb"
        )

        # Save the cache at this point, because the packaging was successful
        self.saveCache()

    def buildProject(self):
        self.createWorkspace()
        print "Config:", self.deploy_yam
        os.system(self.deploy_yam['buildscript'])
        self.createPackage()

sideloader = Sideloader()
sideloader.buildProject()
