from search.zenodo import ZenodoSearcher
from search.fsd    import FSDSearcher
from search.sikt   import SiktSearcher

ALL_SEARCHERS = [
    ZenodoSearcher(),   # full files + metadata
    FSDSearcher(),      # metadata only (login required for files)
    SiktSearcher(),     # metadata only (agreement required for files)
]