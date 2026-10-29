#!/bin/bash
#* ******************************************************************************
#*  If not stated otherwise in this file or this component's LICENSE
#*  file the following copyright and licenses apply:
#*
#*  Copyright 2025 RDK Management
#*
#*  Licensed under the Apache License, Version 2.0 (the License);
#*  you may not use this file except in compliance with the License.
#*  You may obtain a copy of the License at
#*
#*  http://www.apache.org/licenses/LICENSE-2.0
#*
#*  Unless required by applicable law or agreed to in writing, software
#*  distributed under the License is distributed on an AS IS BASIS,
#*  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#*  See the License for the specific language governing permissions and
#*  limitations under the License.
#*
#* ******************************************************************************

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

declare -r TOP=`dirname $(realpath $0)`
UT_CORE_DEFAULT_VERSION="5.1.0"
export UT_CORE_VERSION="${UT_CORE_VERSION:-${UT_CORE_DEFAULT_VERSION}}"
RDK_HALIF_AIDL_VERSION="${RDK_HALIF_AIDL_VERSION:-main}"
RDK_HALIF_TEST_BASE_URL="https://github.com/rdkcentral/rdk-halif-aidl-test-"
OUT_TAR_FILE=vts_unified.tar.gz

declare -a HALIF_TEST_COMPONENTS=(
  avbuffer audiodecoder audiosink videodecoder videosink avclock planecontrol
  hdmicec hdmiinput hdmioutput deepsleep compositeinput deviceinfo bootreason firmwareupdate indicator
  audiomixer thermalsensor motionsensor
)

# Define the directory where the repository will be cloned
declare -r UT_CORE_DIR="${TOP}/ut-core"
declare -r TOP_BUILD_DIR="${TOP}/build"
declare -r COMMON_DIR="${TOP}/common"
declare -r BUILD_INSTALL_PREFIX=${TOP_BUILD_DIR}/usr
declare -r RDK_HAL_DIR=${TOP}/rdk-halif-aidl
declare -r RDK_HAL_TEST_DIR=${TOP}/vts_hal_test_components
declare -r PROFILES_DIR=${TOP}/profiles
declare -r L4_TEST_DIR=${RDK_HAL_TEST_DIR}/l4_tests
declare -r AV_L4_TEST_DIR=${RDK_HAL_TEST_DIR}/l4_tests/src/av/

#TODO: change to server path
DEF_GST_LIB_PATH="`realpath ${TOP}/../`/gstreamer_aidl_package/build/install"
GST_LIB_PATH=${GST_LIB_PATH:-${DEF_GST_LIB_PATH}}

#TODO: change to server path
declare -r DEF_EGL_LIB_PATH="${TOP}/../egl_pkg"
EGL_LIB_PATH=${EGL_LIB_PATH:-${DEF_EGL_LIB_PATH}}

mkdir -p $TOP_BUILD_DIR

# Parse Target argument (e.g., Target=arm or target=linux)
# Default to 'linux' if not provided
TARGET="linux"

###############################################################################
# Function to validate TARGET option
###############################################################################
for arg in "$@"; do
    if [[ $arg == [Tt]arget=* ]]; then
        TARGET="${arg#*=}"
    fi
done

# Validate TARGET
valid_targets=("linux" "arm")
if [[ ! " ${valid_targets[@]} " =~ " ${TARGET} " ]]; then
    echo -e "${BOLD}${RED}Invalid Target: $TARGET. Valid targets are: ${valid_targets[@]}${RESET}"
    help
    exit 1
fi

###############################################################################
# Function to validate repo tool is installed
###############################################################################
validate_repo_tool()
{
    if ! command -v repo &>/dev/null; then
        echo -e "${BOLD}${RED}Error: 'repo' tool is not installed or not in PATH.${RESET}"
        echo -e "${BOLD}${YELLOW}Install it with:${RESET}"
        echo -e "${BOLD}${CYAN}  mkdir -p ~/.local/bin${RESET}"
        echo -e "${BOLD}${CYAN}  curl -o ~/.local/bin/repo https://storage.googleapis.com/git-repo-downloads/repo${RESET}"
        echo -e "${BOLD}${CYAN}  chmod a+rx ~/.local/bin/repo${RESET}"
        echo -e "${BOLD}${YELLOW}Then add ~/.local/bin to your PATH:${RESET}"
        echo -e "${BOLD}${CYAN}  export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
        exit 1
    fi
}

###############################################################################
# Function to validate cross compiler for arm target
###############################################################################
validate_cross_compiler()
{
    if [ -z "${CC}" ]; then
        echo -e "${BOLD}${RED}Error: CC is not set. A cross-compiler is required to build for arm target.${RESET}"
        echo -e "${BOLD}${YELLOW}Please set CC to your cross-compiler (e.g. export CC=aarch64-linux-gnu-gcc)${RESET}"
        echo -e "${BOLD}${YELLOW}Alternatively, consider using the provided Docker environment to build for arm.${RESET}"
        exit 1
    fi

    # Extract just the compiler binary (first word) for PATH check
    local CC_BIN
    CC_BIN=$(echo "${CC}" | awk '{print $1}')
    if ! command -v "${CC_BIN}" &>/dev/null; then
        echo -e "${BOLD}${RED}Error: Cross-compiler '${CC_BIN}' not found in PATH.${RESET}"
        echo -e "${BOLD}${YELLOW}Please install the cross-compiler or consider using the provided Docker environment to build for arm.${RESET}"
        exit 1
    fi

    # Derive CXX from CC if not already set (replace gcc with g++)
    if [ -z "${CXX}" ]; then
        export CXX="${CC/gcc/g++}"
        echo -e "${BOLD}${GREEN}Derived CXX=${CXX}${RESET}"
    fi

    # Extract flags from CC (everything after the binary)
    local CC_FLAGS
    CC_FLAGS=$(echo "${CC}" | cut -d' ' -f2-)

    # Extract sysroot value from CC flags
    local SYSROOT
    SYSROOT=$(echo "${CC_FLAGS}" | sed -n 's/.*--sysroot=\([^ ]*\).*/\1/p')

    # Set CFLAGS from CC flags if not already set
    if [ -z "${CFLAGS}" ] && [ -n "${CC_FLAGS}" ]; then
        export CFLAGS="${CC_FLAGS}"
        echo -e "${BOLD}${GREEN}Derived CFLAGS=${CFLAGS}${RESET}"
    fi

    # Set CXXFLAGS from CC flags if not already set
    if [ -z "${CXXFLAGS}" ] && [ -n "${CC_FLAGS}" ]; then
        export CXXFLAGS="${CC_FLAGS}"
        echo -e "${BOLD}${GREEN}Derived CXXFLAGS=${CXXFLAGS}${RESET}"
    fi

    # Set LDFLAGS with sysroot if not already set
    if [ -z "${LDFLAGS}" ] && [ -n "${SYSROOT}" ]; then
        export LDFLAGS="--sysroot=${SYSROOT}"
        echo -e "${BOLD}${GREEN}Derived LDFLAGS=${LDFLAGS}${RESET}"
    fi

    # Set TARGET_LIB32_VERSION for 32-bit ARM (arm- prefix, not aarch64)
    if [ -z "${TARGET_LIB32_VERSION}" ] && [[ "${CC_BIN}" == arm-* ]]; then
        export TARGET_LIB32_VERSION=ON
        echo -e "${BOLD}${GREEN}Derived TARGET_LIB32_VERSION=${TARGET_LIB32_VERSION}${RESET}"
    fi
}

