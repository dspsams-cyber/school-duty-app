import streamlit as st
import pandas as pd

# ==========================================
# 核心排表邏輯 (完全體：6大檔案 + 專責老師全面豁免 + 簡稱顯示)
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
                if short_n.lower() in ['nan', 'none']: 
                    short_n = ''
                    
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
                name, day, week = str(row.get('老師姓名','')).strip(), str(row.get('星期','')).strip(), str(row.get('週次','')).strip()
                if name and day in cp['單週']:
                    if week in ['單週', '每週']: cp['單週'][day].append(name)
                    if week in ['雙週', '每週']: cp['雙週'][day].append(name)
        return cp

    def _process_subjects(self, df):
        subjects = {}
        if not df.empty and '班別' in df.columns:
            for class_name in df['班別'].unique():
                subjects[class_name] = list(df[df['班別'] == class_name]['老師姓名'].unique())
        return subjects

    def _process_fixed_duties(self, df):
        fd_map = {}
        f_teachers = set()
        if not df.empty and '崗位名稱' in df.columns and '負責老師' in df.columns:
            for _, row in df.iterrows():
                duty_name = str(row.get('崗位名稱', '')).strip()
                teacher = str(row.get('負責老師', '')).strip()
                if duty_name and teacher:
                    fd_map[duty_name] = teacher
                    f_teachers.add(teacher)
        return fd_map, f_teachers

    def _define_duties(self):
        duties = {}
        days = ['星期一', '星期二', '星期三', '星期四', '星期五']
        
        # 1. 早會前當值 (0.5分)
        morning_slots = {
            "早會_雨天操場_7:30-7:45": (1, 0.5), "早會_雨天操場_7:45-8:00": (1, 0.5),
            "早會_詢問處_7:30-7:45": (1, 0.5), "早會_詢問處_7:45-8:00": (1, 0.5), "早會_詢問處_8:00-8:15": (1, 0.5),
            "早會_正門大閘_7:30-7:45": (1, 0.5), "早會_正門大閘_7:45-8:00": (1, 0.5), "早會_正門大閘_8:00-8:15": (1, 0.5),
            "早會_雨天操場(二)_7:40-7:55": (1, 0.5), "早會_雨天操場_7:55-8:10": (1, 0.5),
            "早會_雨天操場持咪_7:55-8:15": (1, 0.5), "早會_宣佈_8:20-8:35": (1, 0.5)
        }
        for day in days:
            for duty, (count, weight) in morning_slots.items():
                duties[f'{day}_{duty}_單週'] = {'weight': weight, 'roles': ['副校', '主任'], 'headcount': count}
                duties[f'{day}_{duty}_雙週'] = {'weight': weight, 'roles': ['副校', '主任'], 'headcount': count}
                
                for fixed_duty_key, fixed_teacher in self.fixed_duties_map.items():
                    if fixed_duty_key in duty:
                        duties[f'{day}_{duty}_單週']['fixed_teacher'] = [fixed_teacher]
                        duties[f'{day}_{duty}_雙週']['fixed_teacher'] = [fixed_teacher]
        
        # 2. 一年級入班當值 (0.5分)
        grade_1_classes = [cls for cls in self.subjects.keys() if str(cls).startswith('1')]
        for day in days:
            for cls in grade_1_classes:
                duties[f'{day}_入班當值_{cls}_07:55-08:15_單週'] = {'weight': 0.5, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}
                duties[f'{day}_入班當值_{cls}_07:55-08:15_雙週'] = {'weight': 0.5, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}

        # 3. 小息、午膳、放學 (1.0分)
        other_slots = {
            "小息一_6樓": (2, 1.0), "小息一_5樓": (2, 1.0), "小息一_4樓": (2, 1.0), "小息一_2樓": (2, 1.0), "小息一_地下": (2, 1.0), "小息一_3樓": (1, 1.0), "小息一_1樓前後梯": (1, 1.0),
            "小息二_6樓": (2, 1.0), "小息二_5樓": (2, 1.0), "小息二_4樓": (2, 1.0), "小息二_2樓": (2, 1.0), "小息二_地下": (2, 1.0), "小息二_3樓": (1, 1.0), "小息二_1樓前後梯": (1, 1.0),
            "午膳二_6樓": (2, 1.0), "午膳二_5樓": (2, 1.0), "午膳二_4樓": (2, 1.0), "午膳二_3樓": (2, 1.0), "午膳二_2樓": (2, 1.0), "午膳二_地下": (3, 1.0),
            "放學_雨天操場持咪": (1, 1.0), "放學_家長隊(雨天操場)1": (1, 1.0), "放學_家長隊(雨天操場)2": (1, 1.0), "放學_大閘(外)": (1, 1.0), "放學_新翼持咪": (1, 1.0), "放學_正門大閘": (1, 1.0)
        }
        for day in days:
            for duty, (count, weight) in other_slots.items():
                roles = ['班主任', '非班主任'] if '小息' in duty else (['副校', '主任'] if '放學_' in duty else ['副校', '主任', '非班主任'])
                duties[f'{day}_{duty}'] = {'weight': weight, 'roles': roles, 'headcount': count}

        # 4. 放學隊 (每週專責，計1.0分)
        team_lead_routes = ["A", "B", "C", "D", "E", "F"]
        for route in team_lead_routes:
            duties[f'全週_放學隊_{route}'] = {'weight': 1.0, 'roles': ['班主任', '非班主任'], 'headcount': 1}
            
        return duties

    def is_teacher_unavailable(self, teacher_name, day, duty_name, week_type):
        info = self.teachers.get(teacher_name, {})
        
        # 專責老師獲得「全面豁免權」
        if teacher_name in self.fixed_teachers: return True
            
        # 共備豁免 (早會及入班當值)
        if "早上" in duty_name or "入班當值" in duty_name:
            if day in self.coplanning[week_type] and teacher_name in self.coplanning[week_type][day]: return True
                
        # 一年級班主任豁免放學隊
        if "放學隊" in duty_name and info.get('class_name','').startswith('1'): return True
            
        # 輔導主任與圖書館老師特殊豁免
        if info.get('special_role') == '輔導主任' and ('小息' in duty_name or '午膳' in duty_name): return True
        if info.get('special_role') == '圖書館老師' and '放學隊' not in duty_name: return True
        
        return False

    def run_scheduler(self, week_type):
        week_specific_duties = {k: v for k, v in self.duties.items() if week_type in k or ('單週' not in k and '雙週' not in k)}
        schedule = {duty: [] for duty in week_specific_duties}
        scores = {name: 0 for name in self.teachers}
        weekly_afternoon_teachers = set()

        sorted_duties = sorted(week_specific_duties.items(), key=lambda x: 0 if '全週' in x[0] else 1)

        for duty, details in sorted_duties:
            day = duty.split('_')[0]
            assigned = []
            
            if details.get('fixed_teacher'):
                assigned = details['fixed_teacher']
            elif details.get('class_specific'):
                cls = details['class_specific']
                class_teachers = [name for name, info in self.teachers.items() if info.get('class_name') == cls]
                available_ct = [t for t in class_teachers if not self.is_teacher_unavailable(t, day, duty, week_type)]
                if available_ct:
                    available_ct.sort(key=lambda n: scores.get(n, 0))
                    assigned = [available_ct[0]]
                else:
                    backup_teachers = [t for t in self.subjects.get(cls, []) if not self.is_teacher_unavailable(t, day, duty, week_type)]
                    backup_teachers.sort(key=lambda n: scores.get(n, 0))
                    if backup_teachers: assigned = [backup_teachers[0]]
            else:
                candidates = [name for name, info in self.teachers.items() if info['role'] in details['roles'] and not self.is_teacher_unavailable(name, day, duty, week_type)]
                if '放學' in duty and '全週' not in duty:
                    candidates = [c for c in candidates if c not in weekly_afternoon_teachers]
                    
                candidates.sort(key=lambda n: scores.get(n, 0))
                assigned = candidates[:details['headcount']]
            
            schedule[duty] = assigned
            for teacher in assigned:
                if teacher in scores: scores[teacher] += details['weight']
                    
            if '全週_放學隊' in duty:
                weekly_afternoon_teachers.update(assigned)
                
        return schedule, scores

