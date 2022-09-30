#!/usr/bin/env python3

import argparse
import os
import pathlib

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from .utils import path_exists, flock, flock_try, SUCCESS, mkdir
from .utils import run, pushd, popd, Ret

BUILD_DIR = pathlib.PurePath("/build")
SOURCE_DIR = pathlib.PurePath("/source")

GMP_NAME = "gmp"
MPFR_NAME = "mpfr"
MPC_NAME = "mpc"
ISL_NAME = "isl"

BINUTILS_NAME = "binutils"
GCC_NAME = "gcc"
GCC_STATIC = f"{GCC_NAME}-static"
GLIBC_NAME = "glibc"
MAKE_PROG = "make"

# TODO: Move to project specification
ARCH_SPECIFIC_CONFIGS = {
    GCC_NAME: {
        "x86": [],
        "x86_64": [],
        "aarch64": [],
        "ppc": [],  # TODO: lookup proper name for powerpc
        "ppc64": [],
        "arm": [],
        "armhf": [],
    },
    GCC_STATIC: {
        "x86": [],
        "x86_64": [],
        "aarch64": [],
        "ppc": [],  # TODO: lookup proper name for powerpc
        "ppc64": [],
        "arm": [],
        "armhf": [],
    },
    BINUTILS_NAME: {
        "x86": [],
        "x86_64": [],
        "aarch64": [],
        "ppc": [],
        "ppc64": [],
        "arm": [],
        "armhf": [],
    },
    GLIBC_NAME: {
        "x86": [],
        "x86_64": [],
        "aarch64": [],
        "ppc": [],
        "ppc64": [],
        "arm": [],
        "armhf": [],
    }
}

ARCH_TO_KERNEL_ARCH_MAP = {"aarch64": "arm64"}

# https://stackoverflow.com/a/279586


def map_arch_to_kernel_arch(arch) -> str:
    return ARCH_TO_KERNEL_ARCH_MAP.get(arch, arch)


def make_triplet(arch, org="weaver", os="linux-gnu"):
    return f"{arch}-{org}-{os}"


