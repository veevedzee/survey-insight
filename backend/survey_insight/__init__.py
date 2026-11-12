"""Survey Insight: open-source survey analytics.

The package is split into small modules that each do one job, so they can be
tested in isolation and the HTTP layer (``api.py``) stays thin:

- ``loading``      read CSV/XLSX files and detect column types
- ``privacy``      find and remove personal identifiers
- ``cleaning``     flag low-quality responses
- ``stats``        descriptive statistics, reliability, group comparisons
- ``text_themes``  embed, cluster and label open-ended answers
- ``findings``     turn computed statistics into plain-English findings
"""

__version__ = "0.1.0"
