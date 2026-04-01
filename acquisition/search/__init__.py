from search.zenodo import ZenodoSearcher
from search.fsd    import FSDSearcher
from search.sikt   import SiktSearcher

ALL_SEARCHERS = [
    ZenodoSearcher(),
    FSDSearcher(),
    SiktSearcher(),
]