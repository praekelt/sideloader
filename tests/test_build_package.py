import os.path
import re
import subprocess
import sys

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

        :returns:
            A :class:`BuildResult` object containing the return code and output
            of the build.
        """
        self.add_executable("fpm", '#!/bin/bash\necho "[[$@]]"')
        output = ""
        self.rundir.ensure(dir=True)
        proc = subprocess.Popen(
            ["python", str(build_package_path)] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={"PATH": "%s:%s" % (self.bindir, os.environ["PATH"])},
            cwd=str(self.rundir))

        for line in iter(proc.stdout.readline, ""):
            output += line
            sys.stdout.write(line)

        proc.communicate()

        return BuildResult(proc.returncode, output)


class BuildResult(object):
    def __init__(self, code, output):
        self.code = code
        self.output = output
        self.output_lines = output.splitlines()

    def contains_line(self, line):
        return line in self.output_lines

    def contains_regex(self, line_regex):
        """
        Returns `True` if there is an output line that matches the given regex.

        :param line_regex: May be a regex object or a string.
        """
        if isinstance(line_regex, basestring):
            line_regex = re.compile(line_regex)
        for line in self.output_lines:
            if line_regex.match(line):
                return True
        return False


@pytest.fixture
def builder(tmpdir):
    return Builder(tmpdir)


def test_helloworld_build(builder):
    """
    A trivial build succeeds and includes the build script's output.

    The default build type is "virtualenv", so the generated postinstall script
    containins venv setup.
    """
    builder.write_sideloader_config()
    repo_dir = builder.create_repo("org", "project")
    builder.create_branch(repo_dir, "master", files={
        ".deploy.yaml": yaml.dump({"buildscript": "scripts/build.sh"}),
        "scripts/build.sh": "echo 'hello from builder'",
    })
    build_result = builder.run_build("--id=id0", "file://%s" % repo_dir)
    assert build_result.code == 0
    assert build_result.contains_line("hello from builder")

    workspace_dir = builder.workspace_dir("id0")
    postinstall = workspace_dir.join("postinstall.sh").read().splitlines()

    # Standard variables
    assert "INSTALLDIR=/opt" in postinstall
    assert "REPO=project" in postinstall
    assert "NAME=project" in postinstall
    assert "BRANCH=master" in postinstall

    # Extra stuff for "virtualenv" build type
    assert "/usr/bin/virtualenv /opt/python" in postinstall
    assert "VENV=/opt/python" in postinstall


def test_broken_build_succeeds(builder):
    """
    A build broken in various ways still succeeds if configured to do so.
    """
    builder.write_sideloader_config()
    repo_dir = builder.create_repo("org", "project")
    builder.create_branch(repo_dir, "master", files={
        ".deploy.yaml": yaml.dump({
            "buildscript": "scripts/build.sh",
            "allow_broken_build": True,
        }),
        "scripts/build.sh": "\n".join([
            "echo 'copy fail' > $BUILDDIR/copyfail.txt",
            "exit 1",
        ]),
    })
    build_result = builder.run_build("--id=id0", "file://%s" % repo_dir)
    assert build_result.code == 0

    workspace_dir = builder.workspace_dir("id0")
    build_copyfail = workspace_dir.join("build", "copyfail.txt")
    package_copyfail = workspace_dir.join("package", "opt", "copyfail.txt")
    assert build_copyfail.read() == "copy fail\n"
    assert package_copyfail.check(exists=False)

    assert build_result.contains_regex(
        r"\[.*\] Build failure overridden: Build script exited with code 1$")
    assert build_result.contains_regex(
        r"\[.*\] Build failure overridden: Error copying files to package$")


def test_build_with_bad_branch_fails(builder):
    """
    A build for a branch that doesn't exist fails.
    """
    builder.write_sideloader_config()
    repo_dir = builder.create_repo("org", "project")
    builder.create_branch(repo_dir, "master", files={
        ".deploy.yaml": yaml.dump({"buildscript": "scripts/build.sh"}),
        "scripts/build.sh": "echo 'hello from builder'",
    })
    build_result = builder.run_build(
        "--id=id0", "file://%s" % repo_dir, "--branch", "stormdamage")
    assert build_result.code == 1

    assert build_result.contains_line(
        "error: pathspec 'stormdamage' did not match"
        " any file(s) known to git.")
    assert build_result.contains_regex(
        r"\[.*\] Build failed: Can't switch to branch$")


def test_build_with_bad_file_fails(builder):
    """
    A build with files that can't be copied into the package fails.

    We don't allow top-level files in packages, only directories.
    """
    builder.write_sideloader_config()
    repo_dir = builder.create_repo("org", "project")
    builder.create_branch(repo_dir, "master", files={
        ".deploy.yaml": yaml.dump({"buildscript": "scripts/build.sh"}),
        "scripts/build.sh": "echo 'copy fail' > $BUILDDIR/copyfail.txt",
    })
    build_result = builder.run_build("--id=id0", "file://%s" % repo_dir)
    assert build_result.code == 1

    workspace_dir = builder.workspace_dir("id0")
    copy_warning = "Warning: Could not copy %s to package: %s %s" % (
        "copyfail.txt",
        "<type 'exceptions.OSError'> [Errno 20] Not a directory:",
        "'%s'" % workspace_dir.join("build", "copyfail.txt"))
    assert build_result.contains_line(copy_warning)
    assert build_result.contains_regex(
        r"\[.*\] Build failed: Error copying files to package$")


def test_build_with_script_error_fails(builder):
    """
    A nonzero exit code from the build script causes the build to fail.
    """
    builder.write_sideloader_config()
    repo_dir = builder.create_repo("org", "project")
    builder.create_branch(repo_dir, "master", files={
        ".deploy.yaml": yaml.dump({"buildscript": "scripts/build.sh"}),
        "scripts/build.sh": "echo 'hello from builder'; exit 1",
    })
    build_result = builder.run_build("--id=id0", "file://%s" % repo_dir)
    assert build_result.code == 1
    assert build_result.contains_line("hello from builder")
    assert build_result.contains_regex(
        r"\[.*\] Build failed: Build script exited with code 1$")


def test_venv_path_config(builder):
    """
    The installed virtualenv can be configured to live in a different place.
    """
    builder.write_sideloader_config()
    repo_dir = builder.create_repo("org", "project")
    builder.create_branch(repo_dir, "master", files={
        ".deploy.yaml": yaml.dump({
            "buildscript": "scripts/build.sh",
            "virtualenv_prefix": "plane",
        }),
        "scripts/build.sh": "echo 'hello from builder'",
    })
    build_result = builder.run_build("--id=id0", "file://%s" % repo_dir)
    assert build_result.code == 0
    assert build_result.contains_line("hello from builder")

    workspace_dir = builder.workspace_dir("id0")
    postinstall = workspace_dir.join("postinstall.sh").read().splitlines()

    # Standard variables
    assert "INSTALLDIR=/opt" in postinstall
    assert "REPO=project" in postinstall
    assert "NAME=project" in postinstall
    assert "BRANCH=master" in postinstall

    # Extra stuff for "virtualenv" build type
    assert "/usr/bin/virtualenv /opt/plane-python" in postinstall
    assert "VENV=/opt/plane-python" in postinstall
