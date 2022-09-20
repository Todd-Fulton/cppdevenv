
# get date in format YYYY-MM-DD for tags
variable "DATE" {
    default="${formatdate("YYYY-MM-DD", timestamp())}"
}

variable CFLAGS {
   default=""
}

variable CXXFLAGS {
  default=""
}

variable CPU_THREADS {
  default = 4
}

variable GIT_PULL {
  default = false
}

target "base" {
    dockerfile = "Dockerfile.base"
    tags = ["cppdevenv-base:latest", "cppdevenv-base:${DATE}"]
}

target "base-upgrade" {
    dockerfile = "Dockerfile.base_upgrade"
    contexts = {
        baseimg = "target:base"
    }
    tags = ["cppdevenv-base-upgrade:latest", "cppdevenv-base-upgrade:${DATE}"]
}

target "binutils-git-source" {
    dockerfile = "Dockerfile.binutils-git-source"
    contexts = {
        baseimg = "target:base-upgrade"
    }
    tags = ["cppdevenv-binutils-git-source:latest", "cppdevenv-binutils-git-source:${DATE}"]
}

target "gcc-git-source" {
    dockerfile = "Dockerfile.gcc-git-source"
    contexts = {
        baseimg = "target:base-upgrade"
    }
    tags = ["cppdevenv-gcc-git-source:latest", "cppdevenv-gcc-git-source:${DATE}"]
}

target "gcc-git" {
    dockerfile = "Dockerfile.gcc-git"
    args = {
        timestamp = "${timestamp()}"
        cpu_threads = "${CPU_THREADS}"
        cflags = "${CFLAGS}"
        cxxflags = "${CXXFLAGS}"
    }
    contexts = {
        gccsrc = "target:gcc-git-source"
        baseimg = "target:base-upgrade"
    }
    tags = ["cppdevenv-gcc-git:latest", "cppdevenv-gcc-git:${DATE}"]
}
