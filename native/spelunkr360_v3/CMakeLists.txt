cmake_minimum_required(VERSION 3.25)
project(Spelunkr360 C)

add_executable(Spelunkr360 main.c)
set_target_properties(Spelunkr360 PROPERTIES C_STANDARD 17 C_EXTENSIONS ON)
target_compile_options(Spelunkr360 PRIVATE -Wall -Wextra -Werror)
xsdk_add_xex(Spelunkr360 TITLE_ID 0x53503601 NAME "Spelunkr360" VERSION 0.3.0.0)
