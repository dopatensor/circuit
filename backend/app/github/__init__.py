"""GitHub proof of work (R2).

- client.py: talks to GitHub's API and OAuth endpoints (httpx), turning rate limits and
  errors into a few clear exceptions.
- extract.py: pure functions that turn GitHub's JSON into what we keep (original repos,
  commits, languages, frameworks, merged pull requests, recent activity) and map
  languages and frameworks onto our capability list.
- service.py: the database side: connect (OAuth), import, weekly refresh, disconnect.

GitHub is only called by the connect step and the background import, never while
someone views a page: pages read what the import saved.
"""
