import os, re
path = 'collector/smart_live.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Revert my bad change to smart_live.py first
content = content.replace(
'''    try:
        from collector import embed, realtime
        realtime.main()
        embed.main()
    except Exception:''',
'''    try:
        from collector import embed
        embed.main()
    except Exception:'''
)

old_do_live = '''def do_live_cycle():
    """Un cycle live : score+minute ESPN temps réel, met à jour Elo si match fini, predict."""
    global last_stats_pull
    try:
        from collector import espn_live'''

new_do_live = '''def do_live_cycle():
    """Un cycle live : score+minute ESPN temps réel, met à jour Elo si match fini, predict."""
    global last_stats_pull
    import datetime
    from collector import realtime
    before = realtime._snapshot()
    try:
        from collector import espn_live'''

old_do_live_end = '''    pipeline.predict()
    player_ingest.export_for_web()'''

new_do_live_end = '''    pipeline.predict()
    player_ingest.export_for_web()
    after = realtime._snapshot()
    feed = realtime._load_feed()
    ts = datetime.datetime.now().strftime("%H:%M")
    n = realtime._diff_and_log(before, after, feed, ts)
    if n:
        realtime._save_feed(feed)'''

content = content.replace(old_do_live, new_do_live)
content = content.replace(old_do_live_end, new_do_live_end)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated smart_live.py')
