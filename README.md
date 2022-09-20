A set of Dockerfiles and a bake script for generating a few toolchains and build environments
for bleeding-edge C++20/23 development.

## TODO:
  [x] Minimize image sizes - strip binaries, don't use build only deps.
  [ ] Make toolchain build process generic, use variables for target-arch & versions.
  [ ] Add toolchain files for cmake.
  [ ] Add a base project for cmake.
  [ ] Only use built glibc and custom toolchains, slowly remove base image and package manager.
  [ ] Build/include common tools like busybox, cmake, ninja, etc...
  [ ] Go distroless in final image
  [ ] Make it easy to package build and run-time dependencies for project.
  [ ] Bleeding-edge all the things.
