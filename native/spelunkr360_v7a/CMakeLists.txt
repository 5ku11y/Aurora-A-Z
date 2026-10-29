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

set(V7A_RANGE_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_range_open.c")
set(V7A_PAGED_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_archive_pages.c")
set(V7A_SIZE64_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_size64.c")
set(V7A_DIAG8_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_diag8.c")
set(V7A_MOOV9_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_moov9.c")
set(V7A_STAGE10_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_stage10.c")
set(V7A_CHUNK11_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_chunk11.c")
set(V7A_RETRY12_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_retry12.c")
set(V7A_OPEN13_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_open13.c")
set(V7B_MAIN "${CMAKE_CURRENT_BINARY_DIR}/main_v7b.c")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_range_open.py"
          "${CMAKE_CURRENT_SOURCE_DIR}/main.c" "${V7A_RANGE_MAIN}"
  RESULT_VARIABLE V7A_PATCH_RESULT
  OUTPUT_VARIABLE V7A_PATCH_STDOUT
  ERROR_VARIABLE V7A_PATCH_STDERR
)
if(NOT V7A_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A range-open source generation failed: ${V7A_PATCH_STDERR}")
endif()
message(STATUS "${V7A_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_metadata_pages.py"
          "${V7A_RANGE_MAIN}" "${V7A_PAGED_MAIN}"
  RESULT_VARIABLE V7A_META_PATCH_RESULT
  OUTPUT_VARIABLE V7A_META_PATCH_STDOUT
  ERROR_VARIABLE V7A_META_PATCH_STDERR
)
if(NOT V7A_META_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A paged metadata source generation failed: ${V7A_META_PATCH_STDERR}")
endif()
message(STATUS "${V7A_META_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_size64.py"
          "${V7A_PAGED_MAIN}" "${V7A_SIZE64_MAIN}"
  RESULT_VARIABLE V7A_SIZE64_PATCH_RESULT
  OUTPUT_VARIABLE V7A_SIZE64_PATCH_STDOUT
  ERROR_VARIABLE V7A_SIZE64_PATCH_STDERR
)
if(NOT V7A_SIZE64_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A 64-bit size source generation failed: ${V7A_SIZE64_PATCH_STDERR}")
endif()
message(STATUS "${V7A_SIZE64_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_size_diag8.py"
          "${V7A_SIZE64_MAIN}" "${V7A_DIAG8_MAIN}"
  RESULT_VARIABLE V7A_DIAG8_PATCH_RESULT
  OUTPUT_VARIABLE V7A_DIAG8_PATCH_STDOUT
  ERROR_VARIABLE V7A_DIAG8_PATCH_STDERR
)
if(NOT V7A_DIAG8_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A.8 diagnostic source generation failed: ${V7A_DIAG8_PATCH_STDERR}")
endif()
message(STATUS "${V7A_DIAG8_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_moov9.py"
          "${V7A_DIAG8_MAIN}" "${V7A_MOOV9_MAIN}"
  RESULT_VARIABLE V7A_MOOV9_PATCH_RESULT
  OUTPUT_VARIABLE V7A_MOOV9_PATCH_STDOUT
  ERROR_VARIABLE V7A_MOOV9_PATCH_STDERR
)
if(NOT V7A_MOOV9_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A.9 moov-prefetch source generation failed: ${V7A_MOOV9_PATCH_STDERR}")
endif()
message(STATUS "${V7A_MOOV9_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_stage10.py"
          "${V7A_MOOV9_MAIN}" "${V7A_STAGE10_MAIN}"
  RESULT_VARIABLE V7A_STAGE10_PATCH_RESULT
  OUTPUT_VARIABLE V7A_STAGE10_PATCH_STDOUT
  ERROR_VARIABLE V7A_STAGE10_PATCH_STDERR
)
if(NOT V7A_STAGE10_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A.10 staged playback source generation failed: ${V7A_STAGE10_PATCH_STDERR}")
endif()
message(STATUS "${V7A_STAGE10_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_chunk11.py"
          "${V7A_STAGE10_MAIN}" "${V7A_CHUNK11_MAIN}"
  RESULT_VARIABLE V7A_CHUNK11_PATCH_RESULT
  OUTPUT_VARIABLE V7A_CHUNK11_PATCH_STDOUT
  ERROR_VARIABLE V7A_CHUNK11_PATCH_STDERR
)
if(NOT V7A_CHUNK11_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A.11 chunked header source generation failed: ${V7A_CHUNK11_PATCH_STDERR}")
endif()
message(STATUS "${V7A_CHUNK11_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_retry12.py"
          "${V7A_CHUNK11_MAIN}" "${V7A_RETRY12_MAIN}"
  RESULT_VARIABLE V7A_RETRY12_PATCH_RESULT
  OUTPUT_VARIABLE V7A_RETRY12_PATCH_STDOUT
  ERROR_VARIABLE V7A_RETRY12_PATCH_STDERR
)
if(NOT V7A_RETRY12_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A.12 resilient range source generation failed: ${V7A_RETRY12_PATCH_STDERR}")
endif()
message(STATUS "${V7A_RETRY12_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_open13.py"
          "${V7A_RETRY12_MAIN}" "${V7A_OPEN13_MAIN}"
  RESULT_VARIABLE V7A_OPEN13_PATCH_RESULT
  OUTPUT_VARIABLE V7A_OPEN13_PATCH_STDOUT
  ERROR_VARIABLE V7A_OPEN13_PATCH_STDERR
)
if(NOT V7A_OPEN13_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7A.14 front-moov/shader source generation failed: ${V7A_OPEN13_PATCH_STDERR}")
endif()
message(STATUS "${V7A_OPEN13_PATCH_STDOUT}")

execute_process(
  COMMAND python3 "${CMAKE_CURRENT_SOURCE_DIR}/patch_v7b.py"
          "${V7A_OPEN13_MAIN}" "${V7B_MAIN}"
  RESULT_VARIABLE V7B_PATCH_RESULT
  OUTPUT_VARIABLE V7B_PATCH_STDOUT
  ERROR_VARIABLE V7B_PATCH_STDERR
)
if(NOT V7B_PATCH_RESULT EQUAL 0)
  message(FATAL_ERROR "V7B continuous-playback source generation failed: ${V7B_PATCH_STDERR}")
endif()
message(STATUS "${V7B_PATCH_STDOUT}")

add_executable(Spelunkr360V7A
  "${V7B_MAIN}"
  newlib_compat.c
  ../spelunkr360_v6c/schedule_core.c
)
set_target_properties(Spelunkr360V7A PROPERTIES C_STANDARD 17 C_EXTENSIONS ON)
target_include_directories(Spelunkr360V7A PRIVATE
  "${FFMPEG_XSDK_DIR}/include"
  "${CMAKE_CURRENT_SOURCE_DIR}"
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
xsdk_add_xex(Spelunkr360V7A TITLE_ID 0x53503601 NAME "Spelunkr360" VERSION 0.7.1.0)

configure_file("${MBEDTLS_XENON_DIR}/programs/xsdk/cacert.pem" ca.pem COPYONLY)
