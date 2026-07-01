import sqlite3
c=sqlite3.connect('collector/db/pronofoot.db')
c.execute("UPDATE matches SET live_clock=? WHERE home=? AND away=?", ("Prol. 105'", "Ivory Coast", "Norway"))
c.commit()
