import sqlite3
from datetime import datetime

def migrate_blood_pressure_data():
    """迁移血压监测数据到新的表结构"""
    try:
        conn = sqlite3.connect('monitor.db')
        cursor = conn.cursor()
        
        # 检查旧表是否存在
        old_tables = [
            'bloodpressure_records',
            'bloodpressure2_records',
            'bloodpressure3_records',
            'bloodpressure_morning', 'bloodpressure_afternoon',
            'bloodpressure2_morning', 'bloodpressure2_afternoon',
            'bloodpressure3_morning', 'bloodpressure3_afternoon'
        ]
        
        migrated_count = 0
        
        for old_table in old_tables:
            cursor.execute(f'''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{old_table}'
            ''')
            
            if cursor.fetchone():
                print(f"\n找到旧表 {old_table}，开始迁移数据...")
                try:
                    # 根据表名确定owner_id
                    owner_id = 1
                    if '2' in old_table:
                        owner_id = 2
                    elif '3' in old_table:
                        owner_id = 3
                    
                    # 处理不同的表结构
                    if '_records' in old_table:
                        # 处理合并表的结构
                        cursor.execute(f'''
                            SELECT date, day_of_week, 
                                   morning_high, morning_low,
                                   afternoon_high, afternoon_low,
                                   notes
                            FROM {old_table}
                        ''')
                        records = cursor.fetchall()
                        
                        for record in records:
                            date, day_of_week, m_high, m_low, a_high, a_low, notes = record
                            
                            # 插入早间记录
                            if m_high or m_low:
                                try:
                                    cursor.execute('''
                                        INSERT INTO morning_bloodpressure_records 
                                        (date, day_of_week, owner_id, morning_high, morning_low)
                                        VALUES (?, ?, ?, ?, ?)
                                    ''', [date, day_of_week, owner_id, m_high, m_low])
                                except sqlite3.IntegrityError:
                                    cursor.execute('''
                                        UPDATE morning_bloodpressure_records 
                                        SET morning_high = ?, morning_low = ?
                                        WHERE date = ? AND owner_id = ?
                                    ''', [m_high, m_low, date, owner_id])
                            
                            # 插入晚间记录
                            if a_high or a_low:
                                try:
                                    cursor.execute('''
                                        INSERT INTO night_bloodpressure_records 
                                        (date, day_of_week, owner_id, night_high, night_low)
                                        VALUES (?, ?, ?, ?, ?)
                                    ''', [date, day_of_week, owner_id, a_high, a_low])
                                except sqlite3.IntegrityError:
                                    cursor.execute('''
                                        UPDATE night_bloodpressure_records 
                                        SET night_high = ?, night_low = ?
                                        WHERE date = ? AND owner_id = ?
                                    ''', [a_high, a_low, date, owner_id])
                            
                            # 插入备注
                            if notes:
                                try:
                                    cursor.execute('''
                                        INSERT INTO bloodpressure_notes_records 
                                        (date, day_of_week, owner_id, notes)
                                        VALUES (?, ?, ?, ?)
                                    ''', [date, day_of_week, owner_id, notes])
                                except sqlite3.IntegrityError:
                                    cursor.execute('''
                                        UPDATE bloodpressure_notes_records 
                                        SET notes = ?
                                        WHERE date = ? AND owner_id = ?
                                    ''', [notes, date, owner_id])
                            
                            migrated_count += 1
                    else:
                        # 处理分离表的结构
                        is_morning = 'morning' in old_table
                        cursor.execute(f'''
                            SELECT date, day_of_week, high, low, notes, risk 
                            FROM {old_table}
                        ''')
                        records = cursor.fetchall()
                        
                        for record in records:
                            date, day_of_week, high, low, notes, risk = record
                            
                            if is_morning:
                                try:
                                    cursor.execute('''
                                        INSERT INTO morning_bloodpressure_records 
                                        (date, day_of_week, owner_id, morning_high, morning_low)
                                        VALUES (?, ?, ?, ?, ?)
                                    ''', [date, day_of_week, owner_id, high, low])
                                except sqlite3.IntegrityError:
                                    cursor.execute('''
                                        UPDATE morning_bloodpressure_records 
                                        SET morning_high = ?, morning_low = ?
                                        WHERE date = ? AND owner_id = ?
                                    ''', [high, low, date, owner_id])
                            else:
                                try:
                                    cursor.execute('''
                                        INSERT INTO night_bloodpressure_records 
                                        (date, day_of_week, owner_id, night_high, night_low)
                                        VALUES (?, ?, ?, ?, ?)
                                    ''', [date, day_of_week, owner_id, high, low])
                                except sqlite3.IntegrityError:
                                    cursor.execute('''
                                        UPDATE night_bloodpressure_records 
                                        SET night_high = ?, night_low = ?
                                        WHERE date = ? AND owner_id = ?
                                    ''', [high, low, date, owner_id])
                            
                            if notes:
                                try:
                                    cursor.execute('''
                                        INSERT INTO bloodpressure_notes_records 
                                        (date, day_of_week, owner_id, notes)
                                        VALUES (?, ?, ?, ?)
                                    ''', [date, day_of_week, owner_id, notes])
                                except sqlite3.IntegrityError:
                                    cursor.execute('''
                                        UPDATE bloodpressure_notes_records 
                                        SET notes = ?
                                        WHERE date = ? AND owner_id = ?
                                    ''', [notes, date, owner_id])
                            
                            migrated_count += 1
                    
                    print(f"成功迁移 {len(records)} 条记录从 {old_table}")
                except Exception as e:
                    print(f"迁移表 {old_table} 时出错: {str(e)}")
            else:
                print(f"未找到表 {old_table}")
        
        print(f"\n总共迁移了 {migrated_count} 条记录")
        print("\n开始计算日均值和风险等级...")
        
        # 计算并更新所有日均值和风险等级
        cursor.execute('''
            SELECT DISTINCT date, owner_id 
            FROM (
                SELECT date, owner_id FROM morning_bloodpressure_records
                UNION
                SELECT date, owner_id FROM night_bloodpressure_records
            )
        ''')
        dates = cursor.fetchall()
        
        updated_count = 0
        for date, owner_id in dates:
            cursor.execute('''
                SELECT m.morning_high, m.morning_low, n.night_high, n.night_low
                FROM morning_bloodpressure_records m
                LEFT JOIN night_bloodpressure_records n 
                ON m.date = n.date AND m.owner_id = n.owner_id
                WHERE m.date = ? AND m.owner_id = ?
            ''', [date, owner_id])
            
            record = cursor.fetchone()
            if record:
                morning_high, morning_low, night_high, night_low = record
                
                avg_high = avg_low = None
                if morning_high and night_high:
                    avg_high = round((morning_high + night_high) / 2, 1)
                elif morning_high:
                    avg_high = morning_high
                elif night_high:
                    avg_high = night_high
                    
                if morning_low and night_low:
                    avg_low = round((morning_low + night_low) / 2, 1)
                elif morning_low:
                    avg_low = morning_low
                elif night_low:
                    avg_low = night_low
                
                if avg_high and avg_low:
                    average = f"{avg_high}/{avg_low}"
                    risk = calculate_risk(avg_high, avg_low)
                    day_of_week = get_chinese_weekday(date)
                    
                    try:
                        cursor.execute('''
                            INSERT INTO bloodpressure_calculation_records 
                            (date, day_of_week, owner_id, average, risk)
                            VALUES (?, ?, ?, ?, ?)
                        ''', [date, day_of_week, owner_id, average, risk])
                        updated_count += 1
                    except sqlite3.IntegrityError:
                        cursor.execute('''
                            UPDATE bloodpressure_calculation_records 
                            SET average = ?, risk = ?
                            WHERE date = ? AND owner_id = ?
                        ''', [average, risk, date, owner_id])
                        updated_count += 1
        
        print(f"更新了 {updated_count} 条日均值记录")
        
        conn.commit()
        print("\n数据迁移完成!")
        
    except Exception as e:
        print(f"迁移过程出错: {str(e)}")
    finally:
        conn.close()

