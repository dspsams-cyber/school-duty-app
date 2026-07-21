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
  
