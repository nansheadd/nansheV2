# quick_test_db.py
from app.db.session import engine
print(engine.url.render_as_string(hide_password=True))
