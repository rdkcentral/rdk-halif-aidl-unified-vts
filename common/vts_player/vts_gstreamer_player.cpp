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
    : playbin(nullptr),
      bus(nullptr),
      terminate(false),
      curAudioDecodeBin(nullptr),
      curAudioTypefind(nullptr),
      curAudioParse(nullptr),
      curAudioDecoder(nullptr),
      curAudioPlaysinkBin(nullptr),
      mCurAudioSink(nullptr),
      isAudioAAC_current(true),
      linkTypefindParser(false) {}

VTSGStreamerPlayer::~VTSGStreamerPlayer()
{
    close();
}

bool VTSGStreamerPlayer::init()
{
    //gst_init(nullptr, nullptr);

    playbin = gst_element_factory_make("playbin", "player");
    if (!playbin)
    {
        UT_LOG_ERROR("[GStreamer] Failed to create playbin");
	UT_ASSERT_TRUE(false);
        return false;
    }
    bus = gst_element_get_bus(playbin);
	
    // Register deep element added callback to dynamically trace pipeline creation
    // g_signal_connect(G_OBJECT(playbin), "deep-element-added", G_CALLBACK(deepElementAddedCallback), this);
	
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
	UT_ASSERT_TRUE(false);
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
	    UT_ASSERT_TRUE(false);
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
	    UT_ASSERT_TRUE(false);
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
	    UT_ASSERT_TRUE(false);
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
	    UT_ASSERT_TRUE(false);
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
		UT_ASSERT_TRUE(false);
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
	curAudioDecodeBin = nullptr;
    curAudioTypefind = nullptr;
    curAudioParse = nullptr;
    curAudioDecoder = nullptr;
    curAudioPlaysinkBin = nullptr;
    mCurAudioSink = nullptr;
    //gst_deinit();
}

/* OTF Switch audio codec on the fly (true = AAC, false = EAC3)
bool VTSGStreamerPlayer::switchAudioCodec(bool isAudioAAC)
{
    UT_LOG_INFO("[GStreamer] switchAudioCodec: Current AAC = %d, Target AAC = %d", 
                isAudioAAC_current, isAudioAAC);

    if (isAudioAAC_current == isAudioAAC) {
        UT_LOG_INFO("[GStreamer] Target codec matches current codec. No switch needed.");
        return true;
    }

    // 1. Set fade-out on the current decoder to prevent popping audio, if supported
    if (curAudioDecoder) {
        GParamSpec *spec = g_object_class_find_property(G_OBJECT_GET_CLASS(curAudioDecoder), "otf-fade-out");
        if (spec) {
            g_object_set(curAudioDecoder, "otf-fade-out", TRUE, nullptr);
            UT_LOG_INFO("[GStreamer] Enabled otf-fade-out on decoder");
        }
    }

    // 2. Temporarily pause the playsink and decodebin elements to prevent incoming buffers
    GstState origPlaysinkState = GST_STATE_VOID_PENDING;
    GstState origDecodebinState = GST_STATE_VOID_PENDING;
    if (curAudioPlaysinkBin) {
        gst_element_get_state(curAudioPlaysinkBin, &origPlaysinkState, nullptr, 0);
        gst_element_set_state(curAudioPlaysinkBin, GST_STATE_PAUSED);
    }
    if (curAudioDecodeBin) {
        gst_element_get_state(curAudioDecodeBin, &origDecodebinState, nullptr, 0);
        gst_element_set_state(curAudioDecodeBin, GST_STATE_PAUSED);
    }

    // 3. Send flush events downstream to clean old format samples
    GstEvent *flush_start = gst_event_new_flush_start();
    GstEvent *flush_stop = gst_event_new_flush_stop(TRUE);

    if (curAudioDecoder) {
        GstPad *sinkPad = gst_element_get_static_pad(curAudioDecoder, "sink");
        if (sinkPad) {
            gst_pad_send_event(sinkPad, flush_start);

            // Set next codec flag on the decoder, if supported
            GParamSpec *spec = g_object_class_find_property(G_OBJECT_GET_CLASS(curAudioDecoder), "otf-next-codec");
            if (spec) {
                int next_codec = isAudioAAC ? 0 : 1;
                g_object_set(curAudioDecoder, "otf-next-codec", next_codec, nullptr);
            }

            gst_pad_send_event(sinkPad, flush_stop);
            gst_object_unref(sinkPad);
        }
    }

    // 4. Set configuration caps for the target codec
    GstCaps *newCaps = nullptr;
    if (isAudioAAC) {
        newCaps = gst_caps_from_string("audio/mpeg, mpegversion=4, secure-stream=audio, enable-svp=(string)false");
    }
    else {
        newCaps = gst_caps_from_string("audio/x-eac3, framed=(boolean)true, rate=(int)48000, channels=(int)6, alignment=(string)frame, enable-svp=(string)false");
    }

    // 5. Perform the decoder swap
    isAudioAAC_current = isAudioAAC;
    if (curAudioDecoder == nullptr && isAudioAAC) {
        configAudioPipe(newCaps);
    }
    else {
        reconfigAudioPipe(newCaps);
    }

    if (newCaps) {
        gst_caps_unref(newCaps);
    }

    // 6. Restore element states
    if (curAudioPlaysinkBin && origPlaysinkState != GST_STATE_VOID_PENDING) {
        gst_element_set_state(curAudioPlaysinkBin, origPlaysinkState);
    }
    if (curAudioDecodeBin && origDecodebinState != GST_STATE_VOID_PENDING) {
        gst_element_set_state(curAudioDecodeBin, origDecodebinState);
    }

    // 7. Enable sync / skipping on new decoder if supported
    if (curAudioDecoder) {
        GParamSpec *spec = g_object_class_find_property(G_OBJECT_GET_CLASS(curAudioDecoder), "avsync-audio-skip");
        if (spec) {
            g_object_set(curAudioDecoder, "avsync-audio-skip", TRUE, nullptr);
        }
    }

    UT_LOG_INFO("[GStreamer] switchAudioCodec: Dynamic codec switch finished.");
    return true;
}

*/

