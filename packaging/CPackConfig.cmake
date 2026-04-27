set(CPACK_PACKAGE_NAME "Tomviz")
set(CPACK_PACKAGE_VENDOR "Kitware")
set(CPACK_PACKAGE_DESCRIPTION_FILE "${CMAKE_CURRENT_LIST_DIR}/description.txt")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "3D tomography data processing and visualization")
set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_CURRENT_LIST_DIR}/LICENSE.txt")

# Version from environment
set(CPACK_PACKAGE_VERSION "$ENV{TOMVIZ_VERSION}")

if(NOT CPACK_PACKAGE_VERSION)
  message(FATAL_ERROR "TOMVIZ_VERSION environment variable is not set")
endif()

# Parse version components
string(REPLACE "." ";" _version_list "${CPACK_PACKAGE_VERSION}")
list(LENGTH _version_list _version_len)
list(GET _version_list 0 CPACK_PACKAGE_VERSION_MAJOR)
if(_version_len GREATER 1)
  list(GET _version_list 1 CPACK_PACKAGE_VERSION_MINOR)
else()
  set(CPACK_PACKAGE_VERSION_MINOR "0")
endif()
if(_version_len GREATER 2)
  list(GET _version_list 2 CPACK_PACKAGE_VERSION_PATCH)
else()
  set(CPACK_PACKAGE_VERSION_PATCH "0")
endif()

set(CPACK_PACKAGE_INSTALL_DIRECTORY "Tomviz")
set(CPACK_PACKAGE_FILE_NAME "Tomviz-${CPACK_PACKAGE_VERSION}")

# package.py must be run before cpack to prepare _build/install/

if(APPLE)
  set(CPACK_GENERATOR "DragNDrop")
  set(CPACK_DMG_FORMAT "UDBZ")
  set(CPACK_PACKAGE_ICON "${CMAKE_CURRENT_LIST_DIR}/darwin/tomviz.icns")
  set(CPACK_DMG_VOLUME_NAME "Tomviz ${CPACK_PACKAGE_VERSION}")
  # The .app bundle is what gets put in the DMG
  set(CPACK_INSTALLED_DIRECTORIES
    "${CMAKE_CURRENT_LIST_DIR}/_build/install;.")
elseif(WIN32)
  set(CPACK_GENERATOR "WIX;ZIP")

  # WIX settings
  set(CPACK_WIX_UPGRADE_GUID "F8A5B3C7-2E41-4D9A-B6C8-1A3F5E7D9B0C")
  set(CPACK_WIX_PRODUCT_ICON "${CMAKE_CURRENT_LIST_DIR}/windows/tomviz.ico")
  set(CPACK_WIX_UI_BANNER "${CMAKE_CURRENT_LIST_DIR}/windows/tomviz_wix_ui_banner.png")
  set(CPACK_WIX_UI_DIALOG "${CMAKE_CURRENT_LIST_DIR}/windows/tomviz_wix_ui_dialog.png")
  set(CPACK_WIX_TEMPLATE "${CMAKE_CURRENT_LIST_DIR}/windows/WIX.template.in")
  set(CPACK_WIX_SIZEOF_VOID_P 8)

  set(CPACK_INSTALLED_DIRECTORIES
    "${CMAKE_CURRENT_LIST_DIR}/_build/install/tomviz;.")
else()
  # Linux
  set(CPACK_GENERATOR "TGZ")
  set(CPACK_INSTALLED_DIRECTORIES
    "${CMAKE_CURRENT_LIST_DIR}/_build/install;.")
endif()
