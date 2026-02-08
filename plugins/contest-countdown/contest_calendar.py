"""
Perpetual Ham Radio Contest Calendar Generator
Calculates dates for major ham radio contests for any year.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any

def _nth_weekday(year, month, weekday, n):
    if n > 0:
        first_day = datetime(year, month, 1)
        days_ahead = weekday - first_day.weekday()
        if days_ahead < 0: days_ahead += 7
        return first_day + timedelta(days=days_ahead) + timedelta(weeks=n-1)
    else:
        if month == 12: last_day = datetime(year+1,1,1) - timedelta(days=1)
        else: last_day = datetime(year,month+1,1) - timedelta(days=1)
        days_back = last_day.weekday() - weekday
        if days_back < 0: days_back += 7
        return last_day - timedelta(days=days_back)

def _full_weekend(year, month, n):
    if n > 0:
        sat = _nth_weekday(year, month, 5, n)
        sun = sat + timedelta(days=1)
        if sun.month != month:
            sat = _nth_weekday(year, month, 5, n+1)
            sun = sat + timedelta(days=1)
        return sat, sun
    else:
        last_sat = _nth_weekday(year, month, 5, -1)
        last_sun = last_sat + timedelta(days=1)
        if last_sun.month != month:
            last_sat -= timedelta(weeks=1)
            last_sun = last_sat + timedelta(days=1)
        return last_sat, last_sun

def generate_contest_calendar(year):
    contests = []
    def add(name, start, end, mode="Mixed", bands="HF", sponsor="", description=""):
        contests.append({"name":name,"start":start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end":end.strftime("%Y-%m-%dT%H:%M:%SZ"),"mode":mode,"bands":bands,
            "sponsor":sponsor,"description":description})

    # JANUARY
    sat,sun = _full_weekend(year,1,1)
    add("ARRL RTTY Roundup",sat.replace(hour=18),sun.replace(hour=23,minute=59),mode="RTTY/Digital",sponsor="ARRL",description="Work everyone on RTTY and digital modes")
    sat = _nth_weekday(year,1,5,2)
    add("North American QSO Party CW",sat.replace(hour=18),(sat+timedelta(days=1)).replace(hour=5,minute=59),mode="CW",sponsor="NCJ",description="Low power, NA stations work everyone")
    sat = _nth_weekday(year,1,5,3)
    add("North American QSO Party SSB",sat.replace(hour=18),(sat+timedelta(days=1)).replace(hour=5,minute=59),mode="SSB",sponsor="NCJ",description="Low power, NA stations work everyone")
    sat,sun = _full_weekend(year,1,-1)
    add("CQ 160-Meter Contest CW",(sat-timedelta(days=1)).replace(hour=22),sun.replace(hour=22),mode="CW",bands="160m",sponsor="CQ Magazine",description="CW on 160 meters")
    sat,sun = _full_weekend(year,1,-1)
    add("Winter Field Day",sat.replace(hour=16),sun.replace(hour=21,minute=59),mode="Mixed",sponsor="WFD",description="Portable/emergency operations in winter conditions")

    # FEBRUARY
    sat,sun = _full_weekend(year,2,2)
    add("CQ WW RTTY WPX Contest",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="RTTY",sponsor="CQ Magazine",description="Work prefixes on RTTY")
    sat,sun = _full_weekend(year,2,3)
    add("ARRL International DX Contest CW",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="CW",sponsor="ARRL",description="W/VE work DX, DX works W/VE")
    sat,sun = _full_weekend(year,2,-1)
    add("CQ 160-Meter Contest SSB",(sat-timedelta(days=1)).replace(hour=22),sun.replace(hour=22),mode="SSB",bands="160m",sponsor="CQ Magazine",description="SSB on 160 meters")
    sat,sun = _full_weekend(year,2,-1)
    add("North American QSO Party RTTY",sat.replace(hour=18),sun.replace(hour=5,minute=59),mode="RTTY",sponsor="NCJ",description="Low power, NA stations work everyone on RTTY")

    # MARCH
    sat,sun = _full_weekend(year,3,1)
    add("ARRL International DX Contest SSB",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="SSB",sponsor="ARRL",description="W/VE work DX, DX works W/VE")
    sat,sun = _full_weekend(year,3,-1)
    add("CQ WW WPX Contest SSB",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="SSB",sponsor="CQ Magazine",description="Work prefixes worldwide")

    # APRIL
    sun = _nth_weekday(year,4,6,3)
    add("ARRL Rookie Roundup SSB",sun.replace(hour=18),sun.replace(hour=23,minute=59),mode="SSB",sponsor="ARRL",description="New hams get on the air")

    # MAY
    sat,sun = _full_weekend(year,5,-1)
    add("CQ WW WPX Contest CW",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="CW",sponsor="CQ Magazine",description="Work prefixes worldwide on CW")

    # JUNE
    sat,sun = _full_weekend(year,6,4)
    add("ARRL Field Day",sat.replace(hour=18),sun.replace(hour=20,minute=59),mode="Mixed",sponsor="ARRL",description="Ham radio's open house - portable operations across North America")
    sat = _nth_weekday(year,6,5,3)
    add("ARRL Kids Day",sat.replace(hour=18),sat.replace(hour=23,minute=59),mode="SSB",sponsor="ARRL",description="Getting kids on the air")

    # JULY
    add("RAC Canada Day Contest",datetime(year,7,1,0,0),datetime(year,7,1,23,59),mode="Mixed",sponsor="RAC",description="Work VE stations on Canada Day")
    sat,sun = _full_weekend(year,7,2)
    add("IARU HF World Championship",sat.replace(hour=12),sun.replace(hour=12),mode="Mixed",sponsor="IARU",description="Work HQ and member society stations worldwide")
    sat = _nth_weekday(year,7,5,3)
    add("North American QSO Party RTTY",sat.replace(hour=18),(sat+timedelta(days=1)).replace(hour=5,minute=59),mode="RTTY",sponsor="NCJ",description="Low power, NA stations work everyone on RTTY")

    # AUGUST
    sat = _nth_weekday(year,8,5,1)
    add("North American QSO Party CW",sat.replace(hour=18),(sat+timedelta(days=1)).replace(hour=5,minute=59),mode="CW",sponsor="NCJ",description="Low power, NA stations work everyone")
    sat = _nth_weekday(year,8,5,3)
    add("North American QSO Party SSB",sat.replace(hour=18),(sat+timedelta(days=1)).replace(hour=5,minute=59),mode="SSB",sponsor="NCJ",description="Low power, NA stations work everyone")

    # SEPTEMBER
    sat,sun = _full_weekend(year,9,2)
    add("ARRL September VHF Contest",sat.replace(hour=18),(sun+timedelta(days=1)).replace(hour=2,minute=59),mode="Mixed",bands="VHF+",sponsor="ARRL",description="Work stations on 50 MHz and above")
    sat,sun = _full_weekend(year,9,-1)
    add("CQ WW RTTY DX Contest",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="RTTY",sponsor="CQ Magazine",description="Work CQ zones worldwide on RTTY")

    # OCTOBER
    sat,sun = _full_weekend(year,10,-1)
    add("CQ WW DX Contest SSB",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="SSB",sponsor="CQ Magazine",description="Work CQ zones and countries worldwide - the big one!")
    mon = _nth_weekday(year,10,0,3)
    add("ARRL School Club Roundup",mon.replace(hour=13),(mon+timedelta(days=4)).replace(hour=23,minute=59),mode="Mixed",sponsor="ARRL",description="School radio clubs get on the air")

    # NOVEMBER
    sat,sun = _full_weekend(year,11,1)
    add("ARRL Sweepstakes CW",sat.replace(hour=21),(sun+timedelta(days=1)).replace(hour=2,minute=59),mode="CW",sponsor="ARRL",description="Work all 84 ARRL/RAC sections")
    sat,sun = _full_weekend(year,11,3)
    add("ARRL Sweepstakes SSB",sat.replace(hour=21),(sun+timedelta(days=1)).replace(hour=2,minute=59),mode="SSB",sponsor="ARRL",description="Work all 84 ARRL/RAC sections on phone")
    sat,sun = _full_weekend(year,11,-1)
    add("CQ WW DX Contest CW",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="CW",sponsor="CQ Magazine",description="Work CQ zones and countries worldwide on CW")

    # DECEMBER
    sat,sun = _full_weekend(year,12,1)
    add("ARRL 160-Meter Contest",(sat-timedelta(days=1)).replace(hour=22),sun.replace(hour=15,minute=59),mode="CW",bands="160m",sponsor="ARRL",description="CW on top band")
    sat,sun = _full_weekend(year,12,2)
    add("ARRL 10-Meter Contest",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="Mixed",bands="10m",sponsor="ARRL",description="Work the world on 10 meters")
    sun = _nth_weekday(year,12,6,3)
    add("ARRL Rookie Roundup CW",sun.replace(hour=18),sun.replace(hour=23,minute=59),mode="CW",sponsor="ARRL",description="New CW operators get on the air")
    sat,sun = _full_weekend(year,12,-1)
    add("RAC Winter Contest",sat.replace(hour=0),sun.replace(hour=23,minute=59),mode="Mixed",sponsor="RAC",description="Work VE stations")
    sat,sun = _full_weekend(year,12,-1)
    add("Stew Perry Topband Distance Challenge",sat.replace(hour=15),sun.replace(hour=15),mode="CW",bands="160m",sponsor="BORING ARC",description="Distance-based scoring on 160m")

    contests.sort(key=lambda c: c["start"])
    return contests

def get_upcoming_contests(days_ahead=90):
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days_ahead)
    contests = []
    years = {now.year}
    if cutoff.year != now.year: years.add(cutoff.year)
    for year in years:
        for c in generate_contest_calendar(year):
            start = datetime.strptime(c["start"],"%Y-%m-%dT%H:%M:%SZ")
            end = datetime.strptime(c["end"],"%Y-%m-%dT%H:%M:%SZ")
            if end >= now and start <= cutoff: contests.append(c)
    contests.sort(key=lambda c: c["start"])
    return contests

if __name__ == "__main__":
    import sys
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.utcnow().year
    contests = generate_contest_calendar(year)
    current_month = ""
    print(f"\n{'='*70}\n  Ham Radio Contest Calendar {year}\n{'='*70}")
    for c in contests:
        start = datetime.strptime(c["start"],"%Y-%m-%dT%H:%M:%SZ")
        end = datetime.strptime(c["end"],"%Y-%m-%dT%H:%M:%SZ")
        month = start.strftime("%B")
        if month != current_month:
            print(f"\n  -- {month} {'-'*(60-len(month))}")
            current_month = month
        date_str = start.strftime("%b %d")
        if start.date() != end.date(): date_str += f"-{end.strftime('%d')}"
        print(f"  {date_str:12s} {c['name']:40s} [{c['mode']}]")
    print(f"\n  Total: {len(contests)} contests\n")