void VTSGStreamerPlayer::configAudioPipe(GstCaps *newAudioCaps)
{
    UT_LOG_INFO("[GStreamer] configAudioPipe: First time configuring audio pipeline for AAC");
    if (!curAudioDecodeBin || !curAudioTypefind) {
        UT_LOG_ERROR("[GStreamer] curAudioDecodeBin or curAudioTypefind is NULL");
	UT_ASSERT_TRUE(false);
        return;
    }

    GstPad *pTypfdSrcPad = gst_element_get_static_pad(curAudioTypefind, "src");
    if (!pTypfdSrcPad) {
        UT_LOG_ERROR("[GStreamer] Failed to get typefind src pad");
	UT_ASSERT_TRUE(false);
        return;
    }
    GstPad *pTypfdSrcPeerPad = gst_pad_get_peer(pTypfdSrcPad);
    if (!pTypfdSrcPeerPad) {
        UT_LOG_ERROR("[GStreamer] Failed to get peer pad for typefind src");
	UT_ASSERT_TRUE(false);
        gst_object_unref(pTypfdSrcPad);
        return;
    }

    // Downstream unlink
    gst_pad_unlink(pTypfdSrcPad, pTypfdSrcPeerPad);

    // Create new elements (fall back to desktop gstreamer plugins if platform OMX plugins are missing)
    GstElement *newAudioDecoder = gst_element_factory_make("omxaacdec", "omxaacdec");
    if (!newAudioDecoder) {
        newAudioDecoder = gst_element_factory_make("avdec_aac", "omxaacdec");
    }
    GstElement *newQueue = gst_element_factory_make("queue", "aqueue");

    if (!newAudioDecoder || !newQueue) {
        UT_LOG_ERROR("[GStreamer] Failed to create new decoder or queue");
	UT_ASSERT_TRUE(false);
        gst_object_unref(pTypfdSrcPad);
        gst_object_unref(pTypfdSrcPeerPad);
        return;
    }

    gst_bin_add(GST_BIN(curAudioDecodeBin), newAudioDecoder);
    gst_bin_add(GST_BIN(curAudioDecodeBin), newQueue);

    GstPad *pNewAudioDecoderSrcPad = gst_element_get_static_pad(newAudioDecoder, "src");
    
    // Link decoder to downstream
    gst_pad_link(pNewAudioDecoderSrcPad, pTypfdSrcPeerPad);

    // Link queue to decoder
    gst_element_link_many(newQueue, newAudioDecoder, nullptr);

    // Force caps
    gst_element_set_state(curAudioTypefind, GST_STATE_READY);
    g_object_set(G_OBJECT(curAudioTypefind), "force-caps", newAudioCaps, nullptr);
    gst_element_sync_state_with_parent(curAudioTypefind);

    linkTypefindParser = true;

    gst_element_sync_state_with_parent(newAudioDecoder);
    gst_element_sync_state_with_parent(newQueue);

    curAudioDecoder = newAudioDecoder;

    gst_object_unref(pTypfdSrcPad);
    gst_object_unref(pTypfdSrcPeerPad);
    if (pNewAudioDecoderSrcPad) {
        gst_object_unref(pNewAudioDecoderSrcPad);
    }
}

