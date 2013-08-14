Sideloader
==========

Turn github repos into deb files (using fpm) and put them into a repo. 

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


Whatever your build script does it must put the result into ./build/

Then connect it to your CI system somehow
