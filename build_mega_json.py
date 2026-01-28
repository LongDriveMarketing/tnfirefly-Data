import pandas as pd
import json

def safe_float(val):
    try:
        if isinstance(val, str):
            if '*' in val or '<' in val or '-' == val.strip():
                return None
        return round(float(val), 1)
    except:
        return None

def safe_int(val):
    try:
        return int(val)
    except:
        return None

def safe_pct(val):
    """Convert decimal to percentage if needed"""
    f = safe_float(val)
    if f is not None and f <= 1:
        return round(f * 100, 1)
    return f

print("=" * 60)
print("BUILDING MEGA 'WHAT HAPPENS AFTER GRADUATION' DATASET")
print("=" * 60)

# Master school dictionary - keyed by system-school
schools = {}

# County mapping (we'll build this from the data)
county_map = {}

# ========== 1. GRADUATION DATA (3 years) ==========
print("\n[1/4] Loading Graduation Rates...")
grad_files = [
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Graduation Cohort Data\2022-23_school_grad_rate_suppressed.xlsx', '2023'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Graduation Cohort Data\2023-24_school_grad_rate_suppressed.xlsx', '2024'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Graduation Cohort Data\2024-25_school_grad_rate_suppressed.xlsx', '2025'),
]

for filepath, year in grad_files:
    df = pd.read_excel(filepath)
    df = df[df['student_group'] == 'All Students']
    for _, row in df.iterrows():
        key = f"{int(row['system'])}-{int(row['school'])}"
        if key not in schools:
            schools[key] = {
                'system_code': int(row['system']),
                'district': row['system_name'],
                'school_code': int(row['school']),
                'school': row['school_name'],
                'county': None,
                'graduation': {},
                'ready_grad': {},
                'college_going': {},
                'act': {}
            }
        # Handle different column names across years
        cohort_col = 'grad_cohort_state' if 'grad_cohort_state' in row.index else 'grad_cohort'
        schools[key]['graduation'][year] = {
            'rate': safe_float(row['grad_rate_state']),
            'cohort': safe_int(row[cohort_col])
        }

print(f"   Loaded {len(schools)} schools with graduation data")

# ========== 2. READY GRADUATE DATA (3 years) ==========
print("\n[2/4] Loading Ready Graduate Rates...")
rg_files = [
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Ready Graduate\ready_graduate_school_suppressed_22-23.xlsx', '2023'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Ready Graduate\ready_graduate_school_suppressed_2024.xlsx', '2024'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Ready Graduate\ready_graduate_school_suppressed_2025.xlsx', '2025'),
]

rg_count = 0
for filepath, year in rg_files:
    df = pd.read_excel(filepath)
    df = df[df['student_group'] == 'All Students']
    for _, row in df.iterrows():
        key = f"{int(row['system'])}-{int(row['school'])}"
        if key not in schools:
            schools[key] = {
                'system_code': int(row['system']),
                'district': row['system_name'],
                'school_code': int(row['school']),
                'school': row['school_name'],
                'county': None,
                'graduation': {},
                'ready_grad': {},
                'college_going': {},
                'act': {}
            }
        schools[key]['ready_grad'][year] = {
            'rate': safe_float(row['pct_ready_grad']),
            'count': safe_int(row['n_count'])
        }
        rg_count += 1

print(f"   Added Ready Graduate data ({rg_count} records)")

# ========== 3. ACT DATA (3 years) ==========
print("\n[3/4] Loading ACT Scores...")
act_files = [
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\ACT Data\ACT Data School Level\2022-23_ACT_school_suppressed.xlsx', '2023'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\ACT Data\ACT Data School Level\2023-24_ACT_school_suppressed.xlsx', '2024'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\ACT Data\ACT Data School Level\2024-25_ACT_school_suppressed.xlsx', '2025'),
]

