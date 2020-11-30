import textwrap

from jinja2 import Template

from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_find_package_common import (target_template,
                                                                CMakeFindPackageCommonMacros,
                                                                find_transitive_dependencies)
from conans.client.generators.cmake_multi import extend
from conans.model import Generator
from conans.model.conan_generator import GeneratorComponentsMixin


class CMakeFindPackageGenerator(GeneratorComponentsMixin, Generator):
    name = "cmake_find_package"

    find_template = textwrap.dedent("""
        {macros_and_functions}

        include(FindPackageHandleStandardArgs)

        conan_message(STATUS "Conan: Using autogenerated Find{filename}.cmake")
        # Global approach
        set({filename}_FOUND 1)
        set({filename}_VERSION "{version}")

        find_package_handle_standard_args({filename} REQUIRED_VARS
                                          {filename}_VERSION VERSION_VAR {filename}_VERSION)
        mark_as_advanced({filename}_FOUND {filename}_VERSION)

        {find_libraries_block}
        if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
            # Target approach
            if(NOT TARGET {name}::{name})
                add_library({name}::{name} INTERFACE IMPORTED)
                if({name}_INCLUDE_DIRS)
                    set_target_properties({name}::{name} PROPERTIES INTERFACE_INCLUDE_DIRECTORIES
                                          "${{{name}_INCLUDE_DIRS}}")
                endif()
                set_property(TARGET {name}::{name} PROPERTY INTERFACE_LINK_LIBRARIES
                             "${{{name}_LIBRARIES_TARGETS}};${{{name}_LINKER_FLAGS_LIST}}")
                set_property(TARGET {name}::{name} PROPERTY INTERFACE_COMPILE_DEFINITIONS
                             ${{{name}_COMPILE_DEFINITIONS}})
                set_property(TARGET {name}::{name} PROPERTY INTERFACE_COMPILE_OPTIONS
                             "${{{name}_COMPILE_OPTIONS_LIST}}")
                {find_dependencies_block}
            endif()
        endif()

        foreach(_BUILD_MODULE_PATH ${{{name}_BUILD_MODULES_PATHS}})
            include(${{_BUILD_MODULE_PATH}})
        endforeach()
        """)

    find_components_tpl = Template(textwrap.dedent("""\
        ########## MACROS ###########################################################################
        #############################################################################################
        {{ conan_message }}
        {{ conan_find_apple_frameworks }}
        {{ conan_package_library_targets }}

        ########### FOUND PACKAGE ###################################################################
        #############################################################################################

        include(FindPackageHandleStandardArgs)

        conan_message(STATUS "Conan: Using autogenerated Find{{ pkg_filename }}.cmake")
        set({{ pkg_filename }}_FOUND 1)
        set({{ pkg_filename }}_VERSION "{{ pkg_version }}")

        find_package_handle_standard_args({{ pkg_filename }} REQUIRED_VARS
                                          {{ pkg_filename }}_VERSION VERSION_VAR {{ pkg_filename }}_VERSION)
        mark_as_advanced({{ pkg_filename }}_FOUND {{ pkg_filename }}_VERSION)

        set({{ pkg_name }}_COMPONENTS {{ pkg_components }})

        if({{ pkg_name }}_FIND_COMPONENTS)
            foreach(_FIND_COMPONENT {{ '${'+pkg_name+'_FIND_COMPONENTS}' }})
                list(FIND {{ pkg_name }}_COMPONENTS "{{ pkg_name }}::${_FIND_COMPONENT}" _index)
                if(${_index} EQUAL -1)
                    conan_message(FATAL_ERROR "Conan: Component '${_FIND_COMPONENT}' NOT found in package '{{ pkg_name }}'")
                else()
                    conan_message(STATUS "Conan: Component '${_FIND_COMPONENT}' found in package '{{ pkg_name }}'")
                endif()
            endforeach()
        endif()

        ########### VARIABLES #######################################################################
        #############################################################################################

        {{ global_target_variables }}

        {%- for comp_name, comp in components %}

        ########### COMPONENT {{ comp_name }} VARIABLES #############################################

        set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIRS {{ comp.include_paths }})
        set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIR {{ comp.include_path }})
        set({{ pkg_name }}_{{ comp_name }}_INCLUDES {{ comp.include_paths }})
        set({{ pkg_name }}_{{ comp_name }}_LIB_DIRS {{ comp.lib_paths }})
        set({{ pkg_name }}_{{ comp_name }}_RES_DIRS {{ comp.res_paths }})
        set({{ pkg_name }}_{{ comp_name }}_DEFINITIONS {{ comp.defines }})
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_DEFINITIONS {{ comp.compile_definitions }})
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_C "{{ comp.cflags_list }}")
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_CXX "{{ comp.cxxflags_list }}")
        set({{ pkg_name }}_{{ comp_name }}_LIBS {{ comp.libs }})
        set({{ pkg_name }}_{{ comp_name }}_SYSTEM_LIBS {{ comp.system_libs }})
        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORK_DIRS {{ comp.framework_paths }})
        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS {{ comp.frameworks }})
        set({{ pkg_name }}_{{ comp_name }}_BUILD_MODULES_PATHS {{ comp.build_modules_paths }})
        set({{ pkg_name }}_{{ comp_name }}_DEPENDENCIES {{ comp.public_deps }})
        set({{ pkg_name }}_{{ comp_name }}_LINKER_FLAGS_LIST
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:{{ comp.sharedlinkflags_list }}>"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:{{ comp.sharedlinkflags_list }}>"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:{{ comp.exelinkflags_list }}>"
        )

        {%- endfor %}


        ########## FIND PACKAGE DEPENDENCY ##########################################################
        #############################################################################################

        include(CMakeFindDependencyMacro)

        {%- for pkg_public_dep_filename in pkg_public_deps_filenames %}

        if(NOT {{ pkg_public_dep_filename }}_FOUND)
            find_dependency({{ pkg_public_dep_filename }} REQUIRED)
        else()
            conan_message(STATUS "Conan: Dependency {{ pkg_public_dep_filename }} already found")
        endif()

        {%- endfor %}


        ########## FIND LIBRARIES & FRAMEWORKS / DYNAMIC VARS #######################################
        #############################################################################################

        {%- for comp_name, comp in components %}

        ########## COMPONENT {{ comp_name }} FIND LIBRARIES & FRAMEWORKS / DYNAMIC VARS #############

        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND "")
        conan_find_apple_frameworks({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS}' }}" "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORK_DIRS}' }}")

        set({{ pkg_name }}_{{ comp_name }}_LIB_TARGETS "")
        set({{ pkg_name }}_{{ comp_name }}_NOT_USED "")
        set({{ pkg_name }}_{{ comp_name }}_LIBS_FRAMEWORKS_DEPS {{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS_FOUND}' }} {{ '${'+pkg_name+'_'+comp_name+'_SYSTEM_LIBS}' }} {{ '${'+pkg_name+'_'+comp_name+'_DEPENDENCIES}' }})
        conan_package_library_targets("{{ '${'+pkg_name+'_'+comp_name+'_LIBS}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIB_DIRS}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS}' }}"
                                      {{ pkg_name }}_{{ comp_name }}_NOT_USED
                                      {{ pkg_name }}_{{ comp_name }}_LIB_TARGETS
                                      ""
                                      "{{ pkg_name }}_{{ comp_name }}")

        set({{ pkg_name }}_{{ comp_name }}_LINK_LIBS {{ '${'+pkg_name+'_'+comp_name+'_LIB_TARGETS}' }} {{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS}' }})

        set(CMAKE_MODULE_PATH {{ comp.build_paths }} ${CMAKE_MODULE_PATH})
        set(CMAKE_PREFIX_PATH {{ comp.build_paths }} ${CMAKE_PREFIX_PATH})

        foreach(_BUILD_MODULE_PATH {{ '${'+pkg_name+'_'+comp_name+'_BUILD_MODULES_PATHS}' }})
            include(${_BUILD_MODULE_PATH})
        endforeach()

        {%- endfor %}


        ########## TARGETS ##########################################################################
        #############################################################################################

        {%- for comp_name, comp in components %}

        ########## COMPONENT {{ comp_name }} TARGET #################################################

        if(NOT ${CMAKE_VERSION} VERSION_LESS "3.0")
            # Target approach
            if(NOT TARGET {{ pkg_name }}::{{ comp_name }})
                add_library({{ pkg_name }}::{{ comp_name }} INTERFACE IMPORTED)
                set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_INCLUDE_DIRECTORIES
                                      "{{ '${'+pkg_name+'_'+comp_name+'_INCLUDE_DIRS}' }}")
                set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_LINK_DIRECTORIES
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIB_DIRS}' }}")
                set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_LINK_LIBRARIES
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LINK_LIBS}' }};{{ '${'+pkg_name+'_'+comp_name+'_LINKER_FLAGS_LIST}' }}")
                set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_COMPILE_DEFINITIONS
                                      "{{ '${'+pkg_name+'_'+comp_name+'_COMPILE_DEFINITIONS}' }}")
                set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_COMPILE_OPTIONS
                                      "{{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_C}' }};{{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_CXX}' }}")
            endif()
        endif()

        {%- endfor %}

        ########## GLOBAL TARGET ####################################################################

        if(NOT ${CMAKE_VERSION} VERSION_LESS "3.0")
            if(NOT TARGET {{ pkg_name }}::{{ pkg_name }})
                add_library({{ pkg_name }}::{{ pkg_name }} INTERFACE IMPORTED)
                set_target_properties({{ pkg_name }}::{{ pkg_name }} PROPERTIES INTERFACE_LINK_LIBRARIES
                                      "{{ '${'+pkg_name+'_COMPONENTS}' }}")
            endif()
        endif()

    """))

    @property
    def filename(self):
        return None

    @classmethod
    def _get_filename(cls, obj):
        return obj.get_filename(cls.name)

    @property
    def content(self):
        ret = {}
        for pkg_name, cpp_info in self.deps_build_info.dependencies:
            pkg_filename = self._get_filename(cpp_info)
            pkg_findname = self._get_name(cpp_info)
            ret["Find%s.cmake" % pkg_filename] = self._find_for_dep(
                pkg_name=pkg_name,
                pkg_findname=pkg_findname,
                pkg_filename=pkg_filename,
                cpp_info=cpp_info
            )
        return ret

    def _get_components(self, pkg_name, cpp_info):
        components = super(CMakeFindPackageGenerator, self)._get_components(pkg_name, cpp_info)
        ret = []
        for comp_genname, comp, comp_requires_gennames in components:
            deps_cpp_cmake = DepsCppCmake(comp)
            deps_cpp_cmake.public_deps = " ".join(
                ["{}::{}".format(*it) for it in comp_requires_gennames])
            ret.append((comp_genname, deps_cpp_cmake))
        return ret

    def _find_for_dep(self, pkg_name, pkg_findname, pkg_filename, cpp_info):
        # return the content of the FindXXX.cmake file for the package "pkg_name"
        self._validate_components(cpp_info)

        public_deps = self.get_public_deps(cpp_info)
        deps_names = ';'.join(["{}::{}".format(*self._get_require_name(*it)) for it in public_deps])
        pkg_public_deps_filenames = [self._get_filename(self.deps_build_info[it[0]]) for it in
                                     public_deps]

        pkg_version = cpp_info.version
        if cpp_info.components:
            components = self._get_components(pkg_name, cpp_info)
            # Note these are in reversed order, from more dependent to less dependent
            pkg_components = " ".join(["{p}::{c}".format(p=pkg_findname, c=comp_findname) for
                                       comp_findname, _ in reversed(components)])
            pkg_info = DepsCppCmake(cpp_info)
            global_target_variables = target_template.format(name=pkg_findname, deps=pkg_info,
                                                             build_type_suffix="",
                                                             deps_names=deps_names)
            return self.find_components_tpl.render(
                pkg_name=pkg_findname,
                pkg_filename=pkg_filename,
                pkg_version=pkg_version,
                pkg_components=pkg_components,
                global_target_variables=global_target_variables,
                pkg_public_deps_filenames=pkg_public_deps_filenames,
                components=components,
                conan_message=CMakeFindPackageCommonMacros.conan_message,
                conan_find_apple_frameworks=CMakeFindPackageCommonMacros.apple_frameworks_macro,
                conan_package_library_targets=CMakeFindPackageCommonMacros.conan_package_library_targets)
        else:
            # The common macros
            macros_and_functions = "\n".join([
                CMakeFindPackageCommonMacros.conan_message,
                CMakeFindPackageCommonMacros.apple_frameworks_macro,
                CMakeFindPackageCommonMacros.conan_package_library_targets,
            ])

            # compose the cpp_info with its "debug" or "release" specific config
            dep_cpp_info = cpp_info
            build_type = self.conanfile.settings.get_safe("build_type")
            if build_type:
                dep_cpp_info = extend(dep_cpp_info, build_type.lower())

            # The find_libraries_block, all variables for the package, and creation of targets
            deps = DepsCppCmake(dep_cpp_info)
            find_libraries_block = target_template.format(name=pkg_findname, deps=deps,
                                                          build_type_suffix="",
                                                          deps_names=deps_names)

            # The find_transitive_dependencies block
            find_dependencies_block = ""
            if pkg_public_deps_filenames:
                # Here we are generating FindXXX, so find_modules=True
                f = find_transitive_dependencies(pkg_public_deps_filenames, find_modules=True)
                # proper indentation
                find_dependencies_block = ''.join("        " + line if line.strip() else line
                                                  for line in f.splitlines(True))

            return self.find_template.format(name=pkg_findname, version=pkg_version,
                                             filename=pkg_filename,
                                             find_libraries_block=find_libraries_block,
                                             find_dependencies_block=find_dependencies_block,
                                             macros_and_functions=macros_and_functions)
