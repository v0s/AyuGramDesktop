# Submodule patches

`submodules/series.json` lists the reviewed patches and their exact module revisions. Each patch lives under `submodules/<module path>/` and uses paths relative to that module.

Initialize the required modules, then run from the repository root:

```sh
python Telegram/build/apply_submodule_patches.py
```

The helper checks every listed patch before applying changes. It accepts either the exact original files or the exact patched files, preserving unrelated changes. An unexpected module revision, parent pin, file contents or partially applied patch stops preparation. Repeated runs leave already-patched files unchanged.

`Telegram/configure.py` runs preparation before invoking CMake. Direct CMake users run the helper explicitly first. CMake performs a read-only check and tracks the manifest, patches, helper and patched files as configuration inputs, so a reset patch is checked again before an incremental build.

To inspect without applying changes:

```sh
python Telegram/build/apply_submodule_patches.py --check
```

Export patches with `git diff --full-index` inside the target module. The helper currently supports regular-file modifications with full before/after blob IDs; additions, deletions, renames, mode changes and binary patches require extending its validation first. Combine overlapping changes into one patch per file. Include the patch and its manifest entry in the same parent-repository commit.
