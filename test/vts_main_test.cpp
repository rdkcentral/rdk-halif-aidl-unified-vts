/**
 *  If not stated otherwise in this file or this component's LICENSE
 *  file the following copyright and licenses apply:
 *
 *  Copyright 2025 RDK Management
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
 * @addtogroup UNIFIED_VTS Unified VTS
 * @{
 */

/**
 * @addtogroup UNIFIED_VTS_Halif_Test Unified VTS HALIF Tests
 * @{
 */

/**
 * @defgroup UNIFIED_VTS_Halif_Test_Main Unified VTS HALIF Tests Main File
 * @{
 * @parblock
 *
 * ### main functions for Unified VTS VTS HALIF AIDL tests :
 *
 *
 *
 * **Pre-Conditions:**  None@n
 * **Dependencies:** None@n
 *
 * Ref to API Definition specification documentation :
 *
 * @endparblock
 */

/**
 * @file vts_main_test.cpp
 *
 */

#include <ut.h>
#include <ut_log.h>
#include "vts_avbuffer_init.h"
#include "vts_audiodecoder_init.h"
#include "vts_audiosink_init.h"
#include "vts_videosink_init.h"
#include "vts_videodecoder_init.h"
#include "vts_avclock_init.h"
#ifdef ENABLE_DRM_TEST
#include "vts_drm_init.h"
#endif
#ifdef ENABLE_PLANE_CONTROL_TEST
#include "vts_planecontrol_init.h"
#endif
#ifdef ENABLE_AV_L4_TEST
#include "vts_av_l4_init.h"
#endif

#include "vts_audiomixer_init.h"
#include "vts_hdmicec_init.h"
#include "vts_hdmiinput_init.h"
#include "vts_hdmioutput_init.h"
#include "vts_deepsleep_init.h"
#include "vts_deviceinfo_init.h"
#include "vts_boot_init.h"
#include "vts_firmwareupdate_init.h"
#include "vts_thermalsensor_init.h"
#include "vts_motionsensor_init.h"
#include "vts_indicator_init.h"
#include "vts_compositeinput_init.h"

int main(int argc, char **argv)
{
    UT_status_t result;

    UT_init(argc, argv);

    UT_LOG("==========================================================================");
    UT_LOG("\t BUILD_TIMESTAMP: \033[0;32m%s\033[0m", BUILD_TIMESTAMP);
    UT_LOG("\t UNIFIED VTS Version: \033[0;32m%s\033[0m", HALIF_TEST_PROJECT_VERSION);
    UT_LOG("\t AIDL HALIF Version: \033[0;32m%s\033[0m",RDK_HALIF_AIDL_VERSION);
    UT_LOG("\t VTS UNIFIED Audio Decoder HALIF Test Version: \033[0;32m%s\033[0m",AUDIODECODER_VERSION);
    UT_LOG("\t VTS UNIFIED Audio Sink HALIF Test Version: \033[0;32m%s\033[0m",AUDIOSINK_VERSION);
    UT_LOG("\t VTS UNIFIED Video Decoder HALIF Test Version: \033[0;32m%s\033[0m",VIDEODECODER_VERSION);
    UT_LOG("\t VTS UNIFIED Video Sink HALIF Test Version: \033[0;32m%s\033[0m",VIDEOSINK_VERSION);
    UT_LOG("\t VTS UNIFIED AVBuffer HALIF Test Version: \033[0;32m%s\033[0m",AVBUFFER_VERSION);
#ifdef ENABLE_DRM_TEST
    UT_LOG("\t VTS UNIFIED DRM HALIF Test Version: \033[0;32m%s\033[0m",DRM_VERSION);
#endif
    UT_LOG("\t VTS UNIFIED AV Clock HALIF Test Version: \033[0;32m%s\033[0m",AVCLOCK_VERSION);
    UT_LOG("\t VTS UNIFIED Plane Control HALIF Test Version: \033[0;32m%s\033[0m",PLANECONTROL_VERSION);
    UT_LOG("\t VTS UNIFIED HALIF L4 Test Version: \033[0;32m%s\033[0m",L4_TESTS_VERSION);
    UT_LOG("\t VTS UNIFIED Audio Mixer HALIF Test Version: \033[0;32m%s\033[0m",AUDIOMIXER_VERSION);
    UT_LOG("\t VTS UNIFIED HDMI CEC HALIF Test Version: \033[0;32m%s\033[0m",HDMICEC_VERSION);
    UT_LOG("\t VTS UNIFIED HDMI Input HALIF Test Version: \033[0;32m%s\033[0m",HDMIINPUT_VERSION);
    UT_LOG("\t VTS UNIFIED HDMI Output HALIF Test Version: \033[0;32m%s\033[0m",HDMIOUTPUT_VERSION);
    UT_LOG("\t VTS UNIFIED Deep Sleep HALIF Test Version: \033[0;32m%s\033[0m",DEEPSLEEP_VERSION);
    UT_LOG("\t VTS UNIFIED Device Info HALIF Test Version: \033[0;32m%s\033[0m",DEVICEINFO_VERSION);
    UT_LOG("\t VTS UNIFIED Boot HALIF Test Version: \033[0;32m%s\033[0m",BOOT_VERSION);
    UT_LOG("\t VTS UNIFIED Firmware Update HALIF Test Version: \033[0;32m%s\033[0m",FLASH_VERSION);
    UT_LOG("\t VTS UNIFIED Thermal Sensor HALIF Test Version: \033[0;32m%s\033[0m",THERMALSENSOR_VERSION);
    UT_LOG("\t VTS UNIFIED Motion Sensor HALIF Test Version: \033[0;32m%s\033[0m",MOTIONSENSOR_VERSION);
    UT_LOG("\t VTS UNIFIED Indicator HALIF Test Version: \033[0;32m%s\033[0m",INDICATOR_VERSION);
    UT_LOG("\t VTS UNIFIED Compositeinput HALIF Test Version: \033[0;32m%s\033[0m",COMPOSITEINPUT_VERSION);
    UT_LOG("==========================================================================");
    result = VTS_AVBuffer_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize AVBuffer");
        result = UT_STATUS_FAILURE;
    }

