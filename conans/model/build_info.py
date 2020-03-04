import os
from collections import defaultdict, OrderedDict

import deprecation

DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"
DEFAULT_SHARE = "share"
DEFAULT_BUILD = ""
DEFAULT_FRAMEWORK = "Frameworks"


class Component(object):

    def __init__(self):
        self.name = None
        self.names = {}
        self.system_libs = []  # Ordered list of system libraries
        self.includedirs = []  # Ordered list of include paths
        self.srcdirs = []  # Ordered list of source paths
        self.libdirs = []  # Directories to find libraries
        self.resdirs = []  # Directories to find resources, data, etc
        self.bindirs = []  # Directories to find executables and shared libs
        self.builddirs = []
        self.frameworks = []  # Macos .framework
        self.frameworkdirs = []
        self.rootpaths = []
        self.libs = []  # The libs to link against
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cxxflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags
        self.build_modules = []

    def get_name(self, generator):
        return self.names.get(generator, self.name)


class CppInfo(object):
    """ Build Information declared to be used by the CONSUMERS of a
    conans. That means that consumers must use this flags and configs i order
    to build properly.
    Defined in user CONANFILE, directories are relative at user definition time
    """
    def __init__(self, root_folder):
        self.name = None
        self.names = {}
        self.system_libs = []  # Ordered list of system libraries
        self.includedirs = [DEFAULT_INCLUDE]  # Ordered list of include paths
        self.srcdirs = []  # Ordered list of source paths
        self.libdirs = [DEFAULT_LIB]  # Directories to find libraries
        self.resdirs = [DEFAULT_RES]  # Directories to find resources, data, etc
        self.bindirs = [DEFAULT_BIN]  # Directories to find executables and shared libs
        self.builddirs = [DEFAULT_BUILD]
        self.frameworks = []  # Macos .framework
        self.frameworkdirs = [DEFAULT_FRAMEWORK]
        self.rootpaths = []
        self.libs = []  # The libs to link against
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cxxflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags
        self.build_modules = []
        self.rootpath = ""
        self.sysroot = ""
        self._build_modules_paths = None
        self._include_paths = None
        self._lib_paths = None
        self._bin_paths = None
        self._build_paths = None
        self._res_paths = None
        self._src_paths = None
        self._framework_paths = None
        self.version = None  # Version of the conan package
        self.description = None  # Description of the conan package
        # When package is editable, filter_empty=False, so empty dirs are maintained
        self.filter_empty = True
        self.rootpath = root_folder  # the full path of the package in which the conans is found
        self.components = defaultdict(Component)
        # public_deps is needed to accumulate list of deps for cmake targets
        self.public_deps = []
        self.configs = {}
        self._components_include_paths = []

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self.rootpath, p)
                     if not os.path.isabs(p) else p for p in paths]
        if self.filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    def __getattr__(self, config):
        def _get_cpp_info():
            result = CppInfo(self.rootpath)
            result.rootpath = self.rootpath
            result.sysroot = self.sysroot
            result.includedirs.append(DEFAULT_INCLUDE)
            result.libdirs.append(DEFAULT_LIB)
            result.bindirs.append(DEFAULT_BIN)
            result.resdirs.append(DEFAULT_RES)
            result.builddirs.append(DEFAULT_BUILD)
            result.frameworkdirs.append(DEFAULT_FRAMEWORK)
            return result

        return self.configs.setdefault(config, _get_cpp_info())

    def get_name(self, generator):
        return self.names.get(generator, self.name)

    @property
    def include_paths(self):
        if self._include_paths is None:
            self._include_paths = self._filter_paths(self.includedirs)
        return self._include_paths

    @property
    def lib_paths(self):
        if self._lib_paths is None:
            self._lib_paths = self._filter_paths(self.libdirs)
        return self._lib_paths

    @property
    def src_paths(self):
        if self._src_paths is None:
            self._src_paths = self._filter_paths(self.srcdirs)
        return self._src_paths

    @property
    def bin_paths(self):
        if self._bin_paths is None:
            self._bin_paths = self._filter_paths(self.bindirs)
        return self._bin_paths

    @property
    def build_paths(self):
        if self._build_paths is None:
            self._build_paths = self._filter_paths(self.builddirs)
        return self._build_paths

    @property
    def res_paths(self):
        if self._res_paths is None:
            self._res_paths = self._filter_paths(self.resdirs)
        return self._res_paths

    @property
    def framework_paths(self):
        if self._framework_paths is None:
            self._framework_paths = self._filter_paths(self.frameworkdirs)
        return self._framework_paths

    def get_name(self, generator):
        return self.names.get(generator, self.name)

    # Compatibility for 'cppflags' (old style property to allow decoration)
    @deprecation.deprecated(deprecated_in="1.13", removed_in="2.0", details="Use 'cxxflags' instead")
    def get_cppflags(self):
        return self.cxxflags

    @deprecation.deprecated(deprecated_in="1.13", removed_in="2.0", details="Use 'cxxflags' instead")
    def set_cppflags(self, value):
        self.cxxflags = value

    cppflags = property(get_cppflags, set_cppflags)


