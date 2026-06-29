import sys, os, datetime
sys.path.insert(0, os.path.abspath('.'))
from collector.sources import espn_stats as espn

def main():
    today = datetime.date(2026, 6, 29)
    print("Matches for today:")
    for off in (0, -1, 1):
        for ev in espn.scoreboard(today + datetime.timedelta(days=off)):
            if 'Brazil' in ev['home'] or 'Brazil' in ev['away'] or 'Japan' in ev['home'] or 'Japan' in ev['away']:
                print(ev)

if __name__ == '__main__':
    main()
