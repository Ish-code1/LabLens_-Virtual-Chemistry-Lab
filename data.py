import sqlite3
import os

DB_NAME = "lablens.db"

def init_db():
    # Remove existing db if we want a fresh seed (optional, but good for script)
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create Elements Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS elements (
        atomic_number INTEGER PRIMARY KEY,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL,
        block TEXT NOT NULL,
        period INTEGER NOT NULL,
        group_num INTEGER NOT NULL,
        electronic_config TEXT NOT NULL
    )
    ''')

    # Create Reactions Table
    # Note: Real exam_tag citations should be filled in later from verified past papers.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reactions (
        id INTEGER PRIMARY KEY,
        reactant_1 TEXT NOT NULL,
        reactant_2 TEXT NOT NULL,
        conditions TEXT NOT NULL,
        products TEXT NOT NULL,
        equation TEXT NOT NULL,
        observation TEXT NOT NULL,
        block TEXT NOT NULL,
        animation_type TEXT NOT NULL,
        exam_tag TEXT NOT NULL
    )
    ''')

    # Seed Elements
    elements_data = [
        (1, 'H', 'Hydrogen', 's', 1, 1, '1s1'),
        (3, 'Li', 'Lithium', 's', 2, 1, '[He] 2s1'),
        (11, 'Na', 'Sodium', 's', 3, 1, '[Ne] 3s1'),
        (19, 'K', 'Potassium', 's', 4, 1, '[Ar] 4s1'),
        (12, 'Mg', 'Magnesium', 's', 3, 2, '[Ne] 3s2'),
        (20, 'Ca', 'Calcium', 's', 4, 2, '[Ar] 4s2'),
        (56, 'Ba', 'Barium', 's', 6, 2, '[Xe] 6s2'),
        (13, 'Al', 'Aluminum', 'p', 3, 13, '[Ne] 3s2 3p1'),
        (6, 'C', 'Carbon', 'p', 2, 14, '[He] 2s2 2p2'),
        (7, 'N', 'Nitrogen', 'p', 2, 15, '[He] 2s2 2p3'),
        (8, 'O', 'Oxygen', 'p', 2, 16, '[He] 2s2 2p4'),
        (15, 'P', 'Phosphorus', 'p', 3, 15, '[Ne] 3s2 3p3'),
        (16, 'S', 'Sulfur', 'p', 3, 16, '[Ne] 3s2 3p4'),
        (17, 'Cl', 'Chlorine', 'p', 3, 17, '[Ne] 3s2 3p5'),
        (53, 'I', 'Iodine', 'p', 5, 17, '[Kr] 4d10 5s2 5p5'),
        (30, 'Zn', 'Zinc', 'd', 4, 12, '[Ar] 3d10 4s2'),
        (26, 'Fe', 'Iron', 'd', 4, 8, '[Ar] 3d6 4s2'),
        (29, 'Cu', 'Copper', 'd', 4, 11, '[Ar] 3d10 4s1'),
        (25, 'Mn', 'Manganese', 'd', 4, 7, '[Ar] 3d5 4s2'),
        (24, 'Cr', 'Chromium', 'd', 4, 6, '[Ar] 3d5 4s1'),
        (47, 'Ag', 'Silver', 'd', 5, 11, '[Kr] 4d10 5s1'),
        (82, 'Pb', 'Lead', 'p', 6, 14, '[Xe] 4f14 5d10 6s2 6p2')
    ]
    cursor.executemany('INSERT INTO elements VALUES (?,?,?,?,?,?,?)', elements_data)

    # Seed Reactions
    reactions_data = [
        # (r1, r2, cond, products, eq, obs, block, anim, exam)
        ('Na', 'H2O', 'none', 'NaOH, H2', '2Na + 2H2O -> 2NaOH + H2', 'vigorous fizzing, exothermic, may ignite', 's_block', 'gas', 'VERY HIGH'),
        ('Ca', 'H2O', 'none', 'Ca(OH)2, H2', 'Ca + 2H2O -> Ca(OH)2 + H2', 'steady bubbling, less vigorous than Na', 's_block', 'gas', 'MODERATE'),
        ('NaHCO3', 'HCl', 'none', 'NaCl, H2O, CO2', 'NaHCO3 + HCl -> NaCl + H2O + CO2', 'brisk effervescence', 's_block', 'gas', 'MODERATE'),
        ('CaO', 'H2O', 'none', 'Ca(OH)2', 'CaO + H2O -> Ca(OH)2', 'hissing, heat released, no gas', 's_block', 'exothermic', 'MODERATE'),
        ('NH4Cl', 'NaOH', 'heat', 'NaCl, H2O, NH3', 'NH4Cl + NaOH -> NaCl + H2O + NH3', 'pungent gas, turns moist red litmus blue', 'general', 'gas', 'HIGH'),
        ('Zn', 'H2SO4(dil)', 'none', 'ZnSO4, H2', 'Zn + H2SO4 -> ZnSO4 + H2', 'steady colourless gas', 'general', 'gas', 'HIGH'),
        ('Cu', 'H2SO4(conc)', 'heat', 'CuSO4, SO2, H2O', 'Cu + 2H2SO4 -> CuSO4 + SO2 + 2H2O', 'pungent suffocating gas, solution turns blue', 'd_block', 'gas', 'HIGH'),
        ('Cu', 'HNO3(conc)', 'none', 'Cu(NO3)2, NO2, H2O', 'Cu + 4HNO3 -> Cu(NO3)2 + 2NO2 + 2H2O', 'brown fumes, solution turns blue', 'd_block', 'gas', 'HIGH'),
        ('Mg', 'O2', 'ignite', 'MgO', '2Mg + O2 -> 2MgO', 'dazzling white light, white ash', 's_block', 'exothermic', 'MODERATE'),
        ('Zn', 'NaOH(conc)', 'heat', 'Na2ZnO2, H2', 'Zn + 2NaOH -> Na2ZnO2 + H2', 'bubbling, demonstrates amphoteric Zn', 'p_block', 'gas', 'HIGH'),
        ('AgNO3', 'NaCl', 'none', 'AgCl, NaNO3', 'AgNO3 + NaCl -> AgCl + NaNO3', 'white curdy precipitate, darkens in light', 'p_block', 'precipitate', 'VERY HIGH'),
        ('Pb(NO3)2', 'KI', 'none', 'PbI2, KNO3', 'Pb(NO3)2 + 2KI -> PbI2 + 2KNO3', 'bright yellow precipitate', 'p_block', 'precipitate', 'HIGH'),
        ('BaCl2', 'Na2SO4', 'none', 'BaSO4, NaCl', 'BaCl2 + Na2SO4 -> BaSO4 + 2NaCl', 'white precipitate, insoluble in dilute HCl', 'p_block', 'precipitate', 'HIGH'),
        ('FeCl3', 'NaOH', 'none', 'Fe(OH)3, NaCl', 'FeCl3 + 3NaOH -> Fe(OH)3 + 3NaCl', 'reddish-brown gelatinous precipitate', 'd_block', 'precipitate', 'VERY HIGH'),
        ('CuSO4', 'NaOH', 'none', 'Cu(OH)2, Na2SO4', 'CuSO4 + 2NaOH -> Cu(OH)2 + Na2SO4', 'pale blue gelatinous precipitate', 'd_block', 'precipitate', 'VERY HIGH'),
        ('CuSO4', 'NH4OH(excess)', 'none', '[Cu(NH3)4](OH)2', 'Cu(OH)2 + 4NH3 -> [Cu(NH3)4](OH)2', 'two-stage: pale blue ppt first, then dissolves to deep blue solution in excess', 'd_block', 'colour_change', 'HIGH'),
        ('FeCl3', 'K4[Fe(CN)6]', 'none', 'Fe4[Fe(CN)6]3, KCl', '4FeCl3 + 3K4[Fe(CN)6] -> Fe4[Fe(CN)6]3 + 12KCl', 'deep Prussian-blue precipitate, confirmatory test for Fe3+', 'd_block', 'precipitate', 'HIGH'),
        ('KMnO4', 'FeSO4(acidic)', 'dilute H2SO4', 'Mn2+, Fe3+, H2O', 'MnO4- + 5Fe2+ + 8H+ -> Mn2+ + 5Fe3+ + 4H2O', 'purple decolourises via faint pink to colourless', 'd_block', 'colour_change', 'VERY HIGH'),
        ('K2Cr2O7', 'FeSO4(acidic)', 'dilute H2SO4', 'Cr3+, Fe3+, H2O', 'Cr2O7(2-) + 14H+ + 6Fe2+ -> 2Cr3+ + 6Fe3+ + 7H2O', 'orange solution turns green', 'd_block', 'colour_change', 'HIGH'),
        ('Na2CO3', 'HCl', 'none', 'NaCl, H2O, CO2', 'Na2CO3 + 2HCl -> 2NaCl + H2O + CO2', 'brisk effervescence, gas turns lime water milky', 's_block', 'gas', 'MODERATE')
    ]

    # Map to table (id is auto incremented)
    formatted_reactions = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]) for r in reactions_data]
    
    cursor.executemany('''
    INSERT INTO reactions (reactant_1, reactant_2, conditions, products, equation, observation, block, animation_type, exam_tag)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', formatted_reactions)

    conn.commit()
    conn.close()
    print("Database seeded successfully.")

def test_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM reactions')
    count = cursor.fetchone()[0]
    print(f"\\nTotal reactions in DB: {count}\\n")
    
    cursor.execute('SELECT * FROM reactions')
    rows = cursor.fetchall()
    
    for row in rows:
        print(f"Reaction {row[0]}: {row[1]} + {row[2]} -> {row[4]}")
        print(f"   Observation: {row[6]}")
        print(f"   Tag: {row[9]}")
        print("-" * 40)
        
    conn.close()
    
    assert count == 20, "Error: Reaction count is not 20!"

if __name__ == "__main__":
    init_db()
    test_db()