def calculate_risk(high, low):
    """计算血压风险等级"""
    if not high or not low:
        return "未知"
    try:
        high = float(high)
        low = float(low)
        if high <= 120 and low <= 70:
            return "良好"
        elif high <= 130 and low <= 80:
            return "中等"
        else:
            return "偏高"
    except (ValueError, TypeError):
        return "未知"

def get_chinese_weekday(date_str):
    """根据日期获取中文星期几"""
    try:
        weekday_map = {
            0: "星期一",
            1: "星期二",
            2: "星期三",
            3: "星期四",
            4: "星期五",
            5: "星期六",
            6: "星期日"
        }
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return weekday_map[date_obj.weekday()]
    except ValueError:
        return ""

def verify_migrated_data():
    """验证迁移后的数据完整性"""
    try:
        conn = sqlite3.connect('monitor.db')
        cursor = conn.cursor()
        
        print("\n开始验证数据完整性...")
        
        # 检查每个owner_id的记录数
        for owner_id in [1, 2, 3]:
            # 检查早间记录
            morning_count = cursor.execute('''
                SELECT COUNT(*) FROM morning_bloodpressure_records 
                WHERE owner_id = ?
            ''', [owner_id]).fetchone()[0]
            
            # 检查晚间记录
            night_count = cursor.execute('''
                SELECT COUNT(*) FROM night_bloodpressure_records 
                WHERE owner_id = ?
            ''', [owner_id]).fetchone()[0]
            
            # 检查备注记录
            notes_count = cursor.execute('''
                SELECT COUNT(*) FROM bloodpressure_notes_records 
                WHERE owner_id = ?
            ''', [owner_id]).fetchone()[0]
            
            # 检查计算记录
            calc_count = cursor.execute('''
                SELECT COUNT(*) FROM bloodpressure_calculation_records 
                WHERE owner_id = ?
            ''', [owner_id]).fetchone()[0]
            
            print(f"\nowner_id={owner_id} 的记录统计:")
            print(f"早间记录: {morning_count}")
            print(f"晚间记录: {night_count}")
            print(f"备注记录: {notes_count}")
            print(f"计算记录: {calc_count}")
        
        # 检查日期范围
        date_range = cursor.execute('''
            SELECT MIN(date), MAX(date)
            FROM (
                SELECT date FROM morning_bloodpressure_records
                UNION
                SELECT date FROM night_bloodpressure_records
            )
        ''').fetchone()
        
        print(f"\n数据日期范围: {date_range[0]} 至 {date_range[1]}")
        
        # 检查是否有无效数据
        invalid_records = cursor.execute('''
            SELECT m.date, m.owner_id, 
                   m.morning_high, m.morning_low,
                   n.night_high, n.night_low
            FROM morning_bloodpressure_records m
            LEFT JOIN night_bloodpressure_records n 
            ON m.date = n.date AND m.owner_id = n.owner_id
            WHERE 
                (m.morning_high < 0 OR m.morning_low < 0 OR
                 n.night_high < 0 OR n.night_low < 0 OR
                 m.morning_high > 300 OR m.morning_low > 200 OR
                 n.night_high > 300 OR n.night_low > 200)
        ''').fetchall()
        
        if invalid_records:
            print("\n发现无效数据:")
            for record in invalid_records:
                print(f"日期: {record[0]}, owner_id: {record[1]}")
                print(f"早间: {record[2]}/{record[3]}")
                print(f"晚间: {record[4]}/{record[5]}")
        else:
            print("\n未发现无效数据")
        
        # 检查日均值计算是否正确
        incorrect_calcs = cursor.execute('''
            WITH expected_calcs AS (
                SELECT 
                    m.date,
                    m.owner_id,
                    CASE 
                        WHEN m.morning_high IS NOT NULL AND n.night_high IS NOT NULL 
                        THEN ROUND((m.morning_high + n.night_high) / 2.0, 1)
                        WHEN m.morning_high IS NOT NULL THEN m.morning_high
                        WHEN n.night_high IS NOT NULL THEN n.night_high
                    END as exp_high,
                    CASE 
                        WHEN m.morning_low IS NOT NULL AND n.night_low IS NOT NULL 
                        THEN ROUND((m.morning_low + n.night_low) / 2.0, 1)
                        WHEN m.morning_low IS NOT NULL THEN m.morning_low
                        WHEN n.night_low IS NOT NULL THEN n.night_low
                    END as exp_low
                FROM morning_bloodpressure_records m
                LEFT JOIN night_bloodpressure_records n 
                ON m.date = n.date AND m.owner_id = n.owner_id
            )
            SELECT 
                e.date,
                e.owner_id,
                e.exp_high || '/' || e.exp_low as expected,
                c.average as actual
            FROM expected_calcs e
            JOIN bloodpressure_calculation_records c 
            ON e.date = c.date AND e.owner_id = c.owner_id
            WHERE c.average != (e.exp_high || '/' || e.exp_low)
        ''').fetchall()
        
        if incorrect_calcs:
            print("\n发现计算错误:")
            for calc in incorrect_calcs:
                print(f"日期: {calc[0]}, owner_id: {calc[1]}")
                print(f"期望值: {calc[2]}")
                print(f"实际值: {calc[3]}")
        else:
            print("\n所有日均值计算正确")
        
    except Exception as e:
        print(f"验证数据时出错: {str(e)}")
    finally:
        conn.close()

