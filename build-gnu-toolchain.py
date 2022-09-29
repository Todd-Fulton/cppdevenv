#!/usr/bin/env python3

import argparse
import os
from sre_constants import SUCCESS
import subprocess
import pathlib


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


ARCH_SPECIFIC_CONFIGS = {
  GCC_NAME : {
    "x86" : [],
    "x86_64" : [],
    "aarch64" : [],
    "ppc" : [], # TODO: lookup proper name for powerpc
    "ppc64" : [],
    "arm" : [],
    "armhf": [],
  },
  GCC_STATIC : {
    "x86" : [],
    "x86_64" : [],
    "aarch64" : [],
    "ppc" : [], # TODO: lookup proper name for powerpc
    "ppc64" : [],
    "arm" : [],
    "armhf": [],
  },
  BINUTILS_NAME : {
    "x86" : [],
    "x86_64" : [],
    "aarch64" : [],
    "ppc" : [],
    "ppc64" : [],
    "arm" : [],
    "armhf": [],
  },
  GLIBC_NAME : {
    "x86" : [],
    "x86_64" : [],
    "aarch64" : [],
    "ppc" : [],
    "ppc64" : [],
    "arm" : [],
    "armhf": [],
  }
}

ARCH_TO_KERNEL_ARCH_MAP = {
  "aarch64" : "arm64"
}


SUCCESS = 0
FAILURE = 1

# https://stackoverflow.com/a/279586
def static_vars(**kwargs):
    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func
    return decorate


def map_arch_to_kernel_arch(arch) -> str:
  return ARCH_TO_KERNEL_ARCH_MAP.get(arch, arch)


def make_triplet(arch, org = "weaver", os = "linux-gnu"):
  return f"{arch}-{org}-{os}"


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
    bool(self.returncode)


def run(cmd, *args, **kwargs) -> Ret:
  return Ret(subprocess.run([cmd, *args], **kwargs))


def cd(path):
  try:
    os.chdir(path)
    return Ret(args=[path], returncode=SUCCESS, stdout=None, stderr=None)
  except FileNotFoundError as err:
    return Ret(args=[path], returncode=err.errno, stdout=None, stderr=err.strerror)


@static_vars(previous_paths = [])
def pushd(path):
  pushd.previous_paths.append(os.getcwd())
  return cd(path)


@static_vars(previous_paths = pushd.previous_paths)
def popd():
  if popd.previous_paths:
    return cd(popd.previous_paths.pop())
  else:
    return Ret(args=["popd"], returncode=FAILURE, stdout=None, stderr="directory stack empty.")


def mkdir(path):
  return run("mkdir", "-p", f"{path}")


def path_exists(path):
  return run("/usr/bin/test", "-d", f"{path}")


def flock(path
          , cmd = []
          , conflict_exit_code=None
          , no_fork=None
          , exclusive=None
          , nonblock=None
          , close=None
          , shared=None
          , unlock=None
          , wait=None
          , verbose=None
          , version=None
          , **kwargs):
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
  if verbose:
    options.append("--verbose")
  if version:
    options.append("-V")
  return run(
      "flock", *options
      , f"{path}"
      , *cmd
      , **kwargs
    )


def flock_try(path, cmd, **kwargs):
  return flock(path
              , cmd
              , kwargs=kwargs | {"nonblock" : True}
              , **kwargs
    )


class GitRepo:
  def __init__(self, name : str, remote_url : str):
    self.name = name
    self.remote_url = remote_url
    self.bare_path = SOURCE_DIR / (self.name + ".git")

  def get_hash(self, ref: str) -> str:
    # TODO: Use local if available.
    repo = None
    if path_exists(self.bare_path):
      repo = self.bare_path
    else:
      repo = self.remote_url
    out = run(["git", "ls-remote", f"{repo}", f"{ref}"])
    out.check_returncode()
    return out.stdout.split(" ")[0]

  def clone(self
            , *args
            , output : pathlib.PurePath = None
            , **kwargs) -> Ret:
    output = (self.remote_url.split('/')[-1].removesuffix(".git")
              if output is None else output)
    cmd = ["git"
          , *args
          , *[f"--{k.replace('_', '-')}={v}" for k, v in kwargs]
          , f"{self.remote_url}"
          , f"{output}"
          ]
    return flock_try(output, cmd, exlusive=True)

  def shallow_clone(self
                    , *args 
                    , branch: str = "main"
                    , output  : pathlib.PurePath = None
                    , depth : int = 1) -> Ret:
    output = SOURCE_DIR / self.name / branch if output is None else output
    return self.clone("--single-branch"
                    , *args
                    , branch=branch
                    , output=output
                    , depth=depth)

  def clone_bare(self):
    output = SOURCE_DIR / (self.name + ".git")
    return self.clone("--bare", output=output)
  
  def update_bare(self):
    output = SOURCE_DIR / (self.name + ".git")
    # check if directory exists
    # if not, acquire a lock, then clone the bare repo
    # then run: git fetch <remote_url>
    return ((run (["/usr/bin/test", "-d", f"{output}"])
            or self.clone_bare())
          and run(["git", "fetch", f"{self.remote_url}"]))


