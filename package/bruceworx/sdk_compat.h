/* macOS 27 SDK math.h skips INFINITY and NAN when __has_feature(modules)
   is true. conda-forge clang 18 reports that feature even without -fmodules,
   so libc++ headers such as <random> fail to compile. */
#ifndef INFINITY
#define INFINITY __builtin_huge_valf()
#endif
#ifndef NAN
#define NAN __builtin_nanf("0")
#endif
