Sideloader
==========

Turn (python related) github repos into deb files (using fpm) and put them into a repo. 

Look at this repo to see how it deploys itself (meta!)

Create a .deploy.yaml file in your repository along the lines of ::

    buildscript: buildsomething.sh
    postinstall: syncdb.sh
    nginx:
     - mysite/mysite-nginx.conf
    supervisor:
     - mysite/mysite-supervisor.conf
    pip:
     - gunicorn
     - django
    dependencies:
     - nginx

Most of these are optional of course. Whatever your build script does it must put the result into ./build/

Then connect it to your CI system somehow