#ifdef ENABLE_DRM_TEST
    result = VTS_Drm_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize DRM");
        result = UT_STATUS_FAILURE;
    }
#endif

    result = VTS_AudioDecoder_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize AudioDecoder");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_VideoDecoder_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize VideoDecoder");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_AudioSink_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize AudioSink");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_VideoSink_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize VideoSink");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_AVClock_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize AV Clock");
        result = UT_STATUS_FAILURE;
    }

#ifdef ENABLE_PLANE_CONTROL_TEST
    result = VTS_PlaneControl_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize Plane Control");
        result = UT_STATUS_FAILURE;
    }
#endif

#ifdef ENABLE_AV_L4_TEST
    result = VTS_AV_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize AV L4 Tests");
        result = UT_STATUS_FAILURE;
    }
#endif

    result = VTS_AudioMixer_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize Audio Mixer");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_HDMICEC_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize HDMI CEC Tests");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_HDMIINPUT_init();
    if(result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize HDMI Input Tests");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_HDMIOUTPUT_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize HDMI output service\n");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_DEEPSLEEP_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize Deep Sleep service\n");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_DEVICEINFO_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("VTS_DEVICEINFO_init() failed!");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_BOOT_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("VTS_BOOT_init() failed!");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_FIRMWAREUPDATE_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("VTS_FIRMWAREUPDATE_init() failed!");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_THERMALSENSOR_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize Thermal Sensor service");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_MOTIONSENSOR_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize Motion Sensor service");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_INDICATOR_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("VTS_INDICATOR_init() failed!");
        result = UT_STATUS_FAILURE;
    }

    result = VTS_COMPOSITEINPUT_init();
    if (result != UT_STATUS_OK)
    {
        UT_LOG_ERROR("Failed to initialize Compositeinput service\n");
        result = UT_STATUS_FAILURE;
    }

    UT_status_t ut_result = UT_run_tests();

    if (result != UT_STATUS_OK || ut_result != UT_STATUS_OK)
    {
        result = UT_STATUS_FAILURE;
    }
    else
    {
        result = UT_STATUS_OK;
    }
    VTS_AudioDecoder_destroy();
    VTS_VideoDecoder_destroy();
    VTS_AudioSink_destroy();
    VTS_VideoSink_destroy();
    VTS_AudioMixer_destroy();
    VTS_HDMICEC_destroy();
    VTS_HDMIINPUT_destroy();
    VTS_HDMIOUTPUT_destroy();
    VTS_DEEPSLEEP_destroy();
    VTS_DEVICEINFO_destroy();
    VTS_BOOT_destroy();
    VTS_FIRMWAREUPDATE_destroy();
    VTS_THERMALSENSOR_destroy();
    VTS_MOTIONSENSOR_destroy();
    VTS_INDICATOR_destroy();
    VTS_COMPOSITEINPUT_destroy();
#ifdef ENABLE_DRM_TEST
    VTS_Drm_destroy();
#endif

    return result;
}

/** @} */ // End of UNIFIED_VTS_Halif_Test_Main
/** @} */ // End of UNIFIED_VTS_Halif_Test
/** @} */ // End of UNIFIED_VTS
/** @} */ // End of HPK
