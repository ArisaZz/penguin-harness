# Use a source-built runtime when requested

Method instructions and learned Skills travel in Agent State archives. Installing or editing this toolkit alone does not require a new Penguin executable inside every task container. Use the benchmark's documented published-runtime installation unless the experiment requests a source build or supplies a prepared bundle.

For a source experiment, use the same executable build throughout training and testing. Prefer a prepared installation bundle from the experiment environment. Otherwise locate the current source installation from its CLI entry point and follow the benchmark adapter's installation-bundle contract.

Build the CLI and its workspace dependencies with the repository's package manager. Stage their production dependency graph with the repository's deployment tooling, including the built plugin resources, Benchmark packages and a Node runtime compatible with the task container. An npm install of the CLI alone may resolve workspace dependencies from the registry; it is not equivalent to staging the source build.

Check the adapter's current expected archive layout and launcher path before packaging. Keep symlinks within the bundle and verify its CLI without relying on host-side dependencies. Record the source revision, local changes, runtime versions and bundle digest in the experiment record. Keep credentials and Agent States outside the executable bundle.

Pass the archive using the adapter's documented `install_bundle` option. Reuse it for every trial; there is no need to rebuild it for candidate Skill edits. The learner instructions and requested frozen test States travel in separate State archives.