# ==========================================
# 網頁介面設計 (Streamlit)
# ==========================================
st.set_page_config(page_title="訓導處當值編排系統", page_icon="🏫", layout="wide")
st.title("🏫 訓導處當值表自動編排系統 (完全資料驅動版)")
st.markdown("系統已內置**所有崗位及豁免規則**，結果將會顯示「姓名(簡稱)」。請上傳 6 份核心資料：")
st.divider()

col1, col2, col3 = st.columns(3)
with col1: file_teachers = st.file_uploader("1️⃣ 老師名單", type=['csv'])
with col2: file_timetable = st.file_uploader("2️⃣ 課堂時間表", type=['csv'])
with col3: file_locations = st.file_uploader("3️⃣ 課室樓層表", type=['csv'])

col4, col5, col6 = st.columns(3)
with col4: file_coplanning = st.file_uploader("4️⃣ 共備名單", type=['csv'])
with col5: file_subjects = st.file_uploader("5️⃣ 主科任教名單", type=['csv'])
with col6: file_fixed = st.file_uploader("6️⃣ 專責崗位名單", type=['csv'])

st.divider()

# 將老師姓名轉換為 "姓名(簡稱)" 的輔助函數
def format_teacher_name(name, teachers_dict):
    info = teachers_dict.get(name, {})
    short_name = info.get('short_name', '')
    if short_name:
        return f"{name}({short_name})"
    return name

