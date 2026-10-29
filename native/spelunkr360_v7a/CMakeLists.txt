cmake_minimum_required(VERSION 3.25)
project(Spelunkr360V7A C)

set(MBEDTLS_XENON_DIR "" CACHE PATH "Path to mbedtls-xenon checkout")
set(CURL_XENON_DIR "" CACHE PATH "Path to curl-xenon checkout")
set(FFMPEG_XSDK_DIR "" CACHE PATH "Path to the prebuilt FFmpeg xsdk prefix")

if(NOT EXISTS "${MBEDTLS_XENON_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "MBEDTLS_XENON_DIR must point to mbedtls-xenon")
endif()
if(NOT EXISTS "${CURL_XENON_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "CURL_XENON_DIR must point to curl-xenon")
endif()
if(NOT EXISTS "${FFMPEG_XSDK_DIR}/include/libavformat/avformat.h")
  message(FATAL_ERROR "FFMPEG_XSDK_DIR must point to the installed FFmpeg xsdk prefix")
endif()

set(ENABLE_PROGRAMS OFF CACHE BOOL "" FORCE)
set(ENABLE_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory("${MBEDTLS_XENON_DIR}" mbedtls)

set(MBEDTLS_INCLUDE_DIR "${MBEDTLS_XENON_DIR}/include" CACHE PATH "")
set(MBEDTLS_LIBRARY mbedtls CACHE STRING "")
set(MBEDX509_LIBRARY mbedx509 CACHE STRING "")
set(MBEDCRYPTO_LIBRARY mbedcrypto CACHE STRING "")
set(CURL_DISABLE_INSTALL ON CACHE BOOL "" FORCE)
add_subdirectory("${CURL_XENON_DIR}" curl)

add_library(sp7_avformat STATIC IMPORTED)
add_library(sp7_avcodec STATIC IMPORTED)
add_library(sp7_avutil STATIC IMPORTED)
set_target_properties(sp7_avformat PROPERTIES IMPORTED_LOCATION "${FFMPEG_XSDK_DIR}/lib/libavformat.a")
set_target_properties(sp7_avcodec PROPERTIES IMPORTED_LOCATION "${FFMPEG_XSDK_DIR}/lib/libavcodec.a")
set_target_properties(sp7_avutil PROPERTIES IMPORTED_LOCATION "${FFMPEG_XSDK_DIR}/lib/libavutil.a")

add_executable(Spelunkr360V7A
  main.c
  newlib_compat.c
  ../spelunkr360_v6c/schedule_core.c
)
set_target_properties(Spelunkr360V7A PROPERTIES C_STANDARD 17 C_EXTENSIONS ON)
target_include_directories(Spelunkr360V7A PRIVATE
  "${FFMPEG_XSDK_DIR}/include"
  "${CMAKE_CURRENT_SOURCE_DIR}/../spelunkr360_v6c"
)
target_link_libraries(Spelunkr360V7A PRIVATE
  CURL::libcurl
  mbedtls
  sp7_avformat
  sp7_avcodec
  sp7_avutil
)
target_compile_options(Spelunkr360V7A PRIVATE -Wall -Wextra -Werror -O2)
xsdk_add_shaders(Spelunkr360V7A frame.vert frame.frag)
xsdk_add_xex(Spelunkr360V7A TITLE_ID 0x53503601 NAME "Spelunkr360" VERSION 0.7.0.1)

configure_file("${MBEDTLS_XENON_DIR}/programs/xsdk/cacert.pem" cacert.pem COPYONLY)
