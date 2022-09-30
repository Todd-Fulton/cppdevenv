#!/usr/bin/env python

r"""Make custom configurations of c/c++ projects easier.

WIP:
    Immediate use is for building custom toolchains within docker images.

Future goals is to create a package manager for building docker images.
Reasons to use this over internal package managers (e.g. apt, apk, yum):
    - Docker images should not have package managers installed. There are
    very few reasons to have a package manager installed in a docker image,
    such as making development easier with respect to installing
    new dependencies on the fly, however this should be a rare
    occurance.
    - Dependencies can be tailored to specific hardware.
    - Often distrobutions are opinionated with their packages'
    configurations. You either accept that, or build from source anyways.
    - While most projects follow certain conventions, there are a handful
    of such conventions that need to be handled differently, e.g. make vs
    cmake projects. We can configure and script each build independently.
    - Some projects have many configuration options that bring in new
    dependencies, we can handle that, document what each configuration
    does, and handle conflicting configurations between projects.
    - All the reasons people use Aur on Arch Linux distrobutions.

Example usage:
```sh
python build.py --toolchain=$CUSTOM_TOOLCHAIN \
        build_image --packages=package1,package2,packageY
```

The tool will use configuration files stored in json to build each
package. In the previous example, packageY depends on packageX, packageX
will be built as well.

For development environments...

```sh
python build.py --toolchain=$CUSTOM_TOOLCHAIN \
        build_dev_image --packages=package1,package2,packageY
```

The tool will leave the toolchain and headers installed for development.

Using a configuration file for complicated or lengthy requirements...

```sh
python build.py build_[dev_]image --config=CONFIG.json
```

Building a custom toolchain...
```sh
python build.py build_toolchain --config=CONFIG.json
```
"""


import json

"""
TODO:
    Will need a cycle detector. Will need a way to handle cycles, or stop,
    for example, gcc and glibc often depend on eachother, but we can handle
    that.
"""


class configuration_option:
    """Information about a configuration option.

    A configuration option has:
        - a name
        - a value type
        - a value
        - valid values
        - dependencies (optional)
        - conflicts (optional)
        - a string representation
        - documentation

    To enable options, a project depends on the option, and its dependencies.
        A -> x -> y
        |--> w -> B -> i -> j -> C -> m
        ...
    """

    pass


class project:
    """Interface for project types."""

    __repository = {}

    @classmethod
    def validate_config(cls, config):
        """Validate the configuration."""
        return None

    def __init__(self, jsonfile):
        """Initialize project."""
        pconfig = json.load(jsonfile)
        if err := type(self).validate_config(pconfig):
            # TODO: report error, then exit
            print(f"Invalid config:\n{err}")
            exit(-100)

        self._ptype = self._repository[pconfig["project_type"]]
        self.name = pconfig["name"]
        self.version = pconfig["version"]
        self.maintainers = pconfig["maintainers"]
        self.conflicts_with = pconfig["conflicts_with"]
        self._deps = pconfig["deps"]

        @property
        def _repository(self):
            return type(self).__repository

        @property
        def options(self):
            """List of `configuration_option`s."""
            pass

        @property
        def dependencies(self) -> set:
            """Set of build, runtime, and development dependecies.

            Use depth first search to build all dependencies in proper order.
            """
            return (
                self.build_dependencies
                | self.runtime_dependencies
                | self.development_dependencies
            )

        @property
        def build_dependencies(self) -> set:
            """Set of build dependencies.

            Needed to build this project, but not needed to run or develop
            against this project.
            """

        # TODO: calculate dependencies using options
        pass

        @property
        def runtime_dependencies(self) -> set:
            """Set of runtime dependencies.

            Needed to use this project in production.
            """

        # TODO: calculate dependencies using options
        pass

        @property
        def development_dependencies(self) -> set:
            """Set of development dependencies.

            Needed to develop against this project.
            """
            # TODO: calculate dependencies using options
            pass

        @property
        def fetch_commands(self):
            """Shell commands to fetch the sources for this project."""
            pass

        @property
        def configure_commands(self):
            """Shell commands to configure the project."""
            pass

        @property
        def build_commands(self):
            """Shell commands to build the project."""
            pass

        @property
        def install_commands(self):
            """Shell commands to install the project."""
            pass

        @property
        def clean_commands(self):
            """Shell commands to clean the project."""
            pass

        @property
        def as_json(self):
            """Project configuration as json."""
            pass


class make_project(project):
    """Represents a Make project, its configuration, and how to build it."""

    def __init__(self, jsonfile):
        super().__init__(jsonfile)

    class configure_options:
        def __init__(self, project_config={}):
            pass

        @classmethod
        def format_option(cls, typ, name, value=None):
            if value:
                return f"--{name}={value}"
            return f"--{name}"

        def __str__(self):
            return " ".join([str(v) for v in _confopt])


class Dockerfile:
    """Represents a Dockerfile.

    Once the project has been configured and composed, a Dockerfile can
    be created from it, composed into a string, and piped into `docker build`.
    """

    def __init__(self, proj):
        """Build up a docker file."""
        pass

    def __str__(self) -> str:
        """Compose the dockerfile into a string."""
        pass


if __name__ == "__main__":
    exit(0)

# vim: set syntax=python sw=4 :
