"""Windows route-only secure epoch composer; no shared native source mutation.

The shipped route pilot needs 128 bits of OS-backed unpredictability for each
fresh challenge. MinGW std::random_device::entropy()==0 is a capability
estimate, not grounds for replacing the requirement with a weak PRNG.
Windows CNG BCryptGenRandom provides a supported cryptographic OS source.
A failed call is terminal for this challenge: NEVER synthesize an epoch.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp"
HEADER = "#include <random>\n"
HEADER_REPLACEMENT = "#include <random>\n#ifdef _WIN32\n#ifndef NOMINMAX\n#define NOMINMAX\n#endif\n#include <windows.h>\n#include <bcrypt.h>\n#endif\n"
OLD = """      std::random_device random;
      if(random.entropy()<=0)return; // Unavailable process freshness is never READY.
      char token[33];
      for(int i=0;i<4;++i)std::snprintf(token+i*8,9,"%08x",static_cast<unsigned>(random()));"""
NEW = """      char token[33];
#ifdef _WIN32
      /* Only Windows route mode. A failed OS CSPRNG never permits admission.
       * Keep the original independent pilot/evaluator epoch binding. */
      unsigned char epoch[16];
      if (BCryptGenRandom(nullptr, epoch, static_cast<ULONG>(sizeof(epoch)),
                          BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0) {
        std::fprintf(stderr, "GP_ROUTE_EPOCH_CNG_UNAVAILABLE\\n");
        clearRouteEpoch();
        return;
      }
      std::printf("GP_ROUTE_EPOCH_CNG_ACQUIRED attempt=%llu\\n", current);
      std::fflush(stdout);
      for (int i = 0; i < 16; ++i)
        std::snprintf(token + i * 2, 3, "%02x", static_cast<unsigned>(epoch[i]));
#else
      std::random_device random;
      if(random.entropy()<=0)return; // Existing non-Windows fail-closed path.
      for(int i=0;i<4;++i)std::snprintf(token+i*8,9,"%08x",static_cast<unsigned>(random()));
#endif"""


def compose_route_windows_epoch(source):
    """Refuse upstream anchor changes rather than making a broad rewrite."""
    if (source.count(HEADER) != 1 or source.count(OLD) != 1 or
            source.count("#ifdef WEBEEBLOCKS_GP_ROUTE_MODE") < 1 or
            "BCryptGenRandom" in source):
        raise ValueError("Shared route epoch anchor drift; refuse composition")
    patched = source.replace(HEADER, HEADER_REPLACEMENT, 1).replace(OLD, NEW, 1)
    if (patched.count("BCryptGenRandom(") != 1 or
            patched.count("routeEpoch=token;routeConfig=config;") != 1 or
            patched.count("if(random.entropy()<=0)return;") != 1 or
            patched.count("BCRYPT_USE_SYSTEM_PREFERRED_RNG") != 1):
        raise ValueError("Route CNG epoch postcondition failed")
    return patched


def write_windows_route_deadline(destination):
    destination = Path(destination)
    if destination.parent.resolve() != (ROOT / "controllers/grand_prix_route_flight/build").resolve():
        raise ValueError("Refuse to modify a non-route-controller destination")
    source = ORIGINAL.read_text(encoding="utf-8")
    patched = compose_route_windows_epoch(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.read_text(encoding="utf-8") != patched:
        destination.write_text(patched, encoding="utf-8")
    print("GP_ROUTE_WINDOWS_EPOCH_CNG_COMPOSED_ONLY")