class DepCppInfo(object):

    def __init__(self, cpp_info):
        self._cpp_info = cpp_info
        self._libs = None
        self._system_libs = None
        self._frameworks = None
        self._defines = None
        self._cxxflags = None
        self._cflags = None
        self._sharedlinkflags = None
        self._exelinkflags = None
        self._build_modules_paths = None
        self._include_paths = None
        self._lib_paths = None
        self._bin_paths = None
        self._build_paths = None
        self._res_paths = None
        self._src_paths = None
        self._framework_paths = None

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self._cpp_info.rootpath, p)
                     if not os.path.isabs(p) else p for p in paths]
        if self._cpp_info.filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    @property
    def name(self):
        return self._cpp_info.name

    @property
    def names(self):
        return self._cpp_info.names

    def get_name(self, generator):
        return self._cpp_info.get_name(generator)

    @property
    def rootpath(self):
        return self._cpp_info.rootpath

    @property
    def build_modules_paths(self):
        if self._build_modules_paths is None:
            self._build_modules_paths = [os.path.join(self._cpp_info.rootpath, p) if not os.path.isabs(p) else p for p in self._cpp_info.build_modules]
        return self._build_modules_paths

    @property
    def include_paths(self):
        if self._include_paths is None:
            self._include_paths = self._filter_paths(self._cpp_info.includedirs)
            if self._cpp_info.components:
                for _, component in self._cpp_info.components.items():
                    self._include_paths.extend(self._filter_paths(component.includedirs))
        return self._include_paths

    @property
    def lib_paths(self):
        if self._lib_paths is None:
            self._lib_paths = self._filter_paths(self._cpp_info.libdirs)
            if self._cpp_info.components:
                for _, component in self._cpp_info.components.items():
                    self._lib_paths.extend(self._filter_paths(component.libdirs))
        return self._lib_paths

    @property
    def src_paths(self):
        if self._src_paths is None:
            self._src_paths = self._filter_paths(self._cpp_info.srcdirs)
            if self._cpp_info.components:
                for _, component in self._cpp_info.components.items():
                    self._src_paths.extend(self._filter_paths(component.srcdirs))
        return self._src_paths

    @property
    def bin_paths(self):
        if self._bin_paths is None:
            self._bin_paths = self._filter_paths(self._cpp_info.bindirs)
            if self._cpp_info.components:
                for _, component in self._cpp_info.components.items():
                    self._bin_paths.extend(self._filter_paths(component.bindirs))
        return self._bin_paths

    @property
    def build_paths(self):
        if self._build_paths is None:
            self._build_paths = self._filter_paths(self._cpp_info.builddirs)
            if self._cpp_info.components:
                for _, component in self._cpp_info.components.items():
                    self._build_paths.extend(self._filter_paths(component.builddirs))
        return self._build_paths

    @property
    def res_paths(self):
        if self._res_paths is None:
            self._res_paths = self._filter_paths(self._cpp_info.resdirs)
            if self._cpp_info.components:
                for _, component in self._cpp_info.components.items():
                    self._res_paths.extend(self._filter_paths(component.resdirs))
        return self._res_paths

    @property
    def framework_paths(self):
        if self._framework_paths is None:
            self._framework_paths = self._filter_paths(self._cpp_info.frameworkdirs)
            if self._cpp_info.components:
                for _, component in self._cpp_info.components.items():
                    self._framework_paths.extend(self._filter_paths(component.frameworkdirs))
        return self._framework_paths

    def __getattr__(self, item):
        try:
            attr = DepCppInfo(getattr(self._cpp_info, item))
        except AttributeError:  # item is not defined, get config (CppInfo)
            attr = DepCppInfo(self.configs[item])
        return attr

    @property
    def configs(self):
        return self._cpp_info.configs

    def _aggregated_values(self, item):
        if getattr(self, "_%s" % item) is None:
            values = getattr(self._cpp_info, item)
            for _, component in self._cpp_info.components.items():
                values.extend(getattr(component, item))
            setattr(self, "_%s" % item, values)
        return getattr(self, "_%s" % item)

    @property
    def libs(self):
        if self._libs is None:
            values = self._cpp_info.libs
            if self._cpp_info.components:
                for _, component in self._cpp_info.components.items():
                    values.extend(component.libs)
            self._libs = values
        return self._libs
        #return self._aggregated_values("libs")

    @property
    def system_libs(self):
        return self._aggregated_values("system_libs")

    @property
    def frameworks(self):
        return self._aggregated_values("frameworks")

    @property
    def defines(self):
        return self._aggregated_values("defines")

    @property
    def cxxflags(self):
        return self._aggregated_values("cxxflags")

    @property
    def cflags(self):
        return self._aggregated_values("cflags")

    @property
    def sharedlinkflags(self):
        return self._aggregated_values("sharedlinkflags")

    @property
    def exelinkflags(self):
        return self._aggregated_values("exelinkflags")