class MakeProject:
  _default_config = []
  _default_config_env = {}
  _config_conflicts = {}
  _default_make_args = ["-j{cpus}"]
  _default_install_args = []

  def __init__(self
              , source_dir : pathlib.PurePath
              , build_dir : pathlib.PurePath
              , cpus
              , config={}
              , config_env={}
              , make_targets=[]
              , make_env={}
              , make_args=[]
              , install_targets=["install"]
              , install_env={}
              , install_args=[]
              , **kwargs):
    type(self)._handle_conflicts(config)
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
    self.__dict__.update(**kwargs)

  @classmethod
  def _handle_conflicts(cls, configure_args):
    pass

  def configure(self):
    configure_cmd = [ str(self.source_dir / "configure") ]
    configure_args = [
        cfg.format(**self.__dict__)
        for cfg
        in (self.default_config() + self.config)
      ]
    configure_env = {
        k : v.format(**self.__dict__)
        for k, v
        in (self.default_config_env() | configure_env)
      }
    return (run(["mkdir", "-p", f"{self.build_dir}"])
            and run(["cd", f"{self.build_dir}"])
            and self.pre_config()
            and run(configure_cmd + configure_args
                   , env=configure_env)
            and self.post_config())
  
  def build(self):
    make_targets = [
        target.format(**self.__dict__)
        for target
        in self.make_targets
      ]
    make_env = {
        k : v.format(**self.__dict__)
        for k, v
        in self.make_env
    }
    make_args = [
        arg.format(**self.__dict__)
        for arg
        in self.default_make_args() + self.make_args
    ]
    return (run(["cd", f"{self.build_dir}"])
            and self.pre_build()
            and run([MAKE_PROG] + make_args + make_targets
                    , env=make_env)
            and self.post_build())

  def install(self):
    install_targets = [
        install_target.format(**self.__dict__)
        for install_target
        in self.install_targets
    ]
    install_args = [
        arg.format(**self.__dict__)
        for arg
        in self.default_install_args() + self.install_args
    ]
    return (run(["cd", f"{self.build_dir}"])
            and self.pre_install()
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
  def default_config(cls):
    ret = getattr(cls, "_default_config", [])
    for c in cls.__bases__:
      # TODO: use something else to allow overriding in subclasses
      ret += getattr(c, "default_config", lambda: [])()
    return ret

  @classmethod
  def default_config_env(cls):
    ret = getattr(cls, "_default_config_env", [])
    for c in cls.__bases__:
      # use | ret to allow subclasses to override defaults
      ret = getattr(c, "default_config_env", lambda: [])() | ret
    return ret

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
        "LDFLAGS" : "-Wl,-rpath,${prefix}/lib"
        , "CC" : "{cc}"
        , "CXX" : "{cxx}"
        , "LD" : "{linker}"
      }
  def __init__(self
              , name
              , version
              , prefix
              , cpus
              , cc = "gcc"
              , cxx = "g++"
              , linker = "ld"
              , extra_config=[]
              , config_env={}
              , **kwargs):
    self.name = name
    self.version = version
    self.prefix = prefix
    self.cc = cc
    self.cxx = cxx
    self.linker = linker
    source_dir = SOURCE_DIR / self.name / self.version
    build_dir = BUILD_DIR / self.name / self.version
    super().__init__(source_dir
                    , build_dir
                    , cpus
                    , config=extra_config
                    , config_env=config_env
                    , **kwargs)


class LibGMP(ToolchainSupportLib):
  _default_config = ["--enable-cxx"]
  def __init__(self, version, prefix, cpus, extra_config=[], config_env={}, **kwargs):
    super().__init__(GMP_NAME
                    , version
                    , prefix
                    , cpus
                    , extra_config=extra_config
                    , config_env=config_env
                    , **kwargs)


