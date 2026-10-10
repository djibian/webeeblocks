# Checkpoint #572 — recovered props-off front-range observations (8 October 2026)

This is historical evidence, **not** a repeat of the checkpoint, a formal owner PASS, qualification of a sensor, or authorization for motorized flight. See [#572](https://github.com/djibian/webeeblocks/issues/572), the [original owner-attributed observation report](https://github.com/djibian/webeeblocks/issues/572#issuecomment-6062843463), and the earlier [#566 FAIL](https://github.com/djibian/webeeblocks/issues/566#issuecomment-6054809077).

## Identity / chain of custody

- Checkpoint target: `1d0632971c7cb4f175576fd1ab67111a0aeb3786`, evidence workflow run `37779741683`, artifact ID `11551815617`, artifact digest `sha256:115c541dbab4fdf31bfa51731880faca2c66fe38f1bebc7f0461d03db6095a00`.
- The owner provided an export on 2026-10-10 (original ZIP SHA-256: `5cd8794d53f9015d58b086c7b766778422e6a635b059fa2f9658c2cad8504337`).
- Export contains 30 original evidence files, an exporter manifest and a recovery report. Every original file matches its export manifest's byte length and SHA-256; ZIP CRC checks also passed. **These checks establish consistency of the received export only**, not a cryptographic attestation of drone-generated data.
- The original exporter manifest and recovery report exposed a local home-directory path; they are deliberately excluded from public publication. The published manifest retains each raw file's SHA-256 and byte length. Raw evidence bytes must remain unchanged.
- Any publication of the raw files is an archival record, not retrospective compliance of the physical test procedure.

## Independently recalculated observations

| Raw `front-range.csv` | 0.50 m target | 1.00 m target |
|---|---:|---:|
| Samples | 100 | 100 |
| Available | 100 | 100 |
| Unavailable / malformed | 0 / 0 | 0 / 0 |
| Mean (mm) | 480.26 | 989.24 |
| Min–max (mm) | 477–485 | 981–997 |
| Sample standard deviation (mm) | 1.637 | 3.462 |
| Mean minus nominal target (mm) | -19.74 | -10.76 |
| Device timestamps (ms) | 129187–139087 | 322880–332780 |
| Device sample intervals | 99 × 100 ms | 99 × 100 ms |
| Acquisition result | `OBSERVED` | `OBSERVED` |

There was no `32766`/`32767` unavailable sentinel within these 200 frames. The two windows are separated by ~183.7 s without recorded continuous range coverage. This **does not identify the cause** of #566 or prove availability in moving/motorized conditions. A value `>=8000` remains unavailable, never clearance.

## Configuration and limitations

- Both records refer to the same `PREPARED` firmware setup, with matching SHA-256 source references and exact geometry-file hashes. Crazyflie 2.1, Flow Deck V2 and Multi-ranger are observed; bottom Color LED Deck absent. Props removed, no execution authority.
- Official firmware 2026.08 is reported; live typed readbacks: `firmware.modified=0`, `multiranger.filterMask=1`, `stabilizer.estimator=2` (Kalman), `stabilizer.controller=1` (PID). This is **not** independent remote binary attestation.
- Both original geometry files state `Mesure au metre et photographies face/profil conservees`, although no photographs/video were supplied. The owner attested the independently measured geometry; the physical placement and declared ±10 mm uncertainty cannot be independently corroborated. Do not alter those original strings to create retrospective conformity.
- The original checkpoint instructions required stopping at the first failed verification. The owner report preserves a Python 3.12 package-verifier failure, followed by a new download and verification under Python 3.10. **This is a known procedural deviation** that prevents a conforming uninterrupted formal PASS.
- Complete original terminal transcripts are not contained in the received export; it is unknown whether they remain on the owner's machine.
- Neither the nominal biases nor sensor accuracy are qualified against a predeclared acceptance threshold. Two stationary windows do not establish uninterrupted availability, flight correctness, obstacle clearance, or physical safety.

## Decision boundary

The checkpoint #572 remains open until an exact owner-authoritative `PASS`, `FAIL` or justified `NOT_NEEDED` is recorded through the governed procedure. No verdict is emitted by this archival document. Historic #554, #561 and #566 FAIL remain unchanged, and #157 representative powered acceptance remains `UNPROVEN`. No automatic retry, new checkpoint, hardware action, firmware change, or motorized flight is authorized by this evidence.

A reviewer should verify the released original evidence files against the manifest and these claims before GO.


## Inspect and reproduce offline

The 30 original text/CSV/JSON files are packed into [raw-evidence.tar.xz.base64](raw-evidence.tar.xz.base64), a Base64 **text transport wrapper** for a deterministic `.tar.xz` file. The archive itself contains the public-safe `MANIFEST_PUBLIC.json` and all 30 unaltered files under `raw/`. Its compressed binary SHA-256 is:

`5574217d0deda4da57267a880a0682ab4aa0cac39c3f58c519c80f311c8a4b1a`

Run the [offline verifier](verify_evidence.py) from a normal repository checkout (standard-library Python only; no drone or radio needed):

```bash
python3 docs/evidence/checkpoint-572/verify_evidence.py
```

The verifier checks the compressed archive digest, exactly 30 original raw files and their per-file SHA-256/lengths against the public manifest, then recalculates the two complete finite 100-sample windows and their device-time cadence.

To list or extract the original files for manual independent examination on GNU/Linux:

```bash
base64 --decode docs/evidence/checkpoint-572/raw-evidence.tar.xz.base64 | tar -tJf -
mkdir -p /tmp/webeeblocks-572
base64 --decode docs/evidence/checkpoint-572/raw-evidence.tar.xz.base64 | tar -xJf - -C /tmp/webeeblocks-572
```

The original ZIP's `MANIFEST_SHA256.json` and `RAPPORT_RECUPERATION.txt` were *not* republished because they contain a personal local directory path. Their absence is documented; the source ZIP hash above preserves an integrity identifier without pretending those excluded files were archived publicly. The per-file SHA-256 list and all raw scientific files remain available in the published archive. 
