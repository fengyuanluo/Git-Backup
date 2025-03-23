def init_db():
    """初始化数据库"""
    conn = get_db()
    c = conn.cursor()
    
    # 创建任务表
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source_path TEXT NOT NULL,
            remote_url TEXT NOT NULL,
            branch TEXT NOT NULL DEFAULT 'main',
            auth_type TEXT NOT NULL,
            access_token TEXT,
            ssh_key_content TEXT,
            schedule TEXT,
            webhook_url TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close() 