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

def calculate_flight_score(school):
    """
    TNFirefly Flight Score (0-100)
    
    Formula:
    - Ready Graduate %: 40% weight
    - College-Going Rate: 25% weight  
    - ACT Score (normalized): 20% weight
    - Graduation Rate: 15% weight
    - Momentum Bonus: +/- 5 points based on Ready Grad 2-year trend
    """
    latest = school.get('latest', {})
    
    # Get values
    ready_grad = latest.get('ready_grad_rate')
    college_going = latest.get('college_going_rate')
    act = latest.get('act_composite')
    graduation = latest.get('graduation_rate')
    
    # Need at least Ready Grad or (Graduation + one other metric) to calculate
    valid_metrics = sum([
        ready_grad is not None,
        college_going is not None,
        act is not None,
        graduation is not None
    ])
    
    if valid_metrics < 2:
        return None
    
    # Calculate weighted components
    score = 0
    total_weight = 0
    
    # Ready Graduate (40% weight) - already 0-100 scale
    if ready_grad is not None:
        score += ready_grad * 0.40
        total_weight += 0.40
    
    # College-Going Rate (25% weight) - already 0-100 scale
    if college_going is not None:
        score += college_going * 0.25
        total_weight += 0.25
    
    # ACT Score (20% weight) - normalize to 0-100
    # ACT range: 1-36, benchmark is 21
    # Normalize: 15 = 40, 21 = 70, 27 = 90, 36 = 100
    if act is not None:
        act_normalized = min(100, max(0, (act - 10) * (100 / 26)))
        score += act_normalized * 0.20
        total_weight += 0.20
    
    # Graduation Rate (15% weight) - already 0-100 scale
    if graduation is not None:
        score += graduation * 0.15
        total_weight += 0.15
    
    # Normalize score based on available weights
    if total_weight > 0:
        score = score / total_weight
    else:
        return None
    
    # Momentum Bonus (+/- 5 points)
    # Based on Ready Grad 2-year trend
    rg_data = school.get('ready_grad', {})
    rg_2023 = rg_data.get('2023', {}).get('rate')
    rg_2025 = rg_data.get('2025', {}).get('rate')
    
    if rg_2023 is not None and rg_2025 is not None:
        change = rg_2025 - rg_2023
        if change >= 10:
            score += 5  # Big improvement bonus
        elif change >= 5:
            score += 3  # Moderate improvement
        elif change <= -10:
            score -= 5  # Big decline penalty
        elif change <= -5:
            score -= 3  # Moderate decline
    
    # Cap at 0-100
    score = max(0, min(100, score))
    
    return round(score, 1)

def get_flight_tier(score):
    """Get the tier name based on Flight Score"""
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
print("BUILDING MEGA 'WHAT HAPPENS AFTER GRADUATION' DATASET v2")
print("WITH TNFIREFLY FLIGHT SCORE")
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

for _, row in cgr_df.iterrows():
    school_name = str(row['High_School']).strip().upper()
    district_name = str(row['HS_District']).strip().upper()
    
    if school_name == 'NAN' or district_name == 'NAN':
        continue
    
    # Find matching school by name + district
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
            cgr_matched += 1
            break

print(f"   Matched {cgr_matched} schools with CGR data")

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

# ========== FILTER AND BUILD FINAL SCHOOLS ==========
print("\n[*] Building final school list with Flight Scores...")

final_schools = []
flight_scores = []

for key, school in schools.items():
    # Must have at least graduation OR ready grad data for 2025
    has_2025_grad = school['graduation'].get('2025', {}).get('rate') is not None
    has_2025_rg = school['ready_grad'].get('2025', {}).get('rate') is not None
    
    if has_2025_grad or has_2025_rg:
        # Get latest values
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
        
        school_obj['flight_score'] = flight_score
        school_obj['flight_tier'] = tier_info['tier']
        school_obj['flight_tier_class'] = tier_info['class']
        
        if flight_score is not None:
            flight_scores.append(flight_score)
        
        final_schools.append(school_obj)

# Sort by school name
final_schools.sort(key=lambda x: x['school'])

print(f"   Final count: {len(final_schools)} schools")

# Calculate Flight Score statistics
if flight_scores:
    avg_flight = round(sum(flight_scores) / len(flight_scores), 1)
    max_flight = round(max(flight_scores), 1)
    min_flight = round(min(flight_scores), 1)
else:
    avg_flight = max_flight = min_flight = None

# Count tiers
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
print(f"\nTNFIREFLY FLIGHT SCORE STATS:")
print(f"  Average Score: {avg_flight}")
print(f"  Highest Score: {max_flight}")
print(f"  Lowest Score: {min_flight}")
print(f"\nTIER DISTRIBUTION:")
print(f"  🔥 Firefly Elite (85+):     {tier_counts['elite']} schools")
print(f"  ⭐ Firefly Strong (70-84):  {tier_counts['strong']} schools")
print(f"  ✓  Firefly Ready (55-69):   {tier_counts['ready']} schools")
print(f"  △  Building Momentum (40-54): {tier_counts['building']} schools")
print(f"  ○  Room to Grow (<40):      {tier_counts['grow']} schools")
print(f"  ?  Insufficient Data:       {tier_counts['na']} schools")

# Sample school
sample = [s for s in final_schools if 'Nolensville' in s['school']]
if sample:
    print(f"\nSAMPLE - {sample[0]['school']}:")
    print(f"  Flight Score: {sample[0]['flight_score']}")
    print(f"  Tier: {sample[0]['flight_tier']}")
    print(json.dumps(sample[0]['latest'], indent=4))

# Top 10 schools
print(f"\nTOP 10 SCHOOLS BY FLIGHT SCORE:")
top_10 = sorted([s for s in final_schools if s['flight_score'] is not None], 
                key=lambda x: x['flight_score'], reverse=True)[:10]
for i, s in enumerate(top_10, 1):
    print(f"  {i}. {s['school']} ({s['county']}) - {s['flight_score']}")
