import subprocess
import os

SUCCESS = 0
FAILURE = 1


def static_vars(**kwargs):

    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func

    return decorate


class Ret(subprocess.CompletedProcess):

    def __init__(self, *args, **kwargs):
        if not args and not kwargs:
            self.args = []
            self.returncode = 0
            self.stderr = []
            self.stdout = []
        elif isinstance(args[0], int) and len(args) == 1 and not kwargs:
            self.args = []
            self.returncode = args[0]
            self.stderr = []
            self.stdout = []
        elif isinstance(args[0], subprocess.CompletedProcess):
            other = args[0]
            self.args = other.args
            self.returncode = other.returncode
            self.stderr = other.stderr
            self.stdout = other.stdout
            super().__init__(self, *(args[1:]), **kwargs)
        else:
            super().__init__(*args, **kwargs)

    def __bool__(self):
        """Return true if we contain an error."""
        return bool(self.returncode)


def run(cmd, *args, **kwargs) -> Ret:
    return Ret(subprocess.run([cmd, *args], **kwargs))


def cd(path):
    try:
        os.chdir(path)
        return Ret(args=[path], returncode=SUCCESS, stdout=None, stderr=None)
    except FileNotFoundError as err:
        return Ret(args=[path],
                   returncode=err.errno,
                   stdout=None,
                   stderr=err.strerror)


@static_vars(previous_paths=[])
def pushd(path):
    pushd.previous_paths.append(os.getcwd())
    return cd(path)


@static_vars(previous_paths=pushd.previous_paths)
def popd():
    if popd.previous_paths:
        return cd(popd.previous_paths.pop())
    else:
        return Ret(args=["popd"],
                   returncode=FAILURE,
                   stdout=None,
                   stderr="directory stack empty.")


def mkdir(path):
    return run("mkdir", "-p", f"{path}")


def path_exists(path):
    return run("/usr/bin/test", "-d", f"{path}")


def flock(path,
          cmd=[],
          /,
          *,
          conflict_exit_code=None,
          no_fork=None,
          exclusive=None,
          nonblock=None,
          close=None,
          shared=None,
          unlock=None,
          wait=None,
          **kwargs):
    options = []
    if conflict_exit_code is not None:
        options.append(f"-E {conflict_exit_code}")
    if no_fork:
        options.append("-n")
    if exclusive:
        options.append("-x")
    if nonblock:
        options.append("-n")
    if close:
        options.append("-o")
    if shared:
        options.append("-s")
    if unlock:
        options.append("-u")
    if wait:
        options.append(f"--timeout {wait}")
    return run("flock", *options, f"{path}", *cmd, **kwargs)


def flock_try(path, cmd, /, **kwargs):
    return flock(path, cmd, kwargs=kwargs | {"nonblock": True}, **kwargs)
