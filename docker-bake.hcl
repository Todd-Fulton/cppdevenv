
# TODO: get date in format YYYY/MM/DD for tags

target "base" {
    dockerfile = "Dockerfile.base"
    tags = ["cppdevenv-base:latest"]
}

target "base-upgrade" {
    dockerfile = "Dockerfile.base_upgrade"
    contexts = {
        baseimg = "target:base"
    }
    tags = ["cppdevenv-base-upgrade:latest"]
}

target "gcc-git-source" {
    dockerfile = "Dockerfile.gcc-git-source"
    contexts = {
        baseimg = "target:base-upgrade"
    }
    tags = ["cppdevenv-gcc-git-source:latest"]
}

target "gcc-git-build" {
    dockerfile = "Dockerfile.gcc-git-build"
    contexts = {
        gccsrc = "target:gcc-git-source"
    }
    tags = ["cppdevenv-gcc-git-build:latest"]
}

target "gcc-git-rebuild" {
    dockerfile = "Dockerfile.gcc-git-rebuild"
    contexts = {
        gccbld = "target:gcc-git-build"
    }
    tags = ["cppdevenv-gcc-git-build:latest"]
}

target "gcc-git" {
    dockerfile = "Dockerfile.gcc-git"
    contexts = {
        gccbld = "docker-image://cppdevenv-gcc-git-build:latest"
        baseimg = "target:base-upgrade"
    }
    tags = ["cppdevenv-gcc-git:latest"]
}