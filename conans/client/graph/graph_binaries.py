import os

from conans.client.graph.graph import (BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING,
                                       BINARY_SKIP, BINARY_UPDATE,
                                       RECIPE_EDITABLE, BINARY_EDITABLE,
                                       RECIPE_CONSUMER, RECIPE_VIRTUAL)
from conans.errors import NoRemoteAvailable, NotFoundException, \
    conanfile_exception_formatter
from conans.model.info import ConanInfo, PACKAGE_ID_UNKNOWN
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference
from conans.util.files import is_dirty, rmdir


class GraphBinariesAnalyzer(object):

    def __init__(self, cache, output, remote_manager):
        self._cache = cache
        self._out = output
        self._remote_manager = remote_manager

    def _check_update(self, upstream_manifest, package_folder, output, node):
        read_manifest = FileTreeManifest.load(package_folder)
        if upstream_manifest != read_manifest:
            if upstream_manifest.time > read_manifest.time:
                output.warn("Current package is older than remote upstream one")
                node.update_manifest = upstream_manifest
                return True
            else:
                output.warn("Current package is newer than remote upstream one")

    def _evaluate_node(self, node, build_mode, update, evaluated_nodes, remotes):
        assert node.binary is None, "Node.binary should be None"
        assert node.package_id is not None, "Node.package_id shouldn't be None"
        assert node.package_id != PACKAGE_ID_UNKNOWN, "Node.package_id shouldn't be Unknown"
        assert node.prev is None, "Node.prev should be None"

        if node.package_id == PACKAGE_ID_UNKNOWN:
            node.binary = BINARY_MISSING
            return

        ref, conanfile = node.ref, node.conanfile
        output = conanfile.output

        # If it has lock
        locked = node.graph_lock_node
        if locked and locked.pref.id == node.package_id:
            pref = locked.pref  # Keep the locked with PREV
        else:
            assert node.prev is None, "Non locked node shouldn't have PREV in evaluate_node"
            pref = PackageReference(ref, node.package_id)

        # Check that this same reference hasn't already been checked
        previous_nodes = evaluated_nodes.get(pref)
        if previous_nodes:
            previous_nodes.append(node)
            previous_node = previous_nodes[0]
            # The previous node might have been skipped, but current one not necessarily
            # keep the original node.binary value (before being skipped), and if it will be
            # defined as SKIP again by self._handle_private(node) if it is really private
            if previous_node.binary == BINARY_SKIP:
                node.binary = previous_node.binary_non_skip
            else:
                node.binary = previous_node.binary
            node.binary_remote = previous_node.binary_remote
            node.prev = previous_node.prev
            return
        evaluated_nodes[pref] = [node]

        if node.recipe == RECIPE_EDITABLE:
            node.binary = BINARY_EDITABLE
            # TODO: PREV?
            return

        with_deps_to_build = False
        # For cascade mode, we need to check also the "modified" status of the lockfile if exists
        # modified nodes have already been built, so they shouldn't be built again
        if build_mode.cascade and not (node.graph_lock_node and node.graph_lock_node.modified):
            for dep in node.dependencies:
                dep_node = dep.dst
                if (dep_node.binary == BINARY_BUILD or
                        (dep_node.graph_lock_node and dep_node.graph_lock_node.modified)):
                    with_deps_to_build = True
                    break
        if build_mode.forced(conanfile, ref, with_deps_to_build):
            output.info('Forced build from source')
            node.binary = BINARY_BUILD
            node.prev = None
            return

        package_folder = self._cache.package_layout(pref.ref,
                                                    short_paths=conanfile.short_paths).package(pref)

        # Check if dirty, to remove it
        with self._cache.package_layout(pref.ref).package_lock(pref):
            assert node.recipe != RECIPE_EDITABLE, "Editable package shouldn't reach this code"
            if is_dirty(package_folder):
                output.warn("Package is corrupted, removing folder: %s" % package_folder)
                rmdir(package_folder)  # Do not remove if it is EDITABLE

            if self._cache.config.revisions_enabled:
                metadata = self._cache.package_layout(pref.ref).load_metadata()
                rec_rev = metadata.packages[pref.id].recipe_revision
                if rec_rev and rec_rev != node.ref.revision:
                    output.warn("The package {} doesn't belong "
                                "to the installed recipe revision, removing folder".format(pref))
                    rmdir(package_folder)

        remote = remotes.selected
        if not remote:
            # If the remote_name is not given, follow the binary remote, or
            # the recipe remote
            # If it is defined it won't iterate (might change in conan2.0)
            metadata = self._cache.package_layout(pref.ref).load_metadata()
            remote_name = metadata.packages[pref.id].remote or metadata.recipe.remote
            remote = remotes.get(remote_name)

        if os.path.exists(package_folder):
            if update:
                if remote:
                    try:
                        tmp = self._remote_manager.get_package_manifest(pref, remote)
                        upstream_manifest, pref = tmp
                    except NotFoundException:
                        output.warn("Can't update, no package in remote")
                    except NoRemoteAvailable:
                        output.warn("Can't update, no remote defined")
                    else:
                        if self._check_update(upstream_manifest, package_folder, output, node):
                            node.binary = BINARY_UPDATE
                            node.prev = pref.revision  # With revision
                            if build_mode.outdated:
                                info, pref = self._remote_manager.get_package_info(pref, remote)
                                package_hash = info.recipe_hash
                elif remotes:
                    pass
                else:
                    output.warn("Can't update, no remote defined")
            if not node.binary:
                node.binary = BINARY_CACHE
                metadata = self._cache.package_layout(pref.ref).load_metadata()
                node.prev = metadata.packages[pref.id].revision
                assert node.prev, "PREV for %s is None: %s" % (str(pref), metadata.dumps())
                package_hash = ConanInfo.load_from_package(package_folder).recipe_hash

        else:  # Binary does NOT exist locally
            remote_info = None
            if remote:
                try:
                    remote_info, pref = self._remote_manager.get_package_info(pref, remote)
                except NotFoundException:
                    pass
                except Exception:
                    conanfile.output.error("Error downloading binary package: '{}'".format(pref))
                    raise

            # If the "remote" came from the registry but the user didn't specified the -r, with
            # revisions iterate all remotes

            if not remote or (not remote_info and self._cache.config.revisions_enabled):
                for r in remotes.values():
                    try:
                        remote_info, pref = self._remote_manager.get_package_info(pref, r)
                    except NotFoundException:
                        pass
                    else:
                        if remote_info:
                            remote = r
                            break

            if remote_info:
                node.binary = BINARY_DOWNLOAD
                node.prev = pref.revision
                package_hash = remote_info.recipe_hash
            else:
                if build_mode.allowed(conanfile):
                    node.binary = BINARY_BUILD
                else:
                    node.binary = BINARY_MISSING
                node.prev = None

        if build_mode.outdated:
            if node.binary in (BINARY_CACHE, BINARY_DOWNLOAD, BINARY_UPDATE):
                local_recipe_hash = self._cache.package_layout(ref).recipe_manifest().summary_hash
                if local_recipe_hash != package_hash:
                    output.info("Outdated package!")
                    node.binary = BINARY_BUILD
                    node.prev = None
                else:
                    output.info("Package is up to date")

        node.binary_remote = remote

    @staticmethod
    def _compute_package_id(node, default_package_id_mode):
        conanfile = node.conanfile
        neighbors = node.neighbors()
        direct_reqs = []  # of Nodes
        indirect_reqs = {}   # of {pref: Nodes}, avoid duplicates
        for neighbor in neighbors:
            ref, nconan = neighbor.ref, neighbor.conanfile
            direct_reqs.append((neighbor.pref, neighbor))
            indirect_reqs.update(nconan.info.requires.nodes())
            conanfile.options.propagate_downstream(ref, nconan.info.full_options)
            # Might be never used, but update original requirement, just in case
            conanfile.requires[ref.name].ref = ref

        # Make sure not duplicated
        direct_refs = [pref for pref, _ in direct_reqs]
        indirect_reqs = {k: v for k, v in indirect_reqs.items() if k not in direct_refs}
        # There might be options that are not upstream, backup them, might be
        # for build-requires
        conanfile.build_requires_options = conanfile.options.values
        conanfile.options.clear_unused([pref for (pref, _) in direct_reqs] + list(indirect_reqs.keys()))
        conanfile.options.freeze()

        conanfile.info = ConanInfo.create(conanfile.settings.values,
                                          conanfile.options.values,
                                          direct_reqs,
                                          indirect_reqs,
                                          default_package_id_mode=default_package_id_mode)

        # Once we are done, call package_id() to narrow and change possible values
        with conanfile_exception_formatter(str(conanfile), "package_id"):
            conanfile.package_id()

        info = conanfile.info
        node.package_id = info.package_id()

    def _handle_private(self, node):
        if node.binary in (BINARY_CACHE, BINARY_DOWNLOAD, BINARY_UPDATE, BINARY_SKIP):
            private_neighbours = node.private_neighbors()
            for neigh in private_neighbours:
                if not neigh.private:
                    continue
                # Current closure contains own node to be skipped
                for n in neigh.public_closure.values():
                    if n.private:
                        # store the binary origin before being overwritten by SKIP
                        n.binary_non_skip = n.binary
                        n.binary = BINARY_SKIP
                        self._handle_private(n)

    def evaluate_graph(self, deps_graph, build_mode, update, remotes):
        default_package_id_mode = self._cache.config.default_package_id_mode
        evaluated = deps_graph.evaluated
        for node in deps_graph.ordered_iterate():
            self._compute_package_id(node, default_package_id_mode)
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                continue
            if node.package_id == PACKAGE_ID_UNKNOWN:
                assert node.binary is None
                node.update = update
                node.build_mode = build_mode
                continue
            self._evaluate_node(node, build_mode, update, evaluated, remotes)
            self._handle_private(node)