def clean_invalid_data():
    """清理无效的数据记录"""
    try:
        conn = sqlite3.connect('monitor.db')
        cursor = conn.cursor()
        
        print("\n开始清理无效数据...")
        
        # 删除无效的血压值记录
        cursor.execute('''
            DELETE FROM morning_bloodpressure_records
            WHERE morning_high < 0 OR morning_high > 300 OR
                  morning_low < 0 OR morning_low > 200
        ''')
        morning_cleaned = cursor.rowcount
        
        cursor.execute('''
            DELETE FROM night_bloodpressure_records
            WHERE night_high < 0 OR night_high > 300 OR
                  night_low < 0 OR night_low > 200
        ''')
        night_cleaned = cursor.rowcount
        
        # 删除孤立的备注记录
        cursor.execute('''
            DELETE FROM bloodpressure_notes_records
            WHERE date NOT IN (
                SELECT date FROM morning_bloodpressure_records
                UNION
                SELECT date FROM night_bloodpressure_records
            )
        ''')
        notes_cleaned = cursor.rowcount
        
        # 删除孤立的计算记录
        cursor.execute('''
            DELETE FROM bloodpressure_calculation_records
            WHERE date NOT IN (
                SELECT date FROM morning_bloodpressure_records
                UNION
                SELECT date FROM night_bloodpressure_records
            )
        ''')
        calc_cleaned = cursor.rowcount
        
        conn.commit()
        
        print(f"清理了 {morning_cleaned} 条无效的早间记录")
        print(f"清理了 {night_cleaned} 条无效的晚间记录")
        print(f"清理了 {notes_cleaned} 条孤立的备注记录")
        print(f"清理了 {calc_cleaned} 条孤立的计算记录")
        
    except Exception as e:
        print(f"清理数据时出错: {str(e)}")
    finally:
        conn.close()

