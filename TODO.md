## TODO:
  [-] Make toolchain build process generic, use variables for target-arch & versions.
  [-] Migrate to working with a build script in a running container and saving toolchains
      to a volume or mount.
  [-] Make weaver a proper python package and build script from that.
  [ ] Add toolchain files for cmake.
  [ ] Add a base project for cmake.
  [ ] Only use built glibc and custom toolchains, slowly remove base image and package manager.
  [ ] Build/include common tools like busybox, cmake, ninja, etc...
  [ ] Go distroless in final image | or switch to alpine
  [ ] Make it easy to package build and run-time dependencies for project.
  [ ] Bleeding-edge all the things.


