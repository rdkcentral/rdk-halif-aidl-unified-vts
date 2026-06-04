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
 * @addtogroup HPK Hardware Porting Kit
 * @{
 *
 */

/**
 * @addtogroup AV_MODULE AV pipeline Module
 * @{
 *
 */

/**
 * @defgroup AV_MODULE_HALTEST AV Module HAL Tests
 * @{
 *
 */

/**
 * @defgroup AV_MODULE_HALTEST_PLAYER AV Module HAL Tests Player abstract class
 * @{
 * @parblock
 */

/**
 * @defgroup AV_MODULE_HALTEST_GST_PLAYER AV Module HAL Tests Gstreamer Player class
 * @{
 * @parblock
 *
 * ### Gstreamer Player Interface:
 *
 * This file contains Gstreamer Player Interface.
 *
 * **Pre-Conditions:** @n
 * **Dependencies:** None@n
 *
 * @endparblock
 *
 */

/**
 * @file vts_gstreamer_player.cpp
 *
 */

#include "vts_gstreamer_player.h"
#include <ut.h>
#include <ut_log.h>

// Wrappers for GStreamer global init/deinit
void gstGlobalInitWrapper()
{
    gst_init(nullptr, nullptr);
}
void gstGlobalDeinitWrapper()
{
    gst_deinit();
}

VTSGStreamerPlayer::VTSGStreamerPlayer()
    : playbin(nullptr), bus(nullptr), terminate(false) {}

VTSGStreamerPlayer::~VTSGStreamerPlayer()
{

}

bool VTSGStreamerPlayer::init()
{
    //gst_init(nullptr, nullptr);

    playbin = gst_element_factory_make("playbin", "player");
    if (!playbin)
    {
        UT_LOG_ERROR("[GStreamer] Failed to create playbin");
        return false;
    }
    bus = gst_element_get_bus(playbin);
    return true;
}

bool VTSGStreamerPlayer::play(const std::string &streamPath)
{
    std::string uri = "file://" + streamPath;
    if (!playbin)
    {
        return false;
    }
    g_object_set(G_OBJECT(playbin), "uri", uri.c_str(), NULL);

    if (gst_element_set_state(playbin, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE)
    {
        UT_LOG_ERROR("[GStreamer] Failed to set PLAYING");
        return false;
    }
    return true;
}

void VTSGStreamerPlayer::pause()
{
    if (playbin)
    {
        gst_element_set_state(playbin, GST_STATE_PAUSED);
    }
}

void VTSGStreamerPlayer::resume()
{
    if (playbin)
    {
        gst_element_set_state(playbin, GST_STATE_PLAYING);
    }
}

void VTSGStreamerPlayer::trickMode(float speed)
{
    if (playbin)
    {
        gint64 pos = 0;
        // Query current playback position
        if (!gst_element_query_position(playbin, GST_FORMAT_TIME, &pos)) {
            UT_LOG_ERROR("Failed to query current position, defaulting to 0\n");
            pos = 0;
        }

        if (!gst_element_seek(playbin,
                              speed,
                              GST_FORMAT_TIME,
                              (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_ACCURATE),
                              GST_SEEK_TYPE_SET, pos, // start from current position
                              GST_SEEK_TYPE_NONE, GST_CLOCK_TIME_NONE))
        {
            UT_LOG_ERROR("Playing at %fx speed failed!\n", speed);
        }
    }
}

void VTSGStreamerPlayer::seek(int64_t offset_ms)
{
    gint64 offset_ns = offset_ms * GST_MSECOND;
    gint64 cur_pos = GST_CLOCK_TIME_NONE;
    gint64 new_pos;
    if (playbin)
    {
        if (!gst_element_query_position(playbin, GST_FORMAT_TIME, &cur_pos))
        {
            UT_LOG_ERROR("Failed to query current position\n");
            return;
        }

        new_pos = cur_pos + offset_ns;

        if (new_pos < 0)
            new_pos = 0;

        if (!gst_element_seek(playbin,
                              1.0,
                              GST_FORMAT_TIME,
                              (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT),
                              GST_SEEK_TYPE_SET,
                              new_pos,
                              GST_SEEK_TYPE_NONE, GST_CLOCK_TIME_NONE))
        {
            UT_LOG_ERROR("Relative seek failed!\n");
        }
    }
}

void VTSGStreamerPlayer::stop()
{
    if (playbin)
    {
        gst_element_set_state(playbin, GST_STATE_NULL);
    }
}

void VTSGStreamerPlayer::loop()
{
    terminate = false;
    while (!terminate)
    {
        GstMessage *msg = gst_bus_timed_pop_filtered(
            bus, GST_CLOCK_TIME_NONE,
            static_cast<GstMessageType>(GST_MESSAGE_EOS | GST_MESSAGE_ERROR));

        if (!msg) continue;

        switch (GST_MESSAGE_TYPE(msg))
        {
            case GST_MESSAGE_ERROR:
            {
                GError *err = nullptr;
                gchar *dbg = nullptr;
                gst_message_parse_error(msg, &err, &dbg);
                UT_LOG_ERROR("[GStreamer] ERROR: %s", (err ? err->message : ""));
                if (dbg) g_free(dbg);
                if (err) g_error_free(err);
                terminate = true;
                break;
            }
            case GST_MESSAGE_EOS:
                UT_LOG_INFO("[GStreamer] End of Stream");
                terminate = true;
                break;
            default:
                break;
        }
        gst_message_unref(msg);
    }
}

void VTSGStreamerPlayer::close()
{
    if (playbin)
    {
        gst_element_set_state(playbin, GST_STATE_NULL);
        gst_object_unref(playbin);
        playbin = nullptr;
    }
    //gst_deinit();
}

/** @} */ // End of AV_MODULE_HALTEST_GST_PLAYER
/** @} */ // End of AV_MODULE_HALTEST_PLAYER
/** @} */ // End of AV_MODULE_HALTEST
/** @} */ // End of AV_MODULE
/** @} */ // End of HPK