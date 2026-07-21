import streamlit as st
import pandas as pd

# ==========================================
# 核心排表邏輯 (支援全中文欄位 & 共備名單)
# ==========================================
class DutyScheduler:
    def __init__(self, teachers_df, timetable_df, locations_df, coplanning_df):
        self.teachers = self._process_teachers(teachers_df)
        self.timetable = self._process_timetable(timetable_df)
        self.locations = self._process_locations(locations_df)
        self.coplanning = self._process_coplanning(coplanning_df)
        self.duties = self._define_duties()
        self.schedule = {duty: [] for duty in self.duties}
        
    def _process_teachers(self, df):
        teachers_dict = {}
        for _, row in df.iterrows():
            teachers_dict[row['姓名']] = {
                'role': row['職級'],
                'is_pe': str(row.get('是否體育老師', '否')).strip() == '是',
                'special_role': row.get('特殊身份', '無'),
                'score': 0
            }
        return teachers_dict

    def _process_timetable(self, df):
        tt = {}
        for name in self.teachers:
            tt[name] = {}
            for day in ['星期一', '星期二', '星期三', '星期四', '星期五']:
                if name in df['老師姓名'].values:
                    tt[name][day] = list(df[(df['老師姓名'] == name) & (df['星期'] == day)]['節數'].values)
                else:
                    tt[name][day] = []
        return tt
        
    def _process_locations(self, df):
        return df.set_index(['老師姓名', '星期', '節數'])['樓層'].to_dict() if not df.empty else {}

    def _process_coplanning(self, df):
        cp = {}
        for name in self.teachers:
            cp[name] = {}
            for day in ['星期一', '星期二', '星期三', '星期四', '星期五']:
                # 檢查是否有資料
                if not df.empty and '老師姓名' in df.columns and name in df['老師姓名'].values:
                    cp[name][day] = list(df[(df['老師姓名'] == name) & (df['星期'] == day)]['節數'].values)
                else:
                    cp[name][day] = []
        return cp

    def _define_duties(self):
        duties = {}
        days = ['星期一', '星期二', '星期三', '星期四', '星期五']
        for day in days:
            duties[f'{day}_早上_大閘'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': 2}
            duties[f'{day}_小息_地下'] = {'weight': 1, 'roles': ['班主任', '非班主任'], 'headcount': 3}
            duties[f'{day}_放學_正門'] = {'weight': 1.5, 'roles': ['副校', '主任', '班主任', '非班主任'], 'headcount': 2}
        return duties

    def run_scheduler(self):
        for duty_name, details in self.duties.items():
            candidates = []
            for name, info in self.teachers.items():
                if info['role'] in details['roles']:
                    candidates.append(name)
            
            candidates.sort(key=lambda n: self.teachers[n]['score'])
            
            assigned = candidates[:details['headcount']]
            self.schedule[duty_name] = assigned
            for teacher in assigned:
                self.teachers[teacher]['score'] += details['weight']
                
        return self.schedule, self.teachers

# ==========================================
# 網頁介面設計 (Streamlit)
# ==========================================
st.set_page_config(page_title="訓導處當值編排系統", page_icon="🏫", layout="wide")

st.title("🏫 訓導處當值表自動編排系統")
st.markdown("請在下方上傳最新的 CSV 資料檔，系統將自動為您運算最公平的當值表。")

st.divider()

# 改為 4 個並排的上傳區
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
    # 確保 4 個檔案都已上傳
    if file_teachers and file_timetable and file_locations and file_coplanning:
        with st.spinner('系統正在根據您的條件進行運算，請稍候...'):
            try:
                # 建立一個自動辨識編碼的讀取小幫手
                def read_csv_auto(file):
                    try:
                        return pd.read_csv(file, encoding='utf-8')
                    except UnicodeDecodeError:
                        file.seek(0)
                        try:
                            return pd.read_csv(file, encoding='big5')
                        except UnicodeDecodeError:
                            file.seek(0)
                            return pd.read_csv(file, encoding='cp950')

                # 讀取 4 個檔案
                df_teachers = read_csv_auto(file_teachers)
                df_timetable = read_csv_auto(file_timetable)
                df_locations = read_csv_auto(file_locations)
                df_coplanning = read_csv_auto(file_coplanning)
                
                # 將 df_coplanning 傳入排程器
                scheduler = DutyScheduler(df_teachers, df_timetable, df_locations, df_coplanning)
                schedule_result, scores_result = scheduler.run_scheduler()
                
                st.success("✅ 編排完成！")
                
                tab1, tab2 = st.tabs(["📅 當值表初稿", "📊 老師工作量統計"])
                
                with tab1:
                    schedule_list = [{"當值崗位": k, "負責老師": ", ".join(v)} for k, v in schedule_result.items()]
                    df_schedule = pd.DataFrame(schedule_list)
                    st.dataframe(df_schedule, use_container_width=True, hide_index=True)
                    
                with tab2:
                    scores_list = [{"老師姓名": k, "職級": v['role'], "總權重分數": v['score']} for k, v in scores_result.items()]
                    df_scores = pd.DataFrame(scores_list).sort_values(by="總權重分數", ascending=False)
                    st.dataframe(df_scores, use_container_width=True, hide_index=True)
                    
            except Exception as e:
                st.error(f"讀取檔案或運算時發生錯誤：{e}")
                st.info("請確認您的 CSV 檔案是否使用了正確的「中文欄位名稱」。")
    else:
        st.warning("⚠️ 請先在上方上傳所有 4 個必要的 CSV 檔案！")
