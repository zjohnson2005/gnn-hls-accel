# Provenance follow-ups

## Canary output path

Launchers should write opening-canary output under that launch's run directory.
`derived/h1_hybrid/_canary_opening/` is a shared tracked path. A later launch
overwrites the previous opening canary, so the file mtime and the measurement
`utc` can diverge from the commit that last touched the path.
