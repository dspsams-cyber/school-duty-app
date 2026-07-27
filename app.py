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
       
