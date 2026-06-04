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
 * @defgroup VTS_HELPER_FUNCTIOS VTS HAL Tests helper functions
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
 * @file vts_helper_functions.cpp
 *
 */

#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <stdio.h>
#include <stdlib.h>
#include "vts_helper_functions.h"

/* Status::Exception */
const ut_control_keyStringMapping_t statusException_mapTable[] =
{
    {"EX_NONE",                  (int32_t) Status::EX_NONE},
    {"EX_SECURITY",              (int32_t) Status::EX_SECURITY},
    {"EX_BAD_PARCELABLE",        (int32_t) Status::EX_BAD_PARCELABLE},
    {"EX_ILLEGAL_ARGUMENT",      (int32_t) Status::EX_ILLEGAL_ARGUMENT},
    {"EX_NULL_POINTER",          (int32_t) Status::EX_NULL_POINTER},
    {"EX_ILLEGAL_STATE",         (int32_t) Status::EX_ILLEGAL_STATE},
    {"EX_NETWORK_MAIN_THREAD",   (int32_t) Status::EX_NETWORK_MAIN_THREAD},
    {"EX_UNSUPPORTED_OPERATION", (int32_t) Status::EX_UNSUPPORTED_OPERATION},
    {"EX_SERVICE_SPECIFIC",      (int32_t) Status::EX_SERVICE_SPECIFIC},
    {"EX_PARCELABLE",            (int32_t) Status::EX_PARCELABLE},
    {"EX_HAS_REPLY_HEADER",      (int32_t) Status::EX_HAS_REPLY_HEADER},
    {"EX_TRANSACTION_FAILED",    (int32_t) Status::EX_TRANSACTION_FAILED},
    {NULL, -1}
};

/* bool */
const ut_control_keyStringMapping_t bool_mapTable[] =
{
    {"false", (int32_t) false},
    {"true",  (int32_t) true},
    {NULL, -1}
};

void* vts_kvp_create_instance(char *fileName)
{
    ut_kvp_instance_t* instance;
    ut_kvp_status_t result;

    UT_LOG("In %s, fileName: %s", __FUNCTION__, fileName ? fileName : "NULL");

    instance = ut_kvp_createInstance();

    if(!instance)
    {
        UT_LOG_ERROR("Failed to create ut kvp instance");
        return nullptr;
    }

    result = ut_kvp_open(instance, fileName);

    if(result != UT_KVP_STATUS_SUCCESS)
    {
        UT_LOG_ERROR("Failed to open test configuration file");
        printf("Coverity test workflow %s \n");
        ut_kvp_destroyInstance(instance);
        return nullptr;
    }

    UT_LOG("Out  %s", __FUNCTION__);

    return (ut_kvp_instance_t*)instance;
}

void vts_kvp_destroy_instance(void *instance)
{
    ut_kvp_destroyInstance((ut_kvp_instance_t*)instance);
}

size_t vts_bytesPerSample(audiodecoder::PCMFormat format)
{
    switch (format) {
        case audiodecoder::PCMFormat::F64LE:
        case audiodecoder::PCMFormat::F64BE: return 8;
        case audiodecoder::PCMFormat::F32LE:
        case audiodecoder::PCMFormat::F32BE: return 4;
        case audiodecoder::PCMFormat::S32LE:
        case audiodecoder::PCMFormat::S32BE:
        case audiodecoder::PCMFormat::U32LE:
        case audiodecoder::PCMFormat::U32BE: return 4;
        case audiodecoder::PCMFormat::S24_32LE:
        case audiodecoder::PCMFormat::S24_32BE:
        case audiodecoder::PCMFormat::U24_32LE:
        case audiodecoder::PCMFormat::U24_32BE: return 4;
        case audiodecoder::PCMFormat::S24LE:
        case audiodecoder::PCMFormat::S24BE:
        case audiodecoder::PCMFormat::U24LE:
        case audiodecoder::PCMFormat::U24BE:
        case audiodecoder::PCMFormat::S20LE:
        case audiodecoder::PCMFormat::S20BE:
        case audiodecoder::PCMFormat::U20LE:
        case audiodecoder::PCMFormat::U20BE:
        case audiodecoder::PCMFormat::S18LE:
        case audiodecoder::PCMFormat::S18BE:
        case audiodecoder::PCMFormat::U18LE:
        case audiodecoder::PCMFormat::U18BE: return 3;
        case audiodecoder::PCMFormat::S16LE:
        case audiodecoder::PCMFormat::S16BE:
        case audiodecoder::PCMFormat::U16LE:
        case audiodecoder::PCMFormat::U16BE: return 2;
        case audiodecoder::PCMFormat::S8:
        case audiodecoder::PCMFormat::U8: return 1;
    }
    return 0;
}

videodecoder::Codec videoDecoderStringToCodec(const std::string& codecStr)
{
    static const std::unordered_map<std::string, videodecoder::Codec> codecMap = {
        {"MPEG2_VIDEO", videodecoder::Codec::MPEG2_VIDEO},
        {"H264_AVC", videodecoder::Codec::H264_AVC},
        {"H265_HEVC", videodecoder::Codec::H265_HEVC},
        {"VP9",  videodecoder::Codec::VP9},
        {"AV1",  videodecoder::Codec::AV1}
    };
    auto it = codecMap.find(codecStr);
    if (it != codecMap.end()) {
        return it->second;
    } else {
        throw std::invalid_argument("Unknown codec: " + codecStr);
    }
}