###############################################################################
# Function to validate and set GST_LIB_PATH
###############################################################################
validate_gst_lib_path()
{
    # Resolve GST_LIB_PATH to absolute path before validation
    if [ -n "$GST_LIB_PATH" ]; then
        GST_LIB_PATH=`realpath ${GST_LIB_PATH}` 2>/dev/null || GST_LIB_PATH=""
    fi

    if [ ! -d "$GST_LIB_PATH" ]; then
        echo "GST_LIB_PATH: path does not exists, consider building the GST_LIB_PATH in $DEF_GST_LIB_PATH"
        exit 1
    fi
}

###############################################################################
# Function to validate and set EGL_LIB_PATH
###############################################################################
validate_egl_lib_path()
{
    # Resolve EGL_LIB_PATH to absolute path before validation
    if [ -n "$EGL_LIB_PATH" ]; then
        EGL_LIB_PATH=`realpath ${EGL_LIB_PATH}` 2>/dev/null || EGL_LIB_PATH=""
    fi

    if [ ! -d "$EGL_LIB_PATH" ]; then
        echo "EGL_LIB_PATH: path does not exists, consider building the EGL_LIB_PATH in $DEF_EGL_LIB_PATH"
        exit 1
    fi
}

###############################################################################
# Function to clone  unified VTS repo's
###############################################################################
unified_manifest()
(
    set -euo pipefail

    # .repo/manifests is the same marker used below to confirm a sync actually completed
    # (see the check after `repo sync`); a non-empty RDK_HAL_TEST_DIR alone doesn't prove
    # that - a partially failed sync or a manually created directory would look identical.
    if [ "${FORCE_REPO_SYNC:-0}" != "1" ] && [ -d .repo/manifests ] && [ -d "${RDK_HAL_TEST_DIR}" ] && [ -n "$(ls -A ${RDK_HAL_TEST_DIR} 2>/dev/null)" ]; then
        echo "Manifest already synced, skipping repo sync"
        echo "  (set FORCE_REPO_SYNC=1 to re-sync, e.g. after switching branches or editing the manifest)"
        exit 0
    fi

    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [ "${BRANCH}" = "HEAD" ]; then
        echo "ERROR: Detached HEAD state detected — cannot determine branch for repo init."
        exit 1
    fi

    echo "repo init unified manifest"
    repo init \
        --repo-url=https://gerrit.googlesource.com/git-repo \
        --no-clone-bundle \
        --repo-rev=stable \
        -b "${BRANCH}" \
        -m aidl_unified_manifest.xml \
        -u https://github.com/rdkcentral/rdk-halif-aidl-unified-vts.git \
        -q

    repo sync -cd -j 16 -q

    if [ ! -d .repo/manifests ]; then
        echo "ERROR: Expected .repo/manifests to exist after repo sync, but it was not found."
        exit 1
    fi
    if grep 'fetch="http://' .repo/manifests/aidl_unified_manifest.xml; then
        echo "ERROR: Insecure repo URL detected in aidl_unified_manifest.xml!"
        exit 1
    elif [ $? -ne 1 ]; then
        echo "ERROR: Failed to scan aidl_unified_manifest.xml for insecure repo URLs."
        exit 1
    fi
)

###############################################################################
# Install Binder headers/libs into build/usr/ from the rdk-halif-aidl Binder SDK.
# Call after generate_hal_interfaces().
###############################################################################
install_linux_binder()
{
    local BINDER_SDK="${RDK_HAL_DIR}/out/target"
    local BINDER_INC="${RDK_HAL_DIR}/out/build"

    echo "Install binder 'service manager, headers and libraries'"
    install -d ${BUILD_INSTALL_PREFIX}/bin ${BUILD_INSTALL_PREFIX}/lib ${BUILD_INSTALL_PREFIX}/include

    if [ -d "${BINDER_SDK}/bin" ]; then
        find "${BINDER_SDK}/bin" -maxdepth 1 -type f -executable \
            -exec install -t ${BUILD_INSTALL_PREFIX}/bin {} \; 2>/dev/null || true
    fi

    if [ -d "${BINDER_SDK}/lib/binder" ]; then
        find "${BINDER_SDK}/lib/binder" -maxdepth 1 \( -name "*.so" -o -name "*.so.*" \) \
            -exec install -t ${BUILD_INSTALL_PREFIX}/lib {} \; 2>/dev/null || true
    fi

    if [ -d "${BINDER_INC}/include/binder_sdk" ]; then
        cp -apr ${BINDER_INC}/include/binder_sdk/. ${BUILD_INSTALL_PREFIX}/include/
    fi
}