act_count = 0
for filepath, year in act_files:
    df = pd.read_excel(filepath)
    df = df[df['Subgroup'] == 'All Students']
    for _, row in df.iterrows():
        key = f"{int(row['District'])}-{int(row['School'])}"
        if key not in schools:
            schools[key] = {
                'system_code': int(row['District']),
                'district': row['District Name'],
                'school_code': int(row['School']),
                'school': row['School Name'],
                'county': None,
                'graduation': {},
                'ready_grad': {},
                'college_going': {},
                'act': {}
            }
        schools[key]['act'][year] = {
            'composite': safe_float(row['Average Composite Score']),
            'english': safe_float(row['Average English Score']),
            'math': safe_float(row['Average Math Score']),
            'reading': safe_float(row['Average Reading Score']),
            'science': safe_float(row['Average Science Score']),
            'pct_21_plus': safe_float(row['Percent Scoring 21 or Higher']),
            'tested': safe_int(row['Valid Tests'])
        }
        act_count += 1

print(f"   Added ACT data ({act_count} records)")

# ========== 4. COLLEGE-GOING RATE DATA (5 years) ==========
print("\n[4/4] Loading College-Going Rates...")
cgr_df = pd.read_excel(
    r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\College Data\CGR by HS_Suppressed (1).xlsx',
    sheet_name='5-Year CGR'
)

# Build county map from CGR data
for _, row in cgr_df.iterrows():
    district = str(row['HS_District']).strip().upper()
    county = str(row['HS_County']).strip().upper()
    if district and county and district != 'NAN':
        county_map[district] = county

cgr_matched = 0
cgr_unmatched = []

for _, row in cgr_df.iterrows():
    school_name = str(row['High_School']).strip().upper()
    district_name = str(row['HS_District']).strip().upper()
    
    if school_name == 'NAN' or district_name == 'NAN':
        continue
    
    # Find matching school by name + district
    matched = False
    for key, school in schools.items():
        school_name_clean = str(school['school']).strip().upper() if school['school'] else ''
        district_name_clean = str(school['district']).strip().upper() if school['district'] else ''
        if (school_name_clean == school_name and district_name_clean == district_name):
            # Add CGR data
            for yr in ['2019', '2020', '2021', '2022', '2023']:
                col = f'Class of {yr} CGR'
                if col in row:
                    rate = safe_pct(row[col])
                    if rate is not None:
                        school['college_going'][yr] = {'rate': rate}
            
            # Add county
            school['county'] = row['HS_County'].strip().title()
            matched = True
            cgr_matched += 1
            break
    
    if not matched and school_name != 'NAN':
        cgr_unmatched.append(f"{school_name} ({district_name})")

print(f"   Matched {cgr_matched} schools with CGR data")
print(f"   Unmatched: {len(cgr_unmatched)}")

# ========== ASSIGN COUNTIES TO REMAINING SCHOOLS ==========
print("\n[*] Assigning counties to remaining schools...")
for key, school in schools.items():
    if not school['county']:
        district_str = str(school['district']) if school['district'] else ''
        district_upper = district_str.strip().upper()
        if district_upper in county_map:
            school['county'] = county_map[district_upper].title()
        else:
            # Try to extract county from district name
            if 'COUNTY' in district_upper:
                parts = district_upper.split('COUNTY')[0].strip()
                school['county'] = parts.title()

# ========== CALCULATE STATE AVERAGES ==========
print("\n[*] Calculating state averages...")

state_stats = {
    'graduation': {'2023': [], '2024': [], '2025': []},
    'ready_grad': {'2023': [], '2024': [], '2025': []},
    'college_going': {'2019': [], '2020': [], '2021': [], '2022': [], '2023': []},
    'act': {'2023': [], '2024': [], '2025': []}
}

for school in schools.values():
    for year, data in school['graduation'].items():
        if data['rate'] is not None:
            state_stats['graduation'][year].append(data['rate'])
    for year, data in school['ready_grad'].items():
        if data['rate'] is not None:
            state_stats['ready_grad'][year].append(data['rate'])
    for year, data in school['college_going'].items():
        if data['rate'] is not None:
            state_stats['college_going'][year].append(data['rate'])
    for year, data in school['act'].items():
        if data['composite'] is not None:
            state_stats['act'][year].append(data['composite'])

