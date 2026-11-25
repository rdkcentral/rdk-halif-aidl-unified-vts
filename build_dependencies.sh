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
BOLD='\033[1m'
RESET='\033[0m'

###############################################################################
# Check linux_binder_idl prerequisites
###############################################################################

# Check Ubuntu 22.04
echo "Checking OS..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "${ID}" != "ubuntu" ] || [ "${VERSION_ID}" != "22.04" ]; then
        echo -e "${BOLD}${YELLOW}Warning: Expected Ubuntu 22.04 LTS, detected ${PRETTY_NAME}. Build may not work as expected.${RESET}"
    else
        echo -e "${GREEN}OS OK: ${PRETTY_NAME}${RESET}"
    fi
else
    echo -e "${BOLD}${YELLOW}Warning: Could not detect OS version.${RESET}"
fi

# Update package list
echo "Updating package list..."
sudo apt-get update -y

# Install required packages
echo "Installing required packages..."
sudo apt-get install -y \
    file \
    git \
    gcc \
    g++ \
    zip \
    bzip2 \
    tar \
    libssl-dev \
    cmake \
    make \
    wget \
    flex \
    bison \
    pkg-config

# Verify installation of packages
echo "Verifying installed packages..."
file --version
git --version
gcc --version
g++ --version
zip --version
bzip2 --version
tar --version
cmake --version
make --version
wget --version
flex --version
bison --version
pkg-config --version

# Check CMake >= 3.22.1
echo "Checking CMake version..."
CMAKE_VERSION=$(cmake --version | head -n1 | awk '{print $3}')
if printf '%s\n' "3.22.1" "${CMAKE_VERSION}" | sort -V -C; then
    echo -e "${GREEN}CMake OK: ${CMAKE_VERSION}${RESET}"
else
    echo -e "${BOLD}${RED}Error: CMake ${CMAKE_VERSION} is below the required 3.22.1.${RESET}"
    #exit 1
fi

# Check GCC >= 9.4.0 (recommended >= 11.2.0)
echo "Checking GCC version..."
GCC_VERSION=$(gcc -dumpfullversion)
if printf '%s\n' "9.4.0" "${GCC_VERSION}" | sort -V -C; then
    if ! printf '%s\n' "11.2.0" "${GCC_VERSION}" | sort -V -C; then
        echo -e "${BOLD}${YELLOW}Warning: GCC ${GCC_VERSION} meets the minimum (9.4.0) but recommended is 11.2.0 or later.${RESET}"
    else
        echo -e "${GREEN}GCC OK: ${GCC_VERSION}${RESET}"
    fi
else
    echo -e "${BOLD}${RED}Error: GCC ${GCC_VERSION} is below the minimum required 9.4.0.${RESET}"
    #exit 1
fi

echo "All packages installed successfully!"

# Ensure git identity is set (required for repo init)
echo "Checking git identity..."
GIT_USER=$(git config --global user.name 2>/dev/null)
GIT_EMAIL=$(git config --global user.email 2>/dev/null)
if [ -z "${GIT_USER}" ]; then
    git config --global user.name "Coverity Build"
    GIT_USER="Coverity Build"
    echo -e "${YELLOW}Git user.name not set — defaulting to '${GIT_USER}'${RESET}"
fi
if [ -z "${GIT_EMAIL}" ]; then
    git config --global user.email "coverity@localhost"
    GIT_EMAIL="coverity@localhost"
    echo -e "${YELLOW}Git user.email not set — defaulting to '${GIT_EMAIL}'${RESET}"
fi
echo -e "${GREEN}Git identity OK: ${GIT_USER} <${GIT_EMAIL}>${RESET}"

# Suppress repo init color prompt by pre-configuring git color
git config --global color.ui auto
echo "Checking repo tool..."
if command -v repo >/dev/null; then
    echo -e "${GREEN}repo already installed at $(command -v repo)${RESET}"
else
    echo "Installing repo tool..."
    mkdir -p ~/.local/bin
    curl -o ~/.local/bin/repo https://storage.googleapis.com/git-repo-downloads/repo
    chmod a+rx ~/.local/bin/repo
    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v repo >/dev/null; then
        echo -e "${BOLD}${RED}Error: 'repo' tool installation failed.${RESET}"
        #exit 1
    fi
    echo -e "${GREEN}repo installed at $(command -v repo)${RESET}"
fi

# Ensure ~/.local/bin is in PATH permanently
if ! grep -qF 'HOME/.local/bin' ~/.bashrc 2>/dev/null; then
    echo '' >> ~/.bashrc
    echo '# Added by build_dependencies.sh' >> ~/.bashrc
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo -e "${GREEN}Added ~/.local/bin to PATH in ~/.bashrc${RESET}"
    echo -e "${BOLD}${YELLOW}Note: Run 'source ~/.bashrc' or open a new terminal to apply.${RESET}"
fi
