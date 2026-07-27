import streamlit as st
import pandas as pd
import random

# ==========================================
# 核心排表邏輯 (完全體)
# ==========================================
class DutyScheduler:
    def __init__(self, teachers_df, timetable_df, locations_df, coplanning_df, subjects_df):
        self.teachers = self._process_teachers(teachers_df)
        self.timetable = self._process_timetable(timetable_df)
        self.locations = self._process_locations(locations_df)
        self.coplanning = self._process_coplanning(coplanning_df)
        self.subjects = self._process_subjects(subjects_df)
        self.duties = self._define_duties()
        
    def _process_teachers(self, df):
        teachers_dict = {}
        if not df.empty:
            for _, row in df.iterrows():
                teachers_dict[row['姓名']] = {
                    'role': str(row.get('職級', '')).strip(),
                    'is_pe': str(row.get('是否體育老師', '否')).strip() == '是',
                    'special_role': str(row.get('特殊身份', '無')).strip(),
                    'class_name': str(row.get('所屬班別', '無')).strip()
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

    def _define_duties(self):
        duties = {}
        days = ['星期一', '星期二', '星期三', '星期四', '星期五']
        
        # 早上當值
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
                if '雨天操場持咪' in duty:
                    duties[f'{day}_{duty}_單週']['fixed_teacher'], duties[f'{day}_{duty}_雙週']['fixed_teacher'] = ['陳淑怡'], ['陳淑怡']
                if '宣佈' in duty:
                    duties[f'{day}_{duty}_單週']['fixed_teacher'], duties[f'{day}_{duty}_雙週']['fixed_teacher'] = ['謝翠琳'], ['謝翠琳']
        
        # 新增: 各班入班當值
        all_classes = self.subjects.keys()
        for day in days:
            for cls in all_classes:
                duties[f'{day}_入班當值_{cls}_07:55-08:15'] = {'weight': 0.5, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}

        # 其他當值
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

        # 放學隊
        team_lead_routes = ["A", "B", "C", "D", "E", "G"]
        for day in days:
            for route in team_lead_routes:
                duties[f'{day}_放學隊_{route}'] = {'weight': 1.0, 'roles': ['班主任', '非班主任'], 'headcount': 1}
        return duties

    def is_teacher_unavailable(self, teacher_name, day, duty_name, week_type):
        info = self.teachers[teacher_name]
        if "早上" in duty_name and ("07:45" in duty_name or "08:00" in duty_name or "07:55" in duty_name):
            if day in self.coplanning[week_type] and teacher_name in self.coplanning[week_type][day]: return True
        if "放學隊" in duty_name and info.get('class_name','').startswith('1'): return True
        if info.get('special_role') == '輔導主任' and ('小息' in duty_name or '午膳' in duty_name): return True
        if info.get('special_role') == '圖書館老師' and '放學隊' not in duty_name: return True
        return False

    def run_scheduler(self, week_type):
        duties = {k: v for k, v in self.duties.items() if week_type in k or ('單週' not in k and '雙週' not in k)}
        schedule, scores = {duty: [] for duty in duties}, {name: 0 for name in self.teachers}

        for duty, details in duties.items():
            day = duty.split('_')[0]
            assigned = []
            if details.get('fixed_teacher'):
                assigned = details['fixed_teacher']
            elif details.get('class_specific'):
                cls = details['class_specific']
                class_teacher = [name for name, info in self.teachers.items() if info.get('class_name') == cls]
                if class_teacher and not self.is_teacher_unavailable(class_teacher[0], day, duty, week_type):
                    assigned = class_teacher
                else:
                    backup_teachers = [t for t in self.subjects.get(cls, []) if not self.is_teacher_unavailable(t, day, duty, week_type)]
                    backup_teachers.sort(key=lambda n: scores.get(n, 0))
                    if backup_teachers: assigned = [backup_teachers[0]]
            else:
                candidates = [name for name, info in self.teachers.items() if info['role'] in details['roles'] and not self.is_teacher_unavailable(name, day, duty, week_type)]
                candidates.sort(key=lambda n: scores.get(n, 0))
                assigned = candidates[:details['headcount']]
            
            schedule[duty] = assigned
            for teacher in assigned:
                if teacher in scores: scores[teacher] += details['weight']
        return schedule, scores

# ==========================================
# 網頁介面設計 (Streamlit)
# ==========================================
st.set_page_config(page_title="訓導處當值編排系統", page_icon="🏫", layout="wide")
st.title("🏫 訓導處當值表自動編排系統 (完全體)")
st.markdown("系統已內置**所有崗位及豁免規則**。請上傳 5 份核心資料以產出最終當值表。")
st.divider()

cols = st.columns(5)
files = {"1️⃣ 老師名單": "teachers_list.csv", "2️⃣ 課堂時間表": "timetable.csv", "3️⃣ 課室樓層表": "class_locations.csv", "4️⃣ 共備名單": "co_planning.csv", "5️⃣ 主科任教名單": "subject_teachers.csv"}
uploaded_files = {}
for i, (header, fname) in enumerate(files.items()):
    with cols[i]:
        st.subheader(header)
        uploaded_files[fname] = st.file_uploader(f"上傳 {fname}", type=['csv'])

st.divider()

if st.button("🚀 開始自動編排當值表", use_container_width=True, type="primary"):
    if all(uploaded_files.values()):
        with st.spinner('系統正在根據所有規則，為「單週」與「雙週」進行最終運算...'):
            try:
                def read_csv_auto(file):
                    try: return pd.read_csv(file, encoding='utf-8')
                    except UnicodeDecodeError:
                        file.seek(0)
                        try: return pd.read_csv(file, encoding='big5')
                        except UnicodeDecodeError:
                            file.seek(0); return pd.read_csv(file, encoding='cp950')

                dfs = {fname: read_csv_auto(file) for fname, file in uploaded_files.items()}
                
                scheduler = DutyScheduler(dfs['teachers_list.csv'], dfs['timetable.csv'], dfs['class_locations.csv'], dfs['co_planning.csv'], dfs['subject_teachers.csv'])
                odd_schedule, odd_scores = scheduler.run_scheduler('單週')
                even_schedule, even_scores = scheduler.run_scheduler('雙週')
                st.success("✅ 單雙週編排雙軌完成！")

                tab1, tab2, tab3 = st.tabs(["📅 單週當值表", "📅 雙週當值表", "📊 工作量統計 (單/雙週)"])
                with tab1:
                    st.dataframe(pd.DataFrame([{"崗位": k.replace('_單週',''), "負責老師": ", ".join(v)} for k, v in odd_schedule.items()]), use_container_width=True, hide_index=True)
                with tab2:
                    st.dataframe(pd.DataFrame([{"崗位": k.replace('_雙週',''), "負責老師": ", ".join(v)} for k, v in even_schedule.items()]), use_container_width=True, hide_index=True)
                with tab3:
                    scores_list = [{"老師姓名": name, "職級": info['role'], "單週分數": odd_scores.get(name, 0), "雙週分數": even_scores.get(name, 0), "平均分數": (odd_scores.get(name, 0) + even_scores.get(name, 0)) / 2} for name, info in scheduler.teachers.items()]
                    st.dataframe(pd.DataFrame(scores_list).sort_values(by="平均分數", ascending=False), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"讀取檔案或運算時發生錯誤：{e}")
                st.info("請確認您的5份 CSV 檔案格式與欄位名稱是否正確。")
    else:
        st.warning("⚠️ 請先在上方上傳所有 5 個必要的 CSV 檔案！")