std::vector<std::string> videoDecoderGetAllCodecNames()
{
    // Return all known codec names in the same order as the AIDL definition
    // This is the single source of truth for codec names used in YAML parsing
    return {"MPEG2_VIDEO", "H264_AVC", "H265_HEVC", "VP9", "AV1"};
}

/*currently HAL FEATURE PROFILE contain string value for codec instead of enum. so the helper required to convert*/
audiodecoder::Codec vts_audioDecoder_helper_StringToCodec(const std::string& format)
{
    static const std::unordered_map<std::string, audiodecoder::Codec> formatMap = {
    {"PCM", audiodecoder::Codec::PCM},
    {"AAC_LC", audiodecoder::Codec::AAC_LC},
    {"HE_AAC", audiodecoder::Codec::HE_AAC},
    {"HE_AAC2", audiodecoder::Codec::HE_AAC2},
    {"AAC_ELD", audiodecoder::Codec::AAC_ELD},
    {"DOLBY_AC3", audiodecoder::Codec::DOLBY_AC3},
    {"DOLBY_AC3_PLUS", audiodecoder::Codec::DOLBY_AC3_PLUS},
    {"DOLBY_AC3_PLUS_JOC", audiodecoder::Codec::DOLBY_AC3_PLUS_JOC},
    {"DOLBY_AC4", audiodecoder::Codec::DOLBY_AC4},
    {"DOLBY_MAT", audiodecoder::Codec::DOLBY_MAT},
    {"DOLBY_MAT2", audiodecoder::Codec::DOLBY_MAT2},
    {"DOLBY_TRUEHD", audiodecoder::Codec::DOLBY_TRUEHD},
    {"MPEG2", audiodecoder::Codec::MPEG2},
    {"MP3", audiodecoder::Codec::MP3},
    {"FLAC", audiodecoder::Codec::FLAC},
    {"VORBIS", audiodecoder::Codec::VORBIS},
    {"DTS", audiodecoder::Codec::DTS},
    {"OPUS", audiodecoder::Codec::OPUS},
    {"WMA", audiodecoder::Codec::WMA},
    {"REALAUDIO", audiodecoder::Codec::REALAUDIO},
    {"USAC", audiodecoder::Codec::USAC},
    {"X_HE_AAC", audiodecoder::Codec::X_HE_AAC},
    {"SBC", audiodecoder::Codec::SBC},
    {"AVS", audiodecoder::Codec::AVS}
    };

    auto it = formatMap.find(format);
    if (it != formatMap.end())
    {
        return it->second;
    }
    return static_cast<audiodecoder::Codec>(-1);
}

audiodecoder::PCMFormat vts_audioDecoder_helper_StringToPCMFormat(const std::string& format)
{
    static const std::unordered_map<std::string, audiodecoder::PCMFormat> formatMap = {
        {"F64LE", audiodecoder::PCMFormat::F64LE},
        {"F64BE", audiodecoder::PCMFormat::F64BE},
        {"F32LE", audiodecoder::PCMFormat::F32LE},
        {"F32BE", audiodecoder::PCMFormat::F32BE},
        {"S32LE", audiodecoder::PCMFormat::S32LE},
        {"S32BE", audiodecoder::PCMFormat::S32BE},
        {"U32LE", audiodecoder::PCMFormat::U32LE},
        {"U32BE", audiodecoder::PCMFormat::U32BE},
        {"S24_32LE", audiodecoder::PCMFormat::S24_32LE},
        {"S24_32BE", audiodecoder::PCMFormat::S24_32BE},
        {"U24_32LE", audiodecoder::PCMFormat::U24_32LE},
        {"U24_32BE", audiodecoder::PCMFormat::U24_32BE},
        {"S24LE", audiodecoder::PCMFormat::S24LE},
        {"S24BE", audiodecoder::PCMFormat::S24BE},
        {"U24LE", audiodecoder::PCMFormat::U24LE},
        {"U24BE", audiodecoder::PCMFormat::U24BE},
        {"S20LE", audiodecoder::PCMFormat::S20LE},
        {"S20BE", audiodecoder::PCMFormat::S20BE},
        {"U20LE", audiodecoder::PCMFormat::U20LE},
        {"U20BE", audiodecoder::PCMFormat::U20BE},
        {"S18LE", audiodecoder::PCMFormat::S18LE},
        {"S18BE", audiodecoder::PCMFormat::S18BE},
        {"U18LE", audiodecoder::PCMFormat::U18LE},
        {"U18BE", audiodecoder::PCMFormat::U18BE},
        {"S16LE", audiodecoder::PCMFormat::S16LE},
        {"S16BE", audiodecoder::PCMFormat::S16BE},
        {"U16LE", audiodecoder::PCMFormat::U16LE},
        {"U16BE", audiodecoder::PCMFormat::U16BE},
        {"S8", audiodecoder::PCMFormat::S8},
        {"U8", audiodecoder::PCMFormat::U8}
    };

    auto it = formatMap.find(format);
    if (it != formatMap.end())
    {
        return it->second;
    }
    return static_cast<audiodecoder::PCMFormat>(-1);
}

/** @} */ // End of VTS_HELPER_FUNCTIOS
/** @} */ // End of HPK
