import streamlit as st
import pandas as pd

# ==========================================
# 核心排表邏輯 (完全體 v2.0：連動指派 + 全面豁免)
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
        
        # 早會前當值
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
                
                # 連動指派邏輯
                if '雨天操場持咪' in duty and '雨天操場持咪' in self.fixed_duties_map:
                    teacher = self.fixed_duties_map['雨天操場持咪']
                    duties[f'{day}_{duty}_單週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_{duty}_雙週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_早會_正門大閘_7:30-7:45_單週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_早會_正門大閘_7:30-7:45_雙週']['fixed_teacher'] = [teacher]
                if '宣佈' in duty and '宣佈' in self.fixed_duties_map:
                    teacher = self.fixed_duties_map['宣佈']
                    duties[f'{day}_{duty}_單週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_{duty}_雙週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_早會_雨天操場_7:45-8:00_單週']['fixed_teacher'] = [teacher]
                    duties[f'{day}_早會_雨天操場_7:45-8:00_雙週']['fixed_teacher'] = [teacher]

        # 一年級入班當值
        grade_1_classes = [cls for cls in self.subjects.keys() if str(cls).startswith('1')]
        for day in days:
            for cls in grade_1_classes:
                duties[f'{day}_入班當值_{cls}_07:55-08:15_單週'] = {'weight': 0.5, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}
                duties[f'{day}_入班當值_{cls}_07:55-08:15_雙週'] = {'weight': 0.5, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}

        # 小息(1.0)、午膳(2.0)、放學(1.0)
        other_slots = {
            "小息一_6樓": (2, 1.0), "小息一_5樓": (2, 1.0), "小息一_4樓": (2, 1.0), "小息一_2樓": (2, 1.0), "小息一_地下": (2, 1.0), "小息一_3樓": (1, 1.0), "小息一_1樓前後梯": (1, 1.0),
            "小息二_6樓": (2, 1.0), "小息二_5樓": (2, 1.0), "小息二_4樓": (2, 1.0), "小息二_2樓": (2, 1.0), "小息二_地下": (2, 1.0), "小息二_3樓": (1, 1.0), "小息二_1樓前後梯": (1, 1.0),
            "午膳二_6樓": (2, 2.0), "午膳二_5樓": (2, 2.0), "午膳二_4樓": (2, 2.0), "午膳二_3樓": (2, 2.0), "午膳二_2樓": (2, 2.0), "午膳二_地下": (3, 2.0),
            "放學_雨天操場持咪": (1, 1.0), "放學_家長隊(雨天操場)1": (1, 1.0), "放學_家長隊(雨天操場)2": (1, 1.0), "放學_大閘(外)": (1, 1.0), "放學_新翼持咪": (1, 1.0), "放學_正門大閘": (1, 1.0)
        }
        for day in days:
            for duty, (count, weight) in other_slots.items():
                roles = ['班主任', '非班主任'] if '小息' in duty else (['副校', '主任'] if '放學_' in duty else ['副校', '主任', '非班主任'])
                duties[f'{day}_{duty}'] = {'weight': weight, 'roles': roles, 'headcount': count, 'is_lunch': '午膳' in duty}

        # 放學隊
        team_lead_routes = ["A", "B", "C", "D", "E", "F"]
        for route in team_lead_routes:
            duties[f'全週_放學隊_{route}'] = {'weight': 1.0, 'roles': ['班主任', '非班主任'], 'headcount': 1}
        return duties

    def is_teacher_unavailable(self, teacher_name, day, duty_name, week_type):
        info = self.teachers.get(teacher_name, {})
        if teacher_name in self.fixed_teachers: return True
        if "早上" in duty_name or "入班當值" in duty_name:
            if day in self.coplanning.get(week_type, {}) and teacher_name in self.coplanning[week_type].get(day, []): return True
        if "放學隊" in duty_name and info.get('class_name','').startswith('1'): return True
        if info.get('special_role') == '輔導主任' and ('小息' in duty_name or '午膳' in duty_name): return True
        if info.get('special_role') == '圖書館老師' and '放學隊' not in duty_name: return True
        return False

    def run_scheduler(self, week_type):
        duties = {k: v for k, v in self.duties.items() if week_type in k or ('單週' not in k and '雙週' not in k)}
        schedule, reg_scores, ref_scores = {duty: [] for duty in duties}, {name: 0 for name in self.teachers}, {name: 0 for name in self.teachers}
        weekly_afternoon_teachers = set()

        def get_priority(item):
            name, details = item
            if '全週' in name: return 0
            if details.get('is_lunch'): return 2
            return 1
        sorted_duties = sorted(duties.items(), key=get_priority)

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
                    available_ct.sort(key=lambda n: ref_scores.get(n, 0))
                    assigned = [available_ct[0]]
                else:
                    backup = [t for t in self.subjects.get(cls, []) if not self.is_teacher_unavailable(t, day, duty, week_type)]
                    backup.sort(key=lambda n: ref_scores.get(n, 0))
                    if backup: assigned = [backup[0]]
            else:
                candidates = [name for name, info in self.teachers.items() if info['role'] in details['roles'] and not self.is_teacher_unavailable(name, day, duty, week_type)]
                if '放學' in duty and '全週' not in duty: candidates = [c for c in candidates if c not in weekly_afternoon_teachers]
                candidates.sort(key=lambda n: ref_scores.get(n, 0))
                assigned = candidates[:details['headcount']]
            
            schedule[duty] = assigned
            for teacher in assigned:
                if teacher in ref_scores:
                    ref_scores[teacher] += details['weight']
                    if not details.get('is_lunch', False): reg_scores[teacher] += details['weight']
            if '全週_放學隊' in duty: weekly_afternoon_teachers.update(assigned)
                
        return schedule, reg_scores, ref_scores