###############################################################################
# Function to install gstreamer headers, and libraries
###############################################################################
install_gstreamer_package()
{
    cp -r ${GST_LIB_PATH}/usr/lib/* ${TOP_BUILD_DIR}/usr/lib/
    cp -r ${GST_LIB_PATH}/usr/include/* ${TOP_BUILD_DIR}/usr/include/
}

###############################################################################
# Function to install egl headers, and libraries
###############################################################################
install_egl_package()
{
    cp -r ${EGL_LIB_PATH}/usr/lib/* ${TOP_BUILD_DIR}/usr/lib/
    cp -r ${EGL_LIB_PATH}/usr/include/* ${TOP_BUILD_DIR}/usr/include/
}

###############################################################################
# Validate that target profile YAMLs follow source YAML structure.
# Non-blocking: reports failed modules as info and never fails the build.
###############################################################################
validate_yaml_profiles_non_blocking()
{
    local diff_script="${TOP}/tools/yaml_profile_diff.py"

    if [ ! -f "${diff_script}" ]; then
        echo -e "${BOLD}${CYAN}[INFO] YAML profile check skipped: ${diff_script} not found${RESET}"
        return 0
    fi

    echo -e "${BOLD}${CYAN}[INFO] YAML profile check (source: rdk-halif-aidl, target: vts_hal_test_components)${RESET}"

    local diff_output
    diff_output=$(python3 "${diff_script}" --dirs "${RDK_HAL_DIR}" "${RDK_HAL_TEST_DIR}" --quiet 2>&1)
    local rc=$?

    if [ ${rc} -eq 0 ]; then
        echo -e "${BOLD}${CYAN}[INFO] YAML profile check passed for all discovered modules${RESET}"
        return 0
    fi

    local fail_lines
    fail_lines=$(echo "${diff_output}" | grep -E '^\s*\[FAIL\]\s+target\s+' || true)
    if [ -n "${fail_lines}" ]; then
        local failed_modules
        failed_modules=$(echo "${fail_lines}" \
            | sed -E 's/^.*\[FAIL\][[:space:]]+target[[:space:]]+([^/]+)\/.*$/\1/' \
            | sort -u | tr '\n' ' ' | sed 's/[[:space:]]*$//')
        echo -e "${BOLD}${CYAN}[INFO] YAML profile check found source/target mismatches in module(s): ${failed_modules}${RESET}"
    else
        local err_line
        err_line=$(echo "${diff_output}" | grep -E '^(ERROR:|\[WARN\])' | head -n 1)
        if [ -n "${err_line}" ]; then
            echo -e "${BOLD}${CYAN}[INFO] YAML profile check could not complete cleanly: ${err_line}${RESET}"
        else
            echo -e "${BOLD}${CYAN}[INFO] YAML profile check could not complete cleanly; continuing build${RESET}"
        fi
    fi

    return 0
}

###############################################################################
# Cross-compile ARM binder runtime - build_modules.sh doesn't build it for ARM.
# BUILD_HOST_AIDL=OFF skips the host-only AIDL compiler.
###############################################################################
build_arm_binder()
{
    local BINDER_REPO_DIR="${RDK_HAL_DIR}/build-tools/linux_binder_idl"
    local ARM_BINDER_BUILD="${RDK_HAL_DIR}/build/binder-arm"
    local ARM_BINDER_SDK="${RDK_HAL_DIR}/out/target"

    if [ -f "${ARM_BINDER_SDK}/.sdk_ready" ]; then
        echo "ARM Binder SDK already built at ${ARM_BINDER_SDK}"
        return 0
    fi

    # Clone directly, not via build_binder.sh - OE's native m4 breaks its AIDL parser build.
    if [ ! -d "${BINDER_REPO_DIR}/.git" ]; then
        echo "Cloning linux_binder_idl for ARM build..."
        local _binder_version
        _binder_version=$(grep -vE '^[[:space:]]*(#|$)' \
            "${RDK_HAL_DIR}/binder_sdk.version" 2>/dev/null \
            | head -1 | tr -d '[:space:]')
        _binder_version="${_binder_version:-2.0.0}"

        [ -d "${BINDER_REPO_DIR}" ] && rm -rf "${BINDER_REPO_DIR}"
        mkdir -p "${RDK_HAL_DIR}/build-tools"
        git clone "https://github.com/rdkcentral/linux_binder_idl" \
            "${BINDER_REPO_DIR}" || {
            echo "ERROR: Failed to clone linux_binder_idl."
            exit 1
        }
        ( cd "${BINDER_REPO_DIR}" && \
          git checkout "${_binder_version}" 2>/dev/null || \
          echo "Note: version ${_binder_version} not found, using default branch" )

        # Clone Android binder sources required by the cmake build
        ( cd "${BINDER_REPO_DIR}" && bash ./clone-android-binder-repo.sh ) || {
            echo "ERROR: Failed to clone Android binder sources."
            exit 1
        }
    fi

    if [ -z "${CC:-}" ] || [ -z "${CXX:-}" ]; then
        echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}CC/CXX are not set. Source the ARM toolchain environment${RESET}   ${BOLD}*${RESET}"
        echo -e "${BOLD}* ${RED}before running with Target=arm. Exiting.${RESET}                   ${BOLD}*${RESET}"
        echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
        exit 1
    fi

    # CC/CXX embed flags; CMAKE_C_COMPILER needs just the binary, so flags go into
    # CMAKE_C_FLAGS_INIT via our own toolchain file instead.
    local cc_bin cxx_bin cc_flags cxx_flags
    cc_bin=$(echo "${CC}" | awk '{print $1}')
    cxx_bin=$(echo "${CXX}" | awk '{print $1}')
    cc_flags=$(echo "${CC}" | cut -d' ' -f2-)    # flags embedded in CC by OE
    cxx_flags=$(echo "${CXX}" | cut -d' ' -f2-)  # flags embedded in CXX by OE

    mkdir -p "${ARM_BINDER_BUILD}"
    local TOOLCHAIN_FILE="${ARM_BINDER_BUILD}/arm-cross.cmake"
    cat > "${TOOLCHAIN_FILE}" <<TOOLCHAIN_EOF
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_C_COMPILER   "${cc_bin}")
set(CMAKE_CXX_COMPILER "${cxx_bin}")
set(CMAKE_C_FLAGS_INIT   "${cc_flags} ${CFLAGS:-}")
set(CMAKE_CXX_FLAGS_INIT "${cxx_flags} ${CXXFLAGS:-}")
set(CMAKE_EXE_LINKER_FLAGS_INIT    "${LDFLAGS:-}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${LDFLAGS:-}")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
TOOLCHAIN_EOF

    # Clear OECORE_* vars - if set, cmake auto-enables BUILD_ENV_YOCTO and skips install() rules.
    local _OECORE_NATIVE="${OECORE_NATIVE_SYSROOT:-}"
    local _OECORE_TARGET="${OECORE_TARGET_SYSROOT:-}"
    unset OECORE_NATIVE_SYSROOT OECORE_TARGET_SYSROOT

    echo "Cross-compiling ARM binder runtime (BUILD_HOST_AIDL=OFF)..."
    echo "  Compiler: ${cc_bin}"
    echo "  Flags:    ${cc_flags} ${CFLAGS:-}"
    cmake -S "${BINDER_REPO_DIR}" \
          -B "${ARM_BINDER_BUILD}" \
          -DCMAKE_INSTALL_PREFIX="${ARM_BINDER_SDK}" \
          -DCMAKE_BUILD_TYPE=Release \
          -DBUILD_HOST_AIDL=OFF \
          -DBUILD_ENV_YOCTO=OFF \
          -DCMAKE_TOOLCHAIN_FILE="${TOOLCHAIN_FILE}"
    local cmake_cfg_rc=$?

    # Restore OE env vars before any further steps
    [ -n "${_OECORE_NATIVE}" ] && export OECORE_NATIVE_SYSROOT="${_OECORE_NATIVE}"
    [ -n "${_OECORE_TARGET}" ] && export OECORE_TARGET_SYSROOT="${_OECORE_TARGET}"

    if [ $cmake_cfg_rc -ne 0 ]; then
        echo "ERROR: ARM binder cmake configuration failed."
        exit 1
    fi
    cmake --build "${ARM_BINDER_BUILD}" -j"$(nproc)" || {
        echo "ERROR: ARM binder build failed."
        exit 1
    }
    cmake --install "${ARM_BINDER_BUILD}" || {
        echo "ERROR: ARM binder install failed."
        exit 1
    }

    # Match build_binder.sh's linux-target layout so build_modules.sh finds the SDK.
    # Wipe lib/binder/ first - Step 1 (x86 build) may have left x86_64 libs there.
    local ARM_BINDER_INCLUDE="${RDK_HAL_DIR}/out/build"
    if [ -d "${ARM_BINDER_SDK}/lib" ]; then
        rm -rf "${ARM_BINDER_SDK}/lib/binder"
        mkdir -p "${ARM_BINDER_SDK}/lib/binder"
        mv "${ARM_BINDER_SDK}"/lib/*.so* "${ARM_BINDER_SDK}/lib/binder/" 2>/dev/null || true
    fi
    if [ -d "${ARM_BINDER_SDK}/include" ]; then
        mkdir -p "${ARM_BINDER_INCLUDE}/include/binder_sdk"
        find "${ARM_BINDER_SDK}/include" -mindepth 1 -maxdepth 1 -type d \
            -exec mv {} "${ARM_BINDER_INCLUDE}/include/binder_sdk/" \; 2>/dev/null || true
        find "${ARM_BINDER_SDK}/include" -maxdepth 1 -type f -name "*.h" \
            -exec mv {} "${ARM_BINDER_INCLUDE}/include/binder_sdk/" \; 2>/dev/null || true
        rmdir "${ARM_BINDER_SDK}/include" 2>/dev/null || true
    fi
    mkdir -p "${ARM_BINDER_SDK}/lib/halif"
    touch "${ARM_BINDER_SDK}/.sdk_ready"
    touch "${ARM_BINDER_INCLUDE}/.sdk_ready"
    echo "ARM Binder SDK built and installed to ${ARM_BINDER_SDK}"
}

###############################################################################
# Look up a component's pinned version from versions_released.yaml (the same
# manifest build_halif_modules()/create_halif_softlinks() build against, so
# any header/lib pulled via this lookup stays version-matched to what was
# actually built). Falls back to the manifest's `default:` value (normally
# "current") if the component has no explicit entry, or to "current" outright
# if the manifest itself is missing.
###############################################################################
get_halif_component_version()
{
    local component="$1"
    local yaml="${RDK_HAL_DIR}/versions_released.yaml"
    local default_version="current"
    local version=""

    if [ ! -f "$yaml" ]; then
        echo "$default_version"
        return
    fi

    local in_components=0
    while IFS= read -r line; do
        if [[ "$line" =~ ^default:[[:space:]]*([A-Za-z0-9._]+) ]]; then
            default_version="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^components: ]]; then
            in_components=1
        elif [[ $in_components -eq 1 ]]; then
            if [[ "$line" =~ ^[[:space:]]+${component}:[[:space:]]*([A-Za-z0-9._]+) ]]; then
                version="${BASH_REMATCH[1]}"
                break
            elif [[ "$line" =~ ^[^[:space:]] && ! "$line" =~ ^# ]]; then
                in_components=0
            fi
        fi
    done < "$yaml"

    echo "${version:-$default_version}"
}

###############################################################################
# Rename each halif module lib to lib<module>-cpp_vts.so (filename only - SONAME
# rewrite via patchelf dropped for now) and symlink the old versioned name to it,
# so it can't collide with a vendor lib.
###############################################################################
create_halif_softlinks()
{
    local YAML="${RDK_HAL_DIR}/versions_released.yaml"
    local LIB_DIR="${RDK_HAL_DIR}/out/target/lib/rdk-halif-aidl"
    local in_components=0

    if [ ! -f "$YAML" ]; then
        echo "Warning: versions_released.yaml not found, skipping softlink creation"
        return
    fi

    echo "Creating halif library softlinks..."
    while IFS= read -r line; do
        if [[ "$line" =~ ^components: ]]; then
            in_components=1
            continue
        fi
        if [[ $in_components -eq 1 ]]; then
            if [[ "$line" =~ ^[[:space:]]+([A-Za-z0-9_]+):[[:space:]]*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+) ]]; then
                local module="${BASH_REMATCH[1]}"
                local version="${BASH_REMATCH[2]}"
                local versioned="lib${module}-v${version}-cpp.so"
                local vts="lib${module}-cpp_vts.so"
                # Only act on a still-pristine build output; skip if already renamed
                # (e.g. versioned name is already a symlink from a prior run).
                if [ -f "${LIB_DIR}/${versioned}" ] && [ ! -L "${LIB_DIR}/${versioned}" ]; then
                    mv "${LIB_DIR}/${versioned}" "${LIB_DIR}/${vts}"
                    ln -sf "${vts}" "${LIB_DIR}/${versioned}"
                    echo "  ${versioned} -> ${vts} (SONAME still says ${versioned} - patchelf step dropped)"
                fi
            elif [[ "$line" =~ ^[^[:space:]] && ! "$line" =~ ^# ]]; then
                in_components=0
            fi
        fi
    done < "$YAML"

    # Write exact include/lib paths captured now, since Makefile wildcards can't see them before build.sh runs
    local MK_FILE="${RDK_HAL_DIR}/out/halif_generated.mk"
    local mk_inc_dirs mk_module_libs
    mk_inc_dirs=$(find "${RDK_HAL_DIR}/out/build/include" -mindepth 3 -maxdepth 3 \
        -type d -name "include" 2>/dev/null | tr '\n' ' ' | sed 's/ $//')
    mk_module_libs=$(find "${LIB_DIR}" -maxdepth 1 -type f -name 'lib*-cpp_vts.so' \
        2>/dev/null | sed 's|.*/lib\(.*\)\.so|-l\1|' | tr '\n' ' ' | sed 's/ $//')
    {
        echo "# Auto-generated by build.sh create_halif_softlinks() — do not edit"
        echo "HALIF_INC_DIRS    := ${mk_inc_dirs}"
        echo "HALIF_MODULE_LIBS := ${mk_module_libs}"
    } > "${MK_FILE}"
    echo "  Generated ${MK_FILE}"
}
###############################################################################
# Clone rdk-halif-aidl or switch branches; invalidates the halif modules sentinel on a branch change.
###############################################################################
checkout_halif_repo()
{
    if [ ! -d "$RDK_HAL_DIR" ]; then
        echo "Cloning rdk-halif-aidl (branch: $RDK_HALIF_AIDL_VERSION)..."
        git clone -b "$RDK_HALIF_AIDL_VERSION" https://github.com/rdkcentral/rdk-halif-aidl.git "$RDK_HAL_DIR" || {
            echo "ERROR: Failed to clone rdk-halif-aidl."
            exit 1
        }
    else
        # Undo our build_binder.sh patch first so branch checkout isn't blocked by local edits
        git -C "$RDK_HAL_DIR" checkout -- build_binder.sh 2>/dev/null || true

        git -C "$RDK_HAL_DIR" fetch origin "$RDK_HALIF_AIDL_VERSION" || {
            echo "ERROR: Failed to fetch ${RDK_HALIF_AIDL_VERSION}."
            exit 1
        }

        # Compare resolved commits, not ref names: rev-parse --abbrev-ref HEAD returns the
        # literal string "HEAD" for a detached checkout (tags/commit SHAs), which would never
        # match RDK_HALIF_AIDL_VERSION and would force a needless re-checkout - and halif-modules
        # rebuild - on every run.
        local current_commit target_commit
        current_commit=$(git -C "$RDK_HAL_DIR" rev-parse HEAD 2>/dev/null)
        target_commit=$(git -C "$RDK_HAL_DIR" rev-parse FETCH_HEAD 2>/dev/null)

        if [ -n "${target_commit}" ] && [ "${current_commit}" = "${target_commit}" ]; then
            echo "rdk-halif-aidl already on '${RDK_HALIF_AIDL_VERSION}' (${target_commit})"
        else
            echo "rdk-halif-aidl is on '${current_commit}', switching to '${RDK_HALIF_AIDL_VERSION}' (${target_commit})..."
            git -C "$RDK_HAL_DIR" checkout "$RDK_HALIF_AIDL_VERSION" || {
                echo "ERROR: Failed to checkout branch ${RDK_HALIF_AIDL_VERSION}."
                exit 1
            }
            # Version changed — invalidate the halif modules stamp so they are rebuilt.
            rm -f "${RDK_HAL_DIR}/out/target/lib/rdk-halif-aidl/.halif_modules_ready"
        fi
    fi

    if [ "${TARGET}" = "linux" ]; then
        # Force 64-bit binder protocol; vendored default is 32-bit and mismatches a 64-bit vdevice kernel
        sed -i 's/-DBUILD_HOST_AIDL=ON/-DBUILD_HOST_AIDL=ON -DTARGET_LIB64_VERSION=ON/' \
            "${RDK_HAL_DIR}/build_binder.sh"
    fi
}

