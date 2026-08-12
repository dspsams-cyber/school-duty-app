import streamlit as st
import pandas as pd

# ==========================================
# 核心排表邏輯 (完全體 v4.8：修復放學變數未定義錯誤)
# ==========================================
class DutyScheduler:
    def __init__(self, teachers_df, timetable_df, locations_df, coplanning_df, subjects_df, fixed_duties_df):
        self.teachers = self._process_teachers(teachers_df)
        self.timetable = self._process_timetable(timetable_df)
        self.locations = self._process_locations(locations_df)
        self.coplanning = self._process_coplanning(coplanning_df)
        self.subjects = self._process_subjects(subjects_df)
        self.fixed_duties_map, self.fixed_teachers = self._process_fixed_duties(fixed_duties_df)
        self.duties = self._define_duties()
        
    def _process_teachers(self, df):
        teachers_dict = {}
        if not df.empty:
            for _, row in df.iterrows():
                short_n = str(row.get('簡稱', '')).strip()
                if short_n.lower() in ['nan', 'none']: short_n = ''
                teachers_dict[row['姓名']] = {
                    'role': str(row.get('職級', '')).strip(),
                    'is_pe': str(row.get('是否體育老師', '否')).strip() == '是',
                    'special_role': str(row.get('特殊身份', '無')).strip(),
                    'class_name': str(row.get('所屬班別', '無')).strip(),
                    'short_name': short_n
                }
        return teachers_dict

    def _process_timetable(self, df):
        tt = {}
        for name in self.teachers:
            tt[name] = {}
            for day in ['星期一', '星期二', '星期三', '星期四', '星期五']:
                if not df.empty and '老師姓名' in df.columns and name in df['老師姓名'].values:
                    tt[name][day] = list(df[(df['老師姓名'] == name) & (df['星期'] == day)]['節數'].values)
                else:
                    tt[name][day] = []
        return tt
        
    def _process_locations(self, df):
        if not df.empty and '老師姓名' in df.columns:
            return df.set_index(['老師姓名', '星期', '節數'])['樓層'].to_dict()
        return {}

    def _process_coplanning(self, df):
        cp = {'單週': {}, '雙週': {}}
        for day in ['星期一', '星期二', '星期三', '星期四', '星期五']:
            cp['單週'][day] = []
            cp['雙週'][day] = []
        if not df.empty and '老師姓名' in df.columns:
            for _, row in df.iterrows():
                name = str(row.get('老師姓名','')).strip()
                day = str(row.get('星期','')).strip()
                week = str(row.get('週次','')).strip()
                
                # 嚴格區分單週與雙週名單
                if name and day in cp['單週']:
                    if week == '單週': cp['單週'][day].append(name)
                    if week == '雙週': cp['雙週'][day].append(name)
        return cp

    def _process_subjects(self, df):
        subjects = {}
        if not df.empty and '班別' in df.columns:
            for class_name in df['班別'].unique():
                subjects[class_name] = list(df[df['班別'] == class_name]['老師姓名'].unique())
        return subjects

    def _process_fixed_duties(self, df):
        fd_map, f_teachers = {}, set()
        if not df.empty and '崗位名稱' in df.columns and '負責老師' in df.columns:
            for _, row in df.iterrows():
                duty_name, teacher = str(row.get('崗位名稱', '')).strip(), str(row.get('負責老師', '')).strip()
                if duty_name and teacher:
                    fd_map[duty_name] = teacher
                    f_teachers.add(teacher)
        return fd_map, f_teachers

    def _define_duties(self):
        duties = {}
        days = ['星期一', '星期二', '星期三', '星期四', '星期五']
        
        # 1. 早會前當值 (精細設定職級鎖)
        morning_slots = {
            "早會_雨天操場_7:30-7:55": {"count": 2, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_雨天操場_7:55-8:20": {"count": 2, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_詢問處_7:30-7:55": {"count": 2, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_詢問處_7:55-8:20": {"count": 3, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_正門大閘_7:30-7:55": {"count": 2, "weight": 25, "roles": ['副校', '主任']}, # 大閘保安鎖
            "早會_正門大閘_7:55-8:20": {"count": 3, "weight": 25, "roles": ['副校', '主任']}, # 大閘保安鎖
            "早會_雨天操場持咪_7:55-8:20": {"count": 1, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_宣佈_8:15-8:35": {"count": 1, "weight": 20, "roles": ['副校', '主任', '非班主任']}
        }
        
        for day in days:
            for duty, details in morning_slots.items():
                duties[f'{day}_{duty}_單週'] = {'weight': details['weight'], 'roles': details['roles'], 'headcount': details['count']}
                duties[f'{day}_{duty}_雙週'] = {'weight': details['weight'], 'roles': details['roles'], 'headcount': details['count']}
                
                # 連動指派邏輯
                if '雨天操場持咪' in duty and '雨天操場持咪' in self.fixed_duties_map:
                    teacher = self.fixed_duties_map['雨天操場持咪']
                    duties[f'{day}_{duty}_單週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_{duty}_雙週']['fixed_teacher'] = [teacher]
                if '早會_正門大閘_7:30-7:55' == duty and '雨天操場持咪' in self.fixed_duties_map:
                    teacher = self.fixed_duties_map['雨天操場持咪']
                    duties[f'{day}_{duty}_單週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_{duty}_雙週']['fixed_teacher'] = [teacher]
                if '宣佈' in duty and '宣佈' in self.fixed_duties_map:
                    teacher = self.fixed_duties_map['宣佈']
                    duties[f'{day}_{duty}_單週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_{duty}_雙週']['fixed_teacher'] = [teacher]
                    
        # 2. 全校 (1-6年級) 入班當值
        all_classes = [cls for cls in self.subjects.keys() if str(cls) and str(cls)[0] in '123456']
        for day in days:
            for cls in all_classes:
                duties[f'{day}_入班當值_{cls}_07:55-08:15_單週'] = {'weight': 20, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}
                duties[f'{day}_入班當值_{cls}_07:55-08:15_雙週'] = {'weight': 20, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}
                
        # 3. 小息(15分)、午膳(30分)、放學(20分)
        other_slots = {
            "小息一_6樓_9:45-10:00": (1, 15), "小息一_5樓_9:45-10:00": (1, 15), "小息一_4樓_9:45-10:00": (1, 15),
            "小息一_2樓_9:45-10:00": (1, 15), "小息一_地下_9:45-10:00": (1, 15), "小息一_3樓_9:45-10:00": (1, 15),
            "小息一_1樓前後梯_9:45-10:00": (1, 15),
            "小息二_6樓_11:10-11:25": (1, 15), "小息二_5樓_11:10-11:25": (1, 15), "小息二_4樓_11:10-11:25": (1, 15),
            "小息二_2樓_11:10-11:25": (1, 15), "小息二_地下_11:10-11:25": (1, 15), "小息二_3樓_11:10-11:25": (1, 15),
            "小息二_1樓前後梯_11:10-11:25": (1, 15),
            "午膳二_6樓_13:05-13:35": (1, 30), "午膳二_5樓_13:05-13:35": (1, 30), "午膳二_4樓_13:05-13:35": (1, 30),
            "午膳二_3樓_13:05-13:35": (1, 30), "午膳二_2樓_13:05-13:35": (1, 30), "午膳二_地下_13:05-13:35": (1, 30),
            "放學_雨天操場持咪_15:25-15:45": (1, 20), "放學_家長隊(雨天操場)1_15:25-15:45": (1, 20),
            "放學_家長隊(雨天操場)2_15:25-15:45": (1, 20), "放學_大閘(外)_15:25-15:45": (1, 20),
            "放學_新翼持咪_15:25-15:45": (1, 20), "放學_正門大閘_15:25-15:45": (1, 20)
        }
        
        for day in days:
            for duty, (count, weight) in other_slots.items():
                roles = ['班主任', '非班主任'] if '小息' in duty else (['副校', '主任'] if '放學_' in duty else ['副校', '主任', '非班主任'])
                duties[f'{day}_{duty}'] = {'weight': weight, 'roles': roles, 'headcount': count, 'is_lunch': '午膳' in duty}
                
        # 4. 全週放學隊
        team_lead_routes = ["A", "B", "C", "D", "E", "F"]
        for route in team_lead_routes:
            duties[f'全週_放學隊_{route}_15:25-15:45'] = {'weight': 20, 'roles': ['班主任', '非班主任'], 'headcount': 1}
        return duties

    # 時段分類器，負責萃取崗位的時間段
    def _get_duty_slot(self, duty_name):
        if "7:30" in duty_name: return "M1"
        if "7:55" in duty_name or "07:55" in duty_name: return "M2"
        if "8:15" in duty_name or "宣佈" in duty_name: return "M3"
        if "小息一" in duty_name or "9:45" in duty_name: return "R1"
        if "小息二" in duty_name or "11:10" in duty_name: return "R2"
        if "午膳" in duty_name or "13:05" in duty_name: return "L1"
        if "放學" in duty_name or "15:25" in duty_name: return "D1"
        return "UNKNOWN"

    def is_teacher_unavailable(self, teacher_name, day, duty_name, week_type):
        info = self.teachers.get(teacher_name, {})
        
        if teacher_name in self.fixed_teachers: return True
        
        # 單雙週共備嚴格豁免
        if "早會" in duty_name or "入班當值" in duty_name:
            if day in self.coplanning.get(week_type, {}) and teacher_name in self.coplanning[week_type].get(day, []): 
                return True
                
        # 條件 1：楊不能在 7:30-7:55 的時段當值
        if "7:30-7:55" in duty_name and "楊" in teacher_name:
            return True
            
        # 條件 2：負責「宣佈」的老師不能在 7:55-8:20 站崗
        if "7:55-8:20" in duty_name:
            announcer = self.fixed_duties_map.get("宣佈", "")
            if announcer and announcer == teacher_name:
                return True
            
        # 條件 3：特定日子特定老師免午膳當值
        if "午膳" in duty_name:
            if day == "星期一" and "浩" in teacher_name:
                return True
            if day == "星期二" and "馬" in teacher_name:
                return True
            if day == "星期四" and "蔡" in teacher_name:
                return True

        if "放學隊" in duty_name and info.get('class_name','').startswith('1'): return True
        if info.get('special_role') == '輔導主任' and ('小息' in duty_name or '午膳' in duty_name): return True
        if info.get('special_role') == '圖書館老師' and '放學隊' not in duty_name: return True
        
        return False

    def run_scheduler(self, week_type):
        duties = {k: v for k, v in self.duties.items() if week_type in k or ('單週' not in k and '雙週' not in k)}
        schedule = {duty: [] for duty in duties}
        reg_scores = {name: 0 for name in self.teachers}
        lunch_scores = {name: 0 for name in self.teachers}
        ref_scores = {name: 0 for name in self.teachers}
        
        # 【重要修正】初始化宣告放學防重複追蹤名單，解決未定義錯誤！
        weekly_afternoon_teachers = set()
        
        # 每日時段佔用追蹤器
        teacher_busy_slots = {name: {d: set() for d in ['星期一', '星期二', '星期三', '星期四', '星期五']} for name in self.teachers}
        
        def is_free(t_name, d, s):
            if s == "UNKNOWN": return True
            days_to_check = ['星期一', '星期二', '星期三', '星期四', '星期五'] if d == '全週' else [d]
            for check_day in days_to_check:
                busy = teacher_busy_slots.get(t_name, {}).get(check_day, set())
                if s in busy: return False
                
                # 防禦 M2(7:55) 與 M3(8:15) 的重疊
                if s == "M2" and "M3" in busy: return False
                if s == "M3" and "M2" in busy: return False
                
                # 防禦 M1(7:30) 與 M2(7:55/入班) 連續當值，避免站 50 分鐘
                if s == "M1" and "M2" in busy: return False
                if s == "M2" and "M1" in busy: return False
                
            return True

        def mark_busy(t_name, d, s):
            if s == "UNKNOWN": return
            days_to_mark = ['星期一', '星期二', '星期三', '星期四', '星期五'] if d == '全週' else [d]
            for mark_day in days_to_mark:
                if t_name in teacher_busy_slots:
                    teacher_busy_slots[t_name][mark_day].add(s)
        
        def get_priority(item):
            name, details = item
            if '全週' in name: return 0
            if details.get('is_lunch'): return 2
            return 1
            
        sorted_duties = sorted(duties.items(), key=get_priority)
        for duty, details in sorted_duties:
            day = duty.split('_')[0]
            slot = self._get_duty_slot(duty)
            assigned = []
            
            if details.get('class_specific'):
                cls = details['class_specific']
                class_teachers = [name for name, info in self.teachers.items() if info.get('class_name') == cls]
                available_ct = [t for t in class_teachers if not self.is_teacher_unavailable(t, day, duty, week_type) and is_free(t, day, slot)]
                if available_ct:
                    available_ct.sort(key=lambda n: ref_scores.get(n, 0))
                    assigned = [available_ct[0]]
                else:
                    backup = [t for t in self.subjects.get(cls, []) if not self.is_teacher_unavailable(t, day, duty, week_type) and is_free(t, day, slot)]
                    backup.sort(key=lambda n: ref_scores.get(n, 0))
                    if backup: assigned = [backup[0]]
            else:
                if details.get('fixed_teacher'):
                    assigned.extend(details['fixed_teacher'])
                    # 專責老師雖然強制排入，但也要標記佔用時段，以免系統把他們排去別的時段
                    for t in details['fixed_teacher']:
                        mark_busy(t, day, slot)
                
                remaining_spots = details['headcount'] - len(assigned)
                if remaining_spots > 0:
                    candidates = [name for name, info in self.teachers.items() if info['role'] in details['roles'] and name not in assigned and not self.is_teacher_unavailable(name, day, duty, week_type) and is_free(name, day, slot)]
                    if '放學' in duty and '全週' not in duty: 
                        candidates = [c for c in candidates if c not in weekly_afternoon_teachers]
                    candidates.sort(key=lambda n: ref_scores.get(n, 0))
                    assigned.extend(candidates[:remaining_spots])
            
            schedule[duty] = assigned
            for teacher in assigned:
                # 只有非專責(剛剛動態加入的)或未標記的才標記
                mark_busy(teacher, day, slot)
                
                if teacher in ref_scores:
                    ref_scores[teacher] += details['weight']
                    if details.get('is_lunch', False):
                        lunch_scores[teacher] += details['weight']
                    else:
                        reg_scores[teacher] += details['weight']
            
            if '全週_放學隊' in duty: weekly_afternoon_teachers.update(assigned)
                
        return schedule, reg_scores, lunch_scores, ref_scores

# ==========================================
# 網頁介面設計 (Streamlit)
# ==========================================
st.set_page_config(page_title="訓導處當值編排系統", page_icon="🏫", layout="wide")
st.title("🏫 訓導處當值表自動編排系統 (以「分鐘」精準計分版)")
st.markdown("系統已加入**同日同時段防分身**及**早會防連續當值**機制，確保老師工作分配公平且人性化。")
st.divider()

cols1 = st.columns(3); cols2 = st.columns(3)
files_map = {"1️⃣ 老師名單": "teachers_list.csv", "2️⃣ 課堂時間表": "timetable.csv", "3️⃣ 課室樓層表": "class_locations.csv", "4️⃣ 共備名單": "co_planning.csv", "5️⃣ 主科任教名單": "subject_teachers.csv", "6️⃣ 專責崗位名單": "fixed_duties.csv"}
uploaded_files = {}

for i, (header, fname) in enumerate(files_map.items()):
    col = cols1[i] if i < 3 else cols2[i-3]
    with col:
        uploaded_files[fname] = st.file_uploader(header, type=['csv'])
st.divider()

def format_name(name, teachers_dict):
    info = teachers_dict.get(name, {})
    s_name = info.get('short_name', '')
    return f"{name}({s_name})" if s_name else name

if st.button("🚀 開始自動編排當值表", use_container_width=True, type="primary"):
    if all(uploaded_files.values()):
        with st.spinner('系統正啟動最高權限引擎，以「實際分鐘數」進行排程...'):
            try:
                def read_csv_auto(file):
                    try: return pd.read_csv(file, encoding='utf-8')
                    except UnicodeDecodeError:
                        file.seek(0)
                        try: return pd.read_csv(file, encoding='big5')
                        except UnicodeDecodeError: file.seek(0); return pd.read_csv(file, encoding='cp950')
                        
                dfs = {fname: read_csv_auto(file) for fname, file in uploaded_files.items()}
                
                scheduler = DutyScheduler(dfs['teachers_list.csv'], dfs['timetable.csv'], dfs['class_locations.csv'], dfs['co_planning.csv'], dfs['subject_teachers.csv'], dfs['fixed_duties.csv'])
                odd_schedule, odd_reg, odd_lunch, odd_ref = scheduler.run_scheduler('單週')
                even_schedule, even_reg, even_lunch, even_ref = scheduler.run_scheduler('雙週')
                st.success("✅ 單雙週編排雙軌完成！")
                
                tab1, tab2, tab3 = st.tabs(["📅 單週當值表", "📅 雙週當值表", "📊 工作量統計 (分鐘數)"])
                with tab1:
                    st.dataframe(pd.DataFrame([{"崗位": k.replace('_單週',''), "負責老師": ", ".join([format_name(t, scheduler.teachers) for t in v])} for k, v in odd_schedule.items()]), use_container_width=True, hide_index=True)
                with tab2:
                    st.dataframe(pd.DataFrame([{"崗位": k.replace('_雙週',''), "負責老師": ", ".join([format_name(t, scheduler.teachers) for t in v])} for k, v in even_schedule.items()]), use_container_width=True, hide_index=True)
                with tab3:
                    scores_list = [{
                        "老師姓名": format_name(name, scheduler.teachers), 
                        "職級": info['role'], 
                        "常規(單週分鐘)": odd_reg.get(name, 0), 
                        "常規(雙週分鐘)": even_reg.get(name, 0), 
                        "午膳(單週分鐘)": odd_lunch.get(name, 0), 
                        "午膳(雙週分鐘)": even_lunch.get(name, 0), 
                        "總分鐘數(平均)": (odd_ref.get(name, 0) + even_ref.get(name, 0)) / 2
                    } for name, info in scheduler.teachers.items()]
                    st.dataframe(pd.DataFrame(scores_list).sort_values(by="總分鐘數(平均)", ascending=False), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"讀取檔案或運算時發生錯誤：{e}")
                st.info("請確認您的 6 份 CSV 檔案格式與欄位名稱是否正確。")
    else:
        st.warning("⚠️ 請先在上方上傳所有 6 個必要的 CSV 檔案！")
