find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(submodule_patch_helper "${CMAKE_CURRENT_SOURCE_DIR}/Telegram/build/apply_submodule_patches.py")
set(submodule_patch_manifest "${CMAKE_CURRENT_SOURCE_DIR}/patches/submodules/series.json")
execute_process(
    COMMAND "${Python3_EXECUTABLE}" "${submodule_patch_helper}" --check --print-files
    RESULT_VARIABLE submodule_patch_result
    OUTPUT_VARIABLE submodule_patch_files
    ERROR_VARIABLE submodule_patch_error
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
if (NOT submodule_patch_result STREQUAL "0")
    message(FATAL_ERROR "${submodule_patch_error}")
endif()

file(GLOB_RECURSE submodule_patch_inputs CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/patches/submodules/*.patch")
string(REPLACE "\r\n" "\n" submodule_patch_files "${submodule_patch_files}")
string(REPLACE "\n" ";" submodule_patch_files "${submodule_patch_files}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${submodule_patch_helper}"
    "${submodule_patch_manifest}"
    ${submodule_patch_inputs}
    ${submodule_patch_files}
)
