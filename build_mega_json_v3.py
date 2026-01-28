import pandas as pd
import json
import re

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

def create_slug(name):
    """Create URL-friendly slug from school name"""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')

def calculate_trend(school_obj):
    """Calculate trend info based on Ready Grad 2-year change"""
    rg_data = school_obj.get('ready_grad', {})
    rg_2023 = rg_data.get('2023', {}).get('rate') if rg_data.get('2023') else None
    rg_2025 = rg_data.get('2025', {}).get('rate') if rg_data.get('2025') else None
    
    if rg_2023 is None or rg_2025 is None:
        return {'direction': 'none', 'change': None, 'arrow': ''}
    
    change = round(rg_2025 - rg_2023, 1)
    
    if change >= 5:
        return {'direction': 'up', 'change': change, 'arrow': 'up'}
    elif change <= -5:
        return {'direction': 'down', 'change': change, 'arrow': 'down'}
    else:
        return {'direction': 'stable', 'change': change, 'arrow': 'stable'}

def calculate_flight_score(school):
    """
    TNFirefly Flight Score (0-100)
    """
    latest = school.get('latest', {})
    
    ready_grad = latest.get('ready_grad_rate')
    college_going = latest.get('college_going_rate')
    act = latest.get('act_composite')
    graduation = latest.get('graduation_rate')
    
    valid_metrics = sum([
        ready_grad is not None,
        college_going is not None,
        act is not None,
        graduation is not None
    ])
    
    if valid_metrics < 2:
        return None
    
    score = 0
    total_weight = 0
    
    if ready_grad is not None:
        score += ready_grad * 0.40
        total_weight += 0.40
    
    if college_going is not None:
        score += college_going * 0.25
        total_weight += 0.25
    
    if act is not None:
        act_normalized = min(100, max(0, (act - 10) * (100 / 26)))
        score += act_normalized * 0.20
        total_weight += 0.20
    
    if graduation is not None:
        score += graduation * 0.15
        total_weight += 0.15
    
    if total_weight > 0:
        score = score / total_weight
    else:
        return None
    
    # Momentum Bonus
    rg_data = school.get('ready_grad', {})
    rg_2023 = rg_data.get('2023', {}).get('rate') if rg_data.get('2023') else None
    rg_2025 = rg_data.get('2025', {}).get('rate') if rg_data.get('2025') else None
    
    if rg_2023 is not None and rg_2025 is not None:
        change = rg_2025 - rg_2023
        if change >= 10:
            score += 5
        elif change >= 5:
            score += 3
        elif change <= -10:
            score -= 5
        elif change <= -5:
            score -= 3
    
    return round(max(0, min(100, score)), 1)

def get_flight_tier(score):
    if score is None:
        return {'tier': 'Insufficient Data', 'class': 'tier-na'}
    if score >= 85:
        return {'tier': 'Firefly Elite', 'class': 'tier-elite'}
    if score >= 70:
        return {'tier': 'Firefly Strong', 'class': 'tier-strong'}
    if score >= 55:
        return {'tier': 'Firefly Ready', 'class': 'tier-ready'}
    if score >= 40:
        return {'tier': 'Building Momentum', 'class': 'tier-building'}
    return {'tier': 'Room to Grow', 'class': 'tier-grow'}

print("=" * 60)
print("BUILDING MEGA DATASET v3 - WITH TRENDS & COUNTY RANKINGS")
print("=" * 60)

schools = {}
county_map = {}

# ========== 1. GRADUATION DATA ==========
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
        cohort_col = 'grad_cohort_state' if 'grad_cohort_state' in row.index else 'grad_cohort'
        schools[key]['graduation'][year] = {
            'rate': safe_float(row['grad_rate_state']),
            'cohort': safe_int(row[cohort_col])
        }

print(f"   Loaded {len(schools)} schools")

# ========== 2. READY GRADUATE DATA ==========
print("\n[2/4] Loading Ready Graduate Rates...")
rg_files = [
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Ready Graduate\ready_graduate_school_suppressed_22-23.xlsx', '2023'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Ready Graduate\ready_graduate_school_suppressed_2024.xlsx', '2024'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\Ready Graduate\ready_graduate_school_suppressed_2025.xlsx', '2025'),
]

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

print(f"   Added Ready Graduate data")