###############################################################################
# Set up the Binder SDK required by build_modules.sh; sets BINDER_SDK_DIR.
###############################################################################
setup_binder_sdk()
{
    # build_binder.sh must run first - build_modules.sh's preflight check needs out/target/lib/binder to exist.
    local binder_toolchain_dir="${RDK_HAL_DIR}/build-tools/linux_binder_idl"

    if [ "${TARGET}" = "arm" ]; then
        if [ -n "${BINDER_SDK_DIR:-}" ]; then
            return
        fi

        if [ -n "${OECORE_TARGET_SYSROOT:-}" ] && [ -d "${OECORE_TARGET_SYSROOT}/usr/lib/binder" ]; then
            export BINDER_SDK_DIR="${OECORE_TARGET_SYSROOT}/usr"
            echo "ARM build: using OE sysroot binder SDK at ${BINDER_SDK_DIR}"
            return
        fi

        # Step 1: build AIDL host tools with x86 compiler; clear cross-compile/OECORE env so cmake installs run
        echo "ARM build: building AIDL host tools with x86 compiler..."
        local _CC="${CC:-}" _CXX="${CXX:-}" _CFLAGS="${CFLAGS:-}"
        local _CXXFLAGS="${CXXFLAGS:-}" _LDFLAGS="${LDFLAGS:-}"
        local _ARCH="${ARCH:-}" _CMAKE_TOOLCHAIN_FILE="${CMAKE_TOOLCHAIN_FILE:-}"
        local _OECORE_NATIVE="${OECORE_NATIVE_SYSROOT:-}"
        local _OECORE_TARGET="${OECORE_TARGET_SYSROOT:-}"
        unset CC CXX CFLAGS CXXFLAGS LDFLAGS ARCH CMAKE_TOOLCHAIN_FILE
        unset OECORE_NATIVE_SYSROOT OECORE_TARGET_SYSROOT
        (
            export M4=/usr/bin/m4
            cd "${RDK_HAL_DIR}"
            ./build_binder.sh
        ) || {
            echo "ERROR: build_binder.sh (host tools) failed."
            exit 1
        }
        # Restore ARM cross-compile environment.
        [ -n "${_CC}" ]                   && export CC="${_CC}"
        [ -n "${_CXX}" ]                  && export CXX="${_CXX}"
        [ -n "${_CFLAGS}" ]               && export CFLAGS="${_CFLAGS}"
        [ -n "${_CXXFLAGS}" ]             && export CXXFLAGS="${_CXXFLAGS}"
        [ -n "${_LDFLAGS}" ]              && export LDFLAGS="${_LDFLAGS}"
        [ -n "${_ARCH}" ]                 && export ARCH="${_ARCH}"
        [ -n "${_CMAKE_TOOLCHAIN_FILE}" ] && export CMAKE_TOOLCHAIN_FILE="${_CMAKE_TOOLCHAIN_FILE}"
        [ -n "${_OECORE_NATIVE}" ]        && export OECORE_NATIVE_SYSROOT="${_OECORE_NATIVE}"
        [ -n "${_OECORE_TARGET}" ]        && export OECORE_TARGET_SYSROOT="${_OECORE_TARGET}"

        # Step 2: remove Step 1's .sdk_ready so build_arm_binder() doesn't skip itself, then cross-compile
        rm -f "${RDK_HAL_DIR}/out/target/.sdk_ready"
        echo "ARM build: cross-compiling ARM binder runtime..."
        build_arm_binder
        export BINDER_SDK_DIR="${RDK_HAL_DIR}/out/target"
    else
        # Linux: always call build_binder.sh first so linux_binder_idl/aidl_ops.py exist
        # before build_modules.sh's preflight check; it's a no-op if the SDK is up to date.
        if [ -d "${binder_toolchain_dir}" ] && [ ! -d "${binder_toolchain_dir}/.git" ]; then
            echo "Removing incomplete toolchain stub before fresh clone..."
            rm -rf "${binder_toolchain_dir}"
        fi
        (
            cd "${RDK_HAL_DIR}"
            ./build_binder.sh
        ) || {
            echo "ERROR: build_binder.sh failed. Cannot continue."
            exit 1
        }
    fi
}

