
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

variable TARGET_TRIPLET {
  default = "x86_64-linux-gnu"
}

variable KERNEL_ARCH {
  default = "x86_64"
}

target "base" {
    dockerfile = "Dockerfile.base"
    tags = ["cppdevenv-base:latest", "cppdevenv-base:${DATE}"]
}

target "gnu-toolchain" {
    dockerfile = "Dockerfile.gnu-toolchain"
    args = {
        target_triplet = "${TARGET_TRIPLET}"
        gcc_commit = "master"
        binutils_commit = "master"
        glibc_commit = "master"
        kernel_version = "6.0-rc6"
        kernel_arch = "${KERNEL_ARCH}"
        cpu_threads = "${CPU_THREADS}"
        cflags = "${CFLAGS}"
        cxxflags = "${CXXFLAGS}"
    }
    tags = ["cppdevenv-gnu-toolchain:${TARGET_TRIPLET}_latest", "cppdevenv-gnu-toolchain:${TARGET_TRIPLET}_${DATE}"]
}