# ========== 3. ACT DATA ==========
print("\n[3/4] Loading ACT Scores...")
act_files = [
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\ACT Data\ACT Data School Level\2022-23_ACT_school_suppressed.xlsx', '2023'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\ACT Data\ACT Data School Level\2023-24_ACT_school_suppressed.xlsx', '2024'),
    (r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\ACT Data\ACT Data School Level\2024-25_ACT_school_suppressed.xlsx', '2025'),
]

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

print(f"   Added ACT data")

# ========== 4. COLLEGE-GOING RATE DATA ==========
print("\n[4/4] Loading College-Going Rates...")
cgr_df = pd.read_excel(
    r'C:\Users\gardn\OneDrive\Desktop\TDOE Data\College Data\CGR by HS_Suppressed (1).xlsx',
    sheet_name='5-Year CGR'
)

for _, row in cgr_df.iterrows():
    district = str(row['HS_District']).strip().upper()
    county = str(row['HS_County']).strip().upper()
    if district and county and district != 'NAN':
        county_map[district] = county

for _, row in cgr_df.iterrows():
    school_name = str(row['High_School']).strip().upper()
    district_name = str(row['HS_District']).strip().upper()
    
    if school_name == 'NAN' or district_name == 'NAN':
        continue
    
    for key, school in schools.items():
        school_name_clean = str(school['school']).strip().upper() if school['school'] else ''
        district_name_clean = str(school['district']).strip().upper() if school['district'] else ''
        if (school_name_clean == school_name and district_name_clean == district_name):
            for yr in ['2019', '2020', '2021', '2022', '2023']:
                col = f'Class of {yr} CGR'
                if col in row:
                    rate = safe_pct(row[col])
                    if rate is not None:
                        school['college_going'][yr] = {'rate': rate}
            school['county'] = row['HS_County'].strip().title()
            break

print(f"   Matched CGR data")

# ========== ASSIGN COUNTIES ==========
print("\n[*] Assigning counties...")
for key, school in schools.items():
    if not school['county']:
        district_str = str(school['district']) if school['district'] else ''
        district_upper = district_str.strip().upper()
        if district_upper in county_map:
            school['county'] = county_map[district_upper].title()
        elif 'COUNTY' in district_upper:
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

# ========== BUILD FINAL SCHOOLS LIST ==========
print("\n[*] Building final school list...")

final_schools = []
flight_scores = []

for key, school in schools.items():
    has_2025_grad = school['graduation'].get('2025', {}).get('rate') is not None
    has_2025_rg = school['ready_grad'].get('2025', {}).get('rate') is not None
    
    if has_2025_grad or has_2025_rg:
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
        
        school_obj = {
            'school': school['school'],
            'district': school['district'],
            'county': school['county'] or 'Unknown',
            'system_code': school['system_code'],
            'school_code': school['school_code'],
            'slug': create_slug(school['school']),
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
        }
        
        # Calculate Flight Score
        flight_score = calculate_flight_score(school_obj)
        tier_info = get_flight_tier(flight_score)
        trend_info = calculate_trend(school_obj)
        
        school_obj['flight_score'] = flight_score
        school_obj['flight_tier'] = tier_info['tier']
        school_obj['flight_tier_class'] = tier_info['class']
        school_obj['trend'] = trend_info
        
        if flight_score is not None:
            flight_scores.append(flight_score)
        
        final_schools.append(school_obj)

# Sort by school name
final_schools.sort(key=lambda x: x['school'])

print(f"   Final count: {len(final_schools)} schools")

# ========== CALCULATE COUNTY RANKINGS ==========
print("\n[*] Calculating county rankings...")

# Group schools by county
county_schools = {}
for school in final_schools:
    county = school['county']
    if county not in county_schools:
        county_schools[county] = []
    county_schools[county].append(school)

# Rank within each county and mark top 3
for county, schools_list in county_schools.items():
    # Sort by flight score (descending)
    ranked = sorted(
        [s for s in schools_list if s['flight_score'] is not None],
        key=lambda x: x['flight_score'],
        reverse=True
    )
    
    for i, school in enumerate(ranked):
        school['county_rank'] = i + 1
        school['county_total'] = len(ranked)
        school['is_top_county'] = (i < 3)  # Top 3 get the firefly badge!

# Handle schools without flight scores
for school in final_schools:
    if 'county_rank' not in school:
        school['county_rank'] = None
        school['county_total'] = None
        school['is_top_county'] = False

# ========== FIND BIGGEST IMPROVERS ==========
print("\n[*] Finding biggest improvers...")

