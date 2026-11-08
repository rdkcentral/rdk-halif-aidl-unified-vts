/**
 *  If not stated otherwise in this file or this component's LICENSE
 *  file the following copyright and licenses apply:
 *
 *  Copyright 2024 RDK Management
 *
 *  Licensed under the Apache License, Version 2.0 (the License);
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *  http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an AS IS BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

/**
 * @addtogroup HPK Hardware Porting Kit
 * @{
 * @par The Hardware Porting Kit
 * HPK is the next evolution of the well-defined Hardware Abstraction Layer
 * (HAL), but augmented with more comprehensive documentation and test suites
 * that OEM or SOC vendors can use to self-certify their ports before taking
 * them to RDKM for validation or to an operator for final integration and
 * deployment. The Hardware Porting Kit effectively enables an OEM and/or SOC
 * vendor to self-certify their own Video Accelerator devices, with minimal RDKM
 * assistance.
 *
 */

/**
 * @defgroup VTS_HELPER_FUNCTIOS_H VTS helper functions Header File
 * @{
 * @parblock
 *
 * ### Helper functions for VTS tests :
 *
 * Helper functions required for the module across all vendors.
 *
 * **Pre-Conditions:**  None @n
 * **Dependencies:** None @n
 *
 * @endparblock
 *
 */

/**
 * @file vts_audiodecoder_helper_functions.h
 *
 */

#ifndef __VTS_HELPER_H__
#define __VTS_HELPER_H__

#include <ut.h>
#include <ut_kvp_profile.h>
#include <ut_log.h>
#include <ut_control_plane.h>
#include <binder/IServiceManager.h>
#include <binder/ProcessState.h>
#include <binder/IPCThreadState.h>
#include <binder/Status.h>
#include <utils/String16.h>
#include <stdio.h>
#include <vector>
#include <optional>
#include <algorithm>
#include <unordered_set>
#include "com/rdk/hal/audiodecoder/IAudioDecoderManager.h"
#include "com/rdk/hal/audiodecoder/BnAudioDecoderControllerListener.h"
#include "com/rdk/hal/audiodecoder/BnAudioDecoderEventListener.h"
#include "com/rdk/hal/videodecoder/IVideoDecoderManager.h"
#include "com/rdk/hal/videodecoder/Codec.h"

using android::sp;
using android::String16;
using android::defaultServiceManager;
using android::binder::Status;

using namespace com::rdk::hal;
using namespace com::rdk::hal::audiodecoder;

extern const ut_control_keyStringMapping_t statusException_mapTable[];
extern const ut_control_keyStringMapping_t bool_mapTable[];
extern const ut_control_keyStringMapping_t decoder_operationalMode_mapTable[];

size_t vts_bytesPerSample(audiodecoder::PCMFormat format);
//size_t vts_bytesPerPixel(PixelFormat format);
void* vts_kvp_create_instance(char *fileName);
void vts_kvp_destroy_instance(void *instance);
videodecoder::Codec videoDecoderStringToCodec(const std::string& codecStr);
std::vector<std::string> videoDecoderGetAllCodecNames();
audiodecoder::Codec vts_audioDecoder_helper_StringToCodec(const std::string& format);
audiodecoder::PCMFormat vts_audioDecoder_helper_StringToPCMFormat(const std::string& format);

#endif //__VTS_HELPER_H__

/** @} */ // End of VTS_HELPER_FUNCTIOS_H
/** @} */ // End of HPK
