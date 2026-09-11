# Raw physical evidence for #70

Byte-for-byte UTF-8 copies of the owner-attached checkpoint archives, accessible
through ordinary Git clones and GitHub file reads. No attachment download is
needed to inspect the retained CSV data.

| Checkpoint | Text files | CSV files | Archive SHA-256 provenance |
| --- | ---: | ---: | --- |
| [#180](https://github.com/djibian/webeeblocks/issues/180) | 50 | 36 | Observed digest; no prior archive digest was published |
| [#236](https://github.com/djibian/webeeblocks/issues/236) | 16 | 14 | Matches the owner's published digest |
| [#251](https://github.com/djibian/webeeblocks/issues/251) | 28 | 26 | Matches the owner's published digest |

Each `SOURCE.json` records the source attachment/comment, archive hash and size,
and the exact paths, sizes and SHA-256 digests of the copied files.
`MANIFEST.sha256` independently supports local file verification. Archive hashes
identify the human result archives, not the separately published firmware bundles.

From this directory, verify the retained bytes with:

```sh
(cd checkpoint-180 && sha256sum -c MANIFEST.sha256)
(cd checkpoint-236 && sha256sum -c MANIFEST.sha256)
(cd checkpoint-251 && sha256sum -c MANIFEST.sha256)
```

The nested binary `original/S3-8561ec3-results.tar.gz` in #236 contains the
excluded initial series. It remains in the original owner attachment; its exact
hash, size and omission are recorded in `checkpoint-236/SOURCE.json`. No omitted
archive is silently treated as an empty or successful experiment. The top-level
valid runs and the separately retained excluded fast S3-C trial are copied here.

Original line endings are preserved. The local `.gitattributes` prevents Git
newline conversion and recognizes CRLF in whitespace checks; CSV values and
source hashes are not rewritten to satisfy formatting checks. The failed
temporary importer run [34480695293](https://github.com/djibian/webeeblocks/actions/runs/34480695293)
had successfully downloaded and verified the archives, then stopped at
`git diff --cached --check` on those CRLF files. The importer workflow and its
temporary notes have been removed from the final candidate.

Preserve the original checkpoint verdicts and exclusions. In particular, the
initial invalid series and operator-error trials are not acceptance evidence.
These files do not establish a new physical capability, validate a terrain
classifier, or authorize firmware retuning or motorized testing. Script/cache
files in the archives are historical evidence, not an instruction to execute
them or an additional source of observed sensor samples.