###############################################################################
# Build HAL modules from versions_released.yaml; skips if .halif_modules_ready sentinel exists.
###############################################################################
build_halif_modules()
{
    local HALIF_LIB_DIR="${RDK_HAL_DIR}/out/target/lib/rdk-halif-aidl"
    local HALIF_READY="${HALIF_LIB_DIR}/.halif_modules_ready"

    if [ -f "${HALIF_READY}" ]; then
        echo "HAL module .so files already present, skipping build_modules.sh..."
        create_halif_softlinks
        return
    fi

    echo "Building HAL modules from versions_released.yaml..."
    local manifest_file="${RDK_HAL_DIR}/versions_released.yaml"
    local sdk_dir_arg=""
    if [ "${TARGET}" = "arm" ] && [ -n "${BINDER_SDK_DIR:-}" ]; then
        sdk_dir_arg="--sdk-dir ${BINDER_SDK_DIR}"
    fi
    (
        cd "${RDK_HAL_DIR}"
        # Bypass build_modules.sh's Yocto/cross-toolchain guard: our ARM binder SDK is already cross-compiled correctly
        if [ "${TARGET}" = "arm" ]; then
            export BINDER_ALLOW_CROSS_ENV=1
        fi
        ./build_modules.sh manifest --file "${manifest_file}" ${sdk_dir_arg}
    ) || {
        echo -e "${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to build HAL modules. Exiting.${RESET}"
        echo -e "${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
        exit 1
    }
    create_halif_softlinks
    touch "${HALIF_READY}"
}

