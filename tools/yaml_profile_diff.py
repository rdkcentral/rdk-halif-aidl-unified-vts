#!/usr/bin/env python3
#** *****************************************************************************
# *
# * If not stated otherwise in this file or this component's LICENSE file the
# * following copyright and licenses apply:
# *
# * Copyright 2025 RDK Management
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# * http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
# *
#* ******************************************************************************
#
# Compares two YAML profile files for structural compatibility.
# Fails (exit 1) if the target is missing any root nodes or keys present in the source.
# Passes (exit 0) if only values differ; extra roots/keys in the target are informational.
#
# Usage:
#   python3 yaml_profile_diff.py <file1.yaml> <file2.yaml>
#   python3 yaml_profile_diff.py --dirs <rdk-halif-aidl/> <vts_hal_test_components/>

import sys
import argparse
import os
import yaml


SOURCE_FILE_MAP = {
    "motionsensor": [
        os.path.join(
            "sensor",
            "{version}",
            "com",
            "rdk",
            "hal",
            "sensor",
            "motion",
            "hfp-sensor-motion.yaml",
        )
    ],
    "thermalsensor": [
        os.path.join(
            "sensor",
            "{version}",
            "com",
            "rdk",
            "hal",
            "sensor",
            "thermal",
            "hfp-sensor-thermal.yaml",
        )
    ],
}


def load_released_versions(source_dir):
    """Load the released component-version map and its default version."""
    manifest_path = os.path.join(source_dir, "versions_released.yaml")
    try:
        manifest = load_yaml(manifest_path)
    except Exception:
        return "current", {}

    if not isinstance(manifest, dict):
        return "current", {}

    default_version = manifest.get("default", "current")
    components = manifest.get("components", {})
    return default_version, components if isinstance(components, dict) else {}


def get_component_version(source_component, default_version, component_versions):
    """Return the released version configured for a source component."""
    return component_versions.get(source_component, default_version)


def get_explicit_source_files(
    source_dir, target_component, default_version, component_versions
):
    """Return explicit source YAML files for target components with file-level aliases."""
    rel_paths = SOURCE_FILE_MAP.get(target_component, [])
    candidates = []
    for rel_path in rel_paths:
        path_parts = rel_path.split(os.sep)
        source_component = path_parts[0]
        version = get_component_version(
            source_component, default_version, component_versions
        )
        abs_path = os.path.join(source_dir, rel_path.format(version=version))
        if os.path.isfile(abs_path):
            candidates.append(abs_path)
    return candidates


def get_candidate_source_files(
    source_dir, source_component, default_version, component_versions
):
    """Return YAML files under the source component to consider for matching."""
    candidates = []
    version = get_component_version(source_component, default_version, component_versions)
    version_dir = os.path.join(source_dir, source_component, version)
    if os.path.isdir(version_dir):
        for entry in sorted(os.listdir(version_dir)):
            if entry.endswith(".yaml"):
                candidates.append(os.path.join(version_dir, entry))
    return candidates


def collect_key_paths(obj, prefix=""):
    """Recursively collect all key paths in a YAML object."""
    paths = set()
    if isinstance(obj, dict):
        for key in obj:
            full_path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(full_path)
            paths |= collect_key_paths(obj[key], full_path)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                paths |= collect_key_paths(item, prefix)
    return paths


def collect_values(obj, prefix=""):
    """Recursively collect all key-value pairs (leaf nodes)."""
    result = {}
    if isinstance(obj, dict):
        for key, val in obj.items():
            full_path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(val, (dict, list)):
                result.update(collect_values(val, full_path))
            else:
                result[full_path] = val
    elif isinstance(obj, list):
        scalar_vals = [v for v in obj if not isinstance(v, (dict, list))]
        if scalar_vals:
            result[prefix] = scalar_vals
        for item in obj:
            if isinstance(item, dict):
                result.update(collect_values(item, prefix))
    return result


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_root_keys(data):
    if not isinstance(data, dict):
        return set()
    return set(data.keys())


def is_ignorable_missing_key(key_path):
    """Allow missing <root>.interfaceVersion in target."""
    parts = key_path.split(".")
    return len(parts) == 2 and parts[1] == "interfaceVersion"


