import streamlit as st
import pandas as pd
import re

# ==========================================
# 核心排表邏輯 (v5.16 方案B 橫向擴展版 - 完美樓層銜接)
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

    # 智能老師姓名匹配引擎
    def find_teacher_name(self, query_name):
        if not query_name or pd.isna(query_name): return None
        query_name = str(query_name).strip()
        if query_name in self.teachers: return query_name
        for full_name, info in self.teachers.items():
            if info['short_name'] and info['short_name'].lower() == query_name.lower(): return full_name
        for full_name, info in self.teachers.items():
            if query_name in full_name or full_name in query_name: return full_name
        return None

    # 智能星期格式統一引擎
    def normalize_day(self, d_str):
        if pd.isna(d_str): return ""
        d_str = str(d_str).strip().upper()
        if '一' in d_str or '1' in d_str or 'MON' in d_str: return '星期一'
        if '二' in d_str or '2' in d_str or 'TUE' in d_str: return '星期二'
        if '三' in d_str or '3' in d_str or 'WED' in d_str: return '星期三'
        if '四' in d_str or '4' in d_str or 'THU' in d_str: return '星期四'
        if '五' in d_str or '5' in d_str or 'FRI' in d_str: return '星期五'
        return d_str

    # 中文漢字節數解碼器 (支援: "1", "第1節", "第一節")
    def decode_chinese_lesson(self, lesson_str):
        lesson_str = str(lesson_str).strip()
        nums = re.findall(r'\d+', lesson_str)
        if nums: return int(nums[0])
        cn_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        for char, val in cn_map.items():
            if char in lesson_str: return val
        return None
        
    def _process_teachers(self, df):
        teachers_dict = {}
        if not df.empty:
            for _, r in df.iterrows():
                short_n = str(r.get('簡稱', '')).strip()
                if short_n.lower() in ['nan', 'none']: short_n = ''
                teachers_dict[str(r['姓名']).strip()] = {
                    'role': str(r.get('職級', '')).strip(),
                    'is_pe': str(r.get('是否體育老師', '否')).strip() == '是',
                    'special_role': str(r.get('特殊身份', '無')).strip(),
                    'class_name': str(r.get('所屬班別', '無')).strip(),
                    'short_name': short_n
                }
        return teachers_dict

    def _process_timetable(self, df):
        tt = {name: {day: [] for day in ['星期一', '星期二', '星期三', '星期四', '星期五']} for name in self.teachers}
        if not df.empty and '老師姓名' in df.columns:
            for _, r in df.iterrows():
                matched_name = self.find_teacher_name(r.get('老師姓名', ''))
                day = self.normalize_day(r.get('星期', ''))
                slot_raw = r.get('節數')
                slot_val = self.decode_chinese_lesson(slot_raw)
                if matched_name and day in tt[matched_name] and slot_val is not None:
                    tt[matched_name][day].append(slot_val)
        return tt
        
    def _process_locations(self, df):
        loc_dict = {}
        if not df.empty and '老師姓名' in df.columns and '星期' in df.columns and '節數' in df.columns and '樓層' in df.columns:
            for _, r in df.iterrows():
                matched_name = self.find_teacher_name(r.get('老師姓名', ''))
                day = self.normalize_day(r.get('星期', ''))
                lesson_raw = r.get('節數', '')
                floor_raw = str(r.get('樓層', ''))
                lesson_val = self.decode_chinese_lesson(lesson_raw)
                if not matched_name or not day or lesson_val is None: continue
                
                floor_str = floor_raw.strip().upper()
                if 'G' in floor_str or '地下' in floor_str: floor_val = 0
                else:
                    floor_nums = re.findall(r'\d+', floor_str)
                    floor_val = int(floor_nums[0]) if floor_nums else None
                
                if floor_val is not None:
                    loc_dict[(matched_name, day, lesson_val)] = floor_val
        return loc_dict

    def _process_coplanning(self, df):
        cp = {'單週': {d: [] for d in ['星期一', '星期二', '星期三', '星期四', '星期五']}, '雙週': {d: [] for d in ['星期一', '星期二', '星期三', '星期四', '星期五']}}
        if not df.empty and '老師姓名' in df.columns:
            for _, r in df.iterrows():
                matched_name = self.find_teacher_name(r.get('老師姓名',''))
                day = self.normalize_day(r.get('星期',''))
                week = str(r.get('週次','')).strip()
                if matched_name and day in cp['單週']:
                    if week == '單週': cp['單週'][day].append(matched_name)
                    if week == '雙週': cp['雙週'][day].append(matched_name)
        return cp

    def _process_subjects(self, df):
        subjects = {}
        if not df.empty and '班別' in df.columns:
            for c_name in df['班別'].unique():
                teachers_list = df[df['班別'] == c_name]['老師姓名'].dropna()
                matched_teachers = [self.find_teacher_name(t) for t in teachers_list if self.find_teacher_name(t)]
                subjects[c_name] = list(set(matched_teachers))
        return subjects

    def _process_fixed_duties(self, df):
        fd_map, f_teachers = {}, set()
        if not df.empty and '崗位名稱' in df.columns and '負責老師' in df.columns:
            for _, r in df.iterrows():
                duty_name = str(r.get('崗位名稱', '')).strip()
                matched_name = self.find_teacher_name(r.get('負責老師', ''))
                if duty_name and matched_name:
                    fd_map[duty_name] = matched_name
                    f_teachers.add(matched_name)
        return fd_map, f_teachers

    def _define_duties(self):
        duties = {}
        days = ['星期一', '星期二', '星期三', '星期四', '星期五']
        
        all_slots = {
            "早會_雨天操場_7:30-7:55": {"count": 2, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_雨天操場_7:55-8:20": {"count": 2, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_詢問處_7:30-7:55": {"count": 2, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_詢問處_7:55-8:20": {"count": 3, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_正門大閘_7:30-7:55": {"count": 2, "weight": 25, "roles": ['副校', '主任']},
            "早會_正門大閘_7:55-8:20": {"count": 3, "weight": 25, "roles": ['副校', '主任']},
            "早會_雨天操場持咪_7:55-8:20": {"count": 1, "weight": 25, "roles": ['副校', '主任', '非班主任']},
            "早會_宣佈_8:15-8:35": {"count": 1, "weight": 20, "roles": ['副校', '主任', '非班主任']},
            
            "小息一_6樓_9:45-10:00": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息一_5樓_9:45-10:00": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息一_4樓_9:45-10:00": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息一_3樓_9:45-10:00": {"count": 1, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息一_2樓_9:45-10:00": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息一_1樓前後梯_9:45-10:00": {"count": 1, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息一_地下_9:45-10:00": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            
            "小息二_6樓_11:10-11:25": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息二_5樓_11:10-11:25": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息二_4樓_11:10-11:25": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息二_3樓_11:10-11:25": {"count": 1, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息二_2樓_11:10-11:25": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息二_1樓前後梯_11:10-11:25": {"count": 1, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            "小息二_地下_11:10-11:25": {"count": 2, "weight": 15, "roles": ['副校', '主任', '班主任', '非班主任']},
            
            "午膳二_6樓_13:05-13:35": {"count": 2, "weight": 30, "roles": ['副校', '主任', '非班主任']},
            "午膳二_5樓_13:05-13:35": {"count": 2, "weight": 30, "roles": ['副校', '主任', '非班主任']},
            "午膳二_4樓_13:05-13:35": {"count": 2, "weight": 30, "roles": ['副校', '主任', '非班主任']},
            "午膳二_3樓_13:05-13:35": {"count": 2, "weight": 30, "roles": ['副校', '主任', '非班主任']},
            "午膳二_2樓_13:05-13:35": {"count": 2, "weight": 30, "roles": ['副校', '主任', '非班主任']},
            "午膳二_地下_13:05-13:35": {"count": 3, "weight": 30, "roles": ['副校', '主任', '非班主任']},
            
            "放學_雨天操場持咪_15:25-15:45": {"count": 1, "weight": 20, "roles": ['副校', '主任']},
            "放學_家長隊(雨天操場)1_15:25-15:45": {"count": 1, "weight": 20, "roles": ['副校', '主任']},
            "放學_家長隊(雨天操場)2_15:25-15:45": {"count": 1, "weight": 20, "roles": ['副校', '主任']},
            "放學_大閘(外)_15:25-15:45": {"count": 1, "weight": 20, "roles": ['副校', '主任']},
            "放學_新翼持咪_15:25-15:45": {"count": 1, "weight": 20, "roles": ['副校', '主任']},
            "放學_正門大閘_15:25-15:45": {"count": 1, "weight": 20, "roles": ['副校', '主任']},
        }
        for day in days:
            for duty, details in all_slots.items():
                if "早會" in duty:
                    duties[f'{day}_{duty}_單週'] = {'headcount': details['count'], 'weight': details['weight'], 'roles': details['roles']}
                    duties[f'{day}_{duty}_雙週'] = {'headcount': details['count'], 'weight': details['weight'], 'roles': details['roles']}
                else:
                    duties[f'{day}_{duty}'] = {'headcount': details['count'], 'weight': details['weight'], 'roles': details['roles'], 'is_lunch': '午膳' in duty}
        
        for day in days:
            if '雨天操場持咪' in self.fixed_duties_map:
                teacher = self.fixed_duties_map['雨天操場持咪']
                duties[f'{day}_早會_雨天操場持咪_7:55-8:20_單週']['fixed_teacher'] = [teacher]
                duties[f'{day}_早會_雨天操場持咪_7:55-8:20_雙週']['fixed_teacher'] = [teacher]
                duties[f'{day}_早會_正門大閘_7:30-7:55_單週']['fixed_teacher'] = [teacher]
                duties[f'{day}_早會_正門大閘_7:30-7:55_雙週']['fixed_teacher'] = [teacher]
            if '宣佈' in self.fixed_duties_map:
                teacher = self.fixed_duties_map['宣佈']
                duties[f'{day}_早會_宣佈_8:15-8:35_單週']['fixed_teacher'] = [teacher]
                duties[f'{day}_早會_宣佈_8:15-8:35_雙週']['fixed_teacher'] = [teacher]

        all_classes = [cls for cls in self.subjects.keys() if str(cls) and str(cls)[0] in '123456']
        for day in days:
            for cls in all_classes:
                duties[f'{day}_入班當值_{cls}_07:55-08:15_單週'] = {'weight': 20, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}
                duties[f'{day}_入班當值_{cls}_07:55-08:15_雙週'] = {'weight': 20, 'roles': ['班主任', '非班主任'], 'headcount': 1, 'class_specific': cls}
        
        team_lead_routes = ["A", "B", "C", "D", "E", "F"]
        for day in days:
            for route in team_lead_routes:
                duties[f'{day}_放學隊_{route}_15:25-15:45'] = {'weight': 20, 'roles': ['班主任', '非班主任'], 'headcount': 1}
        return duties

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
        if "早會" in duty_name or "入班當值" in duty_name:
            if day in self.coplanning.get(week_type, {}) and teacher_name in self.coplanning[week_type].get(day, []): return True
        if "7:30-7:55" in duty_name and "楊" in teacher_name: return True
        if "7:55-8:20" in duty_name:
            announcer = self.fixed_duties_map.get("宣佈", "")
            if announcer and announcer == teacher_name: return True
        if "午膳" in duty_name:
            if day == "星期一" and "浩" in teacher_name: return True
            if day == "星期二" and "馬" in teacher_name: return True
            if day == "星期四" and "蔡" in teacher_name: return True
        if "放學隊" in duty_name and info.get('class_name','').startswith('1'): return True
        if info.get('special_role') == '輔導主任' and ('小息' in duty_name or '午膳' in duty_name): return True
        if info.get('special_role') == '圖書館老師' and '放學隊' not in duty_name: return True
        return False

    def run_scheduler(self, week_type, fixed_overrides=None):
        duties = {k: v for k, v in self.duties.items() if week_type in k or ('單週' not in k and '雙週' not in k)}
        schedule = {duty: [] for duty in duties}
        reg_scores = {name: 0 for name in self.teachers}
        lunch_scores = {name: 0 for name in self.teachers}
        ref_scores = {name: 0 for name in self.teachers}
        teacher_busy_slots = {name: {d: set() for d in ['星期一', '星期二', '星期三', '星期四', '星期五']} for name in self.teachers}
        
        def is_free(t_name, d, s):
            if s == "UNKNOWN": return True
            busy = teacher_busy_slots.get(t_name, {}).get(d, set())
            if s in busy: return False
            if s == "M2" and "M3" in busy: return False
            if s == "M3" and "M2" in busy: return False
            if s == "M1" and "M2" in busy: return False
            if s == "M2" and "M1" in busy: return False
            return True
            
        def mark_busy(t_name, d, s):
            if s == "UNKNOWN" or t_name not in teacher_busy_slots: return
            teacher_busy_slots[t_name][d].add(s)

        def get_priority(item):
            name, details = item
            if "早會" in name: return 1
            if "入班當值" in name: return 2
            if details.get('is_lunch'): return 4
            return 3
            
        def has_six_consecutive(teacher, day):
            tt_day = self.timetable.get(teacher, {}).get(day, [])
            if not tt_day: return False
            sorted_slots = sorted(list(set(tt_day))) 
            if len(sorted_slots) < 6: return False
            max_c, cur_c = 1, 1
            for i in range(1, len(sorted_slots)):
                if sorted_slots[i] == sorted_slots[i-1] + 1:
                    cur_c += 1
                    max_c = max(max_c, cur_c)
                else: cur_c = 1
            return max_c >= 6

        def get_consecutive_before_recess(teacher, day, duty_name):
            tt_day = self.timetable.get(teacher, {}).get(day, [])
            if not tt_day: return "FREE_BEFORE"
            if "小息一" in duty_name:
                p1, p2 = 1 in tt_day, 2 in tt_day
                if not p2: return "FREE_BEFORE"
                if p1 and p2: return "TWO_CONSECUTIVE_BEFORE"
            elif "小息二" in duty_name:
                p3, p4 = 3 in tt_day, 4 in tt_day
                if not p4: return "FREE_BEFORE"
                if p3 and p4: return "TWO_CONSECUTIVE_BEFORE"
            return "NORMAL"

        # ★★★ 全新四層優先權評分系統 ★★★
        def get_combined_score(teacher, day, lesson, duty_floor, current_workload, duty_name):
            penalty = 0
            
            # 第一優先：絕對疲勞保護 (連堂懲罰)
            if has_six_consecutive(teacher, day): penalty += 100000 
            if "小息" in duty_name:
                status = get_consecutive_before_recess(teacher, day, duty_name)
                # 第二優先：輕度疲勞保護 (空堂獎勵 vs 連堂懲罰)
                if status == "FREE_BEFORE": penalty -= 5000  
                elif status == "TWO_CONSECUTIVE_BEFORE": penalty += 50000 
            
            # 第三優先：工作量平衡 (分鐘數 * 權重，確保大於樓層分數)
            workload_score = current_workload * 10
            
            # 第四優先：小息後同樓層上課獎勵
            distance_score = 0
            if duty_floor is not None and lesson is not None:
                teacher_floor = self.locations.get((teacher, day, lesson))
                if teacher_floor is not None:
                    floor_diff = abs(teacher_floor - duty_floor)
                    if floor_diff == 0:
                        distance_score = -50  # 完美同層：最後關頭決選獎勵
                    else:
                        distance_score = floor_diff * 5  # 不同層：每差一層微調加分(降低優先)
                else:
                    distance_score = 10 # 小息後沒課的情況，給予中立分數
            
            return penalty + workload_score + distance_score

        sorted_duties = sorted(duties.items(), key=get_priority)

        for duty, details in sorted_duties:
            day, slot = duty.split('_')[0], self._get_duty_slot(duty)
            assigned = []
            
            if fixed_overrides and duty in fixed_overrides:
                assigned = fixed_overrides[duty].copy()
                for t in assigned: mark_busy(t, day, slot)
            elif "小息" in duty:
                lesson_to_check = 3 if "小息一" in duty else 5
                duty_floor_str = ""
                for part in duty.split('_'):
                    if '樓' in part or '地下' in part:
                        duty_floor_str = part
                        break
                if '地下' in duty_floor_str: duty_floor = 0
                else: 
                    nums = re.findall(r'\d+', duty_floor_str)
                    duty_floor = int(nums[0]) if nums else None
                
                candidates = [name for name, info in self.teachers.items() if info['role'] in details['roles'] and not self.is_teacher_unavailable(name, day, duty, week_type) and is_free(name, day, slot)]
                if '地下' in duty_floor_str:
                    pe_c = [c for c in candidates if self.teachers[c].get('is_pe')]
                    non_pe_c = [c for c in candidates if not self.teachers[c].get('is_pe')]
                    pe_c.sort(key=lambda t: get_combined_score(t, day, lesson_to_check, duty_floor, ref_scores.get(t, 0), duty))
                    non_pe_c.sort(key=lambda t: get_combined_score(t, day, lesson_to_check, duty_floor, ref_scores.get(t, 0), duty))
                    if pe_c: assigned.append(pe_c.pop(0))
                    rem = pe_c + non_pe_c
                    rem.sort(key=lambda t: get_combined_score(t, day, lesson_to_check, duty_floor, ref_scores.get(t, 0), duty))
                    spots = details['headcount'] - len(assigned)
                    assigned.extend(rem[:spots])
                else:
                    candidates.sort(key=lambda t: get_combined_score(t, day, lesson_to_check, duty_floor, ref_scores.get(t, 0), duty))
                    assigned = candidates[:details['headcount']]
            elif details.get('class_specific'):
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
                    for t in details['fixed_teacher']: mark_busy(t, day, slot)
                
                remaining_spots = details['headcount'] - len(assigned)
                if remaining_spots > 0:
                    candidates = [name for name, info in self.teachers.items() if info['role'] in details['roles'] and name not in assigned and not self.is_teacher_unavailable(name, day, duty, week_type) and is_free(name, day, slot)]
                    if '地下' in duty and remaining_spots > 0:
                        pe_c = [c for c in candidates if self.teachers[c].get('is_pe')]
                        non_pe_c = [c for c in candidates if not self.teachers[c].get('is_pe')]
                        pe_c.sort(key=lambda t: get_combined_score(t, day, None, None, ref_scores.get(t, 0), duty))
                        non_pe_c.sort(key=lambda t: get_combined_score(t, day, None, None, ref_scores.get(t, 0), duty))
                        if pe_c:
                            assigned.append(pe_c.pop(0))
                            remaining_spots -= 1
                        rem = pe_c + non_pe_c
                        rem.sort(key=lambda t: get_combined_score(t, day, None, None, ref_scores.get(t, 0), duty))
                        if remaining_spots > 0: assigned.extend(rem[:remaining_spots])
                    else:
                        candidates.sort(key=lambda n: get_combined_score(n, day, None, None, ref_scores.get(n, 0), duty))
                        assigned.extend(candidates[:remaining_spots])
            
            schedule[duty] = assigned
            for teacher in assigned:
                mark_busy(teacher, day, slot)
                if teacher in ref_scores:
                    ref_scores[teacher] += details['weight']
                    if details.get('is_lunch', False): lunch_scores[teacher] += details['weight']
                    else: reg_scores[teacher] += details['weight']
                
        return schedule, reg_scores, lunch_scores, ref_scores

# ==========================================
# 網頁介面設計 (Streamlit)
# ==========================================
st.set_page_config(page_title="訓導處當值編排系統", page_icon="🏫", layout="wide")
st.title("🏫 訓導處當值表自動編排系統 (v5.16 方案B 橫向擴展版)")
st.markdown("搭載**四大疲勞保護機制**、**體育老師保留位**與**小息完美樓層銜接**，完全採用**方案B (橫向擴展星期)** 設計。")
st.divider()

cols1 = st.columns(3); cols2 = st.columns(3)
files_map = {"1️⃣ 老師名單": "teachers_list.csv", "2️⃣ 課堂時間表": "timetable.csv", "3️⃣ 課室樓層表": "class_locations.csv", "4️⃣ 共備名單": "co_planning.csv", "5️⃣ 主科任教名單": "subject_teachers.csv", "6️⃣ 專責崗位名單": "fixed_duties.csv"}
uploaded_files = {}

for i, (header, fname) in enumerate(files_map.items()):
    col = cols1[i] if i < 3 else cols2[i-3]
    with col:
        uploaded_files[fname] = st.file_uploader(header, type=['csv'])

st.divider()

# ==========================================
# 顯示用輔助函數 (支援簡稱與擴展表格生成)
# ==========================================
def format_name_full(name, teachers_dict):
    info = teachers_dict.get(name, {})
    s_name = info.get('short_name', '')
    return f"{name}({s_name})" if s_name else name

def format_short_name(name, teachers_dict):
    info = teachers_dict.get(name, {})
    s_name = info.get('short_name', '')
    return str(s_name).strip() if pd.notna(s_name) and str(s_name).strip() else str(name)

def get_display_sort_key(item_dict):
    duty_name = item_dict.get("崗位", "")
    days = {'星期一': 1, '星期二': 2, '星期三': 3, '星期四': 4, '星期五': 5}
    day_str = duty_name.split('_')[0] if '_' in duty_name else ""
    time_order = 99
    if "早會" in duty_name: time_order = 1
    elif "入班" in duty_name: time_order = 2
    elif "小息一" in duty_name: time_order = 3
    elif "小息二" in duty_name: time_order = 4
    elif "午膳" in duty_name: time_order = 5
    elif "放學" in duty_name: time_order = 6
    return (days.get(day_str, 99), time_order, duty_name)

# ★★★ 產生二維擴展表格 (方案 B: 橫向擴展星期欄位) ★★★
def build_matrix_table_option_b(schedule, duties_def, base_names, week_suffix, teachers_dict):
    days = ['星期一', '星期二', '星期三', '星期四', '星期五']
    max_hc = 1
    for base in base_names:
        for d in days:
            k1 = f"{d}_{base}{week_suffix}"
            k2 = f"{d}_{base}"
            if k1 in duties_def: max_hc = max(max_hc, duties_def[k1]['headcount'])
            elif k2 in duties_def: max_hc = max(max_hc, duties_def[k2]['headcount'])
            
    rows = []
    for base in base_names:
        row_data = {"崗位": base}
        for d in days:
            k1 = f"{d}_{base}{week_suffix}"
            k2 = f"{d}_{base}"
            target_k = k1 if k1 in schedule else (k2 if k2 in schedule else None)
            
            if target_k:
                assigned = [format_short_name(t, teachers_dict) for t in schedule[target_k]]
                req = duties_def[target_k]['headcount']
                cells = assigned + ["欠1人"] * (req - len(assigned))
                cells += ["-"] * (max_hc - req)
            else:
                cells = ["-"] * max_hc
            
            if max_hc == 1:
                row_data[d] = cells[0]
            else:
                for i in range(max_hc):
                    col_name = f"{d} ({i+1})"
                    row_data[col_name] = cells[i]
                    
        rows.append(row_data)
    return pd.DataFrame(rows)

# 產生放學隊表格 (方案 B 特化：X軸為ABCDEF，Y軸為星期)
def build_dismissal_team_matrix(schedule, teachers_dict):
    days = ['星期一', '星期二', '星期三', '星期四', '星期五']
    routes = ["A", "B", "C", "D", "E", "F"]
    rows = []
    for d in days:
        row_data = {"星期": d}
        for r in routes:
            key = f"{d}_放學隊_{r}_15:25-15:45"
            if key in schedule:
                assigned = [format_short_name(t, teachers_dict) for t in schedule[key]]
                row_data[r] = assigned[0] if assigned else "欠1人"
            else:
                row_data[r] = "-"
        rows.append(row_data)
    return pd.DataFrame(rows).set_index("星期")

# 產生入班當值表格 (X軸為星期，Y軸為班別)
def build_in_class_duty_matrix(schedule, week_suffix, teachers_dict, subjects_dict):
    days = ['星期一', '星期二', '星期三', '星期四', '星期五']
    all_classes = sorted([cls for cls in subjects_dict.keys() if str(cls) and str(cls)[0] in '123456'])
    rows = []
    for cls in all_classes:
        row_data = {"班別": cls}
        for d in days:
            key = f"{d}_入班當值_{cls}_07:55-08:15{week_suffix}"
            if key in schedule:
                assigned = [format_short_name(t, teachers_dict) for t in schedule[key]]
                row_data[d] = assigned[0] if assigned else "欠1人"
            else:
                row_data[d] = "-"
        rows.append(row_data)
    return pd.DataFrame(rows).set_index("班別")

if st.button("🚀 開始自動編排當值表", use_container_width=True, type="primary"):
    if all(uploaded_files.values()):
        with st.spinner('系統正套用優先權重(疲勞保護 > 工作量 > 樓層銜接)進行智能分配...'):
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
                fixed_others = {k: v for k, v in odd_schedule.items() if "小息" in k or "午膳" in k or "放學" in k}
                even_schedule, even_reg, even_lunch, even_ref = scheduler.run_scheduler('雙週', fixed_overrides=fixed_others)
                
                st.success("🎉 演算法執行完畢！系統已產生【方案 B：橫向擴展版】二維表格。")
                morning_bases = [
                    "早會_雨天操場_7:30-7:55", "早會_雨天操場_7:55-8:20", "早會_雨天操場持咪_7:55-8:20",
                    "早會_詢問處_7:30-7:55", "早會_詢問處_7:55-8:20", "早會_正門大閘_7:30-7:55",
                    "早會_正門大閘_7:55-8:20", "早會_宣佈_8:15-8:35"
                ]
                dismissal_bases = [
                    "放學_雨天操場持咪_15:25-15:45", "放學_家長隊(雨天操場)1_15:25-15:45", "放學_家長隊(雨天操場)2_15:25-15:45",
                    "放學_大閘(外)_15:25-15:45", "放學_新翼持咪_15:25-15:45", "放學_正門大閘_15:25-15:45"
                ]
                recess_lunch_bases = [
                    "小息一_6樓_9:45-10:00", "小息一_5樓_9:45-10:00", "小息一_4樓_9:45-10:00", "小息一_3樓_9:45-10:00", "小息一_2樓_9:45-10:00", "小息一_1樓前後梯_9:45-10:00", "小息一_地下_9:45-10:00",
                    "小息二_6樓_11:10-11:25", "小息二_5樓_11:10-11:25", "小息二_4樓_11:10-11:25", "小息二_3樓_11:10-11:25", "小息二_2樓_11:10-11:25", "小息二_1樓前後梯_11:10-11:25", "小息二_地下_11:10-11:25",
                    "午膳二_6樓_13:05-13:35", "午膳二_5樓_13:05-13:35", "午膳二_4樓_13:05-13:35", "午膳二_3樓_13:05-13:35", "午膳二_2樓_13:05-13:35", "午膳二_地下_13:05-13:35"
                ]
                
                tabs = st.tabs([
                    "☀️ 單週早會(表)", "☀️ 雙週早會(表)", "🏫 單週入班(表)", "🏫 雙週入班(表)", 
                    "🚶 放學當值(表)", "🚩 放學隊(表)", "🏫 小息午膳(表)", 
                    "📅 原始列表(單)", "📅 原始列表(雙)", "📊 工作量統計", "👤 個人總覽"
                ])
                
                with tabs[0]: st.dataframe(build_matrix_table_option_b(odd_schedule, scheduler.duties, morning_bases, '_單週', scheduler.teachers).[...](asc_slot://start-slot-1)set_index("崗位"), use_container_width=True)
                with tabs: st.dataframe(build_matrix_table_option_b(even_schedule, scheduler.duties, morning_bases, '_雙週', scheduler.teachers).[...](asc_slot://start-slot-3)set_index("崗位"), use_container_width=True)
                with tabs: st.dataframe(build_in_class_duty_matrix(odd_schedule, '_單週', scheduler.teachers, scheduler.[...](asc_slot://start-slot-5)subjects), use_container_width=True)
                with tabs: st.dataframe(build_in_class_duty_matrix(even_schedule, '_雙週', scheduler.teachers, scheduler.subjects), use_container_width=True)
                with tabs[4]: st.dataframe(build_matrix_table_option_b(odd_schedule, scheduler.duties, dismissal_bases, '', scheduler.teachers).set_index("崗位"), use_container_width=True)
                with tabs[5]: st.dataframe(build_dismissal_team_matrix(odd_schedule, scheduler.teachers), use_container_width=True)
                with tabs[6]: st.dataframe(build_matrix_table_option_b(odd_schedule, scheduler.duties, recess_lunch_bases, '', scheduler.teachers).set_index("崗位"), use_container_width=True)
                
                odd_list = [{"崗位": k.replace('_單週',''), "負責老師": ", ".join([format_name_full(t, scheduler.teachers) for t in v])} for k, v in odd_schedule.items()]
                even_list = [{"崗位": k.replace('_雙週',''), "負責老師": ", ".join([format_name_full(t, scheduler.teachers) for t in v])} for k, v in even_schedule.items()]
                odd_list.sort(key=get_display_sort_key)
                even_list.sort(key=get_display_sort_key)
                with tabs[7]: st.dataframe(pd.DataFrame(odd_list), use_container_width=True, hide_index=True)
                with tabs[8]: st.dataframe(pd.DataFrame(even_list), use_container_width=True, hide_index=True)
                    
                with tabs[9]:
                    scores_list = [{
                        "老師姓名": format_name_full(name, scheduler.teachers), "職級": info['role'],
                        "常規(單週分鐘)": odd_reg.get(name, 0), "常規(雙週分鐘)": even_reg.get(name, 0),
                        "午膳(單週分鐘)": odd_lunch.get(name, 0), "午膳(雙週分鐘)": even_lunch.get(name, 0),
                        "總分鐘數(平均)": (odd_ref.get(name, 0) + even_ref.get(name, 0)) / 2
                    } for name, info in scheduler.teachers.items()]
                    st.dataframe(pd.DataFrame(scores_list).sort_values(by="總分鐘數(平均)", ascending=False), use_container_width=True, hide_index=True)
                    
                with tabs[10]:
                    teacher_duties = {name: {'單週': [], '雙週': []} for name in scheduler.teachers}
                    for duty, assigned in odd_schedule.items():
                        for t in assigned: teacher_duties[t]['單週'].append(duty.replace('_單週', ''))
                    for duty, assigned in even_schedule.items():
                        for t in assigned: teacher_duties[t]['雙週'].append(duty.replace('_雙週', ''))
                    
                    teacher_view_list = [{
                        "老師姓名": format_name_full(name, scheduler.teachers), "職級": info['role'],
                        "單週當值崗位": ", ".join(sorted(teacher_duties[name]['單週'])) if teacher_duties[name]['單週'] else "無",
                        "雙週當值崗位": ", ".join(sorted(teacher_duties[name]['雙週'])) if teacher_duties[name]['雙週'] else "無"
                    } for name, info in scheduler.teachers.items()]
                    st.dataframe(pd.DataFrame(teacher_view_list), use_container_width=True, hide_index=True)
                    
            except Exception as e:
                st.error(f"讀取檔案或運算時發生錯誤：{e}")
                st.info("請確認您的 6 份 CSV 檔案格式與欄位名稱是否正確，特別是『老師姓名』、『簡稱』等欄位。")
    else:
        st.warning("⚠️ 請先在上方上傳所有 6 個必要的 CSV 檔案！")