if st.button("🚀 開始自動編排當值表", use_container_width=True, type="primary"):
    if file_teachers and file_timetable and file_locations and file_coplanning and file_subjects and file_fixed:
        with st.spinner('系統正啟動最高權限引擎，為「單週」與「雙週」進行最終運算...'):
            try:
                def read_csv_auto(file):
                    try: return pd.read_csv(file, encoding='utf-8')
                    except UnicodeDecodeError:
                        file.seek(0)
                        try: return pd.read_csv(file, encoding='big5')
                        except UnicodeDecodeError:
                            file.seek(0); return pd.read_csv(file, encoding='cp950')

                df_teachers = read_csv_auto(file_teachers)
                df_timetable = read_csv_auto(file_timetable)
                df_locations = read_csv_auto(file_locations)
                df_coplanning = read_csv_auto(file_coplanning)
                df_subjects = read_csv_auto(file_subjects)
                df_fixed = read_csv_auto(file_fixed)
                
                scheduler = DutyScheduler(df_teachers, df_timetable, df_locations, df_coplanning, df_subjects, df_fixed)
                odd_schedule, odd_scores = scheduler.run_scheduler('單週')
                even_schedule, even_scores = scheduler.run_scheduler('雙週')
                st.success("✅ 單雙週編排雙軌完成！")

                tab1, tab2, tab3 = st.tabs(["📅 單週當值表", "📅 雙週當值表", "📊 工作量統計 (單/雙週)"])
                
                with tab1:
                    odd_list = [{"崗位": k.replace('_單週',''), "負責老師": ", ".join([format_teacher_name(t, scheduler.teachers) for t in v])} for k, v in odd_schedule.items()]
                    st.dataframe(pd.DataFrame(odd_list), use_container_width=True, hide_index=True)
                with tab2:
                    even_list = [{"崗位": k.replace('_雙週',''), "負責老師": ", ".join([format_teacher_name(t, scheduler.teachers) for t in v])} for k, v in even_schedule.items()]
                    st.dataframe(pd.DataFrame(even_list), use_container_width=True, hide_index=True)
                with tab3:
                    scores_list = [{"老師姓名": format_teacher_name(name, scheduler.teachers), "職級": info['role'], "單週分數": odd_scores.get(name, 0), "雙週分數": even_scores.get(name, 0), "平均分數": (odd_scores.get(name, 0) + even_scores.get(name, 0)) / 2} for name, info in scheduler.teachers.items()]
                    st.dataframe(pd.DataFrame(scores_list).sort_values(by="平均分數", ascending=False), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"讀取檔案或運算時發生錯誤：{e}")
                st.info("請確認您的 6 份 CSV 檔案格式與欄位名稱是否正確。")
    else:
        st.warning("⚠️ 請先在上方上傳所有 6 個必要的 CSV 檔案！")