def diff_files(file1, file2, verbose=True):
    """
        Compare source YAML against target YAML structurally.
    Returns (passed, errors, warnings) where:
            passed  — True if all source roots/keys exist in target (values may differ)
            errors  — list of source entries missing in target (causes failure)
      warnings— list of informational differences
    """
    errors = []
    warnings = []

    try:
        data1 = load_yaml(file1)
    except Exception as e:
        errors.append(f"Cannot parse {file1}: {e}")
        return False, errors, warnings

    try:
        data2 = load_yaml(file2)
    except Exception as e:
        errors.append(f"Cannot parse {file2}: {e}")
        return False, errors, warnings

    if data1 is None or data2 is None:
        errors.append("One or both files are empty or invalid YAML.")
        return False, errors, warnings

    # 1. Check root nodes
    roots1 = get_root_keys(data1)
    roots2 = get_root_keys(data2)

    missing_roots = roots1 - roots2
    extra_roots = roots2 - roots1
    if missing_roots:
        errors.append(
            f"Root node(s) missing in target {os.path.basename(file2)} "
            f"(present in source {os.path.basename(file1)}): {', '.join(sorted(missing_roots))}"
        )
    if extra_roots:
        warnings.append(
            f"  Extra root node(s) in target {os.path.basename(file2)} "
            f"(not present in source {os.path.basename(file1)}): {', '.join(sorted(extra_roots))}"
        )

    # 2. Check all key paths
    keys1 = collect_key_paths(data1)
    keys2 = collect_key_paths(data2)

    missing_keys = keys1 - keys2
    extra_keys = keys2 - keys1

    for key in sorted(missing_keys):
        if is_ignorable_missing_key(key):
            continue
        errors.append(
            f"Key missing in target {os.path.basename(file2)} "
            f"(present in source {os.path.basename(file1)}): {key}"
        )
    for key in sorted(extra_keys):
        warnings.append(
            f"  Extra key in target {os.path.basename(file2)} "
            f"(not present in source {os.path.basename(file1)}): {key}"
        )

    # 3. Collect value differences (informational)
    vals1 = collect_values(data1)
    vals2 = collect_values(data2)
    common_keys = set(vals1.keys()) & set(vals2.keys())
    for key in sorted(common_keys):
        if vals1[key] != vals2[key]:
            warnings.append(f"  {key}:")
            warnings.append(f"    < {vals1[key]}")
            warnings.append(f"    > {vals2[key]}")

    passed = len(errors) == 0

    if verbose:
        col_width = 60
        separator = "=" * (col_width * 2 + 7)
        print(separator)
        print(f"  {'SOURCE YAML':<{col_width}}  |  TARGET YAML")
        print(f"  {os.path.basename(file1):<{col_width}}  |  {os.path.basename(file2)}")
        print(separator)

        if errors:
            print("\n[FAIL] Target does not follow source structure:")
            for e in errors:
                print(f"  ERROR: {e}")
        else:
            print("\n[PASS] Target follows source root nodes and key names.")

        if warnings:
            print("\n[INFO] Non-blocking differences:")
            for w in warnings:
                print(w)
        else:
            print("[INFO] No value differences found.")

        print()

    return passed, errors, warnings


def discover_pairs(dir1, dir2, warn_on_unmatched=True):
    """
        Walk dir1 for canonical profile YAML files and attempt to find a matching file in dir2.
    Pattern:
            dir1: <component>/profiles/hfp-<component>.yaml
      dir2: <component>/current/<name_without_suffix>.yaml
              or <component>/current/<name>.yaml
    Falls back to matching by YAML root node.
    """
    pairs = []
    default_version, component_versions = load_released_versions(dir2)
    for root, _, files in os.walk(dir1):
        if not root.endswith("profiles") and "/profiles" not in root:
            continue
        for fname in files:
            f1 = os.path.join(root, fname)
            rel = os.path.relpath(f1, dir1)   # e.g. hdmicec/profiles/hfp-hdmicec_vcomponent.yaml
            parts = rel.split(os.sep)
            if len(parts) < 3:
                continue
            component = parts[0]
            if fname != f"hfp-{component}.yaml":
                continue

            # Try to load file1 to get its root node for smarter matching
            try:
                data1 = load_yaml(f1)
                root_key = list(data1.keys())[0] if isinstance(data1, dict) else None
            except Exception:
                root_key = None

            match = None
            explicit_candidate_files = get_explicit_source_files(
                dir2, component, default_version, component_versions
            )
            if explicit_candidate_files:
                source_component_candidates = [explicit_candidate_files]
            else:
                source_component_candidates = [
                    get_candidate_source_files(
                        dir2, component, default_version, component_versions
                    )
                ]
            for candidate_files in source_component_candidates:
                for cf_path in candidate_files:
                    if root_key:
                        try:
                            data2 = load_yaml(cf_path)
                            if isinstance(data2, dict) and root_key in data2:
                                match = cf_path
                                break
                        except Exception:
                            pass
                if match:
                    break

                # Fallback: fuzzy name match stripping _vcomponent suffix
                base = fname.replace("_vcomponent", "").replace("-vcomponent", "")
                for cf_path in candidate_files:
                    cf = os.path.basename(cf_path)
                    if base in cf or cf in base:
                        match = cf_path
                        break
                if match:
                    break

            if match:
                pairs.append((f1, match))
            elif warn_on_unmatched:
                print(f"[WARN] No match found in {dir2} for: {rel}")

    return pairs


