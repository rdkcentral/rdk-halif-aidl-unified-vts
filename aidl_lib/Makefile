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

.PHONY: all clean

AIDL_LIB_NAME := aidl_client

AIDL_LIB := lib$(AIDL_LIB_NAME).so

BUILD_DIR ?= $(CURDIR)/../build

AIDL_GEN_DIR ?= $(BUILD_DIR)/current

AIDL_SRC_DIR := ${AIDL_GEN_DIR}/cpp/com/rdk/hal/

# Source files
AIDL_SRC := $(shell find $(AIDL_SRC_DIR) -type f \( -name '*.cpp' -o -name '*.c' \))

AIDL_LIB_INC_FLAGS := -I$(AIDL_GEN_DIR)/h
AIDL_LIB_INC_FLAGS += -I$(BUILD_DIR)/usr/include


#AIDL_LIB_LD_LIBS := -lbinder -lutils

AIDL_LIB_LDFLAGS := -L$(BUILD_DIR)/usr/lib
AIDL_LIB_LDFLAGS += -Wl,-rpath-link=$(BUILD_DIR)/usr/lib

# Base CFLAGS, can be overridden by caller
AIDL_LIB_CFLAGS := -Wall -Wextra -Wformat -Wno-error=format -std=c++17 -ggdb

AIDL_LIB := $(BUILD_DIR)/usr/lib/$(AIDL_LIB)


# Set compiler based on TARGET and VARIANT
TARGET ?= linux
VARIANT ?= CPP  # Default to CPP, as used in build.sh
$(info TARGET: $(TARGET))
$(info VARIANT: $(VARIANT))

ifeq ($(TARGET),arm)
COMPILER := $(if $(filter CPP,$(VARIANT)),$(CXX),$(CC))
else
COMPILER := $(if $(filter CPP,$(VARIANT)),g++ -ggdb -o0 -Wall, gcc -ggdb -o0 -Wall)
endif

all: $(AIDL_LIB)

$(AIDL_LIB): $(AIDL_SRC:%.cpp=%.o)
	$(COMPILER) -shared $(AIDL_LIB_LDFLAGS) $^ -o $@ $(AIDL_LIB_LD_LIBS)

%.o: %.cpp
	$(COMPILER) $(AIDL_LIB_CFLAGS) $(AIDL_LIB_INC_FLAGS) -fPIC -c $< -o $@

clean:
	rm -f $(AIDL_SRC:%.cpp=%.o) $(AIDL_SRC:%.c=%.o) $(AIDL_LIB)