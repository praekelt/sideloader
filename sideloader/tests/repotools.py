"""
Some tools for working with repos in tests.
"""

import os


class LocalRepo(object):
    def __init__(self, name, path, branch='develop'):
        self.name = name
        self.path = os.path.abspath(os.path.join(path, self.name + '.git'))
        os.makedirs(self.path)

        self.run_in_dir("git init")
        self.add_file("README", self.name)
        self.commit("Initial commit.")
        if branch:
            self.run_in_dir("git checkout -b develop")

    @property
    def url(self):
        return 'file://%s' % (self.path,)

    def rpath(self, path):
        return os.path.join(self.path, path)

    def run_in_dir(self, *cmds):
        cmds = ("cd %s" % (self.path,),) + cmds
        os.system('\n'.join(cmds))

    def mkdir(self, path):
        os.makedirs(self.rpath(path))

    def add_file(self, filepath, content, executable=False):
        with open(self.rpath(filepath), 'w') as f:
            f.write(content)
        cmds = []
        if executable:
            cmds.append("chmod ugo+x '%s'" % (filepath,))
        cmds.append("git add '%s'" % (filepath,))
        self.run_in_dir(*cmds)

    def commit(self, msg):
        self.run_in_dir("git commit -a -m '%s'" % (msg,))
