cmake_minimum_required(VERSION 3.25)
project(Spelunkr360V4 C)

add_executable(Spelunkr360V4 main.c)
set_target_properties(Spelunkr360V4 PROPERTIES C_STANDARD 17 C_EXTENSIONS ON)
target_compile_options(Spelunkr360V4 PRIVATE -Wall -Wextra -Werror)
xsdk_add_xex(Spelunkr360V4 TITLE_ID 0x53503601 NAME "Spelunkr360" VERSION 0.4.0.0)
