cmake_minimum_required(VERSION 3.16)
project(gary C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# A checkout of https://github.com/qnx/QNX-AI-workshop.
# Gary reuses its camera wrapper (rpi_cam.cpp) and its flatbuffers version shim
# exactly as shipped, so the camera path is the one QNX already verified.
set(WORKSHOP_DIR "$ENV{HOME}/QNX-AI-workshop" CACHE PATH "Path to a QNX-AI-workshop checkout")
if(NOT EXISTS "${WORKSHOP_DIR}/rpi_cam.cpp")
  message(FATAL_ERROR
    "QNX-AI-workshop not found at ${WORKSHOP_DIR}.\n"
    "Clone it:  git clone https://github.com/qnx/QNX-AI-workshop ${WORKSHOP_DIR}\n"
    "or pass:   -DWORKSHOP_DIR=/path/to/QNX-AI-workshop")
endif()

find_package(Threads REQUIRED)
find_package(OpenCV REQUIRED)
find_library(TFLITE_LIB tensorflow-lite REQUIRED)

add_executable(gary gary_qnx.cpp ${WORKSHOP_DIR}/rpi_cam.cpp)
target_include_directories(gary PRIVATE ${WORKSHOP_DIR})
# Same workaround the workshop uses for the packaged flatbuffers version.
target_compile_options(gary PRIVATE -include ${WORKSHOP_DIR}/flatbuffers_version_shim.hpp)
target_link_libraries(gary
    ${TFLITE_LIB}
    ${OpenCV_LIBS}
    camapi              # QNX Camera API, used by RpiCam
    Threads::Threads)