###############################################################################
# Clone rdk-halif-aidl, set up its Binder SDK, and build HAL modules from it.
###############################################################################
generate_hal_interfaces()
{
    checkout_halif_repo
    setup_binder_sdk
    build_halif_modules
}

###############################################################################
# Function to clone and build the ut-core repository
###############################################################################
build_ut_core()
{
    if [ ! -d ${UT_CORE_DIR} ]; then
        git clone https://github.com/rdkcentral/ut-core.git ${UT_CORE_DIR}
        if [ $? -ne 0 ]; then
            echo "Failed to clone the repository. Exiting."
            exit 1
        fi
    fi

    pushd ${UT_CORE_DIR}

    git fetch -q -t origin
    if [ $? -ne 0 ]; then
        echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to fetch ut-core. Exiting.${RESET}            ${BOLD}*${RESET}"
        echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
        exit 1
    fi

    git checkout $UT_CORE_VERSION
    if [ $? -ne 0 ]; then
        echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to checkout ut-core version '$UT_CORE_VERSION'. Exiting.${RESET}"
        echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
        exit 1
    fi

    # Use the user-provided TARGET or default to 'linux'
    ./build.sh TARGET=$TARGET VARIANT=CPP
    if [ $? -ne 0 ]; then
        echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to build the UT Core. Exiting.${RESET}        ${BOLD}*${RESET}"
        echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
        exit 1
    fi

    popd
}