void VTSGStreamerPlayer::reconfigAudioPipe(GstCaps *newAudioCaps)
{
    UT_LOG_INFO("[GStreamer] reconfigAudioPipe: Swapping audio decoder");
    if (!curAudioDecodeBin || !curAudioDecoder) {
        UT_LOG_ERROR("[GStreamer] curAudioDecodeBin or curAudioDecoder is NULL");
	UT_ASSERT_TRUE(false);
        return;
    }

    GstPad *audioDecSrcPad = gst_element_get_static_pad(curAudioDecoder, "src");
    GstPad *audioDecSinkPad = gst_element_get_static_pad(curAudioDecoder, "sink");
    if (!audioDecSrcPad || !audioDecSinkPad) {
        UT_LOG_ERROR("[GStreamer] Failed to get audio decoder pads");
	UT_ASSERT_TRUE(false);
        if (audioDecSrcPad) gst_object_unref(audioDecSrcPad);
        if (audioDecSinkPad) gst_object_unref(audioDecSinkPad);
        return;
    }

    GstPad *audioDecSrcPeerPad = gst_pad_get_peer(audioDecSrcPad);
    GstPad *audioDecSinkPeerPad = gst_pad_get_peer(audioDecSinkPad);
    if (!audioDecSrcPeerPad || !audioDecSinkPeerPad) {
        UT_LOG_ERROR("[GStreamer] Failed to get peer pads for audio decoder");
	UT_ASSERT_TRUE(false);
        gst_object_unref(audioDecSrcPad);
        gst_object_unref(audioDecSinkPad);
        if (audioDecSrcPeerPad) gst_object_unref(audioDecSrcPeerPad);
        if (audioDecSinkPeerPad) gst_object_unref(audioDecSinkPeerPad);
        return;
    }

    // Downstream and upstream unlink
    gst_pad_unlink(audioDecSrcPad, audioDecSrcPeerPad);
    gst_pad_unlink(audioDecSinkPeerPad, audioDecSinkPad);

    // Stop and remove old decoder
    gst_element_set_state(curAudioDecoder, GST_STATE_NULL);
    gst_bin_remove(GST_BIN(curAudioDecodeBin), curAudioDecoder);

    GstElement *newAudioDecoder = nullptr;
    if (isAudioAAC_current) {
        UT_LOG_INFO("[GStreamer] Creating AAC decoder");
        newAudioDecoder = gst_element_factory_make("omxaacdec", "omxaacdec");
        if (!newAudioDecoder) {
            newAudioDecoder = gst_element_factory_make("avdec_aac", "omxaacdec");
        }
    }
    else {
        UT_LOG_INFO("[GStreamer] Creating EAC3 decoder");
        newAudioDecoder = gst_element_factory_make("omxeac3dec", "omxeac3dec");
        if (!newAudioDecoder) {
            newAudioDecoder = gst_element_factory_make("avdec_ac3", "omxeac3dec");
        }
    }

    if (!newAudioDecoder) {
        UT_LOG_ERROR("[GStreamer] Failed to create new audio decoder");
	UT_ASSERT_TRUE(false);
        gst_object_unref(audioDecSrcPad);
        gst_object_unref(audioDecSinkPad);
        gst_object_unref(audioDecSrcPeerPad);
        gst_object_unref(audioDecSinkPeerPad);
        return;
    }

    // Enable skipping/sync if supported
    g_object_set(newAudioDecoder, "avsync-audio-skip", TRUE, nullptr);

    // Add new decoder
    gst_bin_add(GST_BIN(curAudioDecodeBin), newAudioDecoder);

    GstPad *newAudioDecoderSrcPad = gst_element_get_static_pad(newAudioDecoder, "src");
    GstPad *newAudioDecoderSinkPad = gst_element_get_static_pad(newAudioDecoder, "sink");

    // Link new pads
    gst_pad_link_full(newAudioDecoderSrcPad, audioDecSrcPeerPad, GST_PAD_LINK_CHECK_NOTHING);
    gst_pad_link_full(audioDecSinkPeerPad, newAudioDecoderSinkPad, GST_PAD_LINK_CHECK_NOTHING);

    // Force caps if upstream is typefind
    GstElement *audioDecoderUpstreamEl = GST_ELEMENT_CAST(gst_pad_get_parent(audioDecSinkPeerPad));
    if (audioDecoderUpstreamEl && audioDecoderUpstreamEl == curAudioTypefind) {
        gst_element_set_state(audioDecoderUpstreamEl, GST_STATE_READY);
        g_object_set(G_OBJECT(audioDecoderUpstreamEl), "force-caps", newAudioCaps, nullptr);
        gst_element_sync_state_with_parent(audioDecoderUpstreamEl);
        linkTypefindParser = true;
    }
    if (audioDecoderUpstreamEl) {
        gst_object_unref(audioDecoderUpstreamEl);
    }

    gst_element_sync_state_with_parent(newAudioDecoder);

    curAudioDecoder = newAudioDecoder;

    gst_object_unref(audioDecSrcPad);
    gst_object_unref(audioDecSinkPad);
    gst_object_unref(audioDecSrcPeerPad);
    gst_object_unref(audioDecSinkPeerPad);
    if (newAudioDecoderSrcPad) gst_object_unref(newAudioDecoderSrcPad);
    if (newAudioDecoderSinkPad) gst_object_unref(newAudioDecoderSinkPad);
}

