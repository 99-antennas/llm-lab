#!/usr/bin/env python3
import sqlite3
import json
import subprocess

conn = sqlite3.connect('/app/backend/data/webui.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM config LIMIT 1')
row = cursor.fetchone()
config = json.loads(row[1])
config['openai']['api_base_urls'] = ['http://host.docker.internal:8080/v1', 'http://pipelines:9099']
config['openai']['api_keys'] = ['not-needed', '0p3n-w3bu!']
cursor.execute('UPDATE config SET data = ? WHERE id = 1', (json.dumps(config),))
conn.commit()

cursor.execute('SELECT * FROM config LIMIT 1')
row = cursor.fetchone()
updated = json.loads(row[1])
print("SUCCESS: Updated API base URLs")
print(updated['openai']['api_base_urls'])
