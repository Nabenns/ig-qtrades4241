import shutil
import sqlite3
from pathlib import Path

c = sqlite3.connect("data/ig_qt.db")
c.execute("UPDATE post_drafts SET status='pending' WHERE status='consumed'")
c.execute("DELETE FROM posts")
c.commit()
posts_dir = Path("data/posts")
if posts_dir.exists():
    shutil.rmtree(posts_dir)
print("reset complete: drafts back to pending, posts cleared, asset dir deleted")
