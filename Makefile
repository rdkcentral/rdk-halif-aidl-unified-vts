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

TARGET ?= linux
VARIANT := CPP

ROOT_DIR := $(CURDIR)
VTS_TEST_DIR := $(ROOT_DIR)/vts_hal_test_components
AUDIO_DECODER_TEST_DIR := $(VTS_TEST_DIR)/audiodecoder
AUDIO_SINK_TEST_DIR := $(VTS_TEST_DIR)/audiosink
VIDEO_DECODER_TEST_DIR := $(VTS_TEST_DIR)/videodecoder
VIDEO_SINK_TEST_DIR := $(VTS_TEST_DIR)/videosink
AV_BUFFER_TEST_DIR := $(VTS_TEST_DIR)/avbuffer
AV_CLOCK_TEST_DIR := $(VTS_TEST_DIR)/avclock
PLANE_CONTROL_TEST_DIR := $(VTS_TEST_DIR)/planecontrol
L4_TEST_DIR := $(VTS_TEST_DIR)/l4_tests
AV_L4_TESTS_DIR := $(L4_TEST_DIR)/src/av
HDMICEC_TEST_DIR := $(VTS_TEST_DIR)/hdmicec
HDMIINPUT_TEST_DIR := $(VTS_TEST_DIR)/hdmiinput
HDMIOUTPUT_TEST_DIR := $(VTS_TEST_DIR)/hdmioutput
DEEPSLEEP_TEST_DIR := $(VTS_TEST_DIR)/deepsleep
DEVICEINFO_TEST_DIR := $(VTS_TEST_DIR)/deviceinfo
BOOT_TEST_DIR := $(VTS_TEST_DIR)/boot
FLASH_TEST_DIR := $(VTS_TEST_DIR)/flash
INDICATOR_TEST_DIR := $(VTS_TEST_DIR)/indicator
AUDIOMIXER_TEST_DIR := $(VTS_TEST_DIR)/audiomixer
CDM_TEST_DIR := $(VTS_TEST_DIR)/cdm
BROADCAST_TEST_DIR := $(VTS_TEST_DIR)/broadcast
PANEL_TEST_DIR := $(VTS_TEST_DIR)/panel
FARFIELDVOICE_TEST_DIR := $(VTS_TEST_DIR)/farfieldvoice

COMMON_DIR := $(ROOT_DIR)/common
VTS_PLAYER := $(COMMON_DIR)/vts_player
HELPER_FUNCTIONS_DIR := $(COMMON_DIR)/helper_functions
BIN_DIR := $(ROOT_DIR)/build/bin
LIB_DIR := $(ROOT_DIR)/build/$(TARGET)/lib
BUILD_DIR := $(ROOT_DIR)/build/$(TARGET)/obj

TARGET_EXEC := vts_hal_test


# Get overall project version from .repo/manifests
MANIFEST_DIR := $(ROOT_DIR)/.repo/manifests
ifneq ($(wildcard $(MANIFEST_DIR)/.git),)
	VERSION := $(shell cd $(MANIFEST_DIR) && git describe --tags --always 2>/dev/null || echo "unknown")
else
	VERSION := unknown
$(warning Manifest directory $(MANIFEST_DIR) not found or not a Git repository. Using VERSION=unknown)
endif
$(info PROJECT_VERSION: $(VERSION))


