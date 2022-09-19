
# get date in format YYYY-MM-DD for tags
variable "DATE" {
    default="${formatdate("YYYY-MM-DD", timestamp())}"
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

target "gcc-git-source" {
    dockerfile = "Dockerfile.gcc-git-source"
    contexts = {
        baseimg = "target:base-upgrade"
    }
    tags = ["cppdevenv-gcc-git-source:latest", "cppdevenv-gcc-git-source:${DATE}"]
}

target "gcc-git-build" {
    dockerfile = "Dockerfile.gcc-git-build"
    contexts = {
        gccsrc = "target:gcc-git-source"
    }
    tags = ["cppdevenv-gcc-git-build:latest", "cppdevenv-gcc-git-build:${DATE}"]
}


target "gcc-git" {
    dockerfile = "Dockerfile.gcc-git"
    args = {
        rebuild = "false"
        cpu_threads = 6
    }
    contexts = {
        gccbld = "target:gcc-git-build"
        baseimg = "target:base-upgrade"
    }
    tags = ["cppdevenv-gcc-git:latest", "cppdevenv-gcc-git:${DATE}"]
}