state_averages = {}
for metric, years in state_stats.items():
    state_averages[metric] = {}
    for year, values in years.items():
        if values:
            state_averages[metric][year] = round(sum(values) / len(values), 1)

print(f"   State averages calculated")

# ========== FILTER TO SCHOOLS WITH MEANINGFUL DATA ==========
print("\n[*] Filtering schools...")

final_schools = []
for key, school in schools.items():
    # Must have at least graduation OR ready grad data for 2025
    has_2025_grad = school['graduation'].get('2025', {}).get('rate') is not None
    has_2025_rg = school['ready_grad'].get('2025', {}).get('rate') is not None
    has_cgr = len(school['college_going']) > 0
    has_act = len(school['act']) > 0
    
    # Include if has recent graduation/ready grad data
    if has_2025_grad or has_2025_rg:
        # Get latest values for sorting
        latest_grad = school['graduation'].get('2025', {}).get('rate') or \
                      school['graduation'].get('2024', {}).get('rate') or \
                      school['graduation'].get('2023', {}).get('rate')
        latest_rg = school['ready_grad'].get('2025', {}).get('rate') or \
                    school['ready_grad'].get('2024', {}).get('rate') or \
                    school['ready_grad'].get('2023', {}).get('rate')
        latest_cgr = school['college_going'].get('2023', {}).get('rate') or \
                     school['college_going'].get('2022', {}).get('rate')
        latest_act = school['act'].get('2025', {}).get('composite') or \
                     school['act'].get('2024', {}).get('composite') or \
                     school['act'].get('2023', {}).get('composite')
        
        final_schools.append({
            'school': school['school'],
            'district': school['district'],
            'county': school['county'] or 'Unknown',
            'system_code': school['system_code'],
            'school_code': school['school_code'],
            'latest': {
                'graduation_rate': latest_grad,
                'ready_grad_rate': latest_rg,
                'college_going_rate': latest_cgr,
                'act_composite': latest_act
            },
            'graduation': school['graduation'],
            'ready_grad': school['ready_grad'],
            'college_going': school['college_going'],
            'act': school['act']
        })

# Sort by school name
final_schools.sort(key=lambda x: x['school'])

print(f"   Final count: {len(final_schools)} schools")

# ========== BUILD OUTPUT JSON ==========
output = {
    'meta': {
        'title': 'What Happens After Graduation - Tennessee High School Outcomes',
        'description': 'Comprehensive data on graduation rates, college readiness, college enrollment, and ACT scores for Tennessee high schools',
        'source': 'Tennessee Department of Education',
        'updated': '2025-01',
        'metrics': {
            'graduation': 'Percentage of students who graduate within 4 years',
            'ready_grad': 'Percentage meeting Ready Graduate criteria (ACT 21+, industry cert, military, etc.)',
            'college_going': 'Percentage enrolled in postsecondary education within 1 year',
            'act': 'Average ACT composite score'
        }
    },
    'state': {
        'schools_count': len(final_schools),
        'counties_count': len(set(s['county'] for s in final_schools)),
        'averages': state_averages
    },
    'schools': final_schools
}

# Save
output_path = r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\tennessee-after-graduation-data.json'
with open(output_path, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n{'=' * 60}")
print(f"SUCCESS! Saved to: {output_path}")
print(f"{'=' * 60}")
print(f"\nSUMMARY:")
print(f"  Total Schools: {len(final_schools)}")
print(f"  Counties: {len(set(s['county'] for s in final_schools))}")
print(f"\nSTATE AVERAGES (2025 where available):")
print(f"  Graduation Rate: {state_averages['graduation'].get('2025', 'N/A')}%")
print(f"  Ready Graduate:  {state_averages['ready_grad'].get('2025', 'N/A')}%")
print(f"  College-Going:   {state_averages['college_going'].get('2023', 'N/A')}%")
print(f"  ACT Composite:   {state_averages['act'].get('2025', 'N/A')}")

# Sample school
sample = [s for s in final_schools if 'Nolensville' in s['school']]
if sample:
    print(f"\nSAMPLE - {sample[0]['school']}:")
    print(json.dumps(sample[0], indent=2))
