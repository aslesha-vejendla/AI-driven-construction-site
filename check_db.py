import sqlite3
from datetime import datetime

conn = sqlite3.connect('construction.db')
cursor = conn.cursor()

# Step 1 - Table structure
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('TABLES:', cursor.fetchall())

cursor.execute("PRAGMA table_info(elis_events)")
print('ELIS_EVENTS SCHEMA:', cursor.fetchall())

# Step 2 - Count and sample existing events
cursor.execute("SELECT COUNT(*) FROM elis_events")
print('TOTAL EVENTS:', cursor.fetchone())

cursor.execute("SELECT event_type, severity, category, ml_confidence FROM elis_events LIMIT 5")
print('SAMPLE EVENTS:')
for row in cursor.fetchall():
    print(row)

# Step 3 - Seed test events if table is empty
cursor.execute("SELECT COUNT(*) FROM elis_events")
count = cursor.fetchone()[0]

if count == 0:
    print('\nTable is empty. Seeding test events...')
    test_events = [
        ('safety_violation', 'high',     'safety',    'sensor_01',    1,    'Worker not wearing PPE near Zone B',           '{}'),
        ('equipment_fault',  'critical',  'equipment', 'crane_sensor', None, 'Crane hydraulic pressure drop detected',       '{}'),
        ('delay_alert',      'medium',    'schedule',  'pm_system',    None, 'Concrete pour delayed by 2 hours',             '{}'),
        ('worker_fatigue',   'low',       'health',    'wearable_03',  2,    'Elevated heart rate detected for 30 mins',     '{}'),
        ('site_intrusion',   'high',      'security',  'cctv_02',      None, 'Unauthorised access at Gate 3',                '{}'),
    ]

    for e in test_events:
        cursor.execute("""
            INSERT INTO elis_events 
            (event_type, severity, category, source, worker_id, message, extra_data, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (*e, datetime.now().isoformat()))

    conn.commit()
    print('Seeding done.')
else:
    print(f'\nTable already has {count} events. Skipping seed.')

# Step 4 - Show all events after seed
cursor.execute("SELECT id, event_type, severity, category, source, ml_class, ml_confidence FROM elis_events")
print('\nAll events (id | type | severity | category | source | ml_class | ml_confidence):')
for row in cursor.fetchall():
    print(row)

# Step 5 - Check ML columns populated
cursor.execute("SELECT COUNT(*) FROM elis_events WHERE ml_confidence IS NOT NULL")
ml_count = cursor.fetchone()[0]
print(f'\nEvents with ML confidence populated: {ml_count}')

if ml_count == 0:
    print('WARNING: ml_class and ml_confidence are NULL on all rows.')
    print('         Step 4 (ML classifier) is NOT wired up yet.')
else:
    print('OK: ML classifier is populating confidence scores.')

conn.close()