def main():
    parser = argparse.ArgumentParser(
         description="Diff YAML profile files for source-to-target structural compatibility.\n"
                  "Fails only when source roots/keys are missing in target; target extras are informational.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
             "  python3 yaml_profile_diff.py source.yaml target.yaml\n"
             "  python3 yaml_profile_diff.py --dirs vts_hal_test_components/ rdk-halif-aidl/",
    )
    parser.add_argument("file_or_dir1", metavar="FILE1_or_DIR1",
                        help="First YAML file, or first root directory (with --dirs).")
    parser.add_argument("file_or_dir2", metavar="FILE2_or_DIR2",
                        help="Second YAML file, or second root directory (with --dirs).")
    parser.add_argument("--dirs", action="store_true",
                        help="Treat arguments as root directories and auto-discover profile pairs.")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress per-file diff output; only print summary.")

    args = parser.parse_args()
    verbose = not args.quiet

    if args.dirs:
        # Directory mode convention:
        #   target repository contains <component>/profiles/*.yaml
        #   source repository contains <component>/<released-version>/*.yaml
        # If args are reversed, auto-detect and swap.
        arg1, arg2 = args.file_or_dir1, args.file_or_dir2
        target_dir, source_dir = arg1, arg2

        if not os.path.isdir(arg1):
            print(f"ERROR: Not a directory: {arg1}", file=sys.stderr)
            sys.exit(2)
        if not os.path.isdir(arg2):
            print(f"ERROR: Not a directory: {arg2}", file=sys.stderr)
            sys.exit(2)

        pairs = discover_pairs(target_dir, source_dir, warn_on_unmatched=False)
        if not pairs:
            swapped_pairs = discover_pairs(arg2, arg1, warn_on_unmatched=False)
            if swapped_pairs:
                target_dir, source_dir = arg2, arg1
                pairs = swapped_pairs
                if verbose:
                    print(
                        f"[INFO] Auto-detected directory order: target={target_dir}, source={source_dir}"
                    )

        # Re-run with warnings enabled now that the direction is known.
        if pairs:
            pairs = discover_pairs(target_dir, source_dir, warn_on_unmatched=True)

        if not pairs:
            print("ERROR: No matching profile pairs found.", file=sys.stderr)
            sys.exit(2)

        overall_pass = True
        results = []
        for target_file, source_file in pairs:
            passed, errors, warnings = diff_files(source_file, target_file, verbose=verbose)
            results.append((source_file, target_file, passed, errors, warnings))
            if not passed:
                overall_pass = False

        print("=" * 80)
        print(f"SUMMARY: {len(pairs)} pair(s) compared")
        for source_file, target_file, passed, errors, _ in results:
            status = "PASS" if passed else "FAIL"
            print(
                f"  [{status}] target {os.path.relpath(target_file, target_dir)} "
                f"follows source {os.path.relpath(source_file, source_dir)}"
            )
            if not passed:
                for e in errors:
                    print(f"         {e}")

        sys.exit(0 if overall_pass else 1)

    else:
        f1, f2 = args.file_or_dir1, args.file_or_dir2
        if not os.path.isfile(f1):
            print(f"ERROR: File not found: {f1}", file=sys.stderr)
            sys.exit(2)
        if not os.path.isfile(f2):
            print(f"ERROR: File not found: {f2}", file=sys.stderr)
            sys.exit(2)

        passed, errors, warnings = diff_files(f1, f2, verbose=verbose)
        sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