class LibMPFR(ToolchainSupportLib):
  _default_config = ["--with-gmp={prefix}"]
  def __init__(version, prefix, cpus, extra_config, config_env={}, **kwargs):
    super().__init__(MPFR_NAME
                    , version
                    , prefix
                    , cpus=cpus
                    , extra_config=extra_config
                    , configure_env=config_env
                    , **kwargs)


class LibMPC(ToolchainSupportLib):
  _default_config = ["--with-gmp={prefix}", "--with-mpfr={prefix}"]
  def __init__(self
              , version
              , prefix
              , cpus
              , extra_config=[]
              , config_env={}
              , **kwargs):
    super().__init__(MPC_NAME
                    , version
                    , prefix
                    , cpus
                    , extra_config=extra_config
                    , config_env=config_env
                    , **kwargs)


class LibISL(ToolchainSupportLib):
  _default_config = ["--with-gmp-prefix={prefix}"]
  def __init__(self
              , version
              , prefix
              , cpus
              , extra_config=[]
              , config_env={}
              , **kwargs):
    super().__init__(ISL_NAME
                    , version
                    , prefix
                    , cpus
                    , extra_config=extra_config
                    , config_env=config_env
                    , **kwargs)


class Binutils(MakeProject):
  _default_config = [
    "--prefix={prefix}"
    , "--host={host_triplet}"
    , "--build={build_triplet}"
    , "--target={target_triplet}"
    , "--with-sysroot=${sysroot}"
    , "--with-gmp={prefix}"
    , "--with-mpfr={prefix}"
    , "--with-mpc={prefix}"
    , "--with-isl={prefix}"
    , "--disable-werror"
  ]
  _default_config_env = {
      "LDFLAGS" : "-Wl,-rpath,{prefix}/lib"
      , "CC" : "{cc}"
      , "CXX" : "{cxx}"
      , "LD" : "{ld}"
    }

  def __init__(self
              , version
              , prefix
              , host
              , arch
              , build
              , cc
              , cxx
              , ld
              , cpus
              , config_env={}
              , extra_config=[]
              , **kwargs):
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
    super().__init__(source_dir
                    , build_dir
                    , cpus
                    , config=ARCH_SPECIFIC_CONFIGS[BINUTILS_NAME][arch] + extra_config
                    , config_env=config_env
                    , **kwargs)


class KernelHeaders(MakeProject):
  _default_install_args = [
      "ARCH={arch}"
      , "INSTALL_HDR_PATH={hdr_dir}"
  ]
  def __init__(self, version : str
                    , sysroot : pathlib.PurePath
                    , arch : str
                    , **kwargs):
    source_dir = SOURCE_DIR / "linux" / version
    self.hdr_dir = sysroot / "usr"
    self.version = version
    self.arch = map_arch_to_kernel_arch(arch)
    super().__init__(
          source_dir
          , source_dir
          , cpus=1
          , install_targets=["headers_install"]
          , install_targets=[], **kwargs)
    
  def configure(self):
    return Ret(SUCCESS)

  def build(self):
    return Ret(SUCCESS)


class StaticGCC(MakeProject):
  _default_config = [
      "--prefix={prefix}"
      , "--target={target_triplet}"
      , "--build={build}"
      , "--host={host}"
      , "--with-sysroot={sysroot}"
      , "--with-native-system-header-dir=/usr/include"
      , "--without-headers"
      , "--with-newlib"
      , "--enable-default-pie"
      , "--enable-default-ssp"
      , "--disable-nls"
      , "--disable-shared"
      , "--disable-decimal-float"
      , "--disable-threads"
      , "--disable-libatomic"
      , "--disable-libgomp"
      , "--disable-libmudflap"
      , "--disable-libssp"
      , "--disable-libitm"
      , "--disable-libsanitizer"
      , "--disable-libquadmath"
      , "--disable-libstdcxx"
      , "--with-gmp={prefix}"
      , "--with-mpfr={prefix}"
      , "--with-mpc={prefix}"
      , "--with-isl={prefix}"
      , "--enable-languages=c"
      , "--disable-werror"
    ]
  _default_config_env = {
      "LDFLAGS" : "-Wl,-rpath,${prefix}/lib"
      , "CC" : "{cc}"
      , "CXX" : "{cxx}"
      , "LD" : "{linker}"
      , "AR" : "{ar}"
    }
  def __init__(self
              , version
              , prefix
              , arch
              , host
              , build
              , sysroot
              , cc="gcc"
              , cxx="g++"
              , linker="ld"
              , ar="ar"
              , cpus=os.cpu_count()
              , config_env={}
              , extra_config=[]
              , **kwargs) -> Ret:
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
    super().__init__(source_dir
                    , build_dir
                    , cpus
                    , config=ARCH_SPECIFIC_CONFIGS[GCC_STATIC][arch] + extra_config
                    , config_env=config_env
                    , make_targets=["all-gcc", "all-target-libgcc"]
                    , install_targets=["install-gcc", "install-target-libgcc"]
                    , **kwargs)

