import streamlit as st
import pandas as pd

# ==========================================
# 核心排表邏輯 (支援進階條件與多檔案上傳)
# ==========================================
class DutyScheduler:
    def __init__(self, teachers_df, timetable_df, locations_df, meetings_df):
        self.teachers = self._process_teachers(teachers_df)
        self.timetable = self._process_timetable(timetable_df)
        self.locations = self._process_locations(locations_df)
        self.meetings = self._process_meetings(meetings_df) # 新增：備課會議名單
        self.duties = self._define_duties() # 暫時使用內建預設，待您上傳 Excel 後可改為動態讀取
        self.schedule = {duty: [] for duty in self.duties}
        
    def _process_teachers(self, df):
        teachers_dict = {}
        for _, row in df.iterrows():
            # 使用「簡稱」或「全名」皆可，這裡假設以全名為主，並建立簡稱對照
            name = str(row['姓名']).strip()
            teachers_dict[name] = {
                'role': str(row['職級']).strip(),
                'is_pe': str(row.get('是否體育老師', '否')).strip() == '是',
                'special_role': str(row.get('特殊身份', '無')).strip(),
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

    def _process_meetings(self, df):
        # 處理備課會議名單，格式預期為：老師姓名, 星期, 單雙周
        meetings = {}
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                name = str(row.get('老師姓名', '')).strip()
                day = str(row.get('星期', '')).strip()
                week_type = str(row.get('單雙周', '單雙周')).strip() # 單周/雙周/單雙周
                if name not in meetings:
                    meetings[name] = []
                meetings[name].append({'day': day, 'week_type': week_type})
        return meetings

    def _define_duties(self):
        # 這裡先預設寫入您的核心條件，日後可改為直接讀取您上傳的 Excel
        duties = {}
        days = ['星期一', '星期二', '星期三', '星期四', '星期五']
        for day in days:
            # 1. 早會前當值 (分單雙周，限副校/主任)
            duties[f'{day}_早會_雨天操場持咪(單周)'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': 1, 'fixed': '陳淑怡', 'type': '早會', 'week': '單周'}
            duties[f'{day}_早會_雨天操場持咪(雙周)'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': 1, 'fixed': '陳淑怡', 'type': '早會', 'week': '雙周'}
            duties[f'{day}_早會_早會宣佈(單周)'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': 1, 'fixed': '謝翠琳', 'type': '早會', 'week': '單周'}
            duties[f'{day}_早會_早會宣佈(雙周)'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': 1, 'fixed': '謝翠琳', 'type': '早會', 'week': '雙周'}
            duties[f'{day}_早會_一般崗位(單周)'] = {'weight': 1, 'roles': ['副校', '主任'], 'headcount': 2, 'type': '早會', 'week': '單周'}
            
            # 2. 小息當值 (地下需體育老師，盡量避開淑、謝)
            duties[f'{day}_小息_地下'] = {'weight': 1, 'roles': ['班主任', '非班主任', '主任'], 'headcount': 3, 'need_pe': True, 'type': '小息'}
            duties[f'{day}_小息_樓層'] = {'weight': 1, 'roles': ['班主任', '非班主任', '主任'], 'headcount': 4, 'type': '小息'}
            
            # 3. 午膳當值 (限主任/非班主任，盡量避開淑、謝)
            duties[f'{day}_午膳_地下'] = {'weight': 2, 'roles': ['主任', '非班主任'], 'headcount': 2, 'need_pe': True, 'type': '午膳'}
            
            # 4. 放學當值 (限副校/主任，淑不能編入)
            duties[f'{day}_放學_一般崗位'] = {'weight': 1.5, 'roles': ['副校', '主任'], 'headcount': 3, 'exclude': ['陳淑怡'], 'type': '放學'}
            
        return duties

    def _is_in_meeting(self, teacher, day, week_type):
        if teacher not in self.meetings:
            return False
        for m in self.meetings[teacher]:
            if m['day'] == day and (m['week_type'] == week_type or m['week_type'] == '單雙周'):
                return True
        return False

    def run_scheduler(self):
        for duty_name, details in self.duties.items():
            assigned = []
            day = duty_name.split('_')[0]
            duty_type = details.get('type', '')
            week_type = details.get('week', '單雙周')
            
            # --- 處理強制固定人員 (例如：淑負責持咪，謝負責宣佈) ---
            if 'fixed' in details:
                fixed_teacher = details['fixed']
                # 檢查是否因為開會衝突 (硬條件)
                if not self._is_in_meeting(fixed_teacher, day, week_type):
                    assigned.append(fixed_teacher)
                    if fixed_teacher in self.teachers:
                        self.teachers[fixed_teacher]['score'] += details['weight']
                self.schedule[duty_name] = assigned
                continue # 固定崗位處理完直接跳下一個
                
            # --- 篩選候選人 ---
            candidates = []
            pe_candidates = []
            
            for name, info in self.teachers.items():
                # 條件 A：職級限制
                if info['role'] not in details['roles']:
                    continue
                
                # 條件 B：特定人員排除 (例如放學不編淑)
                if 'exclude' in details and name in details['exclude']:
                    continue
                    
                # 條件 C：早會需避開備課會議
                if duty_type == '早會' and self._is_in_meeting(name, day, week_type):
                    continue
                    
                # 條件 D：淑和謝盡量不編入小息及午膳 (軟條件：分數懲罰或直接排除)
                if duty_type in ['小息', '午膳'] and name in ['陳淑怡', '謝翠琳']:
                    continue # 訓導主任盡量避開
                    
                # 加入候選名單
                candidates.append(name)
                if info['is_pe']:
                    pe_candidates.append(name)
            
            # 依分數排序 (實現公平性)
            candidates.sort(key=lambda n: self.teachers[n]['score'])
            pe_candidates.sort(key=lambda n: self.teachers[n]['score'])
            
            # --- 處理體育老師綁定要求 (小息/午膳地下) ---
            needed = details['headcount']
            if details.get('need_pe') and pe_candidates:
                assigned.append(pe_candidates[0])
                candidates.remove(pe_candidates[0])
                needed -= 1
                
            # --- 指派剩餘名額 ---
            for c in candidates:
                if needed <= 0:
                    break
                assigned.append(c)
                needed -= 1
                
            # --- 更新分數與排表 ---
            self.schedule[duty_name] = assigned
            for teacher in assigned:
                if teacher in self.teachers:
                    self.teachers[teacher]['score'] += details['weight']
                
        return self.schedule, self.teachers

# ==========================================
# 網頁介面設計 (Streamlit)
# ==========================================
st.set_page_config(page_title="訓導處當值編排系統 (進階版)", page_icon="🏫", layout="wide")

st.回答問題時發生錯誤，請稍後再試。
