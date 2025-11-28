cmake_minimum_required(VERSION 3.16)
project(StarlinkMonitor LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Network)
find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

# gRPC C++ plugin
find_program(GRPC_CPP_PLUGIN_EXECUTABLE grpc_cpp_plugin)

# Generate Protobuf and gRPC sources
set(PROTO_FILES
    protos/spacex/api/common/status/status.proto
    protos/spacex/api/device/command.proto
    protos/spacex/api/device/common.proto
    protos/spacex/api/device/device.proto
    protos/spacex/api/device/dish.proto
    protos/spacex/api/device/transceiver.proto
    protos/spacex/api/device/wifi.proto
    protos/spacex/api/device/wifi_config.proto
)

# Helper function to generate gRPC and Protobuf code
function(generate_grpc_proto_sources PROTO_FILES OUT_SOURCES OUT_HEADERS)
    foreach(PROTO_FILE ${PROTO_FILES})
        get_filename_component(PROTO_NAME ${PROTO_FILE} NAME_WE)
        get_filename_component(PROTO_PATH ${PROTO_FILE} DIRECTORY)
        
        set(PROTO_SRC "${CMAKE_CURRENT_BINARY_DIR}/${PROTO_NAME}.pb.cc")
        set(PROTO_HDR "${CMAKE_CURRENT_BINARY_DIR}/${PROTO_NAME}.pb.h")
        set(GRPC_SRC "${CMAKE_CURRENT_BINARY_DIR}/${PROTO_NAME}.grpc.pb.cc")
        set(GRPC_HDR "${CMAKE_CURRENT_BINARY_DIR}/${PROTO_NAME}.grpc.pb.h")

        add_custom_command(
            OUTPUT ${PROTO_SRC} ${PROTO_HDR} ${GRPC_SRC} ${GRPC_HDR}
            COMMAND ${Protobuf_PROTOC_EXECUTABLE}
            ARGS --grpc_out=${CMAKE_CURRENT_BINARY_DIR}
                 --cpp_out=${CMAKE_CURRENT_BINARY_DIR}
                 --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN_EXECUTABLE}
                 -I ${CMAKE_CURRENT_SOURCE_DIR}/protos
                 ${PROTO_FILE}
            DEPENDS ${PROTO_FILE}
        )

        list(APPEND ${OUT_SOURCES} ${PROTO_SRC} ${GRPC_SRC})
        list(APPEND ${OUT_HEADERS} ${PROTO_HDR} ${GRPC_HDR})
    endforeach()

    set(${OUT_SOURCES} ${${OUT_SOURCES}} PARENT_SCOPE)
    set(${OUT_HEADERS} ${${OUT_HEADERS}} PARENT_SCOPE)
endfunction()

set(PROTO_SOURCES "")
set(PROTO_HEADERS "")
generate_grpc_proto_sources("${PROTO_FILES}" PROTO_SOURCES PROTO_HEADERS)

# Application sources
set(SOURCES
    src/main.cpp
    src/mainwindow.cpp
    src/starlinkclient.cpp
    ${PROTO_SOURCES}
)

set(HEADERS
    src/mainwindow.h
    src/starlinkclient.h
    ${PROTO_HEADERS}
)

# Qt Resources
# qt_add_resources(RESOURCES resources.qrc)

add_executable(starlink-monitor ${SOURCES} ${HEADERS})

target_link_libraries(starlink-monitor PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::Network
    protobuf::libprotobuf
    gRPC::grpc++
)

target_include_directories(starlink-monitor PRIVATE
    src
    ${CMAKE_CURRENT_BINARY_DIR}
)