class DepsCppInfo(object):
    """ Build Information necessary to build a given conans. It contains the
    flags, directories and options if its dependencies. The conans CONANFILE
    should use these flags to pass them to the underlaying build system (Cmake, make),
    so deps info is managed
    """

    def __init__(self):
        self.sysroot = None
        self.system_libs = []
        self.includedirs = []
        self.srcdirs = []
        self.libdirs = []
        self.bindirs = []
        self.resdirs = []
        self.builddirs = []
        self.frameworkdirs = []
        self.libs = []
        self.frameworks = []
        self.rootpaths = []

        # Note these are in reverse order
        self.defines = []
        self.cxxflags = []
        self.cflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []
        self.build_modules = []

        self._dependencies = OrderedDict()
        self.configs = {}

    @property
    def dependencies(self):
        return self._dependencies.items()

    @property
    def deps(self):
        return self._dependencies.keys()

    def __getitem__(self, item):
        return self._dependencies[item]

    def update(self, cpp_info, pkg_name):
        assert isinstance(cpp_info, CppInfo)
        dep_cpp_info = DepCppInfo(cpp_info)

        def merge_lists(seq1, seq2):
            return [s for s in seq1 if s not in seq2] + seq2

        self.system_libs = merge_lists(self.system_libs, dep_cpp_info.system_libs)
        self.includedirs = merge_lists(self.includedirs, dep_cpp_info.include_paths)
        self.srcdirs = merge_lists(self.srcdirs, dep_cpp_info.src_paths)
        self.libdirs = merge_lists(self.libdirs, dep_cpp_info.lib_paths)
        self.bindirs = merge_lists(self.bindirs, dep_cpp_info.bin_paths)
        self.resdirs = merge_lists(self.resdirs, dep_cpp_info.res_paths)
        self.builddirs = merge_lists(self.builddirs, dep_cpp_info.build_paths)
        self.frameworkdirs = merge_lists(self.frameworkdirs, dep_cpp_info.framework_paths)
        self.libs = merge_lists(self.libs, dep_cpp_info.libs)
        self.frameworks = merge_lists(self.frameworks, dep_cpp_info.frameworks)
        self.rootpaths.append(dep_cpp_info.rootpath)

        # Note these are in reverse order
        self.defines = merge_lists(dep_cpp_info.defines, self.defines)
        self.cxxflags = merge_lists(dep_cpp_info.cxxflags, self.cxxflags)
        self.cflags = merge_lists(dep_cpp_info.cflags, self.cflags)
        self.sharedlinkflags = merge_lists(dep_cpp_info.sharedlinkflags, self.sharedlinkflags)
        self.exelinkflags = merge_lists(dep_cpp_info.exelinkflags, self.exelinkflags)
        self.build_modules = merge_lists(self.build_modules, dep_cpp_info.build_modules_paths)

        if not self.sysroot:
            self.sysroot = dep_cpp_info.sysroot

        self._dependencies[pkg_name] = dep_cpp_info
        for config, cpp_info in dep_cpp_info.configs.items():
            self.configs.setdefault(config, DepsCppInfo()).update(cpp_info, pkg_name)

    def __getattr__(self, config):
        return self.configs.setdefault(config, DepsCppInfo())

    @property
    def rootpath(self):
        if self.rootpaths:
            return self.rootpaths[0]
        return ""

    @property
    def include_paths(self):
        return self.includedirs

    @property
    def lib_paths(self):
        return self.libdirs

    @property
    def src_paths(self):
        return self.srcdirs

    @property
    def bin_paths(self):
        return self.bindirs

    @property
    def build_paths(self):
        return self.builddirs

    @property
    def res_paths(self):
        return self.resdirs

    @property
    def build_module_paths(self):
        return self.build_modules

    @property
    def framework_paths(self):
        return self.frameworkdirs