# make glibc
# see https://sourceware.org/bugzilla/show_bug.cgi?id=24183
# NOTE: need install_root=$SYSROOT so that libc.so linker script has
# correct paths.
class Glibc(MakeProject):
  _default_config_env = config_env = {
      "BUILD_CC" : "{cc}"
      , "CC" : "{target_triplet}-gcc"
      , "CXX" : "{target_triplet}-g++"
      , "AR" : "{target_triplet}-ar"
      , "RANLIB" : "{triplet}-ranlib"
    }
  _default_config = [
      "--host={target_triplet}"
      , "--build={host_triplet}"
      , "--prefix=/usr"
      , "--libdir=/usr/lib"
      , "--with-headers={sysroot}/usr/include"
      , "--with-binutils={prefix}/bin"
      , "--enable-kernel={kernel_version}"
      , "--enable-shared"
      , "--disable-profile"
      , "--disable-werror"
  ]
  _default_install_args=["install_root={}"]
  def __init__(self
              , version
              , prefix
              , arch
              , host
              , kernel_version
              , cpus = os.cpu_count()
              , extra_config=[]
              , config_env={}
              , **kwargs):
    build_dir = BUILD_DIR / GLIBC_NAME / version
    source_dir = SOURCE_DIR / GLIBC_NAME / version
    self.sysroot = prefix / "rootfs"
    self.target_triplet = make_triplet(arch)
    self.arch = arch
    self.host_triplet = host
    self.kernel_version = kernel_version
    super().__init__(source_dir
                    , build_dir
                    , cpus
                    , config=ARCH_SPECIFIC_CONFIGS[GLIBC_NAME][arch] + extra_config
                    , config_env=config_env
                    , **kwargs)
  
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

## make final compiler
class GCC(MakeProject):
  _default_config_env =  {
      "AR" : "ar"
      , "LDFLAGS" : "-Wl,-rpath,{prefix}/lib"
      , "CC" : "{cc}"
      , "CXX" : "{cxx}"
    }
  _default_config = [
        "--prefix=${prefix}"
        , "--target=${target_triplet}"
        , "--host=${host_triplet}"
        , "--build=${build_triplet}"
        , "--with-sysroot=${sysroot}"
        , "--with-native-system-header-dir=/usr/include"
        , "--enable-default-pie"
        , "--enable-default-ssp"
        , "--enable-languages=c,c++"
        , "--enable-threads=posix"
        , "--with-mpc=${prefix}"
        , "--with-mpfr=${prefix}"
        , "--with-gmp=${prefix}"
        , "--with-isl=${prefix}"
    ]

  _default_make_args = [
      "AS_FOR_TARGET={target_triplet}-as"
      , "LD_FOR_TARGET={target_triplet}-ld"
    ]
  def __init__(self
              , version
              , prefix
              , arch
              , host
              , build
              , sysroot
              , cc="gcc"
              , cxx="g++"
              , ar="ar"
              , cpus=os.cpu_count()
              , config_env={}
              , extra_config=[]
              , **kwargs):
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
    super().__init__(source_dir
                    , build_dir
                    , cpus
                    , config=ARCH_SPECIFIC_CONFIGS[GCC_NAME][arch] + extra_config
                    , config_env=config_env
                    , **kwargs
                    )
    
# && cd ${PREFIX}/${target_triplet} \
# && cp -a include/* ${SYSROOT}/usr/include \
# && rm -rf include \
# && cd / \
# && rm -rf /gcc*

