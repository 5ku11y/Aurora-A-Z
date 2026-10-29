cmake_minimum_required(VERSION 3.25)
project(Spelunkr360V5 C)

set(MBEDTLS_XENON_DIR "" CACHE PATH "Path to mbedtls-xenon checkout")
set(CURL_XENON_DIR "" CACHE PATH "Path to curl-xenon checkout")
if(NOT EXISTS "${MBEDTLS_XENON_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "MBEDTLS_XENON_DIR must point to mbedtls-xenon")
endif()
if(NOT EXISTS "${CURL_XENON_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "CURL_XENON_DIR must point to curl-xenon")
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

add_executable(Spelunkr360V5 main.c)
set_target_properties(Spelunkr360V5 PROPERTIES C_STANDARD 17 C_EXTENSIONS ON)
target_link_libraries(Spelunkr360V5 PRIVATE CURL::libcurl mbedtls)
target_compile_options(Spelunkr360V5 PRIVATE -Wall -Wextra -Werror)
xsdk_add_xex(Spelunkr360V5 TITLE_ID 0x53503601 NAME "Spelunkr360" VERSION 0.5.0.0)

# curl-xenon has no built-in CA bundle. Ship the Mozilla roots used by the
# port's own hardware checks beside the XEX.
configure_file("${MBEDTLS_XENON_DIR}/programs/xsdk/cacert.pem" cacert.pem COPYONLY)