# ==========================================
# 網頁介面設計 (Streamlit)
# ==========================================
st.set_page_config(page_title="訓導處當值編排系統", page_icon="🏫", layout="wide")
st.title("🏫 訓導處當值表自動編排系統 (完全資料驅動版)")
st.markdown("系統已搭載**所有崗位及豁免規則**，專責老師將獲連動指派。請上傳 **6** 份核心資料。")
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
        with st.spinner('系統正啟動最高權限引擎，為「單週」與「雙週」進行最終運算...'):
            try:
                def read_csv_auto(file):
                    try: return pd.read_csv(file, encoding='utf-8')
                    except UnicodeDecodeError:
                        file.seek(0)
                        try: return pd.read_csv(file, encoding='big5')
                        except UnicodeDecodeError: file.seek(0); return pd.read_csv(file, encoding='cp950')

                dfs = {fname: read_csv_auto(file) for fname, file in uploaded_files.items()}
                
                scheduler = DutyScheduler(dfs['teachers_list.csv'], dfs['timetable.csv'], dfs['class_locations.csv'], dfs['co_planning.csv'], dfs['subject_teachers.csv'], dfs['fixed_duties.csv'])
                odd_schedule, odd_reg, odd_ref = scheduler.run_scheduler('單週')
                even_schedule, even_reg, even_ref = scheduler.run_scheduler('雙週')
                st.success("✅ 單雙週編排雙軌完成！")

                tab1, tab2, tab3 = st.tabs(["📅 單週當值表", "📅 雙週當值表", "📊 工作量統計 (常規 / 參考)"])
                with tab1:
                    st.dataframe(pd.DataFrame([{"崗位": k.replace('_單週',''), "負責老師": ", ".join([format_name(t, scheduler.teachers) for t in v])} for k, v in odd_schedule.items()]), use_container_width=True, hide_index=True)
                with tab2:
                    st.dataframe(pd.DataFrame([{"崗位": k.replace('_雙週',''), "負責老師": ", ".join([format_name(t, scheduler.teachers) for t in v])} for k, v in even_schedule.items()]), use_container_width=True, hide_index=True)
                with tab3:
                    scores_list = [{"老師姓名": format_name(name, scheduler.teachers), "職級": info['role'], "常規(單)": odd_reg.get(name, 0), "常規(雙)": even_reg.get(name, 0), "常規平均": (odd_reg.get(name, 0) + even_reg.get(name, 0)) / 2, "午膳(單)": int((odd_ref.get(name, 0) - odd_reg.get(name, 0)) / 2), "午膳(雙)": int((even_ref.get(name, 0) - even_reg.get(name, 0)) / 2), "加權參考總分": (odd_ref.get(name, 0) + even_ref.get(name, 0)) / 2} for name, info in scheduler.teachers.items()]
                    st.dataframe(pd.DataFrame(scores_list).sort_values(by="加權參考總分", ascending=False), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"讀取檔案或運算時發生錯誤：{e}")
                st.info("請確認您的 6 份 CSV 檔案格式與欄位名稱是否正確。")
    else:
        st.warning("⚠️ 請先在上方上傳所有 6 個必要的 CSV 檔案！")