/* This maybe useful for RDKE hence keeping the implementation here
void VTSGStreamerPlayer::deepElementAddedCallback(GstBin *bin, GstBin *sub_bin, GstElement *element, gpointer user_data)
{
    VTSGStreamerPlayer *player = static_cast<VTSGStreamerPlayer *>(user_data);
    GstObject *parent = gst_element_get_parent(element);
    
    if (parent == GST_OBJECT_CAST(sub_bin)) {
        gchar *elementName = gst_element_get_name(element);
	gchar *subBinName = gst_element_get_name(GST_ELEMENT(sub_bin));
        if (elementName) {
            if (g_strrstr(elementName, "typefind")) {
                player->curAudioTypefind = element;
                g_signal_connect(G_OBJECT(element), "have-type", G_CALLBACK(typeFoundCallback), player);
            }

	    if (subBinName && g_strrstr(subBinName,"decodebin")) {
		player->curAudioDecodeBin = GST_ELEMENT(sub_bin);

		if (g_strrstr(elementName, "parse"))
		{
		    player->curAudioParse = element;
		    UT_LOG_INFO("[DeepAdded] Found Audio Parser: %s",
				elementName);
		}
	        else if (g_strrstr(elementName, "dec"))
		{
		    player->curAudioDecoder = element;
	            UT_LOG_INFO("[DeepAdded] Found Audio Decoder: %s",
			        elementName);
	        }
            }
            else
	    {
	        if (g_strrstr(elementName, "audiosink"))
	        {
	            player->mCurAudioSink = element;
                    
                    GstElement *audioSinkParent = 
	                GST_ELEMENT(gst_element_get_parent(element));
                    if (audioSinkParent)
	            {
			gchar *audioSinkParentName = 
		            gst_element_get_name(audioSinkParent);

			if (audioSinkParentName &&
			    g_strrstr(audioSinkParentName, "bin"))
			{
			    player->curAudioPlaysinkBin = audioSinkParent;
			    UT_LOG_INFO("[DeepAdded] Found Audio Playsink Bin");
			}

			g_free(audioSinkParentName);
			gst_object_unref(audioSinkParent);
		    }
		}
	    }

	    g_free(elementName);
	}

	if (subBinName)
	    g_free(subBinName);
    }

    if (parent)
	gst_object_unref(parent);
}


void VTSGStreamerPlayer::typeFoundCallback(GstElement *typefind, guint probability, const GstCaps *caps, gpointer user_data)
{
    VTSGStreamerPlayer *player = static_cast<VTSGStreamerPlayer *>(user_data);
    if (caps == nullptr) {
        return;
    }
    
    gchar *caps_str = gst_caps_to_string(caps);
    if (caps_str) {
        if (g_strrstr(caps_str, "audio/")) {
            GstElement *typeFindParent = (GstElement *)gst_element_get_parent(typefind);
            if (typeFindParent) {
                gchar *parentName = gst_element_get_name(typeFindParent);
                if (parentName && g_strrstr(parentName, "decodebin")) {
                    player->curAudioDecodeBin = typeFindParent;
                    player->curAudioTypefind = typefind;

                    if (player->linkTypefindParser) {
                        if (player->curAudioParse != nullptr) {
                            if (gst_element_link(typefind, player->curAudioParse)) {
                                player->linkTypefindParser = false;
                            }
                        }
                        else if (player->curAudioDecoder != nullptr) {
                            if (gst_element_link(typefind, player->curAudioDecoder)) {
                                player->linkTypefindParser = false;
                            }
                        }
                    }
                }
                g_free(parentName);
                gst_object_unref(typeFindParent);
            }
        }
        g_free(caps_str);
    }
}
*/