## clean up
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
  parser.add_argument("arch"
                      , type=str
                      , help="The target architecture the toolchain will"
                      "compile code fore")

  parser.add_argument("cpus"
                      , type=int
                      , help="the number of concurrent build tasks.")

  parser.add_argument("kernel-version"
                      , type=str
                      , default="lts"
                      , help="the minimum kernel version to target.")

  parser.add_argument("gmp-version"
                      , type=str
                      , default="latest"
                      , help="the version of libgmp to use.")

  parser.add_argument("mpfr-version"
                      , type=str
                      , default="latest"
                      , help="the version of libmpfr to use.")

  parser.add_argument("mpc-version"
                      , type=str
                      , default="latest"
                      , help="the version of libmpc to use.")

  parser.add_argument("isl-version"
                      , type=str
                      , default="latest"
                      , help="the version of libisl to use.")

  parser.add_argument("binutils-version"
                      , type=str
                      , default="latest"
                      , help="the version of binutils to build.")

  parser.add_argument("gcc-version"
                      , type=str
                      , default="latest"
                      , help="the version of gcc to build.")

  parser.add_argument("glibc-version"
                      , type=str
                      , default="latest"
                      , help="the version of glibc to build.")

  parser.add_argument("gcc-extra-config"
                      , type=list
                      , help="extra configuration options for gcc.")

  parser.add_argument("binutils-extra-config"
                      , type=list
                      , help="extra configuration options for binutils.")

  parser.add_argument("glibc-extra-config"
                      , type=list
                      , help="extra configuration options for glibc.")
  return parser


def hash_build_config(*argv):
  from hashlib import sha256
  h = sha256()
  for arg in argv:
    h.update(str(arg))
  return h.digest()




def get_kernel_version(version : str) -> str:
  if version.lower() in ["master", "latest", "main"]:
    version = git_get_hash(SOURCE_DIR / "linux.git")
  else:
    #TODO: check tags and branches to verify that version exists
    version = version
  return version


def get_glibc_version(version) -> str:
  if version.lower() in ["master", "latest", "main"]:
    version = git_get_hash(GLIBC_NAME)
  return version


def get_gcc_version(version) -> str:
  if version.lower() in ["master", "latest", "main"]:
    version = git_get_hash(GCC_NAME)
  return version


def get_binutils_version(version) -> str:
  if version.lower() in ["master", "latest", "main"]:
    version = git_get_hash(BINUTILS_NAME)
  return version


def get_libgmp_version(version) -> str:
  pass


def get_libmpfr_version(version) -> str:
  pass


def get_libmpc_version(version) -> str:
  pass


def get_libisl_version(version) -> str:
  pass


def parse_args(argv):
  parser = get_arg_parser()
  args = parser.parse_args(argv)
  cfg = object()
  cfg.common_cfg = {
    "target" : make_triplet(args.arch, args.org)
    , "host" : None
    , "build" : None
    , "arch" : args.arg
    , "cpus" : args.cpus
    , "org" : args.org
  }
  cfg.libgmp_cfg = {
    "version" : get_libgmp_version(args.libgmp_version)
  }
  cfg.libmpfr_cfg = {
    "veresion" : get_libmpfr_version(args.libmpfr_version)
  }
  cfg.libmpc_cfg = {
    "version" : get_libmpc_version(args.libmpc_version)
  }
  cfg.libisl_cfg = {
    "version" : get_libisl_version(args.libisl_version)
  }
  cfg.kernel_hdr_cfg = {
    "version" : get_kernel_version(args.kernel_version)
  }
  cfg.glibc_cfg = {
    "version" : get_glibc_version(args.glibc_version)
  }
  cfg.gcc_cfg = {
    "version": get_gcc_version(args.gcc_version)
    , "extra_config" : args.gcc_extra_config
  }
  cfg.static_gcc_cfg = {
    "version": get_gcc_version(args.gcc_version)
  }
  cfg.binutils_cfg = {
    "version" : get_binutils_version(args.binutils_version)
    , "extra_config" : args.binutils_extra_config
  }
  cfg.common_cfg["build_hash"] = hash_build_config(cfg)
  cfg.common_cfg["prefix"] = pathlib.PurePath("/opt") / cfg.target / cfg.build_hash
  cfg.common_cfg["sysroot"] = cfg.prefix / "rootfs"
  return cfg


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
    if out := (build_libgmp(**cfg.common_cfg, **cfg.libgmp_cfg)
          and build_libmpfr(**cfg.common_cfg, **cfg.libmpc_cfg)
          and build_libmpc(**cfg.common_cfg, **cfg.libmpc_cfg)
          and build_libisl(**cfg.common_cfg, **cfg.libisl_cfg)
          and build_binutils(**cfg.common_cfg, **cfg.binutils_cfg)
          and build_static_gcc(**cfg.common_cfg, **cfg.static_gcc_cfg)
          and build_glibc(**cfg.common_cfg, **cfg.glibc_cfg)
          and build_gcc(**cfg.common_cfg, **cfg.gcc_cfg)):
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