def fix_data_issues():
    """修复数据问题"""
    try:
        conn = sqlite3.connect('monitor.db')
        cursor = conn.cursor()
        
        print("\n开始修复数据问题...")
        
        # 1. 修复日期格式问题
        cursor.execute('''
            UPDATE morning_bloodpressure_records
            SET date = substr(date, 1, 10)
            WHERE length(date) > 10
        ''')
        date_fixed_morning = cursor.rowcount
        
        cursor.execute('''
            UPDATE night_bloodpressure_records
            SET date = substr(date, 1, 10)
            WHERE length(date) > 10
        ''')
        date_fixed_night = cursor.rowcount
        
        # 2. 修复星期几信息
        cursor.execute('''
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records
                UNION
                SELECT date FROM night_bloodpressure_records
            )
        ''')
        dates = cursor.fetchall()
        
        weekday_fixed = 0
        for (date,) in dates:
            day_of_week = get_chinese_weekday(date)
            if day_of_week:
                cursor.execute('''
                    UPDATE morning_bloodpressure_records
                    SET day_of_week = ?
                    WHERE date = ? AND day_of_week != ?
                ''', [day_of_week, date, day_of_week])
                weekday_fixed += cursor.rowcount
                
                cursor.execute('''
                    UPDATE night_bloodpressure_records
                    SET day_of_week = ?
                    WHERE date = ? AND day_of_week != ?
                ''', [day_of_week, date, day_of_week])
                weekday_fixed += cursor.rowcount
        
        # 3. 修复空值为NULL
        cursor.execute('''
            UPDATE morning_bloodpressure_records
            SET morning_high = NULL
            WHERE morning_high = '' OR morning_high = '0'
        ''')
        null_fixed = cursor.rowcount
        
        cursor.execute('''
            UPDATE morning_bloodpressure_records
            SET morning_low = NULL
            WHERE morning_low = '' OR morning_low = '0'
        ''')
        null_fixed += cursor.rowcount
        
        cursor.execute('''
            UPDATE night_bloodpressure_records
            SET night_high = NULL
            WHERE night_high = '' OR night_high = '0'
        ''')
        null_fixed += cursor.rowcount
        
        cursor.execute('''
            UPDATE night_bloodpressure_records
            SET night_low = NULL
            WHERE night_low = '' OR night_low = '0'
        ''')
        null_fixed += cursor.rowcount
        
        # 4. 重新计算所有日均值和风险等级
        cursor.execute('''
            SELECT DISTINCT date, owner_id 
            FROM (
                SELECT date, owner_id FROM morning_bloodpressure_records
                UNION
                SELECT date, owner_id FROM night_bloodpressure_records
            )
        ''')
        dates = cursor.fetchall()
        
        recalc_count = 0
        for date, owner_id in dates:
            cursor.execute('''
                SELECT m.morning_high, m.morning_low, n.night_high, n.night_low
                FROM morning_bloodpressure_records m
                LEFT JOIN night_bloodpressure_records n 
                ON m.date = n.date AND m.owner_id = n.owner_id
                WHERE m.date = ? AND m.owner_id = ?
            ''', [date, owner_id])
            
            record = cursor.fetchone()
            if record:
                morning_high, morning_low, night_high, night_low = record
                
                avg_high = avg_low = None
                if morning_high and night_high:
                    avg_high = round((morning_high + night_high) / 2, 1)
                elif morning_high:
                    avg_high = morning_high
                elif night_high:
                    avg_high = night_high
                    
                if morning_low and night_low:
                    avg_low = round((morning_low + night_low) / 2, 1)
                elif morning_low:
                    avg_low = morning_low
                elif night_low:
                    avg_low = night_low
                
                if avg_high and avg_low:
                    average = f"{avg_high}/{avg_low}"
                    risk = calculate_risk(avg_high, avg_low)
                    day_of_week = get_chinese_weekday(date)
                    
                    cursor.execute('''
                        UPDATE bloodpressure_calculation_records 
                        SET average = ?, risk = ?
                        WHERE date = ? AND owner_id = ?
                    ''', [average, risk, date, owner_id])
                    if cursor.rowcount > 0:
                        recalc_count += 1
        
        conn.commit()
        
        print(f"修复了 {date_fixed_morning + date_fixed_night} 条日期格式问题")
        print(f"修复了 {weekday_fixed} 条星期几信息")
        print(f"修复了 {null_fixed} 条空值问题")
        print(f"重新计算了 {recalc_count} 条日均值记录")
        
    except Exception as e:
        print(f"修复数据时出错: {str(e)}")
    finally:
        conn.close()

