import os.path
import subprocess

import py.path
import pytest
import yaml


build_package_path = py.path.local(__file__).dirpath("../bin/build_package")


class Builder(object):
    """
    A fixture for managing sideloader build machinery.
    """
    def __init__(self, tmpdir):
        self.tmpdir = tmpdir
        self.rundir = tmpdir.join("rundir")
        self.bindir = tmpdir.join("bin")
        self.workspace_base = tmpdir.join("workspace")

    def workspace_dir(self, build_id):
        return self.workspace_base.join(build_id)

    def write_sideloader_config(self, config=None):
        """
        Write a sideloader build_package `config.yaml` file.

        :param dict config:
            The config data to write. If `None`, a default config is used.
        """
        if config is None:
            config = {
                "workspace_base": str(self.workspace_base),
                "install_location": "/opt",
                "default_branch": "master",
            }
        self.rundir.ensure(dir=True)
        self.rundir.join("config.yaml").write(yaml.dump(config))

    def create_repo(self, org, name):
        """
        Create a git repository for sideloader to build.

        :param str org: The (fake) github organisation/owner name.
        :param str name: The (fake) github project name.

        :returns: A py.path.local object pointing to the repository root.
        """
        repo_dir = self.tmpdir.join(org, name + ".git")
        repo_dir.ensure(dir=True)
        with repo_dir.as_cwd():
            os.system("git init")
        return repo_dir

    def _add_file(self, basedir, path, content, permissions=None):
        filepath = basedir.join(path)
        filepath.dirpath().ensure(dir=True)
        filepath.write(content)
        if permissions is not None:
            filepath.chmod(0o755)

    def create_branch(self, repo_dir, name, files=None):
        """
        Create a git branch containing some files.

        :param py.path.local repo_dir:
            The repository root returned by :meth:`create_repo`.
        :parm str name:
            The name of the branch.
        :param dict files:
            A dict mapping file path (relative to the repo root) to file
            content.
        """
        branch_files = {}
        if files:
            branch_files.update(files)
        with repo_dir.as_cwd():
            os.system("git checkout -b %s" % name)
            for filename, content in branch_files.items():
                self._add_file(repo_dir, filename, content)
                os.system("git add %s" % filename)
            os.system("git commit -m 'sideloader test'")

    def add_executable(self, name, content):
        self._add_file(self.bindir, name, content, 0o755)

    def run_build(self, *args):
        """
        Run a sideloader build.

        :param *args: Arguments to pass to the `build_package` invocation.

        :returns: A tuple of (returncode, output) for the `build_package` run.
        """
        self.add_executable("fpm", '#!/bin/bash\necho "[[$@]]"')
        output = ""
        self.rundir.ensure(dir=True)
        proc = subprocess.Popen(
            [str(build_package_path)] + list(args), cwd=str(self.rundir),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={"PATH": "%s:%s" % (self.bindir, os.environ["PATH"])})

        for line in iter(proc.stdout.readline, ""):
            output += line

        proc.communicate()

        return (proc.returncode, output)


@pytest.fixture
def builder(tmpdir):
    return Builder(tmpdir)


def test_helloworld_build(builder):
    """
    A trivial build succeeds and includes the build script's output.
    """
    builder.write_sideloader_config()
    repo_dir = builder.create_repo("org", "project")
    builder.create_branch(repo_dir, "master", files={
        ".deploy.yaml": yaml.dump({"buildscript": "scripts/build.sh"}),
        "scripts/build.sh": "echo 'hello from builder'",
    })
    returncode, output = builder.run_build("--id=id0", "file://%s" % repo_dir)
    assert returncode == 0
    assert "hello from builder" in output.splitlines()
