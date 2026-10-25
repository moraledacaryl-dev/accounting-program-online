# Accounting release service access correction

The guarded deployment of `8a84ddcbaeec76be8eb6ebfae1a3f292e0ef3be8`
stopped during immutable release preparation, before backup, migration, service
restart or activation. The workflow uses `umask 077`, leaving the new release
directory and its frontend parents at `0700`. The prepared image-cache leaf was
owned by `hiddenoasis`, but that service account could not traverse its parents.
The active production release remained `f636c8ed4113882877a66c89c5340cb656dbc880`.

Preparation now grants read/traverse access to the `hiddenoasis` group and no
group write access to the release tree. Only the Next.js image-cache leaf is
service-writable. Verification checks backend and frontend executables, build
identity and image-cache access as the actual service user before activation.

The DR contract runs a Linux test with synthetic files under `umask 077`. It
first proves the original access failure, then applies the release helper and
checks both service readability and protection against editing source/build
files. The failed prepared release is preserved; the correction uses a fresh
exact SHA and the existing guarded deployment workflow.