class Repo(ABC):
    _name: str

    def __init_subclass__(cls, /, name="", **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._name = name

    @classmethod
    @abstractmethod
    def initial_fetch(self):
        ...

    @classmethod
    @abstractmethod
    def update(cls):
        ...

    @classmethod
    @abstractmethod
    def fetch_version(cls, version, outdir):
        ...

    @classmethod
    @abstractmethod
    def _list_versions(cls):
        ...

    @classmethod
    @abstractmethod
    def _get_name(cls):
        return cls._name

    @property
    def versions(cls):
        return cls._list_versions()

    @property
    def name(cls):
        return cls._get_name()


class GitRepo(Repo):
    _name: str
    _remote_url: str
    _bare_path: pathlib.PurePath

    def __init_subclass__(cls,
                          /,
                          remote_url=None,
                          bare_path=None,
                          **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._remote_url = remote_url
        cls._bare_path = SOURCE_DIR / f"{cls.name}.git" \
            if bare_path is None else bare_path

    @classmethod
    def get_hash(cls, ref: str) -> str:
        repo = None
        if path_exists(cls.bare_path):
            repo = cls.bare_path
        else:
            repo = cls.remote_url
        out = run(["git", "ls-remote", f"{repo}", f"{ref}"])
        out.check_returncode()
        return out.stdout.split(" ")[0]

    @classmethod
    def clone(cls, *args, output: pathlib.PurePath = None, **kwargs) -> Ret:
        output = (cls.remote_url.split('/')[-1].removesuffix(".git")
                  if output is None else output)
        cmd = [
            "git", *args, *[f"--{k.replace('_', '-')}={v}" for k, v in kwargs],
            f"{cls.remote_url}", f"{output}"
        ]
        return mkdir(output) and flock_try(output, cmd, exlusive=True)

    @classmethod
    def shallow_clone(cls,
                      *args,
                      branch: str = "main",
                      output: pathlib.PurePath = None,
                      depth: int = 1) -> Ret:
        output = SOURCE_DIR / cls.name / branch if output is None else output
        return cls.clone("--single-branch",
                         *args,
                         branch=branch,
                         output=output,
                         depth=depth)

    @classmethod
    def fetch_version(cls, version):
        return cls.shallow_clone(branch=version)

    @classmethod
    def initial_fetch(cls):
        output = SOURCE_DIR / (cls.name + ".git")
        return cls.clone("--bare", output=output)

    @classmethod
    def update(cls):
        output = SOURCE_DIR / (cls.name + ".git")
        # check if directory exists
        # if not, then clone the bare repo
        # finally run: git fetch <remote_url>
        return ((run(["/usr/bin/test", "-d", f"{output}"])
                 or cls.initial_fetch()) and pushd(output)
                and flock(output, ["git", "fetch", f"{cls.remote_url}"],
                          exlusive=True) and popd())

    @classmethod
    def _list_versions(cls):
        """List all branches and tags in upstream repository.

    Can be overriden in subclasses if the project doesn't use
    branches and/or tags to store versions.
    """
        out = run("git", "ls-remote", "--tags", "--heads", f"{cls.bare_path}")
        out.stdout = sorted(list({
            tag.split('/')[-1].split('^')[0]
            for tag in out.stdout.split('\n')
        }),
                            reverse=True)
        return out

    @classmethod
    def _get_name(cls):
        return super()._get_name()

    @classmethod
    @abstractmethod
    def _get_bare_path(cls):
        return cls._bare_path

    @classmethod
    @abstractmethod
    def _get_remote_url(cls):
        return cls._remote_url

    @property
    def bare_path(cls):
        return cls._get_bare_path()

    @property
    def remote_url(cls):
        return cls._get_remote_url()


class TarRepo(Repo):
    pass


class HgRepo(Repo):
    pass


@dataclass
class OptionDependency:
    name: str


@dataclass
class PackageDependency:
    name: str
    options: List[str]


class Option:

    def __init__(
        self,
        name: str,
        /,
        long_name: str = None,
        value: Optional[Any] = None,
        type: Optional[type] = None,
        choices: Optional[List[Any]] = None,
        help: str = "",
        dependencies: Set[OptionDependency | PackageDependency] = set(),
        conflicts: Set[OptionDependency | PackageDependency] = set(),
        **kwargs,
    ):
        self._name = name
        self._long_name = long_name
        self._type = type
        self.choices: Optional[List[self._type]] = choices
        self._help = help
        self._dependencies = dependencies
        self._conflicts = conflicts
        self._value = value
        self.__dict__.update(kwargs)

    @property
    def name(self) -> str:
        return self._name

    @property
    def long_name(self) -> str:
        return self._long_name

    @property
    def type(self) -> type:
        return self._type

    @property
    def choices(self) -> Optional[List[Any]]:
        return self._choices

    @property
    def help(self) -> str:
        return self._help

    @property
    def dependencies(self) -> Set[OptionDependency | PackageDependency]:
        return self._dependencies

    @property
    def conflicts(self) -> Set[OptionDependency | PackageDependency]:
        return self._conflicts

    @property
    def value(self) -> Optional[Any]:
        return self._value

    def __hash__(self):
        return hash(self.name) if self.long_name is None else hash(
            self.long_name)


class Project(ABC):

    @abstractmethod
    def configure(self) -> Ret:
        raise NotImplementedError()

    @abstractmethod
    def build(self) -> Ret:
        raise NotImplementedError()

    @abstractmethod
    def install(self) -> Ret:
        raise NotImplementedError()

    @abstractmethod
    def test(self) -> Ret:
        raise NotImplementedError()

    @abstractmethod
    def test_dependencies(self) -> Ret:
        raise NotImplementedError()

    @abstractmethod
    def test_reverse_dependencies(self) -> Ret:
        raise NotImplementedError()

    @abstractmethod
    def _get_dependencies(self):
        raise NotImplementedError()

    @abstractmethod
    def _get_reverse_dependencies(self):
        raise NotImplementedError()

    @abstractmethod
    def _get_available_options(self):
        raise NotImplementedError()

    @abstractmethod
    def _get_current_config(self):
        raise NotImplementedError()

    @property
    def dependencies(self):
        return self._get_dependencies()

    @property
    def reverse_dependencies(self):
        return self._get_reverse_dependencies()


class MakeProject(Project, Repo):
    """Subclasses represent specific projects built using Make and friends."""
    _name: str
    _configuration_options: Set[Option]
    _default_config: Set[Option]
    _default_config_env: Dict[str, str]
    _default_make_args: List[str]
    _default_install_args: List[str]
    _dependencies: Set[PackageDependency]
    _conflicts: Set[PackageDependency]
    _repo: Repo

    def __init_subclass__(cls,
                          /,
                          default_config: list = [],
                          default_config_env: dict = {},
                          config_conflicts: list = [],
                          default_make_args: list = ["-j{cpus}"],
                          default_install_args: list = [],
                          **kwargs):
        super().__init_subclass__(**kwargs)
        cls._default_config = default_config
        cls._default_config_env = default_config_env
        cls._config_conflicts = config_conflicts
        cls._default_make_args = default_make_args
        cls._default_install_args = default_install_args

    def __init__(self,
                 source_dir: pathlib.PurePath,
                 build_dir: pathlib.PurePath,
                 cpus,
                 /,
                 config={},
                 config_env={},
                 make_targets=[],
                 make_env={},
                 make_args=[],
                 install_targets=["install"],
                 install_env={},
                 install_args=[],
                 **kwargs):
        type(self)._handle_conflicts(config)
        super().__init__(self, **kwargs)
        self.source_dir = source_dir
        self.build_dir = build_dir
        self.cpus = cpus
        self.config = config
        self.config_env = config_env
        self.make_targets = make_targets
        self.make_env = make_env
        self.make_args = make_args
        self.install_targets = install_targets
        self.install_env = install_env
        self.install_args = install_args

    @classmethod
    def _handle_conflicts(cls, configure_args):
        pass

    def configure(self):
        configure_cmd = [str(self.source_dir / "configure")]
        configure_args = [
            cfg.format(**self.__dict__)
            for cfg in (self.default_config() + self.config)
        ]
        configure_env = {
            k: v.format(**self.__dict__)
            for k, v in (self.default_config_env() | self.configure_env)
        }
        return (run(["mkdir", "-p", f"{self.build_dir}"])
                and run(["cd", f"{self.build_dir}"]) and self.pre_config()
                and run(configure_cmd + configure_args, env=configure_env)
                and self.post_config())

    def build(self):
        make_targets = [
            target.format(**self.__dict__) for target in self.make_targets
        ]
        make_env = {k: v.format(**self.__dict__) for k, v in self.make_env}
        make_args = [
            arg.format(**self.__dict__)
            for arg in self.default_make_args() + self.make_args
        ]
        return (run(["cd", f"{self.build_dir}"]) and self.pre_build()
                and run([MAKE_PROG] + make_args + make_targets, env=make_env)
                and self.post_build())

    def install(self):
        install_targets = [
            install_target.format(**self.__dict__)
            for install_target in self.install_targets
        ]
        install_args = [
            arg.format(**self.__dict__)
            for arg in self.default_install_args() + self.install_args
        ]
        return (run(["cd", f"{self.build_dir}"]) and self.pre_install()
                and run([MAKE_PROG] + install_args + install_targets)
                and self.post_install())

    def pre_config(self):
        return Ret(SUCCESS)

    def post_config(self):
        return Ret(SUCCESS)

    def pre_build(self):
        return Ret(SUCCESS)

    def post_build(self):
        return Ret(SUCCESS)

    def pre_install(self):
        return Ret(SUCCESS)

    def post_install(self):
        return Ret(SUCCESS)

    def clean(self):
        return Ret(SUCCESS)

    def run(self):
        return (self.config() and self.build() and self.install())

    @classmethod
    def _get_default_config(cls):
        ret = getattr(cls, "_default_config", [])
        for c in cls.__bases__:
            # TODO: use something else to allow overriding in subclasses
            ret += getattr(c, "default_config", lambda: [])()
        return ret

    @property
    def default_config(cls):
        return cls._get_default_config()

    @classmethod
    def _get_default_config_env(cls):
        ret = getattr(cls, "_default_config_env", {})
        for c in cls.__bases__:
            # use | ret to allow subclasses to override defaults
            ret = getattr(c, "_get_default_config_env", lambda: [])() | ret
        return ret

    @property
    def default_config_env(cls):
        return cls._get_default_config_env()

    @classmethod
    def default_make_args(cls):
        ret = getattr(cls, "_default_make_args", [])
        for c in cls.__bases__:
            # TODO: use something else to allow overriding in subclasses
            ret += getattr(c, "default_make_args", lambda: [])()
        return ret

    @classmethod
    def default_install_args(cls):
        ret = getattr(cls, "_default_install_args", [])
        for c in cls.__bases__:
            # TODO: use something else to allow overriding in subclasses
            ret += getattr(c, "default_install_args", lambda: [])()
        return ret


class ToolchainSupportLib(MakeProject):
    _default_config = ["--disable-static", "--prefix={prefix}"]
    _default_config_env = config_env = {
        "LDFLAGS": "-Wl,-rpath,${prefix}/lib",
        "CC": "{cc}",
        "CXX": "{cxx}",
        "LD": "{linker}"
    }

    def __init__(self,
                 name,
                 version,
                 prefix,
                 cpus,
                 cc="gcc",
                 cxx="g++",
                 linker="ld",
                 extra_config=[],
                 config_env={},
                 **kwargs):
        self.name = name
        self.version = version
        self.prefix = prefix
        self.cc = cc
        self.cxx = cxx
        self.linker = linker
        source_dir = SOURCE_DIR / self.name / self.version
        build_dir = BUILD_DIR / self.name / self.version
        super().__init__(source_dir,
                         build_dir,
                         cpus,
                         config=extra_config,
                         config_env=config_env,
                         **kwargs)


class LibGMP(ToolchainSupportLib):
    _default_config = ["--enable-cxx"]

    def __init__(self,
                 version,
                 prefix,
                 cpus,
                 extra_config=[],
                 config_env={},
                 **kwargs):
        super().__init__(GMP_NAME,
                         version,
                         prefix,
                         cpus,
                         extra_config=extra_config,
                         config_env=config_env,
                         **kwargs)


class LibMPFR(ToolchainSupportLib):
    _default_config = ["--with-gmp={prefix}"]

    def __init__(version, prefix, cpus, extra_config, config_env={}, **kwargs):
        super().__init__(MPFR_NAME,
                         version,
                         prefix,
                         cpus=cpus,
                         extra_config=extra_config,
                         configure_env=config_env,
                         **kwargs)


class LibMPC(ToolchainSupportLib):
    _default_config = ["--with-gmp={prefix}", "--with-mpfr={prefix}"]

    def __init__(self,
                 version,
                 prefix,
                 cpus,
                 extra_config=[],
                 config_env={},
                 **kwargs):
        super().__init__(MPC_NAME,
                         version,
                         prefix,
                         cpus,
                         extra_config=extra_config,
                         config_env=config_env,
                         **kwargs)


class LibISL(ToolchainSupportLib):
    _default_config = ["--with-gmp-prefix={prefix}"]

    def __init__(self,
                 version,
                 prefix,
                 cpus,
                 extra_config=[],
                 config_env={},
                 **kwargs):
        super().__init__(ISL_NAME,
                         version,
                         prefix,
                         cpus,
                         extra_config=extra_config,
                         config_env=config_env,
                         **kwargs)


class Binutils(MakeProject, GitRepo):
    _default_config = [
        "--prefix={prefix}", "--host={host_triplet}",
        "--build={build_triplet}", "--target={target_triplet}",
        "--with-sysroot=${sysroot}", "--with-gmp={prefix}",
        "--with-mpfr={prefix}", "--with-mpc={prefix}", "--with-isl={prefix}",
        "--disable-werror"
    ]
    _default_config_env = {
        "LDFLAGS": "-Wl,-rpath,{prefix}/lib",
        "CC": "{cc}",
        "CXX": "{cxx}",
        "LD": "{ld}"
    }

    def __init__(self,
                 version,
                 prefix,
                 host,
                 arch,
                 build,
                 cc,
                 cxx,
                 ld,
                 cpus,
                 config_env={},
                 extra_config=[],
                 **kwargs):
        self.prefix = prefix
        self.sysroot = prefix / "rootfs"
        self.target_triplet = make_triplet(arch)
        self.host_triplet = host
        self.build_triplet = build
        self.version = version
        self.cc = cc
        self.cxx = cxx
        self.ld = ld
        source_dir = SOURCE_DIR / BINUTILS_NAME / version
        build_dir = BUILD_DIR / BINUTILS_NAME / version
        super().__init__(source_dir,
                         build_dir,
                         cpus,
                         config=ARCH_SPECIFIC_CONFIGS[BINUTILS_NAME][arch] +
                         extra_config,
                         config_env=config_env,
                         **kwargs)


class KernelHeaders(MakeProject):
    _default_install_args = ["ARCH={arch}", "INSTALL_HDR_PATH={hdr_dir}"]

    def __init__(self, version: str, sysroot: pathlib.PurePath, arch: str,
                 **kwargs):
        source_dir = SOURCE_DIR / "linux" / version
        self.hdr_dir = sysroot / "usr"
        self.version = version
        self.arch = map_arch_to_kernel_arch(arch)
        super().__init__(source_dir,
                         source_dir,
                         cpus=1,
                         install_targets=["headers_install"],
                         install_targets=[],
                         **kwargs)

    def configure(self):
        return Ret(SUCCESS)

    def build(self):
        return Ret(SUCCESS)


class StaticGCC(MakeProject):
    _default_config = [
        "--prefix={prefix}", "--target={target_triplet}", "--build={build}",
        "--host={host}", "--with-sysroot={sysroot}",
        "--with-native-system-header-dir=/usr/include", "--without-headers",
        "--with-newlib", "--enable-default-pie", "--enable-default-ssp",
        "--disable-nls", "--disable-shared", "--disable-decimal-float",
        "--disable-threads", "--disable-libatomic", "--disable-libgomp",
        "--disable-libmudflap", "--disable-libssp", "--disable-libitm",
        "--disable-libsanitizer", "--disable-libquadmath",
        "--disable-libstdcxx", "--with-gmp={prefix}", "--with-mpfr={prefix}",
        "--with-mpc={prefix}", "--with-isl={prefix}", "--enable-languages=c",
        "--disable-werror"
    ]
    _default_config_env = {
        "LDFLAGS": "-Wl,-rpath,${prefix}/lib",
        "CC": "{cc}",
        "CXX": "{cxx}",
        "LD": "{linker}",
        "AR": "{ar}"
    }

    def __init__(self,
                 version,
                 prefix,
                 arch,
                 host,
                 build,
                 sysroot,
                 cc="gcc",
                 cxx="g++",
                 linker="ld",
                 ar="ar",
                 cpus=os.cpu_count(),
                 config_env={},
                 extra_config=[],
                 **kwargs) -> Ret:
        self.prefix = prefix
        self.version = version
        build_dir = BUILD_DIR / GCC_NAME / version
        source_dir = SOURCE_DIR / GCC_NAME / version
        self.target_triplet = make_triplet(arch)
        self.target_host = host
        self.target_build = build
        self.sysroot = sysroot
        self.cc = cc
        self.cxx = cxx
        self.linker = linker
        self.ar = ar
        super().__init__(
            source_dir,
            build_dir,
            cpus,
            config=ARCH_SPECIFIC_CONFIGS[GCC_STATIC][arch] + extra_config,
            config_env=config_env,
            make_targets=["all-gcc", "all-target-libgcc"],
            install_targets=["install-gcc", "install-target-libgcc"],
            **kwargs)


# make glibc
# see https://sourceware.org/bugzilla/show_bug.cgi?id=24183
# NOTE: need install_root=$SYSROOT so that libc.so linker script has
# correct paths.
class Glibc(MakeProject):
    _default_config_env = config_env = {
        "BUILD_CC": "{cc}",
        "CC": "{target_triplet}-gcc",
        "CXX": "{target_triplet}-g++",
        "AR": "{target_triplet}-ar",
        "RANLIB": "{triplet}-ranlib"
    }
    _default_config = [
        "--host={target_triplet}", "--build={host_triplet}", "--prefix=/usr",
        "--libdir=/usr/lib", "--with-headers={sysroot}/usr/include",
        "--with-binutils={prefix}/bin", "--enable-kernel={kernel_version}",
        "--enable-shared", "--disable-profile", "--disable-werror"
    ]
    _default_install_args = ["install_root={}"]

    def __init__(self,
                 version,
                 prefix,
                 arch,
                 host,
                 kernel_version,
                 cpus=os.cpu_count(),
                 extra_config=[],
                 config_env={},
                 **kwargs):
        build_dir = BUILD_DIR / GLIBC_NAME / version
        source_dir = SOURCE_DIR / GLIBC_NAME / version
        self.sysroot = prefix / "rootfs"
        self.target_triplet = make_triplet(arch)
        self.arch = arch
        self.host_triplet = host
        self.kernel_version = kernel_version
        super().__init__(source_dir,
                         build_dir,
                         cpus,
                         config=ARCH_SPECIFIC_CONFIGS[GLIBC_NAME][arch] +
                         extra_config,
                         config_env=config_env,
                         **kwargs)

    # && mkdir -p ${SYSROOT}/usr/lib \
    # && cd ${SYSROOT} \
    # && ( ( /usr/bin/test -d ${SYSROOT}/lib \
    #        && cp -a ${SYSROOT}/lib/* ${SYSROOT}/usr/lib64 \
    #        && rm -rf ${SYSROOT}/lib ) || true ) \
    # && ( ( /usr/bin/test -d ${SYSROOT}/lib64 \
    #        && cp -a ${SYSROOT}/lib64/* ${SYSROOT}/usr/lib64 \
    #        && rm -rf ${SYSROOT}/lib64 ) || true ) \
    # && ( ( /usr/bin/test -d ${SYSROOT}/usr/lib \
    #        && cp -a ${SYSROOT}/usr/lib/* ${SYSROOT}/usr/lib64 \
    #        && rm -rf ${SYSROOT}/usr/lib ) || true ) \
    # && ln -s usr/lib64 ${SYSROOT}/lib \
    # && ln -s usr/lib64 ${SYSROOT}/lib64 \
    # && ln -s lib64 ${SYSROOT}/usr/lib \
    # && cd ${PREFIX}/${target_triplet} \
    # && ( ( /usr/bin/test -d lib \
    #        && cp -a lib/* ${SYSROOT}/usr/lib64/ \
    #        && rm -r lib ) || true ) \
    # && ( ( /usr/bin/test -d lib \
    #        && cp -a lib64/* ${SYSROOT}/usr/lib64/ \
    #        && rm -r lib64 ) || true ) \
    # && ln -s ../rootfs/usr/lib64 lib \
    # && ln -s ../rootfs/usr/lib64 lib64 \
    # && cd / \
    # && rm -rf /glibc*


# make final compiler
class GCC(MakeProject):
    _default_config_env = {
        "AR": "ar",
        "LDFLAGS": "-Wl,-rpath,{prefix}/lib",
        "CC": "{cc}",
        "CXX": "{cxx}"
    }
    _default_config = [
        "--prefix=${prefix}", "--target=${target_triplet}",
        "--host=${host_triplet}", "--build=${build_triplet}",
        "--with-sysroot=${sysroot}",
        "--with-native-system-header-dir=/usr/include", "--enable-default-pie",
        "--enable-default-ssp", "--enable-languages=c,c++",
        "--enable-threads=posix", "--with-mpc=${prefix}",
        "--with-mpfr=${prefix}", "--with-gmp=${prefix}", "--with-isl=${prefix}"
    ]

    _default_make_args = [
        "AS_FOR_TARGET={target_triplet}-as",
        "LD_FOR_TARGET={target_triplet}-ld"
    ]

    def __init__(self,
                 version,
                 prefix,
                 arch,
                 host,
                 build,
                 sysroot,
                 cc="gcc",
                 cxx="g++",
                 ar="ar",
                 cpus=os.cpu_count(),
                 config_env={},
                 extra_config=[],
                 **kwargs):
        build_dir = BUILD_DIR / GCC_NAME / version
        source_dir = SOURCE_DIR / GCC_NAME / version
        self.prefix = prefix
        self.target_triplet = make_triplet(arch)
        self.host_triplet = host
        self.build_triplet = build
        self.arch = arch
        self.version = version
        self.sysroot = sysroot
        self.cc = cc
        self.cxx = cxx
        self.ar = ar
        super().__init__(source_dir,
                         build_dir,
                         cpus,
                         config=ARCH_SPECIFIC_CONFIGS[GCC_NAME][arch] +
                         extra_config,
                         config_env=config_env,
                         **kwargs)


# && cd ${PREFIX}/${target_triplet} \
# && cp -a include/* ${SYSROOT}/usr/include \
# && rm -rf include \
# && cd / \
# && rm -rf /gcc*

# # clean up
# RUN \
#   cd / \
#   && ln -s ${SYSROOT}/usr/include ${PREFIX}/${target_triplet}/include \
#   && ((find $PREFIX -not -type d -executable \
#         | xargs file \
#         | grep ELF \
#         | grep -v "LSB shared object" \
#         | grep -v "SYSV" \
#         | cut -d: -f1 \
#         | xargs strip 2>/dev/null) || true) \


def get_arg_parser():
    parser = argparse.ArgumentParser(description="Build a gnu toolchain")
    parser.add_argument("arch",
                        type=str,
                        help="The target architecture the toolchain will"
                        "compile code fore")

    parser.add_argument("cpus",
                        type=int,
                        help="the number of concurrent build tasks.")

    parser.add_argument("kernel-version",
                        type=str,
                        default="lts",
                        help="the minimum kernel version to target.")

    parser.add_argument("gmp-version",
                        type=str,
                        default="latest",
                        help="the version of libgmp to use.")

    parser.add_argument("mpfr-version",
                        type=str,
                        default="latest",
                        help="the version of libmpfr to use.")

    parser.add_argument("mpc-version",
                        type=str,
                        default="latest",
                        help="the version of libmpc to use.")

    parser.add_argument("isl-version",
                        type=str,
                        default="latest",
                        help="the version of libisl to use.")

    parser.add_argument("binutils-version",
                        type=str,
                        default="latest",
                        help="the version of binutils to build.")

    parser.add_argument("gcc-version",
                        type=str,
                        default="latest",
                        help="the version of gcc to build.")

    parser.add_argument("glibc-version",
                        type=str,
                        default="latest",
                        help="the version of glibc to build.")

    parser.add_argument("gcc-extra-config",
                        type=list,
                        help="extra configuration options for gcc.")

    parser.add_argument("binutils-extra-config",
                        type=list,
                        help="extra configuration options for binutils.")

    parser.add_argument("glibc-extra-config",
                        type=list,
                        help="extra configuration options for glibc.")
    return parser


def hash_build_config(*argv):
    from hashlib import sha256
    h = sha256()
    for arg in argv:
        h.update(str(arg))
    return h.digest()


def parse_args(argv):
    parser = get_arg_parser()
    args = parser.parse_args(argv)
    cfg = object()
    cfg.common_cfg = {
        "target": make_triplet(args.arch, args.org),
        "host": None,
        "build": None,
        "arch": args.arg,
        "cpus": args.cpus,
        "org": args.org
    }


def report_error(ret: Ret) -> None:
    print(ret.stderr)


def report_exception(ex: Exception) -> None:
    print(ex)


def clean_up(cfg):
    pass


def main(argv):
    err = 0
    try:
        cfg = parse_args(argv)
        if out := (GCC(**cfg.common_cfg, **cfg.libgmp_cfg).run()):
            err = out.returncode
            report_error(out)
    except Exception as err:
        report_exception(err)
    finally:
        clean_up(cfg)
    return err


if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
