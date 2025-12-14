import requests
import pandas as pd
from icalendar import Calendar
import io
from src import config

def download_and_parse_calendar(url, ota_name):
    """
    Downloads and parses an iCal calendar from a URL.
    Returns a list of events.
    """
    if not url:
        return []
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        cal = Calendar.from_ical(response.content)
        
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                summary = component.get('summary')
                # Decode bytes if necessary, though icalendar usually handles it
                if isinstance(summary, bytes):
                    summary = summary.decode('utf-8')
                else:
                    summary = str(summary) if summary else None

                start = component.get('dtstart').dt
                end = component.get('dtend').dt
                uid = component.get('uid')
                if isinstance(uid, bytes):
                    uid = uid.decode('utf-8')
                else:
                    uid = str(uid) if uid else None
                
                events.append({
                    'ota': ota_name,
                    'summary': summary,
                    'start': start,
                    'end': end,
                    'uid': uid,
                    'description': str(component.get('description', ''))
                })
        return events
    except Exception as e:
        print(f"Error processing {ota_name} calendar from {url}: {e}")
        return []

def apply_summary_rules(row):
    """
    Applies the specific rules to the summary field.
    """
    summary = row['summary']
    
    if summary == 'CLOSED - Not available':
        return 'Booking'
    elif summary == 'Airbnb (Not available)':
        return 'Direto'
    elif summary == 'Reserved':
        return 'Airbnb'
    elif not summary:
        return 'Origem Desconhecida'
    
    return summary

def get_calendar_data():
    """
    Iterates through all apartments in config.OTA_URLS,
    downloads calendars, merges them, and applies rules.
    Returns a dictionary of DataFrames keyed by apartment code.
    """
    all_data = {}
    
    for apt, otas in config.OTA_URLS.items():
        apt_events = []
        for ota_name, url in otas.items():
            events = download_and_parse_calendar(url, ota_name)
            apt_events.extend(events)
            
        if not apt_events:
            all_data[apt] = pd.DataFrame()
            continue
            
        df = pd.DataFrame(apt_events)
        
        # Apply rules
        if not df.empty:
            df['summary'] = df.apply(apply_summary_rules, axis=1)
            
            # Ensure datetime objects are timezone-naive or consistent if needed
            # For now, we keep them as is, but pandas might complain if mixing tz-aware and naive
            df['start'] = pd.to_datetime(df['start'], utc=True)
            df['end'] = pd.to_datetime(df['end'], utc=True)
        
        all_data[apt] = df
        
    return all_data
