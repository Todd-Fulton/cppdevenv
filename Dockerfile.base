# syntax=docker/dockerfile:labs
FROM ubuntu:rolling

# install tools
RUN DEBIAN_FRONTEND=noninteractive \
    apt-get update

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get install --yes \
        git \
        gnupg \
        cmake \
        ninja-build \
        openssh-server \
        pkg-config

