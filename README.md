# Portable Test Matrix (PTM)
A portable test environment matrix generator for python packages.

The goal of PTM is to as simply as possible:

0. Use project's package manager directly for virtual environment management.
1. Specify testing dependency environments in pyproject.toml
2. Define environments by:
    * python versions
    * dependency versions
    * environment variables
    * version solving strategy (e.g. lowest vs highest)
    * tags
2. Integrate seamlessly with github actions.
    - Allow environments to be read into the GHA strategy matrix.
3. Produce test matrix visualizations.
4. Remote test matrix definitions (drive matrix from a URL holding a toml config)
5. Dynamic Test Strategies (Experimental)
    - Driven off endoflife.date
    - Dynamic dependency ranges

**PTM is not a test runner it is an environment definer, visualizer and bootstrapper.**


*visualization idea: 2D: version x package matrix, heatmapped with shading based on number of runs version appears in, and when a version is hovered over the versions of other packages that are tested in combo are highlighted*