# Define module versions (use main VERSION if no distinct tags)
AUDIODECODER_VERSION := $(shell cd $(AUDIO_DECODER_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
AUDIOSINK_VERSION := $(shell cd $(AUDIO_SINK_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
VIDEODECODER_VERSION := $(shell cd $(VIDEO_DECODER_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
VIDEOSINK_VERSION := $(shell cd $(VIDEO_SINK_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
AVBUFFER_VERSION := $(shell cd $(AV_BUFFER_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
AVCLOCK_VERSION := $(shell cd $(AV_CLOCK_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
PLANECONTROL_VERSION := $(shell cd $(PLANE_CONTROL_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
HDMICEC_VERSION := $(shell cd $(HDMICEC_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
HDMIINPUT_VERSION := $(shell cd $(HDMIINPUT_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
HDMIOUTPUT_VERSION := $(shell cd $(HDMIOUTPUT_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
DEEPSLEEP_VERSION := $(shell cd $(DEEPSLEEP_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
DEVICEINFO_VERSION := $(shell cd $(DEVICEINFO_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
BOOT_VERSION := $(shell cd $(BOOT_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
FLASH_VERSION := $(shell cd $(FLASH_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
INDICATOR_VERSION := $(shell cd $(INDICATOR_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
AUDIOMIXER_VERSION := $(shell cd $(AUDIOMIXER_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
CDM_VERSION := $(shell cd $(CDM_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
BROADCAST_VERSION := $(shell cd $(BROADCAST_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
PANEL_VERSION := $(shell cd $(PANEL_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
FARFIELDVOICE_VERSION := $(shell cd $(FARFIELDVOICE_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
L4_TESTS_VERSION := $(shell cd $(L4_TEST_DIR) && git describe --tags --always 2>/dev/null || echo "$(VERSION)")
BUILD_TIMESTAMP := $(shell date +"%Y-%m-%d_%H:%M:%S")

# Print module versions
$(info AUDIODECODER_VERSION: $(AUDIODECODER_VERSION))
$(info AUDIOSINK_VERSION: $(AUDIOSINK_VERSION))
$(info VIDEODECODER_VERSION: $(VIDEODECODER_VERSION))
$(info VIDEOSINK_VERSION: $(VIDEOSINK_VERSION))
$(info AVBUFFER_VERSION: $(AVBUFFER_VERSION))
$(info AVCLOCK_VERSION: $(AVCLOCK_VERSION))
$(info PLANECONTROL_VERSION: $(PLANECONTROL_VERSION))
$(info HDMICEC_VERSION: $(HDMICEC_VERSION))
$(info HDMIINPUT_VERSION: $(HDMIINPUT_VERSION))
$(info HDMIOUTPUT_VERSION: $(HDMIOUTPUT_VERSION))
$(info DEEPSLEEP_VERSION: $(DEEPSLEEP_VERSION))
$(info DEVICEINFO_VERSION: $(DEVICEINFO_VERSION))
$(info BOOT_VERSION: $(BOOT_VERSION))
$(info FLASH_VERSION: $(FLASH_VERSION))
$(info INDICATOR_VERSION: $(INDICATOR_VERSION))
$(info AUDIOMIXER_VERSION: $(AUDIOMIXER_VERSION))
$(info CDM_VERSION: $(CDM_VERSION))
$(info BROADCAST_VERSION: $(BROADCAST_VERSION))
$(info PANEL_VERSION: $(PANEL_VERSION))
$(info FARFIELDVOICE_VERSION: $(FARFIELDVOICE_VERSION))
$(info L4_TESTS_VERSION: $(L4_TESTS_VERSION))
$(info BUILD_TIMESTAMP: $(BUILD_TIMESTAMP))
$(info TARGET: $(TARGET))
$(info VARIANT: $(VARIANT))

# Read RDK_HALIF_AIDL_VERSION from environment, default to 'main'
RDK_HALIF_AIDL_VERSION ?= main
$(info RDK_HALIF_AIDL_VERSION: $(RDK_HALIF_AIDL_VERSION))

# Compiler flags with version and debug info
CXXFLAGS := -std=c++17 -g3 -O0 -Wno-unknown-pragmas -Wno-attributes\
            -DHALIF_TEST_PROJECT_VERSION=\"$(VERSION)\" \
            -DRDK_HALIF_AIDL_VERSION=\"$(RDK_HALIF_AIDL_VERSION)\" \
            -DAUDIODECODER_VERSION=\"$(AUDIODECODER_VERSION)\" \
            -DAUDIOSINK_VERSION=\"$(AUDIOSINK_VERSION)\" \
            -DVIDEODECODER_VERSION=\"$(VIDEODECODER_VERSION)\" \
            -DVIDEOSINK_VERSION=\"$(VIDEOSINK_VERSION)\" \
            -DAVBUFFER_VERSION=\"$(AVBUFFER_VERSION)\" \
            -DAVCLOCK_VERSION=\"$(AVCLOCK_VERSION)\" \
            -DPLANECONTROL_VERSION=\"$(PLANECONTROL_VERSION)\" \
            -DHDMICEC_VERSION=\"$(HDMICEC_VERSION)\" \
            -DHDMIINPUT_VERSION=\"$(HDMIINPUT_VERSION)\" \
            -DHDMIOUTPUT_VERSION=\"$(HDMIOUTPUT_VERSION)\" \
            -DDEEPSLEEP_VERSION=\"$(DEEPSLEEP_VERSION)\" \
            -DDEVICEINFO_VERSION=\"$(DEVICEINFO_VERSION)\" \
            -DBOOT_VERSION=\"$(BOOT_VERSION)\" \
            -DFLASH_VERSION=\"$(FLASH_VERSION)\" \
            -DINDICATOR_VERSION=\"$(INDICATOR_VERSION)\" \
            -DAUDIOMIXER_VERSION=\"$(AUDIOMIXER_VERSION)\" \
            -DCDM_VERSION=\"$(CDM_VERSION)\" \
            -DBROADCAST_VERSION=\"$(BROADCAST_VERSION)\" \
            -DPANEL_VERSION=\"$(PANEL_VERSION)\" \
            -DFARFIELDVOICE_VERSION=\"$(FARFIELDVOICE_VERSION)\" \
            -DL4_TESTS_VERSION=\"$(L4_TESTS_VERSION)\"

$(info CXXFLAGS: $(CXXFLAGS))
CXXFLAGS += -DBUILD_TIMESTAMP=\"$(BUILD_TIMESTAMP)\"


# Add CXXFLAGS if ENABLE_PLANE_CONTROL_TEST is set
ifeq ($(ENABLE_PLANE_CONTROL_TEST),1)
CXXFLAGS += -DENABLE_PLANE_CONTROL_TEST
endif

ifeq ($(ENABLE_AV_L4_TEST),1)
CXXFLAGS += -DENABLE_AV_L4_TEST
endif

SRC_DIRS := $(AUDIO_DECODER_TEST_DIR)/src
SRC_DIRS += $(AUDIO_SINK_TEST_DIR)/src
SRC_DIRS += $(AV_BUFFER_TEST_DIR)/src
SRC_DIRS += $(VIDEO_DECODER_TEST_DIR)/src
SRC_DIRS += $(VIDEO_SINK_TEST_DIR)/src
SRC_DIRS += $(AV_CLOCK_TEST_DIR)/src
ifeq ($(ENABLE_PLANE_CONTROL_TEST),1)
SRC_DIRS += $(PLANE_CONTROL_TEST_DIR)/src
endif
SRC_DIRS += $(HDMICEC_TEST_DIR)/src
SRC_DIRS += $(HDMIINPUT_TEST_DIR)/src
SRC_DIRS += $(HDMIOUTPUT_TEST_DIR)/src
SRC_DIRS += $(DEEPSLEEP_TEST_DIR)/src
SRC_DIRS += $(DEVICEINFO_TEST_DIR)/src
SRC_DIRS += $(BOOT_TEST_DIR)/src
#SRC_DIRS += $(FLASH_TEST_DIR)/src
SRC_DIRS += $(INDICATOR_TEST_DIR)/src
SRC_DIRS += $(AUDIOMIXER_TEST_DIR)/src
SRC_DIRS += $(CDM_TEST_DIR)/src
SRC_DIRS += $(BROADCAST_TEST_DIR)/src
SRC_DIRS += $(PANEL_TEST_DIR)/src
SRC_DIRS += $(FARFIELDVOICE_TEST_DIR)/src
ifeq ($(ENABLE_AV_L4_TEST),1)
SRC_DIRS += $(AV_L4_TESTS_DIR)
SRC_DIRS += $(VTS_PLAYER)
endif
SRC_DIRS += $(HELPER_FUNCTIONS_DIR)
SRC_DIRS += $(ROOT_DIR)/test

INC_DIRS := $(ROOT_DIR)/build/current/h/

INC_DIRS += $(ROOT_DIR)/rdk-halif-aidl/avbuffer/current
INC_DIRS += $(ROOT_DIR)/build/usr/include
INC_DIRS += $(ROOT_DIR)/common/avbufferhelper_skeleton/
INC_DIRS += $(SRC_DIRS)
INC_DIRS += $(ROOT_DIR)/common/graphics_libraries/include

# Graphics libraries
INC_DIRS += $(ROOT_DIR)/build/usr/include/EGL/
INC_DIRS += $(ROOT_DIR)/build/usr/include/GLES2/
INC_DIRS += $(ROOT_DIR)/build/usr/include/KHR/


INC_DIRS += $(ROOT_DIR)/build/usr/include/gstreamer-1.0/
INC_DIRS += $(ROOT_DIR)/build/usr/include/glib-2.0/
INC_DIRS += $(ROOT_DIR)/build/usr/lib/glib-2.0/include/

XLDFLAGS := -L$(ROOT_DIR)/build/usr/lib
XLDFLAGS += -Wl,-rpath-link=$(ROOT_DIR)/build/usr/lib
XLDFLAGS += -lbinder -lutils
XLDFLAGS += -laidl_client
XLDFLAGS += -lavbufferhelper
ifeq ($(ENABLE_AV_L4_TEST),1)
XLDFLAGS += -lgstreamer-1.0 -lgobject-2.0 -lglib-2.0 -lgio-2.0 -lpcre
endif
ifeq ($(ENABLE_PLANE_CONTROL_TEST),1)
XLDFLAGS += -lEGL -lGLESv2 -lpthread
XLDFLAGS += -ldrm
endif
# required for EGL
CXXFLAGS += -D_EGL_NO_X11
CXXFLAGS += -DMESA_EGL_NO_X11_HEADERS

# required for std::optional
CXXFLAGS += -std=c++17
CXXFLAGS += -Wall -Wformat -Wno-error=format

UT_CORE_DIR := $(CURDIR)/ut-core

export VARIANT
export BIN_DIR
export LIB_DIR
export BUILD_DIR
export SRC_DIRS
export TARGET_EXEC
export INC_DIRS
export XLDFLAGS
export CXXFLAGS
export TARGET

.PHONY: all clean

all: $(TARGET_EXEC)

$(TARGET_EXEC):
	make -C $(UT_CORE_DIR) -j $(shell nproc) TARGET=$(TARGET) VARIANT=$(VARIANT)

clean:
	make -C $(UT_CORE_DIR) -j TARGET=$(TARGET) VARIANT=$(VARIANT) clean