###############################################################################
# Function to generate the avbufferhelper skeleton
###############################################################################
generate_avbufferhelper_skeleton()
{
    # generic stub used for both targets; real HW/vdevice middleware supplies its own
    # implementation at runtime, this is only a link-time placeholder (stripped by install_test())
    local AVBUFFER_HELPER_DIR=${COMMON_DIR}/avbufferhelper_skeleton
    local AVBUFFER_READY="${BUILD_INSTALL_PREFIX}/lib/.avbufferhelper_ready"

    if [ -f "${AVBUFFER_READY}" ]; then
        echo "avbufferhelper skeleton already built, skipping..."
        return
    fi

    local AVBUFFER_VERSION
    AVBUFFER_VERSION=$(get_halif_component_version "avbuffer")
    echo "Using avbuffer interface version: ${AVBUFFER_VERSION}"

    mkdir -p $AVBUFFER_HELPER_DIR/build
    cd $AVBUFFER_HELPER_DIR/build

    cmake -DAVBUFFER_VERSION="${AVBUFFER_VERSION}" ..
    if [ $? -ne 0 ]; then
        echo -e "${BOLD}╔═══════════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to generate av buffer skeleton. Exiting.${RESET}"
        echo -e "${BOLD}╚═══════════════════════════════════════════════════╝${RESET}"
        exit 1
    fi

    make
    if [ $? -ne 0 ]; then
        echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to generate av buffer skeleton Lib. Exiting.${RESET}"
        echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${RESET}"
        exit 1
    fi

    cp libavbufferhelper.so ${TOP_BUILD_DIR}/usr/lib/
    if [ $? -ne 0 ]; then
        echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to install libavbufferhelper.so. Exiting.${RESET}"
        echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${RESET}"
        exit 1
    fi

    install -m 644 "${RDK_HAL_DIR}/avbuffer/${AVBUFFER_VERSION}/avbufferhelper.h" "${BUILD_INSTALL_PREFIX}/include/"
    if [ $? -ne 0 ]; then
        echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to install avbufferhelper.h. Exiting.${RESET}"
        echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${RESET}"
        exit 1
    fi

    touch "${AVBUFFER_READY}"
    cd -
    rm -rf $AVBUFFER_HELPER_DIR/build
}

###############################################################################
# Function to Build HALIF test
###############################################################################
build_halif_test()
{
    # Build the tests
    make -j`nproc` -C ${TOP} TARGET=$TARGET VARIANT=CPP
    if [ $? -ne 0 ]; then
        echo -e "${BOLD}╔════════════════════════════════════════════╗${RESET}"
        echo -e "${BOLD}* ${RED}Failed to build the main tests. Exiting.${RESET}"
        echo -e "${BOLD}╚════════════════════════════════════════════╝${RESET}"
        exit 1
    fi
}