def generate_migration_report():
    """生成数据迁移报告"""
    try:
        conn = sqlite3.connect('monitor.db')
        cursor = conn.cursor()
        
        print("\n生成数据迁移报告...")
        print("=" * 50)
        
        # 1. 总体统计
        print("\n1. 总体数据统计")
        print("-" * 30)
        
        stats = {}
        for owner_id in [1, 2, 3]:
            stats[owner_id] = {
                'morning': cursor.execute('''
                    SELECT COUNT(*), 
                           COUNT(morning_high), 
                           COUNT(morning_low),
                           MIN(date),
                           MAX(date)
                    FROM morning_bloodpressure_records 
                    WHERE owner_id = ?
                ''', [owner_id]).fetchone(),
                
                'night': cursor.execute('''
                    SELECT COUNT(*), 
                           COUNT(night_high), 
                           COUNT(night_low),
                           MIN(date),
                           MAX(date)
                    FROM night_bloodpressure_records 
                    WHERE owner_id = ?
                ''', [owner_id]).fetchone(),
                
                'notes': cursor.execute('''
                    SELECT COUNT(*), COUNT(notes)
                    FROM bloodpressure_notes_records 
                    WHERE owner_id = ?
                ''', [owner_id]).fetchone(),
                
                'calcs': cursor.execute('''
                    SELECT COUNT(*), 
                           COUNT(average),
                           SUM(CASE WHEN risk = '良好' THEN 1 ELSE 0 END),
                           SUM(CASE WHEN risk = '中等' THEN 1 ELSE 0 END),
                           SUM(CASE WHEN risk = '偏高' THEN 1 ELSE 0 END)
                    FROM bloodpressure_calculation_records 
                    WHERE owner_id = ?
                ''', [owner_id]).fetchone()
            }
        
        for owner_id, data in stats.items():
            owner_name = "血压监测" if owner_id == 1 else f"血压监测-{'毛' if owner_id == 2 else '祺'}"
            print(f"\n用户 {owner_name}:")
            print(f"早间记录: {data['morning'][0]} 条 (收缩压: {data['morning'][1]}, 舒张压: {data['morning'][2]})")
            print(f"晚间记录: {data['night'][0]} 条 (收缩压: {data['night'][1]}, 舒张压: {data['night'][2]})")
            print(f"备注记录: {data['notes'][0]} 条 (有效备注: {data['notes'][1]})")
            print(f"计算记录: {data['calcs'][0]} 条 (良好: {data['calcs'][2]}, 中等: {data['calcs'][3]}, 偏高: {data['calcs'][4]})")
            print(f"数据范围: {data['morning'][3] or data['night'][3]} 至 {data['morning'][4] or data['night'][4]}")
        
        # 2. 数据完整性检查
        print("\n2. 数据完整性检查")
        print("-" * 30)
        
        for owner_id in [1, 2, 3]:
            missing_data = cursor.execute('''
                WITH all_dates AS (
                    SELECT DISTINCT date 
                    FROM (
                        SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                        UNION
                        SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
                    )
                )
                SELECT 
                    COUNT(*) as total_days,
                    SUM(CASE WHEN m.date IS NULL THEN 1 ELSE 0 END) as missing_morning,
                    SUM(CASE WHEN n.date IS NULL THEN 1 ELSE 0 END) as missing_night,
                    SUM(CASE WHEN c.date IS NULL THEN 1 ELSE 0 END) as missing_calc
                FROM all_dates d
                LEFT JOIN morning_bloodpressure_records m 
                    ON d.date = m.date AND m.owner_id = ?
                LEFT JOIN night_bloodpressure_records n 
                    ON d.date = n.date AND n.owner_id = ?
                LEFT JOIN bloodpressure_calculation_records c 
                    ON d.date = c.date AND c.owner_id = ?
            ''', [owner_id] * 5).fetchone()
            
            owner_name = "血压监测" if owner_id == 1 else f"血压监测-{'毛' if owner_id == 2 else '祺'}"
            print(f"\n用户 {owner_name}:")
            print(f"总天数: {missing_data[0]}")
            print(f"缺少早间记录: {missing_data[1]} 天")
            print(f"缺少晚间记录: {missing_data[2]} 天")
            print(f"缺少计算记录: {missing_data[3]} 天")
        
        # 3. 异常数据检查
        print("\n3. 异常数据检查")
        print("-" * 30)
        
        for owner_id in [1, 2, 3]:
            abnormal_data = cursor.execute('''
                SELECT 
                    SUM(CASE WHEN morning_high > 200 OR morning_low > 150 THEN 1 ELSE 0 END) as high_morning,
                    SUM(CASE WHEN night_high > 200 OR night_low > 150 THEN 1 ELSE 0 END) as high_night
                FROM (
                    SELECT date, morning_high, morning_low, NULL as night_high, NULL as night_low
                    FROM morning_bloodpressure_records
                    WHERE owner_id = ?
                    UNION ALL
                    SELECT date, NULL, NULL, night_high, night_low
                    FROM night_bloodpressure_records
                    WHERE owner_id = ?
                )
            ''', [owner_id, owner_id]).fetchone()
            
            owner_name = "血压监测" if owner_id == 1 else f"血压监测-{'毛' if owner_id == 2 else '祺'}"
            print(f"\n用户 {owner_name}:")
            print(f"异常早间记录: {abnormal_data[0]} 条")
            print(f"异常晚间记录: {abnormal_data[1]} 条")
        
        print("\n" + "=" * 50)
        print("报告生成完成!")
        
    except Exception as e:
        print(f"生成报告时出错: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    # 在执行前备份数据库
    from datetime import datetime
    import shutil
    
    backup_name = f'monitor_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    shutil.copy2('monitor.db', backup_name)
    print(f"数据库已备份为: {backup_name}")
    
    migrate_blood_pressure_data()
    verify_migrated_data()
    clean_invalid_data()
    fix_data_issues()
    generate_migration_report()  # 添加报告生成步骤 