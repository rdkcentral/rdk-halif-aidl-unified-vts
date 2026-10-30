/**
 *  If not stated otherwise in this file or this component's LICENSE
 *  file the following copyright and licenses apply:
 *
 *  Copyright 2026 RDK Management
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

#ifndef VTS_INPUT_PATH_HELPERS_H
#define VTS_INPUT_PATH_HELPERS_H

#include <algorithm>

namespace vts::input_path
{
template <typename Entries, typename Id, typename IdAccessor>
auto findInputPathEntry(const Entries& entries, const Id& id, IdAccessor idAccessor)
{
    return std::find_if(entries.cbegin(), entries.cend(),
                        [&id, &idAccessor](const auto& entry) {
                            return idAccessor(entry) == id;
                        });
}
} // namespace vts::input_path

#endif // VTS_INPUT_PATH_HELPERS_H