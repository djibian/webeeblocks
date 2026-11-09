// Only the Windows CRT secure random source, no secret values in diagnostics.
// Compiled and run with the same MinGW64 toolchain as native Webots.
#if !defined(_WIN32) || !defined(_CRT_RAND_S)
#error "Windows CRT CSPRNG probe requires _WIN32 and _CRT_RAND_S"
#endif
#include <cstdlib>
#include <cstdio>
#include <random>

int main() {
  unsigned int word=0;
  for(int i=0;i<4;++i) {
    if(::rand_s(&word)!=0) {
      std::fputs("GP_WINDOWS_CSPRNG_UNAVAILABLE\n",stderr);
      return 1;
    }
  }
  try {
    std::random_device device;
    // Only metadata: entropy() is an estimate, not an admission decision.
    std::printf("GP_WINDOWS_CSPRNG_AVAILABLE entropy_estimate=%.1f\n",
                device.entropy());
  } catch(...) {
    std::fputs("GP_WINDOWS_RANDOM_DEVICE_DIAGNOSTIC_FAILED\n",stderr);
    return 1;
  }
  return 0;
}
