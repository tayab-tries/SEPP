cmake_minimum_required(VERSION 3.20)
project(input_hooks)

set(CMAKE_CXX_STANDARD 17)

add_library(input_hooks SHARED input_hooks.cpp)

target_link_libraries(input_hooks user32 kernel32)

set_target_properties(input_hooks PROPERTIES
    PREFIX ""
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/../../client/native"
)