###############################################################################
# Function to install test binaries and scripts to the build directory
###############################################################################
install_test()
{
    declare -r INSTALL_PATH=${TOP_BUILD_DIR}/bin
    declare -r INSTALL_LIB_PATH=${INSTALL_PATH}/lib

    mkdir -p ${INSTALL_LIB_PATH}

    install -t ${INSTALL_PATH} ${TOP_BUILD_DIR}/usr/bin/*
    install -t ${INSTALL_LIB_PATH} ${TOP_BUILD_DIR}/usr/lib/*
    install -t ${INSTALL_PATH} run.sh

    # Remove gstreamer and egl libraries from the install path (not needed in final tar)
    rm -rf ${INSTALL_LIB_PATH}/libgst*  ${INSTALL_LIB_PATH}/libEGL* ${INSTALL_LIB_PATH}/libGL* ${INSTALL_LIB_PATH}/libMali* ${INSTALL_LIB_PATH}/libwayland* ${INSTALL_LIB_PATH}/libgbm* ${INSTALL_LIB_PATH}/libgio*

    cp -r ${PROFILES_DIR} ${INSTALL_PATH}

    for component in "${HALIF_TEST_COMPONENTS[@]}"; do
        if [ -d "${RDK_HAL_TEST_DIR}/${component}/${component}_test_configuration" ]; then
            cp -rf ${RDK_HAL_TEST_DIR}/${component}/${component}_test_configuration ${INSTALL_PATH}/
        fi
        # Fallback for older components still using the plain (unprefixed) name.
        if [ -d "${RDK_HAL_TEST_DIR}/${component}/test_configuration" ]; then
            cp -rf ${RDK_HAL_TEST_DIR}/${component}/test_configuration ${INSTALL_PATH}/
        fi
        if [ -d "${RDK_HAL_TEST_DIR}/${component}/stream_configuration" ]; then
            cp -rf ${RDK_HAL_TEST_DIR}/${component}/stream_configuration ${INSTALL_PATH}/
        fi
        if [ -d "${RDK_HAL_TEST_DIR}/${component}/${component}_stream_configuration" ]; then
            cp -rf ${RDK_HAL_TEST_DIR}/${component}/${component}_stream_configuration ${INSTALL_PATH}/
        fi
        if [ -d "${RDK_HAL_TEST_DIR}/${component}/profiles" ]; then
            cp -rf ${RDK_HAL_TEST_DIR}/${component}/profiles ${INSTALL_PATH}/
        fi
    done
    if [ -d "${L4_TEST_DIR}/av_test_configurations" ]; then
        cp -rf ${L4_TEST_DIR}/av_test_configurations ${INSTALL_PATH}/
    fi

    # Consolidated mock-only config for videodecoder lives under mockservice/config/
    # (not videodecoder_test_configuration/, since it's mock-specific, not shared with
    # real-device testing). Install it alongside the real config so the relative path
    # getVideoDecoderTestConfigPath() builds still resolves at runtime.
    if [ -f "${RDK_HAL_TEST_DIR}/videodecoder/mockservice/config/L3_stream_mock.yaml" ]; then
        mkdir -p ${INSTALL_PATH}/videodecoder_test_configuration
        cp -f ${RDK_HAL_TEST_DIR}/videodecoder/mockservice/config/L3_stream_mock.yaml ${INSTALL_PATH}/videodecoder_test_configuration/
    fi

    # Install halif module libs from the snapshot build
    local HALIF_LIB_DIR="${RDK_HAL_DIR}/out/target/lib/rdk-halif-aidl"
    if [ -d "${HALIF_LIB_DIR}" ]; then
        find "${HALIF_LIB_DIR}" -maxdepth 1 -name "*.so" \
            -exec cp -a {} "${INSTALL_LIB_PATH}/" \; 2>/dev/null || true
    fi

    mkdir -p ${INSTALL_PATH}/assets/streams/input
    mkdir -p ${INSTALL_PATH}/assets/streams/reference
    rm -rf ${INSTALL_LIB_PATH}/libavbufferhelper.so

    # Drop the generic binder runtime libs - device already provides these. The trailing "*"
    # also catches SONAME-versioned variants (e.g. libbinder.so.1) that install_linux_binder()
    # may have staged alongside the unversioned names.
    rm -rf ${INSTALL_LIB_PATH}/libbinder.so* ${INSTALL_LIB_PATH}/libutils.so* ${INSTALL_LIB_PATH}/liblog.so* \
           ${INSTALL_LIB_PATH}/libcutils.so* ${INSTALL_LIB_PATH}/libcutils_sockets.so* ${INSTALL_LIB_PATH}/libbase.so*

    cd ${TOP_BUILD_DIR}
    tar -zcf ${OUT_TAR_FILE} bin
    cd -
}

###############################################################################
# Function to clean the test build directory
###############################################################################
clean_test()
{
    rm -rf ${TOP}/test/*.o
    for component in "${HALIF_TEST_COMPONENTS[@]}"; do
        rm -rf ${RDK_HAL_TEST_DIR}/${component}/mockservice/src/*.o
        rm -rf ${RDK_HAL_TEST_DIR}/${component}/src/*.o
    done

    rm -rf ${AV_L4_TEST_DIR}/*.o
    rm -rf ${COMMON_DIR}/helper_functions/*.o
    rm -rf ${COMMON_DIR}/vts_player/*.o

    find "$TOP_BUILD_DIR" -type f -name "*.o" -delete

    # Remove build output directories (binaries, libs including libbinder.so copies).
    rm -rf "${TOP_BUILD_DIR}/linux"
    rm -rf "${TOP_BUILD_DIR}/arm"
    rm -rf "${TOP_BUILD_DIR}/bin"
    rm -rf "${TOP_BUILD_DIR}/usr"

    # Remove HAL snapshot cmake build dirs, binder SDK build, and installed out/.
    rm -rf "${RDK_HAL_DIR}/build"
    rm -rf "${RDK_HAL_DIR}/out"

    # Clean ut-core compiled objects so ut_log.c recompiles with the correct UT_LOG_LEVEL
    if [ -d "${UT_CORE_DIR}/framework/ut-control" ]; then
        make -C "${UT_CORE_DIR}/framework/ut-control" TARGET=${TARGET} clean 2>/dev/null || true
    fi
}
###############################################################################
# Function to clean the test build directory
###############################################################################
dist_clean_test()
{
    clean_test
    rm -rf $TOP_BUILD_DIR
    rm -rf $RDK_HAL_DIR
    rm -rf ${UT_CORE_DIR}
    rm -rf $RDK_HAL_TEST_DIR
    rm -rf .repo
}

###############################################################################
# help function to display usage information
###############################################################################
help()
{
    echo -e "${BOLD}${CYAN}Usage:${RESET}"

    echo -e "${BOLD}╔════════════════════════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}* ${GREEN}$0 Target=<target>${RESET} ${YELLOW}- Builds the test for specified target (arm, linux)${RESET} ${BOLD}*${RESET}"
    echo -e "${BOLD}* ${GREEN}$0 clean${RESET}           ${YELLOW}- Cleans the build folder${RESET}                           ${BOLD}*${RESET}"
    echo -e "${BOLD}* ${GREEN}$0 dist_clean${RESET}      ${YELLOW}- Deletes all build and checkout folders${RESET}            ${BOLD}*${RESET}"
    echo -e "${BOLD}* ${GREEN}$0 help/-h/--help${RESET}  ${YELLOW}- Prints this message${RESET}                               ${BOLD}*${RESET}"
    echo -e "${BOLD}* ${GREEN}FORCE_REPO_SYNC=1${RESET}  ${YELLOW}- Re-syncs the manifest even if already checked out${RESET}       ${BOLD}*${RESET}"
    echo -e "${BOLD}╚════════════════════════════════════════════════════════════════════════════════╝${RESET}"
}

echo -e "${BOLD}${GREEN}VTS Unified Version    : ${RESET}${YELLOW}$(git rev-parse --abbrev-ref HEAD)${RESET}"
echo -e "${BOLD}${GREEN}UT_CORE_VERSION        : ${RESET}${YELLOW}$UT_CORE_VERSION${RESET}"
echo -e "${BOLD}${GREEN}RDK_HALIF_AIDL_VERSION : ${RESET}${YELLOW}$RDK_HALIF_AIDL_VERSION${RESET}"
echo -e "${BOLD}${GREEN}RDK_HAL_DIR            : ${RESET}${YELLOW}$RDK_HAL_DIR${RESET}"
if [ "${ENABLE_AV_L4_TEST}" = "1" ]; then
echo -e "${BOLD}${GREEN}GST_LIB_PATH           : ${RESET}${YELLOW}$GST_LIB_PATH${RESET}"
fi
if [ "${ENABLE_PLANE_CONTROL_TEST}" = "1" ]; then
echo -e "${BOLD}${GREEN}EGL_LIB_PATH           : ${RESET}${YELLOW}$EGL_LIB_PATH${RESET}"
fi
echo -e "${BOLD}${GREEN}TARGET                 : ${RESET}${YELLOW}$TARGET${RESET}"

###############################################################################
# Main script execution starts here
###############################################################################
if [ "$1" == "clean" ]; then
    clean_test
elif [ "$1" == "dist_clean" ]; then
    dist_clean_test
elif [ "$1" == "help" ] || [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    help
elif [[ "$1" == [Tt]arget=* ]]; then
    validate_repo_tool
    if [ "${TARGET}" = "arm" ]; then
        validate_cross_compiler
    fi
    if [ "${ENABLE_AV_L4_TEST}" = "1" ]; then
        validate_gst_lib_path
    fi
    if [ "${ENABLE_PLANE_CONTROL_TEST}" = "1" ]; then
        validate_egl_lib_path
    fi
    unified_manifest || {
        echo -e "${BOLD}${RED}Failed to sync unified manifest. Exiting.${RESET}"
        exit 1
    }
    generate_hal_interfaces
    install_linux_binder
    if [ "${ENABLE_AV_L4_TEST}" = "1" ]; then
        install_gstreamer_package
    fi
    if [ "${ENABLE_PLANE_CONTROL_TEST}" = "1" ]; then
        install_egl_package
    fi
    build_ut_core
    generate_avbufferhelper_skeleton
    build_halif_test
    install_test
    validate_yaml_profiles_non_blocking
else
    echo -e "${BOLD}${RED}Invalid Arguments${RESET}"
    help
fi