improvers = []
for school in final_schools:
    if school['trend']['change'] is not None and school['trend']['change'] > 0:
        improvers.append({
            'school': school['school'],
            'slug': school['slug'],
            'county': school['county'],
            'district': school['district'],
            'change': school['trend']['change'],
            'flight_score': school['flight_score'],
            'flight_tier': school['flight_tier'],
            'rg_2023': school['ready_grad'].get('2023', {}).get('rate'),
            'rg_2025': school['ready_grad'].get('2025', {}).get('rate')
        })

# Sort by improvement amount
improvers.sort(key=lambda x: x['change'], reverse=True)
top_improvers = improvers[:15]  # Top 15 improvers

# ========== FLIGHT SCORE STATS ==========
if flight_scores:
    avg_flight = round(sum(flight_scores) / len(flight_scores), 1)
    max_flight = round(max(flight_scores), 1)
    min_flight = round(min(flight_scores), 1)
else:
    avg_flight = max_flight = min_flight = None

tier_counts = {
    'elite': len([s for s in final_schools if s['flight_tier'] == 'Firefly Elite']),
    'strong': len([s for s in final_schools if s['flight_tier'] == 'Firefly Strong']),
    'ready': len([s for s in final_schools if s['flight_tier'] == 'Firefly Ready']),
    'building': len([s for s in final_schools if s['flight_tier'] == 'Building Momentum']),
    'grow': len([s for s in final_schools if s['flight_tier'] == 'Room to Grow']),
    'na': len([s for s in final_schools if s['flight_tier'] == 'Insufficient Data'])
}

# ========== BUILD OUTPUT JSON ==========
output = {
    'meta': {
        'title': 'What Happens After Graduation - Tennessee High School Outcomes',
        'description': 'Comprehensive data on graduation rates, college readiness, college enrollment, and ACT scores for Tennessee high schools',
        'source': 'Tennessee Department of Education',
        'updated': '2025-01',
        'version': '3.0',
        'metrics': {
            'graduation': 'Percentage of students who graduate within 4 years',
            'ready_grad': 'Percentage meeting Ready Graduate criteria (ACT 21+, industry cert, military, etc.)',
            'college_going': 'Percentage enrolled in postsecondary education within 1 year',
            'act': 'Average ACT composite score'
        },
        'flight_score': {
            'name': 'TNFirefly Flight Score',
            'description': 'Proprietary score measuring how well a school prepares students for life after graduation',
            'formula': {
                'ready_grad_weight': 0.40,
                'college_going_weight': 0.25,
                'act_weight': 0.20,
                'graduation_weight': 0.15,
                'momentum_bonus': '+/- 5 points based on 2-year Ready Grad trend'
            },
            'tiers': {
                'elite': {'min': 85, 'label': 'Firefly Elite'},
                'strong': {'min': 70, 'label': 'Firefly Strong'},
                'ready': {'min': 55, 'label': 'Firefly Ready'},
                'building': {'min': 40, 'label': 'Building Momentum'},
                'grow': {'min': 0, 'label': 'Room to Grow'}
            }
        }
    },
    'state': {
        'schools_count': len(final_schools),
        'counties_count': len(set(s['county'] for s in final_schools)),
        'averages': state_averages,
        'flight_score': {
            'average': avg_flight,
            'max': max_flight,
            'min': min_flight,
            'tier_counts': tier_counts
        }
    },
    'top_improvers': top_improvers,
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
print(f"  Avg Flight Score: {avg_flight}")
print(f"\nTOP 5 IMPROVERS (Ready Grad 2-year change):")
for i, imp in enumerate(top_improvers[:5], 1):
    print(f"  {i}. {imp['school']} - +{imp['change']}% (now {imp['rg_2025']}%)")

print(f"\nTOP 5 SCHOOLS BY FLIGHT SCORE:")
top_5 = sorted([s for s in final_schools if s['flight_score']], key=lambda x: x['flight_score'], reverse=True)[:5]
for i, s in enumerate(top_5, 1):
    print(f"  {i}. {s['school']} - {s['flight_score']} ({s['county']})")

print(f"\nSAMPLE COUNTY RANKINGS (Williamson):")
williamson = [s for s in final_schools if s['county'] == 'Williamson' and s['flight_score']]
williamson.sort(key=lambda x: x['flight_score'], reverse=True)
for s in williamson[:5]:
    badge = " [FIREFLY]" if s['is_top_county'] else ""
    print(f"  #{s['county_rank']} {s['school']} - {s['flight_score']}{badge}")
