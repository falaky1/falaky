import swisseph as swe
from datetime import datetime

# Get current date
now = datetime.now()

# Convert to Julian Day
jd = swe.julday(now.year, now.month, now.day)

# List of planets to calculate
planets = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO
}

# Calculate and print positions
for name, code in planets.items():
    pos = swe.calc_ut(jd, code)[0]
    print(f"{name}: {pos[0]:.2f}°")
