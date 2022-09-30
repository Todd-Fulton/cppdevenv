# WIP: Warning !!! This is a Work in Progress

A set of scripts for bleeding-edge C++20/23 development.


## Future Goals:

### Weaver

A source package manager using docker for reproducible builds.

Why weaver? There are birds called social weavers that build elaborate nests. Weaver will attempt to weave all the sources together in a systematic fashion to build a "nest", an environment for applications and development.

#### Core principles and guiding philosophy of Weaver:

- Minimalistic. Weaver wont give you what you don't ask for.
- Configurable. Weaver will allow you to tweak every knob in the system.
- Fluid. Weaver will track dependencies and enable options needed throughout the stack.
- Clean. Weaver wont leave trash behind in your target system.
- Declarative. Weaver just needs users to declare what they want.


#### Todd Fulton (Sept, 29 2022):

Moving build process from image build time, to image run time.
This means that we will build an image with the required dependencies to build
a toolchain from scratch, and then build everything from that.

The workflow will begin as such:
`[build image] -> <volume|mount>/crosstools/build_hash/{bin,lib,rootfs,...}`

Once the volume/mount has the required toolchain identified by hashing its configuration,
then we can build packages and install them in the sysroot directory (/build_hash/rootfs).
Once the sysroot is fully populated with the requested packages, then we can build a
container image from that using `FROM scratch` and just copy the sysroot to it.

Inspired by:

 [![this CppNow 2022 talk](https://img.youtube.com/vi/VCrLAmJWZFQ/0.jpg)](https://www.youtube.com/watch?v=VCrLAmJWZFQ)

Also see [the Common Package Specification (CPS)](https://mwoehlke.github.io/cps/overview.html).
