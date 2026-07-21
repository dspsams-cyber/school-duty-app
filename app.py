import streamlit as st
import pandas as pd

# ==========================================
# 核心排表邏輯 (內置完整崗位定義)
# ==========================================
class DutyScheduler:
    def __init__(self, teachers_df, timetable_df, locations_df, coplanning_df):
        self.teachers = self._process_teachers(teachers_df)
        self.timetable = self._process_timetable(timetable_df)
        self.locations = self._process_locations(locations_df)
        self.coplanning = self._process_coplanning(coplanning_df)
        self.duties = self._define_duties()
        
    def _process_teachers(self, df):
        teachers_dict = {}
        if not df.empty:
            for _, row in df.iterrows():
                teachers_dict[row['姓名']] = {
                    'role': row['職級'],
                    'is_pe': str(row.get('是否體育老師', '否')).strip() == '是',
                    'special_role': row.get('特殊身份', '無')
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
                name = str(row.get('老師姓名', '')).strip()
                day = str(row.get('星期', '')).strip()
                week = str(row.get('週次', '')).strip()
                
                if name and day in cp['單週']:
                    if week in ['單週', '每週']:
                        cp['單週'][day].append(name)
                    if week in ['雙週', '每週']:
                        cp['雙週'][day].append(name)
        return cp

    def _define_duties(self):
        duties = {}
        days = ['星期一', '星期二', '星期三', '星期四', '星期五']
        
        # 1. 早會前當值
        morning_slots = {
            "早會_雨天操場_7:30-7:45": 1, "早會_雨天操場_7:45-8:00": 1,
            "早會_詢問處_7:30-7:45": 1, "早會_詢問處_7:45-8:00": 1, "早會_詢問處_8:00-8:15": 1,
            "早會_正門大閘_7:30-7:45": 1, "早會_正門大閘_7:45-8:00": 1, "早會_正門大閘_8:00-8:15": 1,
            "早會_雨天操場(二)_7:40-7:55": 1, "早會_雨天操場_7:55-8:10": 1,
            "早會_雨天操場持咪_7:55-8:15": 1, "早會_宣佈_8:20-8:35": 1
        }
        for day in days:
            for duty_name, headcount in morning_slots.items():
                 # 早會崗位區分單雙週
                duties[f'{day}_{duty_name}_單週'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': headcount}
                duties[f'{day}_{duty_name}_雙週'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': headcount}

        # 2. 小息及午膳當值
        recess_lunch_slots = {
            "小息一_6樓": 2, "小息一_5樓": 2, "小息一_4樓": 2, "小息一_2樓": 2, "小息一_地下": 2,
            "小息一_3樓": 1, "小息一_1樓前後梯": 1,
            "小息二_6樓": 2, "小息二_5樓": 2, "小息二_4樓": 2, "小息二_2樓": 2, "小息二_地下": 2,
            "小息二_3樓": 1, "小息二_1樓前後梯": 1,
            "午膳二_6樓": 2, "午膳二_5樓": 2, "午膳二_4樓": 2, "午膳二_3樓": 2, "午膳二_2樓": 2,
            "午膳二_地下": 3
        }
        for day in days:
            for duty_name, headcount in recess_lunch_slots.items():
                roles = ['班主任', '非班主任'] if '小息' in duty_name else ['副校', '主任', '非班主任']
                duties[f'{day}_{duty_name}'] = {'weight': 1 if '小息' in duty_name else 2, 'roles': roles, 'headcount': headcount}

        # 3. 放學當值
        after_school_slots = {
            "放學_雨天操場持咪": 1, "放學_家長隊(雨天操場)1": 1, "放學_家長隊(雨天操場)2": 1,
            "放學_大閘(外)": 1, "放學_新翼持咪": 1, "放學_正門大閘": 1
        }
        for day in days:
            for duty_name, headcount in after_school_slots.items():
                duties[f'{day}_{duty_name}'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': headcount}

        # 4. 放學隊
        team_lead_slots = ["A", "B", "C", "D", "E", "G", "H"]
        for day in days:
            for route in team_lead_slots:
                duties[f'{day}_放學隊_{route}'] = {'weight': 1, 'roles': ['班主任', '非班主任'], 'headcount': 1}
                
        return duties

    def is_teacher_unavailable(self, teacher_name, day, duty_name, week_type):
        # 早上共備豁免
        if "早上" in duty_name and ("07:45" in duty_name or "08:00" in duty_name or "07:55" in duty_name):
            if day in self.coplanning[week_type] and teacher_name in self.coplanning[week_type][day]:
                return True
        return False

    def run_scheduler(self, week_type):
        # 篩選出符合當前週次的早會崗位
        week_specific_duties = {
            name: details for name, details in self.duties.items() 
            if ('單週' in name and week_type == '單週') or \
               ('雙週' in name and week_type == '雙週') or \
               ('單週' not in name and '雙週' not in name)
        }

        schedule = {duty: [] for duty in week_specific_duties}
        scores = {name: 0 for name in self.teachers}
        
        for duty_name, details in week_specific_duties.items():
            day = duty_name.split('_')[0]
            candidates = []
            for name, info in self.teachers.items():
                if info['role'] not in details['roles']:
                    continue
                if self.is_teacher_unavailable(name, day, duty_name, week_type):
                    continue
                
                candidates.append(name)
            
            candidates.sort(key=lambda n: scores[n])
            
            assigned = candidates[:details['headcount']]
            schedule[duty_name] = assigned
            for teacher in assigned:
                scores[teacher] += details['weight']
                
        return schedule, scores

# ==========================================
# 網頁介面設計 (Streamlit)
# ==========================================
st.set_page_config(page_title="訓導處當值編排系統", page_icon="🏫", layout="wide")

st.title("🏫 訓導處當值表自動編排系統")
st.markdown("系統已內置**完整崗位定義**及**單雙週共備豁免**規則。請上傳 4 份核心資料。")

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.subheader("1️⃣ 老師名單")
    file_teachers = st.file_uploader("上傳 teachers_list.csv", type=['csv'])

with col2:
    st.subheader("2️⃣ 課堂時間表")
    file_timetable = st.file_uploader("上傳 timetable.csv", type=['csv'])

with col3:
    st.subheader("3️⃣ 課室樓層表")
    file_locations = st.file_uploader("上傳 class_locations.csv", type=['csv'])

with col4:
    st.subheader("4️⃣ 共備名單")
    file_coplanning = st.file_uploader("上傳 co_planning.csv", type=['csv'])

st.divider()

if st.button("🚀 開始自動編排當值表", use_container_width=True, type="primary"):
    if file_teachers and file_timetable and file_locations and file_coplanning:
        with st.spinner('系統正在根據完整崗位定義，為「單週」與「雙週」進行雙軌運算...'):
            try:
                def read_csv_auto(file):
                    try: return pd.read_csv(file, encoding='utf-8')
                    except UnicodeDecodeError:
                        file.seek(0)
                        try: return pd.read_csv(file, encoding='big5')
                        except UnicodeDecodeError:
                            file.seek(0)
                            return pd.read_csv(file, encoding='cp950')

                df_teachers = read_csv_auto(file_teachers)
                df_timetable = read_csv_auto(file_timetable)
                df_locations = read_csv_auto(file_locations)
                df_coplanning = read_csv_auto(file_coplanning)
                
                scheduler = DutyScheduler(df_teachers, df_timetable, df_locations, df_coplanning)
                
                odd_schedule, odd_scores = scheduler.run_scheduler('單週')
                even_schedule, even_scores = scheduler.run_scheduler('雙週')
                
                st.success("✅ 單雙週編排雙軌完成！")
                
                tab1, tab2, tab3 = st.tabs(["📅 單週當值表", "📅 雙週當值表", "📊 工作量統計 (單/雙週)"])
                
                with tab1:
                    odd_list = [{"當值崗位": k.replace('_單週',''), "負責老師": ", ".join(v)} for k, v in odd_schedule.items()]
                    st.dataframe(pd.DataFrame(odd_list), use_container_width=True, hide_index=True)
                    
                with tab2:
                    even_list = [{"當值崗位": k.replace('_雙週',''), "負責老師": ", ".join(v)} for k, v in even_schedule.items()]
                    st.dataframe(pd.DataFrame(even_list), use_container_width=True, hide_index=True)
                    
                with tab3:
                    scores_list = []
                    for name in scheduler.teachers:
                        scores_list.append({
                            "老師姓名": name, "職級": scheduler.teachers[name]['role'],
                            "單週分數": odd_scores[name], "雙週分數": even_scores[name],
                            "平均分數": (odd_scores.get(name, 0) + even_scores.get(name, 0)) / 2
                        })
                    df_scores = pd.DataFrame(scores_list).sort_values(by="平均分數", ascending=False)
                    st.dataframe(df_scores, use_container_width=True, hide_index=True)
                    
            except Exception as e:
                st.error(f"讀取檔案或運算時發生錯誤：{e}")
                st.info("請確認您的4份 CSV 檔案是否使用了正確的「中文欄位名稱」。")
    else:
        st.warning("⚠️ 請先在上方上傳所有 4 個必要的 CSV 檔案！")
