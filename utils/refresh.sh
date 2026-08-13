#!/bin/bash
# Refresh the tariff / calendar json files from the utility web sites.
#
# Please update script based on your local utility situation, e.g. tariff plan, kenshinbi area etc.
#
# The current json is only rotated out to old_*.json when the scraper that
# produced the replacement exited cleanly; otherwise the good data is kept.
#
# Note: no `set -e` here, `diff` exits non-zero whenever the files differ.

set -u

rc=0

if python tepco_scraper.py tepco_b --nodate new_tepco_b.json; then
    diff -c tepco_b.json new_tepco_b.json
    mv tepco_b.json old_tepco_b.json
    mv new_tepco_b.json tepco_b.json
else
    echo "ERROR: tepco_scraper.py failed, keeping tepco_b.json (see new_tepco_b.json)" >&2
    rc=1
fi

if python tokyo_adj_scraper.py nencho_saiene.json new_nencho_saiene.json; then
    diff -c nencho_saiene.json new_nencho_saiene.json
    mv nencho_saiene.json old_nencho_saiene.json
    mv new_nencho_saiene.json nencho_saiene.json
else
    echo "ERROR: tokyo_adj_scraper.py failed, keeping nencho_saiene.json (see new_nencho_saiene.json)" >&2
    rc=1
fi

COLLECT_BASE=2

# tepco_kenshinbi.py rewrites calendar_<year>.json in place, so stash the
# current one first and only promote it to calendar_old.json on success.
cal_current=$(ls -1t calendar_[0-9]*.json 2>/dev/null | head -1)
cal_backup=""
if [ -n "$cal_current" ]; then
    cal_backup="calendar_backup.$$.json"
    cp "$cal_current" "$cal_backup"
fi

if python tepco_kenshinbi.py $COLLECT_BASE; then
    [ -n "$cal_backup" ] && mv "$cal_backup" calendar_old.json
else
    echo "ERROR: tepco_kenshinbi.py failed, restoring $cal_current" >&2
    # restore in case the run truncated the file part way through
    [ -n "$cal_backup" ] && mv "$cal_backup" "$cal_current"
    rc=1
fi

exit $rc
