A set of Dockerfiles and a bake script for generating a few toolchains and build environments
for bleeding-edge C++20/23 development.

## TODO:
  [ ] Minimize image sizes
  [ ] Go distroless in final image
  [ ] Only use built glibc and custom toolchains
  [ ] Build/include common tools like busybox, cmake, ninja, etc...
  [ ] Add toolchain files for cmake.
  [ ] Add a base project for cmake.
  [ ] Make it easy to package for various distros. (May conflict with the next item)
  [ ] Bleeding-edge all the things.