bool VTSGStreamerPlayer::switchAudioTrack(uint32_t trackIndex)
{
    if(!playbin)
        return false;

    if(trackIndex >= mNumAudioTracks)
    {
        UT_LOG_INFO("Audio tracks : %u", trackIndex);
    }

    gint currentTrack = -1;

    g_object_get(playbin,
		 "current-audio",
		 &currentTrack,
		 nullptr);
    UT_LOG_INFO("Current audio track = %d",currentTrack);

    if ((guint)currentTrack == trackIndex)
    {
	UT_LOG_INFO("Already on requested track.");
	return true;
    }

    g_object_set(playbin,
		 "current-audio",
		 trackIndex,
		 nullptr);
    mCurrentAudioTrack = trackIndex;

    UT_LOG_INFO("Switched to audio track %u", trackIndex);

    return true;
}

bool VTSGStreamerPlayer::switchVideoTrack(uint32_t trackIndex)
{
    if (!playbin)
        return false;

    gint nVideo = 0;
    g_object_get(playbin, "n-video", &nVideo, nullptr);

    UT_LOG_INFO("[Gstreamer] Number of video tracks : %d", nVideo);
    
    if (trackIndex >= static_cast<uint32_t>(nVideo))
    {
        UT_LOG_INFO("Video tracks : %u", trackIndex);
    }

    UT_LOG_INFO("[GSTREAMER] Switching video track to : %u", trackIndex);

    g_object_set(playbin,"current-video",static_cast<gint>(trackIndex),nullptr);

    return true;

}

/** @} */ // End of AV_MODULE_HALTEST_GST_PLAYER
/** @} */ // End of AV_MODULE_HALTEST_PLAYER
/** @} */ // End of AV_MODULE_HALTEST
/** @} */ // End of AV_MODULE
/** @} */ // End of HPK
