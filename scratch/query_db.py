import sqlite3

def main():
    conn = sqlite3.connect('collector/db/pronofoot.db')
    c = conn.cursor()
    c.execute("SELECT utc_date, home, away, home_goals, away_goals, status, live_clock FROM matches WHERE home = 'Brazil' AND away = 'Japan'")
    for row in c.fetchall():
        print(row)

if __name__ == '__main__':
    main()
