"""Offline aggregate wrench closure for the lab-only #637 public ODE probe.

MEASURED does not mean contact/actuator attribution or product PASS.
INDETERMINATE protects against RESET phasing, clamp, damping and missing data.
"""
import argparse
import csv
import json
import math
from pathlib import Path
def vector(row, prefix, n):
    return [float(row[f"{prefix}{i}"]) for i in range(n)]
def mat3(padded):
    return [padded[0:3], padded[4:7], padded[8:11]]
def mv(a, x):
    return [sum(a[i][j] * x[j] for j in range(3)) for i in range(3)]
def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3))
             for j in range(3)] for i in range(3)]
def transpose(a):
    return [list(row) for row in zip(*a)]
def norm(x):
    return math.sqrt(sum(v * v for v in x))

def indeterminate(reason):
    return {"status": "INDETERMINATE", "reason": reason}

def diagnose(pre, post, dt):
    try:
        if not (int(pre["valid"]) and int(post["valid"])
                and int(pre["has_after"]) and int(post["has_after"])):
            return indeterminate("missing or invalid callback pair")
        if not (int(pre["enabled"]) and int(post["enabled"])):
            return indeterminate("body inactive or RESET transition")
        if int(pre["joint_truncated"]):
            return indeterminate("joint inventory exceeds probe limit")
        if float(pre["linear_damping"]) != 0 or float(pre["angular_damping"]) != 0:
            return indeterminate("damping may change velocity")
        mass = float(pre["mass"])
        if mass <= 0 or dt <= 0:
            return indeterminate("nonpositive mass or time step")
        w0, w1 = vector(pre, "w", 3), vector(post, "w", 3)
        if norm(w0) > 1e-10:
            return indeterminate("nonzero initial omega: gyroscopic term unmodeled")
        wmax = float(pre["max_angular_speed"])
        if math.isfinite(wmax) and norm(w1) >= wmax - 1e-9:
            return indeterminate("possible angular speed clamp")
        r = mat3(vector(pre, "r", 12))
        ib = mat3(vector(pre, "I", 12))
        iw = mul(mul(r, ib), transpose(r))
        dv = [a - b for a, b in zip(vector(post, "v", 3), vector(pre, "v", 3))]
        dw = [a - b for a, b in zip(w1, w0)]
        gravity = vector(pre, "g", 3) if int(pre["gravity_mode"]) else [0.0] * 3
        f = vector(pre, "f", 3)
        tau = vector(pre, "t", 3)
        force_residual = [mass * dv[i] / dt - f[i] - mass * gravity[i]
                          for i in range(3)]
        implied = mv(iw, dw)
        torque_residual = [implied[i] / dt - tau[i] for i in range(3)]
        if not all(math.isfinite(x) for x in force_residual + torque_residual):
            return indeterminate("nonfinite mechanics")
        fn, tn = norm(force_residual), norm(torque_residual)
        if not math.isfinite(fn) or not math.isfinite(tn):
            return indeterminate("nonfinite residual norm")
        return {"status": "MEASURED", "force_residual_N": force_residual,
                "torque_residual_Nm": torque_residual,
                "force_norm_N": fn, "torque_norm_Nm": tn,
                "contact_candidates": int(pre["contacts"]),
                "joints_attached": int(pre["joints"])}
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        return indeterminate("malformed/incompatible capture: " + str(exc))

def analyze(path, dt, low, high, top):
    paired = {}
    footer = None
    total_rows = 0
    malformed = False
    with Path(path).open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["frame"].startswith("#"):
                footer = ",".join(v for v in row.values() if isinstance(v, str) and v)
                continue
            total_rows += 1
            try:
                frame, phase, t = int(row["frame"]), row["phase"], float(row["time_ms"])
                if (not math.isfinite(t) or frame != (total_rows - 1) // 2
                        or phase != ("pre" if total_rows % 2 else "post")):
                    malformed = True
                if low <= t <= high:
                    pair = paired.setdefault(frame, {})
                    if (phase in pair or (phase == "post" and "pre" in pair
                                          and pair["pre"]["time_ms"] != row["time_ms"])):
                        malformed = True
                    pair[phase] = row
            except (KeyError, TypeError, ValueError):
                malformed = True
    ranked = []
    statuses = {"MEASURED": 0, "INDETERMINATE": 0}
    for number, pair in paired.items():
        if ("pre" in pair and "post" in pair
                and pair["pre"]["time_ms"] != pair["post"]["time_ms"]):
            result = indeterminate("mismatched callback times")
        else:
            result = diagnose(pair.get("pre", {}), pair.get("post", {}), dt)
        statuses[result["status"]] += 1
        result["frame"] = number
        result["time_ms"] = float(pair["pre"]["time_ms"]) if "pre" in pair else None
        ranked.append(result)
    ranked.sort(key=lambda r: r.get("torque_norm_Nm", -1), reverse=True)
    meta = dict(part.split("=", 1) for part in (footer or "").split(",") if "=" in part)
    capture_ok = (not malformed and total_rows % 2 == 0
                  and meta.get("#frames") == str(total_rows // 2)
                  and meta.get("overflow") == "0" and meta.get("body_missing") == "0")
    if not capture_ok:
        ranked, statuses = [indeterminate("partial or inconsistent capture")], {"MEASURED": 0, "INDETERMINATE": len(paired)}
    return {"capture_status": "COMPLETE" if capture_ok else "PARTIAL_OR_UNKNOWN",
            "footer": footer, "counts": statuses, "top": ranked[:top],
            "claim": "aggregate closure only; never joint validity or product verdict"}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--dt", type=float, default=0.032)
    p.add_argument("--from-ms", dest="low", type=float, default=-math.inf)
    p.add_argument("--to-ms", dest="high", type=float, default=math.inf)
    p.add_argument("--top", type=int, default=12)
    args = p.parse_args()
    print(json.dumps(analyze(args.csv, args.dt, args.low, args.high,
                             args.top), indent=2, allow_nan=False))
