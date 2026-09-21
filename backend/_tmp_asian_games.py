import sqlite3

c = sqlite3.connect("data/football.db")
print("leagues columns:", [r[1] for r in c.execute("pragma table_info(leagues)")])
print("fixtures columns:", [r[1] for r in c.execute("pragma table_info(fixtures)")])
print()
print("=== all leagues ===")
for row in c.execute("select id, name, country, is_catalog, is_hot from leagues order by id"):
    print(row)
print()
print("count leagues", c.execute("select count(*) from leagues").fetchone())
print("count fixtures", c.execute("select count(*) from fixtures").fetchone())
print()
print("=== sample fixtures ===")
for row in c.execute("select * from fixtures limit 1"):
    print(row)
